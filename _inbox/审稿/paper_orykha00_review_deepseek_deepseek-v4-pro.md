# BOUNDARY_SYNC: Measuring Communication-Induced Representational Coupling in Multi-Agent LLM Systems

**Date**: 06/28/2026
**Domain**: computer_science/machine_learning
**Taxonomy**: academic/research_paper
**Filter**: Active comments

---

## Overall Feedback

Here are some overall reactions to the document.

**Outline**

This manuscript presents an interesting measurement protocol for representational coupling in multi‑agent LLM systems, with careful attention to ablation and statistical reporting. However, several fundamental design choices – particularly the use of a text baseline for image conditions, the cross‑model comparison with incompatible protocols, and the overgeneralisation of the stateless‑coupling finding – prevent the main claims from being substantiated as they stand. The experiments need re‑alignment with the stated contributions before the paper can be considered publishable at a top venue.

The authors define a clear measurement protocol and execute a careful ablation to establish that communication drives homogenisation in text‑based GPT‑4o agents. The attention to statistical corrections and the transparent discussion of ratio‑estimator properties are commendable. Nevertheless, the paper’s headline contributions – modality asymmetry, cross‑model effect‑size ranking, and stateless coupling – rest on confounded or insufficiently validated evidence, which significantly weakens the overall impact.

**Image CAF uses a text baseline, invalidating the cross‑modality comparison and the claimed modality asymmetry**

The Confidence-Adjusted Frequency (CAF) is defined as JSD_cond / JSD_C1, where C1 is the isolated text baseline (K=3, text passages). For image conditions, this denominator is not the natural independence reference – image descriptions have different intrinsic diversity. The result is that C5 NoSync CAF = 1.269 is trivially above 1 because image outputs are more varied than text outputs, not because communication causes diversification. The paper’s headline finding of “modality asymmetry” – text homogenizes while image diversifies – collapses under a within‑modality normalization. A proper baseline would compare C5 Sync to C5 NoSync, which yields CAF ≈ 0.836 (0.224 / 0.268), a homogenization effect opposite to the claimed pattern. The image‑sync “directional trend toward baseline” is an artefact of benchmarking against an irrelevant text baseline. The authors must either collect an image isolated baseline or redefine CAF so that each modality is self‑normalized. Until then, the abstract’s third contribution and Section 4.2’s interpretation are unsupported.

**Cross‑model replication confounds task format and measurement protocol, making quantitative comparisons unreliable**

The GPT‑4o experiments measure JSD over sentence‑transformer embeddings of free‑form text descriptions, while the DeepSeek and Qwen experiments use direct 10‑category probability distributions. The tasks themselves are different: free description versus constrained classification. A 97% JSD reduction for DeepSeek may reflect the narrow output space (a 10‑dimensional probability vector) rather than genuinely stronger coupling. The paper acknowledges this limitation but still presents a cross‑model league table (Section 4.3) with statements like “effect magnitude varies by an order of magnitude.” Because the protocol variations are confounded with model, the relative ranking cannot be attributed to model properties alone. The authors should replicate all models with a single standardized task and measurement procedure – or, at minimum, qualify the cross‑model comparisons as preliminary and protocol‑dependent.

**The stateless‑coupling finding is demonstrated only in a special protocol, not in the primary experimental condition**

The per‑round dynamics experiment (Section 4.5) uses a different output space (category probabilities), a toggle design on even‑indexed steps, and only N=10 repetitions. The observed sawtooth pattern and lack of cumulative drift are used to conclude that coupling is “stateless” – a key claim in the abstract and conclusion. However, the main text‑sync results (Section 4.1) used free‑form descriptions and continuous embeddings; no per‑round trajectory of that primary condition is reported. It is possible that the stateless property is an artefact of the discrete output format or the toggle schedule. The paper acknowledges this in a caveat, yet the finding is presented as a major contribution throughout. To justify the claim, the authors should run a per‑round analysis on the original text‑sync (embedding‑based) condition with the same design.

**DeepSeek V4 Pro results are likely dominated by prompt copying, not representational coupling**

