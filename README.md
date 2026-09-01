# Knowledge Quiz Test Environment

A single-page quiz runner used to administer lecture knowledge tests to study
participants and export their responses as JSON.

## Contents

| File | Purpose |
| --- | --- |
| `test_runner.html` | The quiz interface (setup screen, question flow, results export). No build step, no dependencies. |
| `all.json` | The question bank: every lecture / variant / test combination in one bundle. |

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

## Administering a quiz

1. Enter the **Participant ID**.
2. Pick **Lecture**, **Variant**, and **Test**.
3. Click **Load and start test**.
4. The participant answers each question by clicking an option; there is no
   going back. Per-question response time is recorded.
5. On the completion screen, click **End Quiz** to download the results file.
   **Return** goes back to the setup screen for the next participant.

A `beforeunload` guard warns if the tab is closed mid-quiz.

## Results file

Downloaded as:

```
quiz_<lecture>_<test>_<participantId>_<timestamp>.json
```

Shape:

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

The file is plain JSON — no encryption is applied to the export.
