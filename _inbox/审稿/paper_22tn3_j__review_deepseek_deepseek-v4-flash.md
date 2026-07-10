# Measurements of proprietary LLM evaluators can become invalid within weeks—we document one case and provide the diagnostic framework to detect it.

**Date**: 06/28/2026
**Domain**: computer_science/machine_learning
**Taxonomy**: academic/research_paper
**Filter**: Active comments

---

## Overall Feedback

Here are some overall reactions to the document.

**Outline**

The paper documents a clear case of GPT-4o evaluator version drift and introduces the EPC framework for detecting such instability. While the core observational finding is valuable, several methodological and framing issues weaken the overall contribution.

The paper provides an important empirical demonstration that proprietary LLM evaluators can change behavior silently within weeks, and the EPC framework is a useful diagnostic tool. However, overgeneralization from limited data, questionable calibration methodology, and lack of systematic metric validation reduce the paper's impact.

**Overgeneralization from a single case and unpublished work**

The paper explicitly states that one documented case does not establish a general law, yet Section 17 introduces an 'N-sensitivity as a general measurement phenomenon' claim based on an unrelated classifier calibration study that is 'not reported here; full study in preparation.' This is inappropriate—the entire argument for broad N-sensitivity rests on unpublished work that readers cannot evaluate. The paper would be stronger if it removed this speculative generalization entirely and confined its claims to the specific LLM evaluator case it documents.

**Unreliable ECE calibration with only 11 strategy bins**

Section 5.7 reports an ECE of 0.308 for DeepSeek self-evaluation, computed by binning strategies by evaluator win rate. With only 11 strategies (the number of strategies in the protocol), binning produces at most a handful of bins, making the ECE estimate highly unstable and uninformative. Standard calibration evaluation requires many more confidence bins (typically 10–20 bins with thousands of predictions). The paper acknowledges this limitation but still presents the ECE as a calibration metric without clear caveats about its unreliability. A better approach would be to collect more predictions per strategy or use a continuous calibration metric.

**Conflation of completed and planned work in Future Work section**

Section 18 lists seven experiments, labeling several as 'completed' despite being placed under 'Future Work.' This is confusing and suggests the paper mixes results that are already part of the main analysis with speculative extensions. For example, the 'Official API replication' and 'Version-locked LR comparison' are described in Sections 6.3 and 17 as already performed, yet they appear again under Future Work. The paper should clearly separate what has been done from what remains, perhaps moving completed items into the main results and reserving Future Work for truly pending experiments.

**Sensitivity of coupling metrics to hyperparameter choices not explored**

The TTRL protocol uses asymmetric multiplicative reweighting with specific learning rates (alpha_win=0.08, alpha_lose=0.04). The paper tests a symmetric variant but only after version drift confounded that comparison (later resolved in a version-locked test). The impact of different learning rates, floor values, or strategy set size on the coupling coefficient gamma is not investigated. Since gamma is the primary metric, the paper should include sensitivity analysis or at least justify why the chosen hyperparameters are appropriate. Without this, readers cannot assess how robust the coupling measurements are to arbitrary design choices.

**Self-evaluation collapse not adequately distinguished from genuine stability**

DeepSeek self-evaluation shows 97% zero coupling (Section 12) and the paper acknowledges a possible floor effect. However, the discussion still treats this near-zero coupling as evidence of 'evaluator stability' in the broader context (e.g., Recommendation 4). Given that the calibration experiment (ECE=0.31) suggests DeepSeek-chat lacks discriminative capacity, the zero coupling more likely reflects inability to distinguish strategies rather than genuine robustness. The paper should downplay self-evaluation as a negative result and explicitly state that it is not informative about coupling stability.

**Missing synthetic validation of EPC metrics against ground truth**

The paper introduces new metrics (MPCI, CPCI, coupling coefficient gamma) but never validates them against a known ground truth. Without a simulation where evaluator preference is controlled, readers cannot assess whether these metrics actually capture preference collapse or are driven by other factors. The authors should add a small simulation study with a synthetic evaluator that has a known, tunable preference profile. For example, generate responses where one strategy is objectively better and the evaluator is calibrated accordingly, then verify that gamma increases with preference strength. This would strengthen confidence that the metrics measure what they claim.

**Lack of explicit algorithmic description of the EPC framework**

The paper defines metrics and the four-phase isolation protocol in prose, but it lacks a self-contained algorithmic description. Practitioners trying to adopt the framework must piece together steps from scattered sections. The authors should include a pseudocode algorithm in the main paper (e.g., as a numbered list or algorithm block) that specifies exactly how to compute MPCI, CPCI, the coupling matrix, and the phase transitions. This would significantly improve reproducibility and adoption. The current presentation is too diffuse for a framework paper.

**Recommendation**: Major revision. The core empirical finding (GPT-4o version drift) is compelling and the framework has practical value, but the paper overreaches with unsupported generalizations and includes flawed calibration analysis. The revision must remove the N-sensitivity speculation, fix the ECE methodology or drop it, restructure the Future Work section, and clarify the self-evaluation floor effect.

**Key revision targets**:

