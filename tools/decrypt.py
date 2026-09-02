#!/usr/bin/env python3
"""
Decrypt quiz results collected by test_runner.html.

Inputs (any mix, positional):
  * a CSV exported from the Google Sheet   (File -> Download -> CSV)
  * one or more *.enc.json files           (the email fallback)
  * a directory containing *.enc.json files

For each submission this writes the full decrypted quiz-result JSON to the
output directory, and also builds two analysis-friendly tables:

  responses_long.csv  one row per answered question (all participants)
  summary.csv         one row per submission (counts + duration)

Usage:
  python decrypt.py responses.csv
  python decrypt.py inbox/ extra_result.enc.json
  python decrypt.py responses.csv --key keys/private_key.pem --out out/

Requires:  pip install cryptography
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = Path(__file__).resolve().parent


def load_private_key(path: Path):
    data = path.read_bytes()
    return serialization.load_pem_private_key(data, password=None)


def unwrap_and_decrypt(priv, ek_b64: str, iv_b64: str, ct_b64: str) -> dict:
    ek = base64.b64decode(ek_b64)
    iv = base64.b64decode(iv_b64)
    ct = base64.b64decode(ct_b64)

    aes_key = priv.decrypt(
        ek,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    # WebCrypto AES-GCM appends the 16-byte tag to the ciphertext, which is
    # exactly what AESGCM.decrypt expects.
    plaintext = AESGCM(aes_key).decrypt(iv, ct, None)
    return json.loads(plaintext)


def iter_payloads(inputs: list[Path]):
    """Yield (source_label, payload_dict) for every encrypted submission."""
    for p in inputs:
        if p.is_dir():
            yield from iter_payloads(sorted(p.glob("*.enc.json")))
        elif p.suffix.lower() == ".csv":
            with p.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for i, row in enumerate(reader, start=2):  # row 1 = header
                    if not row.get("ct"):
                        continue
                    yield f"{p.name}:row{i}", {
                        "meta": {
                            "participant_id": row.get("participant_id", ""),
                            "lecture": row.get("lecture", ""),
                            "test": row.get("test", ""),
                            "assigned_order": row.get("assigned_order", ""),
                            "finished_at": row.get("finished_at", ""),
                        },
                        "ek": row["ek"],
                        "iv": row["iv"],
                        "ct": row["ct"],
                    }
        else:
            payload = json.loads(p.read_text(encoding="utf-8"))
            yield p.name, payload


def safe_name(*parts: str) -> str:
    raw = "_".join(str(x) for x in parts if x not in (None, ""))
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in raw) or "result"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="CSV file(s), .enc.json file(s), or folder(s)")
    ap.add_argument("--key", type=Path, default=HERE / "keys" / "private_key.pem",
                    help="private key PEM (default: tools/keys/private_key.pem)")
    ap.add_argument("--out", type=Path, default=HERE / "out",
                    help="output directory (default: tools/out/)")
    args = ap.parse_args()

    if not args.key.exists():
        ap.error(f"private key not found: {args.key}")

    priv = load_private_key(args.key)
    args.out.mkdir(parents=True, exist_ok=True)

    long_rows: list[dict] = []
    summary_rows: list[dict] = []
    ok = 0
    failed = 0
    seen: set[str] = set()

    for label, payload in iter_payloads(args.inputs):
        try:
            result = unwrap_and_decrypt(priv, payload["ek"], payload["iv"], payload["ct"])
        except Exception as err:  # noqa: BLE001 - report and continue
            print(f"  FAIL  {label}: {err}", file=sys.stderr)
            failed += 1
            continue

        meta = result.get("meta", {})
        summary = result.get("summary", {})
        pid = meta.get("participant_id", "")
        stamp = str(meta.get("finished_at", "")).replace(":", "-").replace(".", "-")
        key = safe_name("quiz", meta.get("lecture"), meta.get("test"), pid, stamp)

        if key in seen:
            print(f"  skip  {label}: duplicate of {key}")
            continue
        seen.add(key)

        (args.out / f"{key}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        ok += 1

        summary_rows.append({
            "participant_id": pid,
            "lecture": meta.get("lecture", ""),
            "test": meta.get("test", ""),
            "assigned_order": meta.get("assigned_order", ""),
            "n_questions": meta.get("n_questions", ""),
            "correct": summary.get("correct", ""),
            "incorrect": summary.get("incorrect", ""),
            "idk": summary.get("idk", ""),
            "duration_ms": meta.get("duration_ms", ""),
            "started_at": meta.get("started_at", ""),
            "finished_at": meta.get("finished_at", ""),
        })

        for r in result.get("responses", []):
            long_rows.append({
                "participant_id": pid,
                "lecture": meta.get("lecture", ""),
                "test": meta.get("test", ""),
                "assigned_order": meta.get("assigned_order", ""),
                "index": r.get("index", ""),
                "question_id": r.get("question_id", ""),
                "source_variant": r.get("source_variant", ""),
                "selected_answer": r.get("selected_answer", ""),
                "correct_answer": r.get("correct_answer", ""),
                "outcome": r.get("outcome", ""),
                "time_ms": r.get("time_ms", ""),
                "question_text": r.get("question_text", ""),
            })

    if summary_rows:
        write_csv(args.out / "summary.csv", summary_rows)
    if long_rows:
        write_csv(args.out / "responses_long.csv", long_rows)

    print(f"\nDecrypted {ok} submission(s), {failed} failure(s) -> {args.out}")
    if summary_rows:
        print(f"  summary.csv        ({len(summary_rows)} rows)")
        print(f"  responses_long.csv ({len(long_rows)} rows)")
    return 1 if failed and not ok else 0


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
