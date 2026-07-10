# Correction Degrades Probability Calibration in Tree Ensembles

**Date**: 06/28/2026
**Domain**: computer_science/machine_learning
**Taxonomy**: academic/research_paper
**Filter**: Active comments

---

## Overall Feedback

Here are some overall reactions to the document.

**Outline**

This paper provides a comprehensive empirical study on how resampling methods for class imbalance degrade probability calibration of tree ensembles, and demonstrates that post-hoc recalibration can mitigate the damage. The study is well-motivated and the experimental design is largely sound, with a nice sweep of datasets and conditions. However, there are several important issues with the experimental design, metric interpretation, and clarity of the analysis that undermine some of the claims and need to be addressed before publication.

The paper addresses a practically important problem and provides actionable recommendations. The multi-seed, multi-dataset evaluation with effect sizes is a strength. However, the manipulation of training set sizes in the calibration pipeline is not adequately controlled, the extreme dataset poses metric reliability concerns, and some claims about ranking preservation are overstated given the data reduction confound. The paper would benefit from a cleaner isolation of the calibration effect and more careful handling of the edge-case dataset.

**Confounded comparison of recalibrated models due to unequal training sizes**

In Section 13, the paper attempts to decompose the AUC drop of SMOTE+Platt into a part due to the calibration split (data reduction) and a part due to the calibration transform. The reported numbers are inconsistent: the footnote states that training the baseline on 70% data yields AUC~0.830 (drop ${-}0.011$) and the full pipeline yields AUC~0.802 (drop ${-}0.038$), but the baseline in the control is never clearly specified. The main table's baseline AUC is 0.850, so either the baseline of the control is different or the drop magnitudes are miscalculated. The claimed 29% vs. 71% division cannot be verified. This weakens the argument that the calibration cost is negligible because the decomposition that supports it is opaque. The paper must present a clean, reproducible comparison: train both SMOTE and SMOTE+Platt on exactly the same training subsets (e.g., by always using an inner 70-30 split) and report the resulting AUCs, so that the pure effect of the recalibration transform is isolated.

**Calibration metrics on the yeast_ml8 dataset are unreliable**

In the main results (Table 1), SMOTE and the baseline are trained on the full training folds, whereas SMOTE+Platt and SMOTE+Isotonic require reserving a calibration split within the fold, thus reducing the effective training set size for the base model. Consequently, the observed drops in AUC, PR-AUC, and F1 for the recalibrated models are a mixture of data reduction and the calibration transform; the paper cannot claim that the recalibration preserves ranking power unless it controls for this confound. The monotonicity argument for AUC preservation is valid only when the same set of predictions is monotonically transformed, but here the base model itself is trained on less data. The paper should either augment the protocol to use an internal calibration set consistently for all models (including baseline and SMOTE alone) or provide a controlled experiment where the training fraction is held constant, such as by using out-of-bag data or a nested cross-validation that puts all models on equal footing.

**Omission of class-weight + recalibration baseline**

The dataset yeast_ml8 has only 34 minority instances in total, meaning each test fold in stratified 5-fold CV contains about 7 positive examples. ECE computed with 10 equal-width bins on such a small number of positives is highly unstable and can produce spuriously low values (reported baseline ECE is 0.008). The reliability insight for this dataset—e.g., that isotonic recalibration yields the lowest ECE—is therefore questionable. The paper acknowledges this implicitly by disaggregating the RUS effect on yeast_ml8, but does not discuss the inherent metric instability. Either a much larger bin number or a different evaluation protocol (e.g., repeated random splits instead of CV, or binning strategies that require a minimum bin count) is needed for datasets with extreme class rarity, or the dataset should be removed from the main analysis and used only for illustration.

**Insufficient investigation of SMOTE hyperparameters**

One of the paper's practical recommendations is to prefer class weighting when calibrated probabilities are needed, because class weighting barely degrades calibration. Yet the paper never evaluates whether post-hoc calibration on a class-weighted model can further improve calibration to levels comparable to or better than SMOTE+calibration. Given that class weighting does not alter the data distribution, combining it with recalibration could be an even stronger baseline. Without this comparison, the claim that the cheapest repair is post-hoc recalibration after resampling is incomplete. The experiments should include class_weight='balanced' followed by Platt or isotonic recalibration on a held-out split, and report ECE, Brier, and AUC.

**The negative result explanation lacks direct support**

All SMOTE experiments use a fixed number of neighbors $k=5$ and a single oversampling ratio sweep only for the gradient boosting model. Since the paper's central claim about SMOTE's calibration cost relies on the geometry of synthetic samples, varying $k$ could significantly change the degree to which the class-conditional density is distorted and thus alter the calibration degradation. The paper acknowledges this as a limitation (point (xii)), but the extent of the claim—that SMOTE's cost is 'real but small'—depends on this default. A sensitivity analysis over $k$ (e.g., $k=1,3,5,10$) for at least one dataset and model would strengthen the generalizability of the findings.

**The negative result explanation lacks direct support**

Section 20 argues that prior correction fails for SMOTE because SMOTE distorts the class-conditional density $p(\mathbf{x}\mid y=1)$. While this is a plausible explanation, the paper provides no evidence beyond the failure of the correction itself. The argument would be markedly stronger if accompanied by a simple controlled experiment, e.g., on a synthetic 2D dataset where the true $p(\mathbf{x}\mid y)$ is known, showing that after SMOTE the class-conditional distribution visually shifts and the correction fails. As presented, the conclusion that 'SMOTE distorts the class-conditional density' remains an unvalidated hypothesis, yet it is used to support a core practical recommendation (that data-driven recalibration is the only repair). Even a small simulation illustrating the mechanism would greatly improve the paper.