1. Remove or heavily qualify the 'N-sensitivity as a general measurement phenomenon' paragraph in Section 17, as it relies on unpublished work.
2. Either substantially revise the ECE calibration analysis (using more data points per bin or a continuous metric) or remove it, with a clear explanation of why calibration is not reliably measurable with only 11 strategies.
3. Restructure the Future Work section so that experiments already completed are moved into the main results (e.g., the official API replication and version-locked LR comparison) with appropriate citations, leaving only truly pending work.
4. Add a sensitivity analysis for the TTRL learning rates and floor parameter, or provide a justification for the chosen values based on prior work or pilot experiments.
5. Revise the discussion of self-evaluation to clearly state that 97% zero coupling is consistent with a floor effect (lack of discriminative capacity) and should not be interpreted as evidence of stability.

**Status**: [Pending]

---

## Detailed Comments (8)

### 1. Sample size mismatch in γ-JSD correlation

**Status**: [Pending]

**Quote**:
> gamma$-JSD correlation (Pearson $r{=}0.969$, $N{=}152$, $p{<}10^{-4}$) confirms $\gamma$ as excellent proxy

**Feedback**:
The abstract states a total of 122 unique repetitions (N=112 main + N=10 ablation). However, the γ-JSD correlation is reported with N=152, which is 30 observations larger. The source of these additional data points is not explained, and this discrepancy undermines the statistical claim. Correcting this count is essential for the credibility of the reported correlation.

---

### 2. Contradiction between 'planned, not executed' and 'completed' items

**Status**: [Pending]

**Quote**:
> Seven concrete experiments (planned, not executed; estimates June 2026 pricing):
> \begin{enumerate}[leftmargin=*,nosep]
>  \item \textbf{Official API replication (completed).}

**Feedback**:
The section header states that all seven experiments are 'planned, not executed,' yet items 1 and 2 are explicitly labeled '(completed).' This is a logical contradiction. The completed experiments should be moved to the main results, and the introductory sentence should differentiate between completed and planned experiments.

---

### 3. Inconsistency with earlier conclusion on symmetric LR collapse

**Status**: [Pending]

**Quote**:
> tbf{3. Symmetric LR also collapses---evidence for instability regardless of cause.} GPT-4o symmetric LR ($N{=}8$) produced zero coupling in all 8 reps. Whether from version drift or symmetric updates, the measurement instability is the finding; causal attribution is future work.

**Feedback**:
Earlier, the paper states that the symmetric LR collapse was a version drift artifact (Section 'Evaluator-Conditional Coupling and Protocol-Dependence'), resolving the confound. Saying 'causal attribution is future work' contradicts that conclusion. The paper should either remove that sentence or revise it to align with the earlier resolution.

---

### 4. Unpublished work used as evidence for general phenomenon

**Status**: [Pending]

**Quote**:
> In concurrent work on classifier probability calibration (not reported here; full study in preparation)

**Feedback**:
The claim that N-sensitivity is a general phenomenon is supported only by unpublished, non-verifiable work. This is inappropriate for a scientific paper. The authors should either include the concurrent study's data or remove the claim and limit the N-sensitivity discussion to their own results.

---

### 5. Ambiguous symmetric definition with unspecified test

**Status**: [Pending]

**Quote**:
> bf{Symmetric}: $|\Delta\gamma| < 0.15$, $p > 0.1$. Descriptive conveniences, not statistical tests.

**Feedback**:
The definition includes a p-value threshold (>0.1) but does not specify the test that produces it, and the paper states these are 'descriptive conveniences, not statistical tests.' This is inconsistent. The p-value should either be removed or the test should be specified to avoid confusing readers.

---

### 6. Unclear significance of aggregate output-format confound

**Status**: [Pending]

**Quote**:
> $\rho_{\text{agg}}{=}0.89$ at $n{=}6$ strategies, $\rho_{\text{inst}}{=}0.219$ at $n{=}60$ instances, $p{=}0.093$) limits PCI interpretation at the aggregate level but is not significant per-instance.

**Feedback**:
The p-value is reported for the per-instance correlation (0.093) but not for the aggregate correlation. At n=6, a correlation of 0.89 is likely significant (p<0.05), meaning the confound is significant at the aggregate level. The claim that it 'limits aggregate-level interpretation' is correct, but the omission of the aggregate p-value makes the comparison misleading. Report both p-values or note the small sample size prevents testing.

---

### 7. Mismatch between pre-registered Pearson threshold and reported Spearman

**Status**: [Pending]

**Quote**:
> At the per-strategy aggregate level ($n{=}6$ strategies), Spearman $\rho{\approx}0.89$ between mean output length and PCI weight---exceeding the pre-registered $r{>}0.7$ threshold.

**Feedback**:
The pre-registered threshold specifies Pearson r>0.7, but the authors report Spearman ρ=0.89. Please either report the Pearson correlation or justify the use of Spearman in relation to the pre-registered threshold.

---

### 8. Empty formal results section

**Status**: [Pending]

**Quote**:
> Measurements of proprietary LLM evaluators can become invalid within weeks---we provided one documented case and the EPC framework to detect it.

**Feedback**:
The 'Formal Results' section contains no theorems, definitions, or derivations; it is essentially a discussion paragraph. For a section titled 'Formal Results', it should include at minimum the formal definitions of MPCI, coupling matrix Γ^(J), and JSD, along with any derived bounds. Without this, the section's heading is misleading. Either populate the section with formal content or rename it.

---
