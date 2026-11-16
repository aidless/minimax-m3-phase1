# minimax-m3-phase1

STATUS: WORK-IN-PROGRESS — not A yet

The table below is a closed offline measurement. The A-bar item still open is repo metadata: the live GitHub About description has not been changed. Replacement text is in the About section.

<!-- problem:start -->
Agent-written TMLR drafts can carry fake citations, broken identifiers, same-passage number clashes, over-precise figures, and invented acronyms.
The phase-1 gate in this repo is six heuristics in `_inbox/方法论/mm3_hallucination_detector.py`, not a measurement of live MiniMax M3 calls.
The closed result is precision and recall of those heuristics on the synthetic fixtures in `eval/fixtures/snippets.jsonl`, with labels written before the run.
<!-- problem:end -->

<!-- headline:start -->
Headline: With the clock pinned to 2026-07-10 and network lookups blocked, the six heuristics score the precision and recall in the table. Limits: synthetic snippets, same-author labels, offline heuristics only — not live MiniMax M3, and not a real-paper false-positive rate.
<!-- headline:end -->

<!-- fixture-metrics:start -->
| detector | tp | fp | fn | tn | precision | recall |
|---|---:|---:|---:|---:|---|---|
| arxiv | 3 | 1 | 3 | 25 | 3/4 = 0.750 | 3/6 = 0.500 |
| github | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
| internal | 4 | 1 | 1 | 26 | 4/5 = 0.800 | 4/5 = 0.800 |
| doi | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
| precision | 1 | 1 | 2 | 28 | 1/2 = 0.500 | 1/3 = 0.333 |
| terminology | 1 | 1 | 1 | 29 | 1/2 = 0.500 | 1/2 = 0.500 |
n=32 synthetic fixtures; clock=2026-07-10; current_year=2026; network=blocked; check_online=false; labels=same-author, written before the run; heuristic offline mode only; not live MiniMax M3; not a real-paper false-positive rate.
<!-- fixture-metrics:end -->

简体中文：[README.zh-CN.md](README.zh-CN.md). Failure modes: [FAILURE_MODES.md](FAILURE_MODES.md).

## Reproduce

```bash
git clone https://github.com/aidless/minimax-m3-phase1.git
cd minimax-m3-phase1
make check
```

`make check` is the offline entry point. It needs Python 3 from the standard library only: no `pip install`, no API key, and no network. It reruns the K-conflict tree, the 15-case granularity suite, `eval/run_cases.py`, the fixture eval (including a self-test that must go red when a label is flipped), and the cited-number classifier. A fresh clone finishes well under 15 minutes; the suite itself is seconds.

`make check` fails if the table above, the same table in `README.zh-CN.md`, `FAILURE_MODES.md`, and `PREREG.md`, or `eval/fixture_metrics.json`, disagrees with a fresh recompute.

## Where the detector lives

The living detector stays at `_inbox/方法论/mm3_hallucination_detector.py`. The regressions and this eval import that path. Moving it would be a separate change. Design notes also sit at `_inbox/方法论/mm3_hallucination_detector.README.md` and `.loop/hallucination_check.README.md`.

## Traceability

The table is recomputed from `eval/fixtures/snippets.jsonl` by `eval/run_fixture_eval.py`. Per-row predictions, severities, and the detector's own match strings are in `eval/fixture_metrics.json`. Label rules are in `eval/fixtures/PROTOCOL.md`.

`eval/verify_cited_numbers.py` classifies every row of `MiniMax_M3_Phase_1_metrics.csv` and every SHA1 row of `PHASE_1_2_EVIDENCE.md` into `eval/cited_status.json`. The headline uses none of the rows that file marks unverifiable, stale, mismatched, curated, or not a measurement.

## Unverifiable legacy claims

<!-- unverifiable-legacy:start -->
`MiniMax_M3_Phase_1_metrics.csv` rows in `real_data` (PAPER-A counts, and the arXiv notes) describe outputs that are not in this checkout. The 2026-07-10 scan in `PHASE_1_2_EVIDENCE.md` fingerprinted an `F:\Research` tree; rows whose files are here are marked match or stale in `eval/cited_status.json`, and the 16 `mm3.md` filenames are absent. The phase reports' "0 HIGH 误报" sentence depends on M3 outputs that are not committed. It is not a result of this repo. `readme_size` in the CSV does not match the detector README's current size (`RECOMPUTED_MISMATCH`). `scripts_count` and `integration_points` are curated inventories, not a census.
<!-- unverifiable-legacy:end -->

## GitHub About

The live description is still: "MiniMax M3 wired into the TMLR submission pipeline plus a hallucination detector; Phases 1–2 documented, later phases not included".

Replace it with:

<!-- about:start -->
Offline scores for six hallucination-detector heuristics on synthetic fixtures. Not a live MiniMax M3 run and not a real-paper false-positive rate.
<!-- about:end -->

## CI

`.github/workflows/pr-checks.yml` and `.github/workflows/test_k_conflict_decision_tree.yml` both run this same `make check` on pull requests. The weekly schedule was already removed.

## Open pull requests, not merged here

Four open items, all Dependabot, and no other open issues: #3 pyyaml, #4 pdfplumber, #5 pytest, #6 `actions/upload-artifact` 4.6.2 to 7.0.2. `make check` does not install those packages. #6 is a major bump used only by `packaging.yml`. They were read and left open.

## License

MIT. See [LICENSE](LICENSE).
