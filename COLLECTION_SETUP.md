# Collecting results globally (encrypted, no download)

When a participant clicks **End Quiz**, the page now:

1. Builds the same result JSON as before.
2. Encrypts it in the browser with your **RSA public key** (hybrid
   RSA-OAEP + AES-256-GCM). The plaintext never leaves the participant's
   machine.
3. `POST`s the ciphertext to a **Google Apps Script** web app, which appends
   one row to a **Google Sheet**.
4. If the upload fails (offline, endpoint down), it downloads an
   `*.enc.json` file instead and asks the participant to email it. Still
   encrypted — nothing readable is lost.

You collect the Sheet as CSV and run `tools/decrypt.py` to get plaintext
results plus analysis-ready tables.

```
participant browser ──encrypt──▶ Apps Script ──▶ Google Sheet
                                                      │
                                          export CSV  ▼
                                              tools/decrypt.py ──▶ out/*.json
                                              (needs private key)     summary.csv
                                                                      responses_long.csv
```

---

## 1. Keys

A keypair is already committed for the prototype:

- `tools/keys/public_key.pem` — public, also baked into `test_runner.html`
  as `PUBLIC_KEY_SPKI_B64`.
- `tools/keys/private_key.pem` — **git-ignored.** Anyone with this file can
  read every participant's answers.

**Before collecting real data, generate your own keypair** (the committed
private key has passed through other hands):

```bash
bash tools/gen_keys.sh
```

Copy the printed one-line base64 into `PUBLIC_KEY_SPKI_B64` near the top of
`test_runner.html`, commit that, and store `private_key.pem` somewhere safe
and backed up. If you lose it, the collected results are unrecoverable.

No OpenSSL? Any machine works — you only need to run this once and move the
public key over.

---

## 2. Google Sheet

1. Create a blank Google Sheet.
2. From its URL grab the ID:
   `https://docs.google.com/spreadsheets/d/`**`THIS_LONG_ID`**`/edit`.

---

## 3. Apps Script web app

1. In the Sheet: **Extensions → Apps Script**.
2. Delete the stub code, paste all of [`server/Code.gs`](server/Code.gs).
3. Set `SHEET_ID` to the ID from step 2.
   (Optional: set `SHARED_TOKEN` to a random string.)
4. **Deploy → New deployment → ⚙ → Web app**
   - Description: `quiz collector`
   - Execute as: **Me**
   - Who has access: **Anyone**
5. **Deploy**, authorise when prompted (it's your own script — the "unverified
   app" screen is expected; **Advanced → Go to … (unsafe)**).
6. Copy the **Web app URL** (ends in `/exec`).

Test it: open the URL in a browser — you should see
`{"ok":true,"service":"quiz-result-collector"}`.

> Re-deploying after code edits: **Deploy → Manage deployments → ✎ → Version:
> New version → Deploy.** The URL stays the same.

---

## 4. Wire up `test_runner.html`

Near the top of the `<script>`:

```js
const COLLECT_URL = "https://script.google.com/macros/s/AKfy…/exec";
const COLLECT_TOKEN = "";          // match SHARED_TOKEN if you set one
const PUBLIC_KEY_SPKI_B64 = "…";   // your key from step 1
```

Commit and push. Share the Pages link:
<https://alvin-kz83.github.io/test-env/test_runner.html>

Run one test yourself end to end — you should see **Submitted ✓** and a new
row in the Sheet within a second or two.

---

## 5. Get plaintext results

```bash
pip install cryptography        # once

# From the Sheet: File → Download → Comma-separated values
python tools/decrypt.py ~/Downloads/responses.csv

# Any emailed fallback files can go in the same run:
python tools/decrypt.py ~/Downloads/responses.csv ~/Downloads/quiz_*.enc.json
```

Output in `tools/out/`:

| File | Contents |
| --- | --- |
| `quiz_<lecture>_<test>_<id>_<time>.json` | the full result file, one per submission |
| `summary.csv` | one row per submission: counts, duration |
| `responses_long.csv` | one row per answered question — feed straight into R/pandas |

Re-runs are idempotent: duplicate submissions (same participant + finish
time appearing in both the CSV and an emailed file) are decrypted once.

---

## What each party can see

| | participant id / lecture / test / timestamp | answers, per-question timing, score |
| --- | --- | --- |
| Google (Sheet + Apps Script) | yes (cleartext metadata) | **no** — ciphertext only |
| Anyone who gets the Sheet/CSV | yes | **no** |
| You, with `private_key.pem` | yes | yes |

If even the cleartext metadata is too much, delete the `meta` block from
`encryptResult()` in `test_runner.html` and the corresponding columns in
`server/Code.gs`. The Sheet then holds pure ciphertext and you recover
everything at decrypt time.

## Notes / limits

- **Consent & ethics:** results still contain whatever participant ID you
  assign. Encryption protects the transport and storage; it doesn't replace
  an ethics approval or a consent step.
- Apps Script free quota is ~20k requests/day — irrelevant at study scale.
- The `COLLECT_TOKEN` ships in the page, so it deters noise, not a
  determined person. The encryption is what protects the data.
- No endpoint is perfectly reliable; the `.enc.json` download fallback is
  the backstop. Tell participants what to do if they see it.
