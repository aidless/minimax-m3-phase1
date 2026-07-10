# Rebuttal Draft — PAPER-E
# Generated from agent review (score: 4/10)
# 2026-07-05 18:51

## CRITICAL (3)

### Q1: Exact numerical identity of γ and H across conditions A-D contradicts the stocha

**Reviewer concern:** Exact numerical identity of γ and H across conditions A-D contradicts the stochastic protocol
**Evidence cited:** Table 1 reports γ=0.692±0.062 identically for all four conditions. Executor uses temperature 0.7 (stochastic). Evaluator

**Suggested fix:** Report cross-condition agreement rate of evaluator's binary preferences. If 100%, frame as evaluator determinism not emp

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q2: 2x2 factorial design collapses to single-factor experiment

**Reviewer concern:** 2x2 factorial design collapses to single-factor experiment
**Evidence cited:** Gating triggered in only 2.7% of TTRL updates. C/D effectively identical to A/B. 60 runs are redundant.

**Suggested fix:** Redesign gating mechanism or honestly report as single-factor experiment with null conditions.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q3: Dissociation is a design property, not an empirical discovery

**Reviewer concern:** Dissociation is a design property, not an empirical discovery
**Evidence cited:** Evaluator judges relative strategy quality (strategy A beats baseline), which remains unchanged regardless of communicat

**Suggested fix:** Clearly distinguish design-level independence from empirical question of whether communication affects evaluator prefere

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

## IMPORTANT (7)

### Q1: Sensitivity analyses with N=3 have zero inferential power

**Reviewer concern:** Sensitivity analyses with N=3 have zero inferential power
**Evidence cited:** Table 2 reports sensitivity results all with N=3 seeds, no std/p-values/CIs. Used to claim 'mechanism independence'.

**Suggested fix:** Increase N to ≥10 or label as pilot/exploratory with no statistical validity.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q2: Evaluator-identity gradient supported by only one data point per level

**Reviewer concern:** Evaluator-identity gradient supported by only one data point per level
**Evidence cited:** Gradient: self-eval (A-D), within-family DeepSeek Pro (N=5, Δγ=+0.012), cross-family GLM (N=15, Δγ=-0.287). Each level =

**Suggested fix:** Soften language from 'gradient' and 'necessary' to 'preliminary evidence'.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q3: 25 math problems cycled across 30 rounds x 5 agents = problem memorization

**Reviewer concern:** 25 math problems cycled across 30 rounds x 5 agents = problem memorization
**Evidence cited:** 150 problem-agent assignments per condition per seed with only 25 problems. Each problem presented ~30 times.

**Suggested fix:** Report problem-presentation frequency. Test for performance differences between first and subsequent presentations.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q4: 30% accuracy drop is the most practical finding but severely under-analyzed

**Reviewer concern:** 30% accuracy drop is the most practical finding but severely under-analyzed
**Evidence cited:** Accuracy drops 0.281→0.198 (30%). Only mentioned in passing. No per-strategy or per-round analysis.

**Suggested fix:** Add dedicated analysis: per-strategy accuracy changes, per-round trajectories, p-value for A vs B.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q5: Condition E changes executor+evaluator+N+T simultaneously

**Reviewer concern:** Condition E changes executor+evaluator+N+T simultaneously
**Evidence cited:** Qwen self-eval (γ=0.859) vs DeepSeek self-eval (γ=0.692) comparison never reported. Executor identity also matters.

**Suggested fix:** Report DeepSeek vs Qwen self-eval γ comparison. Add DeepSeek+GLM condition to disentangle effects.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q6: Boundary condition claim conflates single observation with general principle

**Reviewer concern:** Boundary condition claim conflates single observation with general principle
**Evidence cited:** One model (DeepSeek) shows γ invariance, one cross-family pair shows shift. Insufficient for 'boundary condition'.

**Suggested fix:** Reframe as 'Self-evaluation appears to suppress strategy-level effects in the models tested'.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q7: Qwen self-eval baseline buried in table footnote

**Reviewer concern:** Qwen self-eval baseline buried in table footnote
**Evidence cited:** Table 1 footnote: '†Qwen self-eval baseline: γ=0.859±0.094, ECE=0.295±0.077'. Essential for Finding 3 but relegated.

**Suggested fix:** Add as row in Table 1. Explain missing Brier score for Condition E.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

## MINOR (3)

### Q1: Heavy reliance on unpublished manuscripts from same author

**Reviewer concern:** Heavy reliance on unpublished manuscripts from same author
**Evidence cited:** 4/5 foundational citations are 'Manuscript' or 'TMLR submission' by same author.

**Suggested fix:** Clearly state publication status. Frame as building on own prior work.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q2: ECE equal-frequency binning not justified, differs from cited literature

**Reviewer concern:** ECE equal-frequency binning not justified, differs from cited literature
**Evidence cited:** 10-bin equal-frequency binning. Guo et al. 2017 (cited) uses equal-width.

**Suggested fix:** Justify choice or switch to equal-width. Report both as robustness check.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---

### Q3: Matched seeds methodology undefined

**Reviewer concern:** Matched seeds methodology undefined
**Evidence cited:** Paper says 'Seeds matched across conditions' but never defines which RNG states are shared.

**Suggested fix:** Explicitly define what is held fixed across conditions.

**Response (draft):**
TODO: Write response here

**Changes made:**
- TODO: List specific changes

---