The DeepSeek V4 Pro condition used category outputs with `thinking` disabled, forcing deterministic‑looking JSON. Several repetitions reached JSD = 0.0, meaning all agents produced identical probability vectors. This is consistent with the model simply echoing the structured neighbour output rather than integrating it with the stimulus. The authors note this possibility but still highlight the CAF = 0.034 as a model‑dependent coupling strength. The extreme value dominates the conclusion that “homogenization appears across all three tested models … varying dramatically.” A replication with free‑form text generation (matching the GPT‑4o setup) and default reasoning mode is essential. Without it, the DeepSeek data point is too fragile to support cross‑model generalisation.

**Group size is confounded with modality, undermining the text–image comparison**

The text communication condition uses K=5 agents while the image condition uses K=3, motivated by vision API cost. Group size can directly affect the Jensen‑Shannon Divergence even without communication, and it may moderate the coupling effect. The paper verifies that the main findings “are consistent across conditions despite this asymmetry,” but no control experiment tests whether the same modality would behave differently with varying K. The cross‑modality contrasts in Section 4.3 pool K=5 text and K=3 image data; any difference attributed to modality could instead reflect group size. A dedicated control with matched K (or a systematic K sweep) is needed to isolate the modality effect.

**The CAF metric is sensitive to embedding model and binning choices, yet a sensitivity analysis is deferred entirely to future work**

CAF is computed from JSD over 10 equal‑frequency bins of sentence‑transformer embeddings (all‑MiniLM‑L6‑v2). The paper itself notes that bin count sets an effective resolution floor and that ratio estimators are biased at finite N. Despite these known vulnerabilities, no sensitivity analysis is presented – not even a figure showing CAF under alternative bin counts or a different embedding model. Given that the primary result (text homogenization) is a 20% reduction in JSD, a modest shift in the embedding space could alter the classification. The authors should include at least a basic robustness check: recompute CAF with a different embedding model and with alternative bin counts (e.g., 5, 15) to show that the qualitative classification holds.

**Text-level blending operation is undefined**

The BOUNDARY_SYNC protocol states that agent outputs are blended via $w \sim \text{Beta}(\alpha,\beta)$ to form the next prompt, but for the main text-sync condition the outputs are free-form descriptions, not probability vectors. The expression $w \cdot o_i^{(t)} + (1-w) \cdot \frac{1}{K-1}\sum_{j\neq i} o_j^{(t)}$ is well-defined for vectors but meaningless for raw text strings without an explicit aggregation rule. The paper does not describe whether blending is performed by concatenation with delimiters, token-level interpolation, or by first embedding the texts and then blending in representation space. Because the entire experimental result hinges on this blending step, the omission makes the protocol impossible to replicate from the manuscript alone. The authors should provide the precise prompt template used, or clarify that blending occurs in the embedding space and specify how the blended vector is decoded back to text (if at all).

**Jensen-Shannon divergence for more than two agents is not specified**

The CAF metric normalizes $\text{JSD}_{\text{cond}}$ by $\text{JSD}_{\text{C1}}$, but the paper never defines the JSD for $K > 2$ agents. The standard JSD is a two-distribution divergence; generalizations include the average pairwise JSD, the generalized JSD $\frac{1}{K}\sum_i \text{KL}(P_i \| \bar{P})$, or the JSD of a mixture. The choice affects sensitivity to coupling and can shift CAF values. Additionally, for embedding-based conditions the paper bins continuous vectors into 10 equal-frequency bins, but it does not explain whether bin edges are derived from the pooled set of all agent responses across all repetitions or from a fixed reference distribution. These details are essential for reproducibility and for interpreting what JSD actually measures. A formal definition of the multi-agent JSD and a description of the binning procedure must appear in the paper.

**No concrete decision framework for practitioners using CAF**

