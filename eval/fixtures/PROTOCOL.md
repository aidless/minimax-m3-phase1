# Label protocol (synthetic fixtures)

Labels in `snippets.jsonl` were written from this protocol before `eval/run_fixture_eval.py` was executed. The scorer only reads the file. It does not assign labels.

This is a closed offline measurement of the six heuristics in `_inbox/方法论/mm3_hallucination_detector.py`. It is not a live MiniMax M3 run and not a false-positive rate on real papers.

## Population

Each row is a short synthetic markdown snippet. Nothing in the set is a passage from a published paper. A row can be positive for one detector and negative for the others.

## Gold label

For each detector, `1` means the fixture author planted a fabrication of that detector's target in the snippet. `0` means the author did not plant one (a clean control, including deliberate near-misses).

The label is not "the string exists on the public web" and not "the detector ought to fire". Existence of arXiv ids, GitHub repos, and DOIs is not re-checked in this offline eval.

## Targets (what a positive label means)

| Key | Planted fabrication |
|---|---|
| `arxiv` | An arXiv id the author invented or deliberately malformed, including ids that only look old or current-year. |
| `github` | A `github.com` reference the author invented or left incomplete. |
| `internal` | A same-passage numerical contradiction of the kind the phase notes talk about (K, bootstrap B, ECE bins, or confidence wording), with no legitimate distinct-purpose or cross-experiment framing. |
| `doi` | A DOI the author invented or deliberately malformed. |
| `precision` | A decimal the author planted as over-precise (four or more digits after the point) and attributed to a result. |
| `terminology` | An all-caps coinage the author invented, absent from the paired `pdf_text`. |

`internal` is numerical contradiction, which is what `detect_internal_contradictions` implements. A "see Section 99" pointer is not that target. Those rows set `unscored.section_pointer` and keep `internal: 0`. They are a documented gap, not a scored false negative of a detector the file does not contain.

## What the scorer counts as a positive prediction

The runner calls the six functions directly with `current_year=2026`, `date.today` pinned to 2026-07-10, `check_online=False`, and the row's `pdf_text`. Sockets and `urlopen` are patched to raise.

- `arxiv`, `github`, `doi`, `precision`, `terminology`: at least one issue from that function.
- `internal`: at least one issue whose severity is `HIGH`, `MEDIUM`, or `LOW`. `INFO` is the function's own "not a contradiction" class and counts as a negative prediction.

## What this protocol cannot support

Same person wrote the snippets, the labels, and the scorer. There is no second annotator. The snippets were chosen to hit known heuristic edges (closed pattern lists, count thresholds, regex shape). Precision and recall are about this file only.
