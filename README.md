# Knowledge Quiz Test Environment

A single-page quiz runner used to administer lecture knowledge tests to study
participants and collect their responses as end-to-end encrypted JSON.

> **Setting this up for a study? Start with [`COLLECTION_SETUP.md`](COLLECTION_SETUP.md)** —
> the full step-by-step for keys, the Google Sheet collector, publishing, and
> decrypting results. This file is just reference material.

## Contents

| File | Purpose |
| --- | --- |
| `test_runner.html` | The quiz interface (setup screen, question flow, encrypted results upload). No build step, no dependencies. |
| `config.json` | Selection mode: `selectable` (researcher picks Variant + Test) or `random` (both assigned at random on start). |
| `all.json` | The question bank: every lecture / variant / test combination in one bundle. |
| `server/Code.gs` | Google Apps Script web app that receives results into a Google Sheet. |
| `tools/decrypt.py` | Decrypts collected results and builds `summary.csv` / `responses_long.csv`. |
| `tools/gen_keys.sh` | Generates your own RSA keypair. |
| `tools/keys/` | `public_key.pem` (committed) and `private_key.pem` (git-ignored — keep it safe). |
| `COLLECTION_SETUP.md` | Step-by-step for wiring up collection. |

## Question bank structure

`all.json` is nested `lecture → order → test → { questions: [...] }`:

- **lecture** — `econ` (Microeconomics) or `psych` (Psychology)
- **order** (variant) — one of `123`, `132`, `213`, `231`, `312`, `321`
- **test** — `A`, `B`, or `C`
- Each set has **10 questions**.

Each question object:

```json
{
  "id": "Q1",
  "source_variant": "V1",
  "q": "Question text",
  "a": ["option 1", "option 2", "option 3", "option 4", "I don't know"],
  "k": "the exact string of the correct option"
}
```

Every question must have exactly **4 substantive answers plus `"I don't know"`**,
and `k` must match one of the entries in `a` verbatim. The runner shuffles the
four substantive options at load time (crypto RNG) and always pins
`"I don't know"` last.

## Running

The page uses `fetch()` to load `all.json`, so it must be served over HTTP —
opening the file directly (`file://`) will not work.

```bash
# from this folder
python -m http.server 8000
```

Then open <http://localhost:8000/test_runner.html>.

Or run it through pages with <https://alvin-kz83.github.io/test-env/test_runner.html>.

## Selection mode

`config.json` controls how the Variant and Test are chosen:

```json
{ "selection_mode": "selectable" }
```

- **`selectable`** (default) — the setup screen shows the **Variant** and
  **Test** dropdowns and the researcher picks them.
- **`random`** — those two dropdowns are hidden; when the test starts the
  runner assigns a Variant (`123`…`321`) and a Test (`A`/`B`/`C`) uniformly at
  random (crypto RNG). Lecture and Participant ID are still entered by hand.

The chosen mode is recorded on each result as `meta.selection_mode`. If
`config.json` is missing, unreachable, or malformed, the runner falls back to
`selectable`.

## Administering a quiz

1. Enter the **Participant ID**.
2. Pick **Lecture**, **Variant**, and **Test**.
3. Click **Load and start test**.
4. The participant answers each question by clicking an option; there is no
   going back. Per-question response time is recorded.
5. On the completion screen, click **End Quiz**. The results are encrypted in
   the browser and uploaded to your collection endpoint (see
   [`COLLECTION_SETUP.md`](COLLECTION_SETUP.md)); the participant sees
   **Submitted ✓**. If the upload fails, an encrypted `*.enc.json` file is
   downloaded instead as a fallback to email over.
   **Return** goes back to the setup screen for the next participant.

A `beforeunload` guard warns if the tab is closed mid-quiz.

## Results

Each submission is uploaded encrypted (RSA-OAEP + AES-256-GCM) and stored as
one row in your Google Sheet. Run `tools/decrypt.py` on the exported CSV to
recover the plaintext result files plus `summary.csv` and
`responses_long.csv`. See [`COLLECTION_SETUP.md`](COLLECTION_SETUP.md).

The decrypted per-submission file has this shape:

```json
{
  "format": "quiz-result",
  "v": 1,
  "meta": {
    "lecture": "econ",
    "test": "A",
    "assigned_order": 123,
    "participant_id": "01",
    "source_file": "all.json",
    "n_questions": 10,
    "started_at": "ISO-8601",
    "finished_at": "ISO-8601",
    "duration_ms": 0
  },
  "summary": { "total_questions": 10, "correct": 0, "incorrect": 0, "idk": 0 },
  "responses": [
    {
      "index": 1,
      "question_id": "Q1",
      "question_text": "...",
      "lecture": "econ",
      "source_test": "A",
      "source_variant": "V1",
      "selected_answer": "...",
      "correct_answer": "...",
      "outcome": "correct | incorrect | idk",
      "time_ms": 0
    }
  ]
}
```

On the wire and in the Sheet this is wrapped as `quiz-result-encrypted`
(`{ meta, ek, iv, ct }`); only the holder of `tools/keys/private_key.pem`
can read the `ct`.