Section 5.2 states that system designers should measure CAF before deploying communication, and that the choice of backbone model matters enormously. However, the paper stops short of providing an actionable guide. A practitioner reading the paper would need to know: what sample size $N$ is needed to achieve a desired CI half-width for a baseline of unknown JSD? What blend ratio $\bar{w}$ should be used as a default? How should one choose $K$ (the number of agents) when their application has a different group size? What CAF threshold constitutes acceptable diversity loss? Without even a minimal decision heuristic or a table mapping experimental parameters to expected precision, the claimed practical utility of BOUNDARY_SYNC as a measurement protocol remains aspirational. A short subsection offering 'recommended settings for first-time users' would transform the protocol from a research instrument into a tool that engineers can actually deploy.

**Recommendation**: major revision

**Key revision targets**:

1. Recalculate image CAF using a properly matched image baseline (e.g., C5 NoSync or a newly collected isolated image condition) and revise the modality‑asymmetry narrative accordingly.
2. Replicate cross‑model experiments with an identical task (free‑form text description) and measurement protocol (embedding‑based JSD) for all models, or drastically qualify the current comparison.
3. Provide a per‑round dynamics analysis of the main text‑sync (embedding) condition to substantiate the stateless‑coupling claim.
4. Re‑run DeepSeek V4 Pro with free‑form text generation and default reasoning settings to separate genuine coupling from output copying.
5. Add a sensitivity analysis varying the embedding model and the number of bins used for JSD computation.

**Status**: [Pending]

---

## Detailed Comments (11)

### 1. Missing citations for documented herding effects

**Status**: [Pending]

**Quote**:
> Relatedly, herding effects in LLM reasoning — where model outputs converge under exposure to peer responses — and information cascades in multi-agent debate have been documented, but these studies focus on accuracy outcomes rather than quantifying the coupling mechanism itself.

**Feedback**:
The sentence asserts that herding effects and information cascades have been documented but provides no citations. Citations are needed to support this claim and allow readers to verify the basis for distinguishing this work from prior studies.

---

### 2. Inconsistency between Welch's test and pooled-variance effect size

**Status**: [Pending]

**Quote**:
> nalysis
> 
> We use Welch's t-test for pairwise comparisons (does not assume equal variance), with Hedges'-corrected Cohen's d for effect size and bootstrap 95\% CI. Omni

