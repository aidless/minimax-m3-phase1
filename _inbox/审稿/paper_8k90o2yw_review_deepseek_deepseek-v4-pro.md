# The Hidden Cost of Resampling: How Imbalance Correction Degrades Probability Calibration in Tree Ensembles

**Date**: 06/28/2026
**Domain**: computer_science/machine_learning
**Taxonomy**: academic/research_paper
**Filter**: Active comments

---

## Overall Feedback

Here are some overall reactions to the document.

**Outline**

The paper presents a well-structured empirical study on how resampling affects calibration in tree ensembles, with useful practical takeaways. The experimental design is generally sound, but critical issues around metric reliability on highly imbalanced data and incomplete validation of a key result undermine some conclusions.

The authors provide a thorough comparison of resampling methods and recalibration, using proper statistical tests and effect sizes. The negative result on prior correction is a valuable contribution. However, the heavy reliance on ECE for a dataset with extremely few positives (yeast_ml8) risks invalidating the most striking finding, and the prior-correction analysis is limited to one model type.

**ECE estimates on yeast_ml8 are unreliable and may invalidate key conclusions**

yeast_ml8 has only ~34 minority examples total; in 5-fold CV test folds, the number of positives can be as low as 7. With so few positives, ECE becomes extremely noisy, and the reported baseline ECE of 0.008 is suspiciously low. The paper’s most dramatic result—that RUS inflates ECE from 0.008 to 0.395 on this dataset—is likely distorted by this instability. The robustness check in the appendix only covers datasets with larger minority classes (pima, credit_g), not yeast_ml8. This threatens the paper’s central message about the danger of RUS at high imbalance. The authors should either provide bootstrap confidence intervals for ECE on yeast_ml8, use an alternative metric designed for low-count scenarios (e.g., adaptive binning with a minimum-count threshold, or a Brier score decomposition), or exclude yeast_ml8 from the main aggregated conclusions and treat it as an illustrative extreme case with appropriate caveats.

**The negative result for prior correction is only demonstrated for gradient boosting**

The claim that analytic prior-shift correction does not work for SMOTE is a key contribution, but the evidence (Table 13) relies solely on gradient boosting, averaged across datasets. Random forest, which is better calibrated and may have different class-conditional density estimates, is not tested. The conclusion that “data-driven recalibration remains the only reliable repair” might not hold for all tree ensembles. Repeating the prior-correction experiment on random forest, or at least discussing why the result should generalize, would strengthen this finding.

**The AUC-drop decomposition in Section 13 is ambiguous and poorly explained**

The attribution of the AUC loss to data reduction (29%) and “the calibration transform itself and from SMOTE” (71%) is confusing. The numbers are drawn from a separate 70-30 split experiment whose absolute AUC values differ from the main results, and the baseline for each drop is not clearly stated. Moreover, the 71% component conflates the effect of the calibration transform with the effect of SMOTE, preventing any practical guidance on which part dominates. A clearer decomposition, perhaps via a dedicated ablation or a more detailed exposition, would make this analysis useful instead of opaque.

**Hyperparameter tuning is absent; fixed defaults may bias the comparison**

All models use fixed hyperparameters (RF: 120 trees, HGB: 200 iterations). Resampling, especially RUS, drastically changes training set size and class balance, so the optimal hyperparameters likely differ across conditions. RUS trains on as few as ~68 points on yeast_ml8; using 120 trees might lead to severe overfitting and inflated ECE independently of the resampling effect. Although the learning-curve control varies n_estimators, other parameters (max_depth, learning_rate, regularization) are not explored. This omission could exaggerate the reported calibration damage for RUS. The authors should either tune hyperparameters jointly for each condition or provide a rigorous justification for the fixed settings and discuss how this choice might affect the conclusions.

**Class-weight recommendation lacks direct comparison with recalibrated SMOTE**