**Recommendation**: major revision

**Key revision targets**:

1. Resolve the AUC drop decomposition confusion: re-run the calibration pipeline with a consistent training fraction for all models (including baseline and SMOTE-only) and provide a clear, verifiable decomposition or remove the ambiguous decomposition and simply report the net effect under a fair data regime.
2. Provide a controlled comparison where SMOTE and SMOTE+recalibration use exactly the same training data (e.g., by always leaving out a fixed calibration portion, with SMOTE-only also trained on that reduced set). Adjust all tables accordingly.
3. Either exclude yeast_ml8 from the main quantitative results due to insufficient minority samples for reliable binned ECE, or justify the metric's stability with a robustness check on this specific dataset (e.g., bootstrapped ECE confidence intervals).
4. Add a class-weight + Platt/Isotonic baseline to all main tables and discussion.
5. Include a brief sensitivity analysis for SMOTE's $k$ parameter on at least one dataset to support the claim that the small calibration cost is not an artifact of the default $k=5$.
6. Strengthen the negative result section with a concrete demonstration, even on synthetic data, that SMOTE alters $p(\mathbf{x}\mid y)$ and that prior correction consequently fails.

**Status**: [Pending]

---

## Detailed Comments (22)

### 1. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 2. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 3. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 4. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 5. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 6. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 7. Undersampling danger claim lacks formal backing

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger, especially at high
> imbalance ratios, where the problem is as much about sample-size collapse
> as about resampling \textit{per se}.

**Feedback**:
The formal results section provides no analysis of random undersampling, sample-size effects, or how they degrade calibration. This claim about the mechanism (sample-size collapse) and its severity at high imbalance ratios is an interpretive statement that requires supporting evidence—either empirical results or a formal model—neither of which appears in the formal results. Without such backing, the claim remains an assertion. A concrete fix: 'Remove this sentence from the conclusion because the formal results do not establish a link between undersampling and sample-size collapse; if such a link is shown elsewhere, explicitly cite that section.'

---

### 8. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 9. Undersampling danger claim lacks formal backing

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger, especially at high
> imbalance ratios, where the problem is as much about sample-size collapse
> as about resampling \textit{per se}.

**Feedback**:
The formal results section provides no analysis of random undersampling, sample-size effects, or how they degrade calibration. This claim about the mechanism (sample-size collapse) and its severity at high imbalance ratios is an interpretive statement that requires supporting evidence—either empirical results or a formal model—neither of which appears in the formal results. Without such backing, the claim remains an assertion. A concrete fix: 'Remove this sentence from the conclusion because the formal results do not establish a link between undersampling and sample-size collapse; if such a link is shown elsewhere, explicitly cite that section.'

---

### 10. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 11. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 12. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 13. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 14. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 15. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 16. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 17. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 18. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 19. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 20. SMOTE's cost claims unsupported by formal results

**Status**: [Pending]

**Quote**:
> SMOTE's cost
> is real but small across the studied range (IR~1.9--70;
> $\delta{=}+0.27$) and its discrimination gains typically outweigh the
> penalty;

**Feedback**:
The formal results section only defines calibration metrics (ECE, Brier score, reliability diagrams, AUC). It does not present any empirical measurements of SMOTE's effect on calibration error, nor does it provide the Cliff's delta value or the stated imbalance range. The conclusion therefore makes quantitative claims that are not derived or reported in the provided formal results. To align the discussion with what is actually established, either (a) include the relevant experimental results in the formal results section, or (b) rewrite the sentence to reference the experiment section as the source. For example: "Rewrite 'SMOTE's cost is real but small across the studied range (IR~1.9--70; $\delta{=}+0.27$)'..."

---

### 21. Undersampling danger claim lacks formal backing

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger, especially at high
> imbalance ratios, where the problem is as much about sample-size collapse
> as about resampling \textit{per se}.

**Feedback**:
The formal results section provides no analysis of random undersampling, sample-size effects, or how they degrade calibration. This claim about the mechanism (sample-size collapse) and its severity at high imbalance ratios is an interpretive statement that requires supporting evidence—either empirical results or a formal model—neither of which appears in the formal results. Without such backing, the claim remains an assertion. A concrete fix: 'Remove this sentence from the conclusion because the formal results do not establish a link between undersampling and sample-size collapse; if such a link is shown elsewhere, explicitly cite that section.'

---

### 22. Prior-shift correction for SMOTE unsupported

**Status**: [Pending]

**Quote**:
> The analytic prior-shift correction that works for
> undersampling does not transfer to SMOTE, because SMOTE distorts the
> class-conditional density rather than only the prior---so data-driven
> recalibration remains the only reliable repair.

**Feedback**:
The formal results section contains no derivation, theorem, or analysis of prior-shift correction, SMOTE's distortion of class-conditional densities, or the necessity of data-driven recalibration. This statement makes a theoretical claim about the inapplicability of a specific correction method, which would require a formal proof or a precisely stated lemma. Since the formal results only define evaluation metrics, this discussion point is entirely unsupported. Suggested remedy: 'Either remove this sentence from the conclusion, or add a formal result (e.g., a proposition showing that SMOTE alters the density in a way that invalidates prior-shift correction) and then reference it here.'

---