**Feedback**:
Welch's test is chosen because equal variance is not assumed, but Cohen's d (and Hedges' correction) uses a pooled standard deviation that assumes homogeneity. With Levene's test significant (p < 0.01) for some comparisons, the reported d may be biased. Use an effect size that does not assume equal variances (e.g., Glass's Δ) or justify the pooled estimator.

---

### 3. Incorrect Beta parameters for mean blend weight 0.4

**Status**: [Pending]

**Quote**:
> We tested two mean neighbor blend weights: \(\bar{w}=0.4\) (Beta(3,2)) and \(\bar{w}=0.5\) (Beta(3,3))

**Feedback**:
The mean of a Beta(3,2) distribution is 3/(3+2) = 0.6, not 0.4. A Beta distribution with mean 0.4 would be, for example, Beta(2,3). The text contradicts the stated blend weight. Either correct the distribution (to Beta(2,3) or similar) or adjust the label to match a mean of 0.6.

---

### 4. Robustness claim unsupported by null result

**Status**: [Pending]

**Quote**:
> ficant difference was found for either modality (q > 0.5). This indicates that the coupling effect is \textbf{robust to blend ratio variation} within the tested range, suggesting the protocol does not require fine-grained tuning of the Beta parameters.

**Feedback**:
Failing to reject the null hypothesis does not demonstrate robustness; it could reflect low power. The small effect sizes (d = −0.13, −0.15) are suggestive, but a formal equivalence test or power analysis is needed. Tone down the claim, e.g., 'The small effect sizes and non-significant differences are consistent with insensitivity to blend ratio, though formal equivalence testing would be required to confirm robustness.'

---

### 5. Inconsistent Cohen's d for C5 Sync vs NoSync

**Status**: [Pending]

**Quote**:
> The difference between C5 Sync and C5 NoSync is highly significant: d=1.63 (p < 0.001).

**Feedback**:
From the table, C5 Sync JSD = 0.224 ± 0.022, C5 NoSync JSD = 0.268 ± 0.025, N=30 each. The mean difference is 0.044. Using pooled standard deviation sqrt((29*0.022^2+29*0.025^2)/58) ≈ 0.0236 gives d ≈ 1.87, not 1.63. Even with alternative formulas (e.g., using NoSync SD alone) the value does not match. Verify the calculation or clarify the variant used.

---

### 6. JSD comparison confounded by group size

**Status**: [Pending]

**Quote**:
> r C1 baseline (independent agents) shows that GPT-4o already produces somewhat similar outputs in isolation (JSD$\approx$0.21). The key finding is that communication reduces diversity \textit{below} this natural sampling baseline (JSD=0.17 for C3 Sync vs. 0.

**Feedback**:
C1 uses K=3 agents while C3 Sync uses K=5; JSD can depend on group size even without communication. C3 NoSync (K=5) yielded JSD=0.208, much closer to C1. To avoid confounding, compare C3 Sync directly to its K-matched no-communication control (C3 NoSync) or justify that JSD is insensitive to K.

---

### 7. Incorrect CAF value for C5 Sync

**Status**: [Pending]

**Quote**:
> the simulation predicts mild homogenization (CAF=0.93) while the real API shows no significant deviation from baseline (CAF=1.03, CI crosses 1.0)

**Feedback**:
The table lists the real API CAF for C5 Sync as 1.056 (CI [0.967, 1.158]), not 1.03. This typo misrepresents the gap between simulation and real data. Correct to 1.056 (or 1.06).

---

### 8. Novelty claim is internally inconsistent

**Status**: [Pending]

**Quote**:
> he image diversification result is, to our knowledge, \textbf{novel}: no prior work has predicted or documented that communication would reduce, rather than cause, output diversity.

**Feedback**:
The sentence contradicts the canonical view that communication reduces diversity. The actual novel observation is that no-communication produces diversification, and communication brings it back to baseline. Rephrase to avoid the impression that prior work predicted that communication increases diversity, e.g., 'no prior work documented that multi-agent image descriptions would spontaneously diverge without communication, and that communication would instead act as a corrective rather than an amplifier.'

---

### 9. Overstated claim that finding challenges the homogenization assumption

**Status**: [Pending]

**Quote**:
> This finding challenges the assumption that agent communication invariably leads to homogenization and opens new questions about modality-specific coupling dynamics.

**Feedback**:
The data do not challenge the assumption in the strong sense stated. For images, communication still reduces diversity relative to the no-communication state (CAF=1.056 vs NoSync CAF=1.269). The result is that communication reins in spontaneous divergence, not that it fails to homogenize. Tone down the claim to reflect that communication still acts as a homogenizing force.

---

### 10. Inconsistent repetition count for DeepSeek V4 Pro

**Status**: [Pending]

**Quote**:
> .} The near-zero CAF for DeepSeek V4 Pro (0.027) warrants caution. In several of the 10 repetitions, the final-round JSD between agents reached \textbf{exactly 0.0}, meaning all five agents produced identical probability vectors. T

**Feedback**:
The abstract and earlier sections state N=30 for DeepSeek V4 Pro, but this passage mentions '10 repetitions.' This contradiction undermines the reported JSD=0.0 observations. Clarify the correct N and, if only a subset was analyzed, explicitly state the subsampling rationale.

---

### 11. Protocol section lacks definition of the coupling metric

**Status**: [Pending]

**Quote**:
> ion
> 
> We presented BOUNDARY\_SYNC, a measurement protocol for quantifying communication-induced representational coupling in LLM agents. We co

**Feedback**:
The formal protocol description (Section 7) defines the steps of stimulus presentation, independent response, and neighbor blending, but never defines or computes the coupling metric (CAF, JSD). Without that, it is merely a procedure for generating coupled outputs. Add the precise definition of the metric (baseline, JSD calculation, CAF threshold) to Section 7 to align with the claim of quantifying coupling.

---