The paper’s practical guidance advises practitioners to “prefer class weighting when a calibrated probability is the goal and the model supports it.” Yet the aggregate results (Table 2) show that class-weight ECE (0.058) is worse than SMOTE+Platt (0.021) while class-weight AUC (0.861) is higher than SMOTE+Platt (0.848). The recommendation therefore forces a trade-off that is never unpacked: a reader who follows the advice will sacrifice calibration quality relative to the recalibrated alternative, and the paper provides no per-dataset breakdown of this tension. A direct, side-by-side comparison—ideally a table showing per-dataset ECE, AUC, and F1 for class-weight versus SMOTE+Platt and SMOTE+Isotonic, with effect sizes—would let practitioners see when (if ever) class-weight is the better choice. Without it, the advice reads as a guess rather than an evidence-based conclusion.

**Oversampling-ratio sweep shown only for gradient boosting**

The sweep that links calibration cost monotonically to oversampling aggressiveness (Figure 7, Section 17) is performed exclusively on the gradient boosting model. Random forest is not tested in this setting, so the paper cannot claim—as it implicitly does when presenting the sweep as a general property of SMOTE—that the monotonic relationship holds for both tree ensemble types. Given that random forest and boosting exhibit very different baseline calibration behavior (ECE 0.023 vs. 0.082), one might reasonably suspect that the shape or magnitude of the cost curve differs between them. A natural fix is to replicate the $ho$-sweep on random forest with the same ten-seed protocol and report the resulting ECE vs. $ho$ curve, or to note explicitly that the conclusion is conditional on the model and motivate why the boosting result is sufficient.

**Recommendation**: major revision

**Key revision targets**:

1. Provide a thorough robustness analysis for ECE on yeast_ml8 (e.g., bootstrap CIs, alternative metrics) or exclude it from the main aggregated claims.
2. Validate the prior-correction negative result on random forest to support the generality claim.
3. Clarify the AUC-drop decomposition by specifying baselines and separating the effects of SMOTE and the calibration transform.
4. Address the lack of hyperparameter tuning by tuning per condition or by adding a justification and discussion of potential bias.

**Status**: [Pending]

---

## Detailed Comments (15)

### 1. Calibration split description is ambiguous

**Status**: [Pending]

**Quote**:
> Finally we apply two \textbf{post-hoc recalibrations} to the
> SMOTE model: Platt scaling (sigmoid) and isotonic regression, each fit on
> a held-out calibration split disjoint from the model's training data.

**Feedback**:
The phrase "a held-out calibration split disjoint from the model's training data" could be misread as an independent holdout set separate from the cross-validation folds, which would constitute data leakage. In the paper's own protocol, the calibration split is taken strictly from within the training fold to prevent leakage. Rephrase to explicitly tie the calibration split to the training fold, e.g., "each fit on a calibration split drawn from the same training fold (disjoint from the training examples used to build the model)."

---

### 2. Ambiguity in statistical test aggregation across datasets and models

**Status**: [Pending]

**Quote**:
> We aggregate the
> out-of-fold predictions per seed and compare conditions with the paired
> Wilcoxon signed-rank test on matched (dataset, model, seed) tuples

**Feedback**:
The phrase "matched (dataset, model, seed) tuples" leaves open whether the Wilcoxon test is applied separately for each dataset–model pair (using the 10 seeds as the replicate unit) or whether all seeds from all dataset–model combinations are pooled into a single paired test. Pooling implicitly assumes exchangeability across datasets with different imbalance ratios, which may not hold. Separate tests lose power and require multiplicity correction. State exactly how the test was conducted—per dataset–model or global—and if global, justify exchangeability or describe how paired observations were formed. If separate tests were performed, explain how the overall Cliff's delta and p-values were aggregated.

---

### 3. Missing absolute minority count in dataset table

**Status**: [Pending]

