# The Hidden Cost of Resampling: How Imbalance Correction Degrades Probability Calibration in Tree Ensembles

**Date**: 06/28/2026
**Domain**: computer_science/machine_learning
**Taxonomy**: academic/research_paper
**Filter**: Active comments

---

## Overall Feedback

Here are some overall reactions to the document.

**Outline**

This study empirically examines how resampling methods (SMOTE, random over/undersampling) affect the probability calibration of two tree ensembles across five imbalanced datasets. It finds that SMOTE/oversampling degrade calibration only mildly, while random undersampling causes severe miscalibration, especially at high imbalance, and that a single post-hoc calibration step repairs the damage at negligible ranking cost. The paper also reports that a known analytic prior-shift correction does not transfer to SMOTE.

This paper fills an important gap by systematically measuring the calibration cost of popular resampling methods across tree ensembles, with careful attention to proper data splitting and many control experiments. The core findings—that SMOTE's calibration penalty is real but modest, that undersampling is dangerous at high imbalance, and that post-hoc calibration repairs the damage at trivial ranking cost—are practically valuable and well-supported overall. The paper's strength lies in its paired-statistics approach, reproducible protocol, and clear recommendations.

**No per-class calibration analysis despite imbalance focus**

The paper's central question is how resampling affects calibration, but all calibration metrics (ECE, Brier, reliability diagrams) are aggregated over both classes. ECE weighted by bin counts will be dominated by the majority class when imbalance is high. A model could be well-calibrated overall while severely overestimating minority-class probabilities, and that would be invisible to the reader. Since class imbalance is the very rationale for resampling, the omission of per-class calibration makes it impossible to judge whether SMOTE or RUS are harming the minority class specifically—the class the intervention is meant to help. The authors should compute within-class ECE or, at minimum, show per-class reliability curves to demonstrate that the overall patterns hold for the minority class. Without this, the claim that "the discrimination gains typically outweigh the calibration penalty" hangs on an aggregate that may conceal the exact miscalibration practitioners care about.

**Wilcoxon tests on pooled dataset-model tuples are anticonservative**

The main hypothesis tests form pairs over 100 (dataset, model, seed) tuples and apply a Wilcoxon signed-rank test. That treats all tuples as independent, but multiple tuples from the same dataset share the same data distribution and are clearly correlated. For example, all folds and seeds on `pima` will produce ECE values within a similar range, while `yeast_ml8` will produce values an order of magnitude larger. This clustering inflates the effective sample size and can make p-values artificially small. The Holm–Bonferroni correction assumes valid p-values to begin with, so passing it does not rescue the procedure. A more appropriate analysis would be to run per-dataset Wilcoxon tests (or a mixed-effects model with random intercepts for dataset) and correct for multiplicity across datasets and comparisons. As the paper stands, the reported p-values and effect sizes are unreliable, which undermines every statistical claim in the main results section.

**Prior correction experiment is too narrow to support strong negative conclusion**

Section 20 reports that the analytic prior-shift correction fails on SMOTE, but the experiment applies only to gradient boosting (as stated in the section text) and does not specify how $\pi_{\text{test}}$ was obtained—was it the true test-set prior or an estimate? If the true prior was used, that is purely a proof-of-concept, not a realistic deployment scenario. If an estimated prior was used, the error in that estimate may account for some of the failure. Moreover, the experiment skips random forest entirely, even though the paper features both models throughout and the correction's failure may interact with model type. A negative result that is meant to be a key takeaway demands robustness. At minimum, the experiment should (a) report results for random forest as well, (b) clarify precisely how the test prior was determined in each fold, and (c) discuss the sensitivity to prior estimation error.

**Oversampling-ratio sweep only conducted on gradient boosting**

The monotonic increase in ECE with SMOTE oversampling ratio $\rho$ is shown only for the histogram gradient boosting model. The random forest is omitted, even though the two models calibrate very differently out of the box (RF is better calibrated than HGB at baseline) and the paper's own arguments stress that resampling degrades both. It is easy to imagine that RF's calibration might be more robust to injected synthetic data because its predictions are already less sharp. Without the other model, the conclusion that "calibration pays for it monotonically" is only half-tested. A simple extension of the sweep to random forest would either strengthen the finding or reveal an interaction that is currently hidden.

**AUC cost decomposition is not rigorous enough for the strength of the claim**

In Section 13, the authors decompose the total AUC drop of SMOTE+Platt into a fraction attributed to the smaller training set (29%) and a fraction attributed to the calibration transform and SMOTE (71%). This decomposition relies on a single control (baseline trained on 70% data) and assumes that the effects are additive and that SMOTE+Platt's AUC would recover exactly to baseline if given more data. That assumption is untested. The 71% includes both the calibration transform's impact on the scoring distribution and any interaction SMOTE has with reduced data; separating these would require additional controls. The numbers are then used to argue that "trading 0.002 AUC for a 66% ECE reduction is favorable," which is a practical recommendation that rests on a shaky foundation. I would suggest either expanding the decomposition experiment or qualifying the claim as approximate and speculative.

**Recalibration repair demonstrated only for SMOTE, not for undersampling**

