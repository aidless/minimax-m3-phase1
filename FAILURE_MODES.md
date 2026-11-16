# Failure modes

中文说明见 [README.zh-CN.md](README.zh-CN.md)。计数只以 `make check` 重算的表为准。

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

Per-row severities and the detector's match strings are in `eval/fixture_metrics.json`. This file names the failing ids. It does not restate a second copy of those severities.

## Synthetic-fixture bias

The 32 snippets were written for this eval. They aim at edges that are visible in the source: the closed K/B/ECE/confidence pairs, the arXiv prefix and digit widths, the DOI registrant width, the GitHub `owner/repo` shape, and the count thresholds (more than three long decimals, more than five acronyms). They are not a sample of MiniMax M3 outputs and not a sample of papers. Precision and recall do not transfer off this file.

## Labels by the same author

One author wrote the snippets, the labels in `eval/fixtures/snippets.jsonl`, and `eval/run_fixture_eval.py`. There is no second annotator and no agreement statistic. The label means "planted in this file", not "checked against arXiv, GitHub, or CrossRef".

The first run reported fx12 as a false positive under that label. The label was left at 0. Scores were not fitted to the detector after the run.

## Network-dependent checks are not what the code does

The module docstring names a GitHub API check and a CrossRef check. `detect_github_issues` never calls `urlopen`. With `check_online=True` it still only edits the severity string. `detect_doi_issues` has no online switch. `detect_arxiv_year_issues` compares year and month digits with a clock. It does not open arxiv.org.

`eval/fixture_metrics.json` field `side_probe` records a call on `https://github.com/openai/gpt-2` with `check_online=True` while sockets were patched to raise. The call returned and did not open a socket. The scored path forces `check_online=False`.

The eval pins `date.today` to 2026-07-10 and passes `current_year=2026`. fx31 and fx32 are planted current-year ids inside and outside that month window. fx02 is a planted id in the previous calendar year, which is the year branch that emits nothing. Running without the pin would change fx02 once the wall-clock year moves past 2026.

## What each miss and false alarm was

- arxiv false positive fx06: a non-planted id. The year heuristic flags old-looking ids. Existence was not checked.
- arxiv misses fx02, fx03, fx04: previous-calendar-year id, a suffix shorter than four digits, and an `abs/` URL with no `arXiv:` token.
- github false positive fx09: a non-planted `owner/repo` URL. Offline mode flags every such URL.
- github miss fx08: an owner with no repository segment.
- internal false positive fx12: K=3 under `实验 1` and K=5 under `实验 2`, labeled as not a planted contradiction. Context samples are 25 characters apart, and the second match sits on the earlier sample, so both values are grouped under `实验1`. The case record is in the metrics file.
- internal miss fx11: K=4 versus K=8. The pattern list only pairs K=3 with K=5 (and the three other fixed pairs).
- doi false positive fx18: a non-planted string that matches `10.` plus four or more registrant digits. No CrossRef call.
- doi miss fx17: a planted DOI whose registrant has fewer than four digits.
- precision false positive fx30: four non-planted long decimals on ECE, gamma, JSD, and CV. The heuristic keys off digit length, not provenance.
- precision misses fx20, fx21: two long decimals (the code requires more than three) and a long decimal that is not after those keywords.
- terminology false positive fx25: ROC, AUC, SGD, MAP, NLL, and FID. They were not planted as coinages. They sit outside the allowlist, the paired excerpt does not contain them, and the count is above five.
- terminology miss fx24: three planted coinages. The code returns no issue unless more than five acronyms are missing from `pdf_text`.

fx13 (distinct bootstrap purposes) and fx26 (acronyms present in the paired excerpt) are negative controls that the scorer counted as true negatives on this file. That is not a claim about other wording.

## Document-start context skips soft-demotion

`_parse_priority` is defined twice in `_inbox/方法论/mm3_hallucination_detector.py`. The later definition does not treat the tag `(文档开头)` as a paragraph. fx27 is a planted same-paragraph K clash with no heading. It is counted as a detection. The paragraph soft-demotion branch does not run for that tag. The stored granularity label is in the metrics file.

## Section pointers are unscored

fx15 plants "Section 99" and "Table 42". The numerical-contradiction label stays 0, and `unscored.section_pointer` is true. The six functions do not check whether a section or table exists. Calling that a false negative would score a detector the file does not contain. It is still a hole relative to the looser name "internal-reference" used in older notes.

## Legacy reports

Phase reports and the CSV `real_data` rows are classified in `eval/cited_status.json`. They are not reproduced by this eval. Do not read the table above as a false-positive rate on those papers.