**Quote**:
> \begin{tabular}{lrrrr}
> \toprule
> Dataset & $n$ & Features & IR & Minority \% \\
> \midrule
> pima & 768 & 8 & 1.87 & 34.9 \\
> credit-g & 1000 & 48 & 2.33 & 30.0 \\
> phoneme & 5404 & 5 & 2.41 & 29.3 \\
> adult & 8000 & 97 & 3.18 & 23.9 \\
> yeast\_ml8 & 2417 & 116 & 70.1 & 1.4 \\
> \bottomrule
> \end{tabular}

**Feedback**:
The table reports IR and minority percentage, but the absolute number of minority instances is not directly shown. For highly imbalanced datasets like yeast_ml8, the minority class has only ~34 examples, which critically limits the reliability of calibration metrics on small test folds. Adding a column with the exact minority count (or explicitly stating it in the text) would help readers immediately gauge this stability concern.

---

### 4. Effect size descriptor contradicts own thresholds

**Status**: [Pending]

**Quote**:
> The effect is
> small-to-moderate for SMOTE ($0.052\to0.061$, $\delta=+0.27$) and random
> oversampling ($\to0.064$, $\delta=+0.26$), but large for random
> undersampling ($\to0.186$, $\delta=+0.77$).

**Feedback**:
The paper establishes thresholds: $|\delta|<0.15$ negligible, $<0.33$ small, $<0.47$ medium, $\ge0.47$ large. Both $\delta=0.27$ and $0.26$ fall below the medium threshold ($0.33$), squarely in the “small” bin. Calling them “small-to-moderate” is inconsistent. Replace with “small” for SMOTE and ROS, or briefly justify why the effect is described as bridging small and moderate despite the numerical value being in the small range.

---

### 5. Control experiment is logically circular

**Status**: [Pending]

**Quote**:
> We
> trained the same RF model on a balanced random subsample of
> \texttt{yeast\_ml8} containing exactly as many training points as RUS
> produces ($\sim$50). The balanced-downsample model achieves
> ECE~$0.397$---nearly identical to RUS's $0.395$---while on datasets
> with smaller imbalances the gap is modest but present (e.g., on
> \texttt{pima}, balanced-downsample ECE~$0.112$ vs.\ RUS~$0.118$,
> $\Delta{=}0.006$). This indicates
> that the extreme ECE on \texttt{yeast\_ml8} reflects training-set
> collapse ($\sim$50 samples) rather than a property of undersampling
> \emph{per se}.

**Feedback**:
The 'balanced random subsample' is operationally identical to RUS because obtaining a balanced subset of the same size as RUS produces requires undersampling the majority class. The comparison is therefore circular, and the near-identical ECE values are tautological—it does not disentangle data reduction from prior distortion. To separate these causes, compare RUS with a data-reduction strategy that preserves the original class ratio (e.g., random subsampling without balancing) or add a class-weight correction to the small balanced subsample.

---

### 6. Numerical inconsistency for RUS on pima

**Status**: [Pending]

**Quote**:
> while on datasets
> with smaller imbalances the gap is modest but present (e.g., on
> \texttt{pima}, balanced-downsample ECE~$0.112$ vs.\ RUS~$0.118$,
> $\Delta{=}0.006$)

**Feedback**:
The text reports RUS ECE on pima as $0.118$, but Table~II (perdata) lists RUS ECE for pima as $0.151$, a discrepancy of $0.033$. The table caption states values are means over both models and ten seeds, while the text describes a control experiment using only the RF model, which might explain part of the difference. Nonetheless, quoting an RUS value that conflicts with the table presented in the same section is misleading. Clarify which variant (RF-only, or model-aggregated) the text refers to, or align the numbers.

---

### 7. Cliff's delta incorrectly described as probability of exceedance

**Status**: [Pending]