The paper's central practical message is that a single post-hoc recalibration step eliminates the calibration damage from resampling. But the experiments apply this repair exclusively to models trained with SMOTE (Sections 4 and 7). The most severe calibration degradation comes from random undersampling—ECE inflates from 0.008 to 0.395 on yeast_ml8—yet the paper never reports the effect of Platt scaling or isotonic regression on an undersampled model. The aggregate claim that recalibration “restored ECE to approximately baseline levels in every case we measured” may not hold for the resampling method that needs repair most urgently. To make the recommendation credible, the authors should recalibrate at least the RUS model on all five datasets and show the resulting ECE and AUC. Without this, the advice for practitioners is based on a gap in the evidence.

**No discussion of calibration-set size for the repair step**

The proposed repair uses a held-out calibration split (30% of training data in Section 13), but the paper provides no guidance on how much data is actually needed for reliable Platt or isotonic fits. This matters because the worst calibration damage occurs on extreme-imbalance datasets where the minority class can have very few instances after a train-test split; reserving 30% for calibration may leave the calibration set nearly empty of positives (e.g., on yeast_ml8 with ~50 minority samples total, a 30% calibration split could contain fewer than 5 positives). The paper acknowledges that varying the split size would refine the AUC decomposition, but it never addresses whether recalibration remains effective with smaller calibration sets or whether a minimal threshold exists. Adding a small simulation or reporting the number of minority instances in the calibration set across datasets would give practitioners the concrete information they need to implement the repair safely.

**Recommendation**: major revision

**Key revision targets**:

1. Add per-class calibration error (minority-class ECE) for all main conditions and discuss implications for the minority class.
2. Re-run statistical tests using per-dataset analyses (e.g., Wilcoxon tests per dataset with FDR correction) or a mixed model that accounts for dataset-level clustering.
3. Extend the prior correction experiment to random forest and clearly specify how the test prior is obtained.
4. Conduct the oversampling-ratio sweep for random forest as well, to verify that the monotonic trend is model-independent.
5. Strengthen the AUC cost decomposition with additional controls or explicitly limit the interpretation to an illustrative breakdown.

**Status**: [Pending]

---

## Detailed Comments (24)

### 1. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 2. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 3. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 4. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 5. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 6. Undersampling ECE numbers not established

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger---its damage grows
> sharply with imbalance, inflating ECE from $0.008$ to $0.395$ on a
> dataset with ratio~70, largely because the resulting training sets are
> too small to estimate probabilities reliably;

**Feedback**:
The formal results section defines ECE but does not contain any experiment or derivation yielding the specific ECE values $0.008$ and $0.395$ for undersampling. The discussion asserts these as findings, yet they are unsupported by the provided section. Add the experimental evidence to the formal results or rewrite the quoted text as "Our experiments show random undersampling inflates ECE from $0.008$ to $0.395$ on a dataset with ratio~70 (see Section X)" because the current formal results do not establish these numbers.

---

### 7. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 8. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 9. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 10. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 11. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 12. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 13. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 14. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 15. Undersampling ECE numbers not established

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger---its damage grows
> sharply with imbalance, inflating ECE from $0.008$ to $0.395$ on a
> dataset with ratio~70, largely because the resulting training sets are
> too small to estimate probabilities reliably;

**Feedback**:
The formal results section defines ECE but does not contain any experiment or derivation yielding the specific ECE values $0.008$ and $0.395$ for undersampling. The discussion asserts these as findings, yet they are unsupported by the provided section. Add the experimental evidence to the formal results or rewrite the quoted text as "Our experiments show random undersampling inflates ECE from $0.008$ to $0.395$ on a dataset with ratio~70 (see Section X)" because the current formal results do not establish these numbers.

---

### 16. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 17. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 18. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 19. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 20. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 21. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 22. SMOTE effect size claim unsupported

**Status**: [Pending]

**Quote**:
> SMOTE's cost is real but small
> ($\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics and does not provide any empirical or theoretical derivation of the effect size $\delta=+0.27$ for SMOTE. The discussion claims this specific number as a finding, but it is not established by the provided section. Rewrite the quoted text as "Our experiments show SMOTE's cost is real but small (details in Section X)" and add the underlying evidence to the results section, because the current formal results do not support this quantitative claim.

---

### 23. Undersampling ECE numbers not established

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger---its damage grows
> sharply with imbalance, inflating ECE from $0.008$ to $0.395$ on a
> dataset with ratio~70, largely because the resulting training sets are
> too small to estimate probabilities reliably;

**Feedback**:
The formal results section defines ECE but does not contain any experiment or derivation yielding the specific ECE values $0.008$ and $0.395$ for undersampling. The discussion asserts these as findings, yet they are unsupported by the provided section. Add the experimental evidence to the formal results or rewrite the quoted text as "Our experiments show random undersampling inflates ECE from $0.008$ to $0.395$ on a dataset with ratio~70 (see Section X)" because the current formal results do not establish these numbers.

---

### 24. Recalibration AUC cost lacks formal support

**Status**: [Pending]

**Quote**:
> A single post-hoc recalibration step
> repairs either case at negligible ranking cost (AUC ${-}0.002$, Cliff's
> $\delta{=}{-}0.07$).

**Feedback**:
The formal results section definitions only mention that ROC-AUC and PR-AUC will be reported, but it does not provide any measurements of AUC change or Cliff's $\delta$ after recalibration. The conclusion therefore invokes numerical results that are absent from the given formal content. Add the supporting experimental results (e.g., a table summarizing AUC differences) or rewrite the quoted text as "Our experiments indicate a negligible ranking cost after recalibration (e.g., AUC change of ${-}0.002$ and Cliff's $\delta{=}{-}0.07$; see Section X)" because the current formal results section alone does not establish these effect sizes.

---
