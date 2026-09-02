# Setup & usage — encrypted result collection

This is the full checklist to take the quiz from "runs locally" to "shared
globally, results arriving encrypted." Everything runs on your machine, a
Google account, and GitHub — there is no server to maintain.

## How it works

When a participant clicks **End Quiz**, the page:

1. Builds the result JSON (same shape as before).
2. **Encrypts it in the browser** — a fresh AES-256-GCM key encrypts the
   JSON, then your RSA public key wraps that AES key. Plaintext never leaves
   the participant's device.
3. `POST`s the ciphertext to a **Google Apps Script** web app, which appends
   one row to a **Google Sheet**.
4. If the upload fails (offline, endpoint down), it downloads a
   `*.enc.json` file instead and asks the participant to email it — still
   encrypted, so nothing readable is lost.

You export the Sheet as CSV and run `tools/decrypt.py`, which needs your
private key, to get plaintext results plus analysis-ready tables.

```
participant browser ──encrypt──▶ Apps Script ──▶ Google Sheet
                                                      │
                                          export CSV  ▼
                                              tools/decrypt.py ──▶ tools/out/*.json
                                              (needs private key)   summary.csv
                                                                    responses_long.csv
```

---

# A. Keys — do this once

### 1. Generate your own keypair

The keypair committed to this repo is for the prototype only — its private
key has been seen by others. In **Git Bash**, from the project folder:

```bash
bash tools/gen_keys.sh
```

This overwrites `tools/keys/private_key.pem` (git-ignored) and
`tools/keys/public_key.pem`, and prints a long one-line base64 string.

> No Bash? Run the two `openssl` commands inside `tools/gen_keys.sh` in any
> terminal that has OpenSSL, on any machine — you only do this once.

### 2. Put the public key in the page

Open `test_runner.html`, find `PUBLIC_KEY_SPKI_B64` near the top of the
`<script>` block, and replace the string with what step 1 printed.

### 3. Back up the private key

Store `tools/keys/private_key.pem` somewhere safe and backed up (password
manager, encrypted drive). **If you lose it, every collected result is
permanently unreadable.** Never commit it, never email it. `.gitignore`
already keeps it out of git — keep it that way.

---

# B. Google Sheet + collector — do this once

### 4. Create the Sheet

Create a blank Google Sheet. From its URL, copy the ID:

```
https://docs.google.com/spreadsheets/d/  <-- THIS LONG ID -->  /edit
```

### 5. Open the script editor

In the Sheet: **Extensions → Apps Script**.

### 6. Paste the collector

Delete the stub code, paste all of [`server/Code.gs`](server/Code.gs), and
set `SHEET_ID` to the ID from step 4. **Save** (Ctrl+S).

### 7. Deploy as a web app

**Deploy → New deployment → ⚙ (gear) → Web app**

| Field | Value |
| --- | --- |
| Description | `quiz collector` |
| Execute as | **Me** |
| Who has access | **Anyone** |

Click **Deploy**, then **Authorize access** → choose your Google account →
on the *"Google hasn't verified this app"* screen click **Advanced → Go to
(project) (unsafe)** → **Allow**. This screen is expected — it is your own
script.

### 8. Copy the Web app URL

It ends in `/exec`. Open it in a browser — you should see:

```json
{"ok":true,"service":"quiz-result-collector"}
```

---

# C. Connect the page to the collector — do this once

### 9. Set the endpoint URL

In `test_runner.html`, near the top of the `<script>`:

```js
const COLLECT_URL = "https://script.google.com/macros/s/AKfy.../exec";  // from step 8
const COLLECT_TOKEN = "";   // leave "" unless you do step 10
```

### 10. (Optional) light spam guard

Pick any random string. Set it as `SHARED_TOKEN` in `server/Code.gs`
**and** as `COLLECT_TOKEN` in `test_runner.html` — they must match. It ships
in the page, so it deters random noise, not a determined person; the
encryption is what protects the data. If you change `Code.gs`, re-deploy
(step 13).

---

# D. Publish

### 11. Commit and push

```bash
git add -A
git commit -m "Encrypted result collection"
git push
```

`tools/keys/private_key.pem` is git-ignored and will not be pushed — verify
with `git status` that it is not listed.

### 12. Confirm GitHub Pages is on

Repo **Settings → Pages →** Source = `main` branch, root.
Your link: <https://alvin-kz83.github.io/test-env/test_runner.html>

### 13. Re-deploying later

- Edited `test_runner.html` → just `git push`.
- Edited `server/Code.gs` → Apps Script **→ Deploy → Manage deployments →
  ✎ → Version: New version → Deploy**. The URL stays the same.

---

# E. Test end to end — before sending to anyone

### 14. Dry run

Open the Pages link, run one quiz as participant `TEST`, click **End Quiz**.
You should see **Submitted ✓** and a new row in the Sheet within a couple
of seconds. If not, open the browser console (F12) and read the error.

---

# F. Collecting results — repeat as needed

### 15. Install the decrypt dependency (once)

```bash
pip install cryptography
```

### 16. Export the Sheet

**File → Download → Comma-separated values (.csv)**

### 17. Decrypt

```bash
python tools/decrypt.py path/to/downloaded.csv
```

Add any emailed fallback files to the same run:

```bash
python tools/decrypt.py downloaded.csv ~/Downloads/quiz_*.enc.json
```

Output lands in `tools/out/`:

| File | Contents |
| --- | --- |
| `quiz_<lecture>_<test>_<id>_<time>.json` | full result file, one per submission |
| `summary.csv` | one row per submission: score, duration |
| `responses_long.csv` | one row per answered question — load straight into R / pandas |

Re-running is idempotent: a submission that appears in both the CSV and an
emailed file is decrypted once.

---

# G. Before real participants

Encryption protects the results in transit and at rest. It does **not**
replace:

- **Ethics approval** for the study.
- A **consent step** — results still contain whatever participant ID you
  assign.

---

## Who can see what

| | id / lecture / test / timestamp | answers, timing, score |
| --- | --- | --- |
| Google (Sheet + Apps Script) | yes (cleartext metadata) | **no** — ciphertext only |
| Anyone who gets the Sheet or CSV | yes | **no** |
| You, with `private_key.pem` | yes | yes |

To hide even the metadata: delete the `meta` block from `encryptResult()` in
`test_runner.html` and the matching columns in `server/Code.gs`. The Sheet
then holds pure ciphertext and you recover everything at decrypt time.

## Limits

- Apps Script free quota is ~20,000 requests/day — irrelevant at study scale.
- No endpoint is perfectly reliable; the `.enc.json` download is the
  backstop. Tell participants what to do if they see it ("email this file
  to me").
- The quiz needs to be served over HTTPS (GitHub Pages) or `localhost` —
  WebCrypto is disabled on `file://`.