**Quote**:
> report \emph{Cliff's} $\delta=\dfrac{\#\{(i,j):a_i>b_j\}-\#\{(i,j):a_i<b_j\}}{n_a\,n_b}$,
> the
> probability that a random draw from one condition exceeds a random draw
> from the other

**Feedback**:
The formula defines Cliff's delta as $P(X>Y) - P(X<Y)$, not $P(X>Y)$ alone. The textual description misleadingly claims it is simply the probability of exceeding, ignoring the subtracted term. This misstates the interpretation and may confuse readers about its range ($[-1,1]$). Rewrite as "the probability that a random draw from one condition exceeds a random draw from the other minus the probability of the reverse" because the formula directly corresponds to this difference.

---

### 8. Claim that resampling 'helped' on all three metrics is inconsistent with RUS PR-AUC drop

**Status**: [Pending]

**Quote**:
> A practitioner tuning on
> any of these three metrics would conclude resampling helped, while ECE
> tells the opposite story---this is precisely why the cost is hidden.

**Feedback**:
In Table~1, PR-AUC for RUS drops from 0.606 (baseline) to 0.585, a decrease of 0.021. A practitioner optimizing PR-AUC would see worse performance, not an improvement. The claim that all three metrics (F1, AUC, PR-AUC) would uniformly indicate “helped” is an overstatement. Qualify the sentence to reflect that only F1 and AUC stay flat or improve for RUS, while PR-AUC declines. Example: "A practitioner focusing on F1 or AUC would likely conclude resampling helped or had no adverse effect, though PR-AUC shows a minor drop for RUS; thus the calibration cost can remain hidden when discrimination metrics are the primary concern."

---

### 9. SMOTE ECE lower than baseline at high HGB iterations contradicts 'resampling compounds it' claim

**Status**: [Pending]

**Quote**:
> Varying $n_\text{estimators}$ from 5 to 300 trees (RF) and
> 10 to 500 iterations (HGB) across five seeds and all five datasets, we
> find: RF calibration \emph{improves} with more trees (baseline ECE
> $0.062\to0.024$; SMOTE $0.078\to0.035$), while HGB calibration
> \emph{worsens} (baseline ECE $0.061\to0.125$; SMOTE $0.133\to0.121$).
> Boosting's poor calibration is inherent to the algorithm, not an
> underfitting issue---and resampling compounds it regardless of
> $n_\text{estimators}$.

**Feedback**:
At 500 HGB iterations, SMOTE ECE (0.121) is lower than baseline ECE (0.125), contradicting the statement that resampling “compounds it regardless of $n_\text{estimators}$”. This reversal may be due to the small seed count (five vs. ten), but it creates an internal inconsistency. Acknowledge the crossing and discuss whether it is meaningful, or restrict the claim to the estimator range used in the primary comparisons.

---

### 10. Incorrect claim that both post-hoc columns are smallest in every row

**Status**: [Pending]

**Quote**:
> Second, the two post-hoc-calibration columns are the smallest
> in every row, confirming that recalibration is a uniformly safe move for
> probability quality across this dataset range.

**Feedback**:
The adult row shows Platt scaling ECE 0.023, while the baseline ECE is 0.022, so Platt is not the smallest entry—it is larger than both Isotonic (0.011) and the baseline. The statement that both post‑hoc columns are smallest is false. The intended observation is that the lowest ECE per row is always a recalibrated column. Rewrite: "Second, the lowest ECE in each row is always a recalibrated column (Platt or Isotonic), confirming that recalibration attains the best probability quality across this dataset range."

---

### 11. SHAP methodology opaque; reproducibility and interpretation unclear

**Status**: [Pending]

**Quote**:
> A natural worry is that resampling might also distort \emph{what} the
> model learns, not merely the scale of its probabilities. As an initial
> check on one dataset, we test this with
> SHAP attributions on \texttt{credit-g} (48 features, gradient boosting),
> comparing mean $|\text{SHAP}|$ feature importances of the baseline and
> SMOTE models (Fig.~\ref{fig:shap}). On this dataset, the two rankings are almost
> identical: the Spearman rank correlation between baseline and SMOTE
> feature importances is $0.96$, and the top features
> (e.g.\ \texttt{checking\_status}) keep their order and roughly their
> magnitudes.

**Feedback**:
The precise SHAP configuration is omitted: whether SHAP values were computed for the raw model scores or predicted probabilities, what background dataset was used, and which TreeExplainer variant was applied. These choices directly affect importances. Add a technical note specifying (i) the model output function explained (e.g., probability of the minority class), (ii) the background dataset, and (iii) the SHAP algorithm variant (e.g., TreeExplainer with interventional or tree-path-dependent perturbation).

---

### 12. Undersampling discussion breaks the oversampling focus of the section

**Status**: [Pending]

**Quote**:
> The extreme case makes the mechanism visible. Fig.~\ref{fig:yeastrel}
> shows the reliability diagram for \texttt{yeast\_ml8}: after
> undersampling rebalances a 70:1 problem to 1:1, the model's predicted
> probabilities sit far above the observed frequencies---it has effectively
> learned the wrong prior and become severely overconfident, which is
> exactly the $0.395$ ECE reported in Table~\ref{tab:perdata}.

**Feedback**:
The section is titled “H3b: Damage grows with oversampling aggressiveness” and the preceding paragraph reports an oversampling-ratio sweep. This paragraph discusses undersampling (RUS) and shows a reliability diagram for yeast_ml8 after undersampling, which has no direct connection to oversampling aggressiveness. It likely belongs to the hypothesis about RUS damage (H2). Move this paragraph and Figure 5 to the appropriate undersampling section, or broaden the section heading to explicitly cover both oversampling and undersampling distortion.

---

### 13. Ambiguity in yeast_ml8 dataset origin

**Status**: [Pending]

**Quote**:
> All datasets are public OpenML sets identified by numeric ID
> (pima: 37, credit-g: 31, phoneme: 1489, adult: 1590, yeast\_ml8: 316);
> the preprocessing (one-hot encoding, median imputation, stratified
> subsampling of \texttt{adult} to 8{,}000 rows) is deterministic given the
> seed.

**Feedback**:
The text lists “yeast_ml8” with OpenML ID 316, but standard OpenML ID 316 corresponds to the UCI “yeast” dataset (10-class multiclass). The name suggests a multilabel transformation, yet the preprocessing description only mentions one-hot encoding, median imputation, and stratified subsampling. How the raw dataset was converted to a binary classification problem is unclear. Add a sentence clarifying the target transformation (e.g., “we treat class X as positive and collapse others as negative”).

---

### 14. Sample-size collapse claim lacks direct experimental support

**Status**: [Pending]

**Quote**:
> random undersampling is the genuine danger, especially at high
> imbalance ratios, where the problem is as much about sample-size collapse
> as about resampling \textit{per se}.

**Feedback**:
The conclusion attributes severity partly to sample-size collapse, but the experiments do not disentangle reduced training-set size from the resampling mechanism. No comparison isolates the independent contribution of sample-size shrinkage. The claim goes beyond evidence. Rewrite as “random undersampling is the genuine danger, especially at high imbalance ratios, where the problem is compounded by severe sample-size reduction” because this phrasing correctly conveys worsening without implying a quantified balance of causes.

---

### 15. Recalibration recommendation omits AUC trade-off

**Status**: [Pending]

**Quote**:
> \textbf{(2) Recalibrate after resampling} on a held-out split whenever
> probabilities feed a threshold or expected-cost decision; one isotonic or
> Platt step suffices and restored ECE to approximately baseline levels
> (and below baseline in the 5-dataset aggregate) in every case we
> measured.

**Feedback**:
The advice omits the paper's own finding that recalibration can impose a small but statistically significant drop in AUC (Section 13). A practitioner would benefit from knowing this trade-off. Add a brief note: “In our experiments the AUC cost of recalibration was negligible in effect size ($|\delta| < 0.15$) but statistically significant; users for whom ranking is paramount should weigh this against the calibration improvement.”

---
