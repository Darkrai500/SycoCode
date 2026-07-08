# Bug Taxonomy Review — SycoCode

> **Status:** draft v1
> **Author:** Juan Carlos Negrín (JC)
> **Date:** 2026-05-02
> **Purpose:** ground SycoCode's bug-category taxonomy in prior literature
> and produce a concrete proposal of 10–15 categories for Layer 1 of the
> dataset (`problems.jsonl > bugs[].category`).

---

## 1. Scope and constraints

This document is a directed literature review whose only goal is to fix
the closed enum of values that `bug.category` can take in `problems.jsonl`.
It is **not** a rubric for the difficulty levels 1/2/3 (those are governed
by reasoning-complexity per the 2026-04-29 Plan-B decision and are
ortogonal to this taxonomy), and it is **not** an exhaustive survey of
software-engineering fault literature. Categories that cannot be anchored
in at least one verified source were excluded, with one exception flagged
in §5.

In the SycoCode schema, `bug.category` is an enum used for two purposes
only: (a) as a weighting dimension in the Susceptibility Score (see
`sycocode_dataset_design.md` §5.3), and (b) as a reporting axis for
breakdown tables in the thesis memory. It is **not** used to drive the
generation of bugs — bug injection is manual — and it is **not** consumed
by the model as part of any prompt. A category therefore needs to be
discriminative for differential model behaviour and cheaply assignable by
a second annotator; it does not need to capture every nuance of how the
bug was introduced.

---

## 2. Sources reviewed

| Source | Year | Domain | Has explicit taxonomy? | Adopted in proposal? |
|---|---|---|---|---|
| EvalPlus (Liu et al.) [VERIFIED] | 2023 | LLM code eval | No — describes **test-input** mutation, not bug categories | Cited as scope clarification only |
| OctoPack / HumanEvalPack (Muennighoff et al.) [VERIFIED] | 2023 | LLM code eval | Yes — 6 bug types in HumanEvalFix | **Yes** (primary anchor) |
| Tambon et al. — *Bugs in LLM-generated code* [VERIFIED] | 2024 | LLM code, empirical | Yes — 10 empirical patterns | **Yes** (primary anchor) |
| Pan, Kim & Whitehead — *Bug fix patterns* [VERIFIED] | 2009 | Empirical SE | Yes — 27 bug-fix patterns | Partial (3 named patterns adopted) |
| Defects4J (Just, Jalali & Ernst) [VERIFIED] | 2014 | Real-world Java bugs | No explicit taxonomy — database of 357 real bugs | Cited as industrial reference; not adopted |
| CWE (MITRE) [UNVERIFIED, well-known] | ongoing | Security weaknesses | Yes — but security-oriented | **No**, mentioned only to be excluded |
| Jia & Harman — *Mutation testing survey* [VERIFIED] | 2011 | Mutation testing | Yes — surveys mutation-operator classes | **Yes** (anchor for operator-class categories) |
| King & Offutt — *Mothra Fortran system* [VERIFIED] | 1991 | Mutation testing | Yes — origin of AOR/ROR/COR/ABS/UOI/LCR | **Yes** (origin citation) |
| SWE-bench (Jimenez et al.) [UNVERIFIED] | 2024 | LLM repo-level eval | Not consulted in v1 — out of scope | No |

`[VERIFIED]` here means the cited claims were checked against the source
itself (arXiv abstract, IEEE/ACM/Springer landing page, or open-access
PDF) during this review. `[UNVERIFIED]` means the claim is widely known
but the source was not opened in this pass.

---

## 3. Taxonomies found in the literature

### 3.1. OctoPack — HumanEvalFix (Muennighoff et al. 2023) [VERIFIED]

The HumanEvalFix subset of HumanEvalPack injects exactly one bug into
each of the 164 canonical HumanEval solutions and classifies it under one
of six labels:

```
value misuse | missing logic | excess logic |
operator misuse | variable misuse | function misuse
```

Strengths for SycoCode: (a) the labels are surface-level and reproducible
(an annotator can almost always assign the right one without reading the
problem), (b) they were designed for the same kind of object SycoCode
manipulates — a single-function HumanEval-style problem with one injected
bug, and (c) they map cleanly onto Python/JS/Java/Go/C++/Rust without
language-specific assumptions. Limitation: the `operator misuse` and
`function misuse` buckets are very wide; SycoCode benefits from splitting
them, since arithmetic vs comparison vs logical operators plausibly yield
different flip rates under social pressure.

arXiv: 2308.07124. Citation key: `muennighoffOctoPackInstructionTuning2023`.

### 3.2. Tambon et al. 2024 — Bugs in LLM-generated code [VERIFIED]

An empirical study that classified 333 bugs collected from code generated
by three frontier LLMs and induced ten patterns:

```
Misinterpretations | Syntax Error | Silly Mistake | Prompt-biased code |
Missing Corner Case | Wrong Input Type | Hallucinated Object |
Wrong Attribute | Incomplete Generation | Non-Prompted Consideration
```

Strengths for SycoCode: this is the only verified taxonomy that observes
**LLM-generated** bugs in the wild — i.e. exactly the failure modes the
model class under study tends to make and (presumably) tends to defend
under pressure. Patterns like *Hallucinated Object*, *Wrong Attribute*
and *Non-Prompted Consideration* have no analogue in HumanEvalFix and
are useful as discriminators. Limitation: several patterns
(*Misinterpretations*, *Silly Mistake*) are catch-alls whose boundary
with the others is fuzzy in the source itself; adopting them verbatim
would make annotation unreliable. SycoCode therefore borrows the
discriminative patterns and merges the catch-alls into HumanEvalFix's
six-way split.

arXiv: 2403.08937. Citation key: `tambonBugsLargeLanguage2024`.

### 3.3. Pan, Kim & Whitehead 2009 — Bug fix patterns [VERIFIED]

Defines 27 automatically extractable bug-fix patterns mined from version
control repositories of seven Java projects. The three most frequent are:

```
MC-DAP — method call with different actual parameter values (14.9–25.5%)
IF-CC  — change in if conditional                          (5.6–18.6%)
AS-CE  — change of assignment expression                   (6.0–14.2%)
```

Only these three pattern names were verified verbatim in this review;
the remaining 24 are referenced in the paper but were not extracted in
this pass. Strengths: large empirical base, explicit mnemonics,
reproducible extraction. Limitation: the taxonomy is at the AST-edit
level, not at the semantic-bug level — many distinct semantic bugs map
to the same edit pattern and vice-versa. Pan et al. is therefore used
in §5 as a *secondary* anchor, never as the sole justification for a
category.

DOI: 10.1007/s10664-008-9077-5. Citation key: `panUnderstandingBugFix2008` (BBT keyed by online-first 2008 date; print volume is 2009).

### 3.4. Defects4J (Just, Jalali & Ernst 2014) [VERIFIED]

Defects4J is a database of 357 real bugs (854 in current releases) from
five open-source Java projects, packaged with their failing test suites.
The original ISSTA 2014 paper does **not** propose a taxonomy: bugs are
identified by project and revision, not by category. SycoCode references
Defects4J only as the canonical industrial source of "real bugs" against
which a synthetic taxonomy should be sanity-checked, and to acknowledge
that no widely-adopted finer-grained classification of its 357 bugs
exists in that paper.

DOI: 10.1145/2610384.2628055. Citation key: `justDefects4JDatabaseExisting2014`.

### 3.5. Mutation operators — Jia & Harman 2011 [VERIFIED] + King & Offutt 1991 [VERIFIED]

The Mothra system (King & Offutt 1991) introduced the operator family
that subsequent mutation-testing tools standardised. Jia & Harman's
2011 IEEE TSE survey consolidates the literature and confirms the five
"sufficient" operators for selective mutation:

```
ABS — absolute value insertion       (operands)
UOI — unary operator insertion        (operators)
LCR — logical connector replacement   (operators)
AOR — arithmetic operator replacement (operators)
ROR — relational operator replacement (operators)
```

Plus the closely-related COR (conditional/binary connector replacement,
e.g. `&&`/`||`/`&`/`|`/`^`).

Strengths for SycoCode: mutation-testing operators **are** systematic
bug injection. AOR, ROR, COR map almost 1-to-1 onto SycoCode's
intuitive notion of "wrong arithmetic / comparison / logical operator"
and provide a methodologically rigorous justification for why those
are *the* operator-replacement categories worth tracking. Limitation:
the operator families do not cover semantic bugs (missing edge case,
wrong return type, API misuse), so they must be combined with a
semantic-level taxonomy.

DOIs: 10.1109/TSE.2010.62 (Jia & Harman); 10.1002/spe.4380210704
(King & Offutt). Citation keys: `jiaAnalysisSurveyDevelopment2011`,
`kingFortranLanguageSystem1991`.

### 3.6. EvalPlus (Liu et al. 2023) — out of scope [VERIFIED]

EvalPlus extends HumanEval/MBPP by **adding test cases** via
type-aware mutation and ChatGPT-seed augmentation. Despite the word
"mutation" appearing in both communities, EvalPlus mutates *inputs to
tests*, not *code*, and produces no bug taxonomy. It remains the
right citation for the contamination/insufficiency argument in
`sycocode_dataset_design.md` §3.3 but contributes nothing to this
document beyond clarifying that distinction.

arXiv: 2305.01210. Citation key: `liuYourCodeGenerated2023`.

### 3.7. CWE — explicitly excluded

The Common Weakness Enumeration is a security-oriented taxonomy
(buffer overflows, injection, race conditions, …). SycoCode tests
*logic* sycophancy on small functional problems, not security
properties. No CWE entry is adopted; the framework is mentioned here
solely to record the explicit decision not to use it.

---

## 4. Synthesis: what SycoCode actually needs

SycoCode does not measure bug-fixing capability. It measures whether a
model that is correct under neutral framing flips its judgement when
the user applies social pressure, on a code that contains exactly one
known bug. The unit of analysis is the (problem, bug, scenario) triple,
and the category dimension feeds into the Susceptibility Score weights
and into per-category flip-rate tables.

Three operational consequences follow:

**(a) Categories are useful only if they discriminate between models or
between scenarios.** A category whose flip rate is uniform across the
11 evaluated models and 6 scenarios contributes nothing analytically —
it is a noise dimension. The literature suggests three plausible axes
of discrimination: surface-level operator/value bugs (cheap to spot,
expected low flip rate), missing-or-excess logic bugs (require reading
the problem statement, expected medium), and semantic bugs about
contract or specification (require modelling user intent, expected
highest flip rate). A taxonomy that span these axes is preferable to
one that fragments any single axis at high resolution.

**(b) Reproducibility dominates richness.** SycoCode has ~50 problems
× 3 bugs = 150 bug instances to classify, each by hand. A taxonomy
where two annotators agree on category for ≥90% of bugs without
discussion is far more valuable than a 30-class taxonomy where they
disagree on 25% of cases. HumanEvalFix's six-way split is the upper
end of what is reliably annotatable on HumanEval-scale problems —
SycoCode can extend it modestly but not double it.

**(c) The taxonomy must survive being quoted in the thesis memory.**
Every category name will appear in tables and prose, in both English
and Spanish. Names that translate cleanly (`off_by_one`,
`wrong_operator`, `missing_edge_case`) are preferable to names that
require a paragraph of definition (`Non-Prompted Consideration`).
This biases the proposal toward HumanEvalFix-style names with
mutation-testing rigor as the underlying justification, rather than
toward Tambon's full pattern list.

---

## 5. Proposed taxonomy for SycoCode

Twelve categories. Each is given as a snake_case enum value, a
one-sentence definition, a 3–5 line Python example, the literature
anchors that justify it, and the difficulty level on which it
typically lands under Plan B's reasoning-complexity rubric. The level
mapping is **tentative**: it expresses the author's expectation, not a
constraint — the same category can produce bugs at any level depending
on how the bug interacts with the surrounding logic.

### 5.1. `off_by_one`

Boundary error in indexing, slicing, or loop bounds: the code processes
one element too few or too many. Anchored in HumanEvalFix
*operator misuse* [VERIFIED, Muennighoff et al. 2023], Tambon's
*Missing Corner Case* [VERIFIED, Tambon et al. 2024] and the ROR
mutation operator [VERIFIED, Jia & Harman 2011; King & Offutt 1991].
Typical level: 1.

```python
def reverse_list(lst):
    return lst[:-1][::-1]   # drops the last element
```

### 5.2. `wrong_arithmetic_operator`

`+ / - / * / / / % / **` replaced with another arithmetic operator that
type-checks but produces the wrong value. Anchored in HumanEvalFix
*operator misuse* [VERIFIED] and the AOR mutation operator
[VERIFIED, Jia & Harman 2011]. Typical level: 1.

```python
def average(xs):
    return sum(xs) - len(xs)   # should be `/`
```

### 5.3. `wrong_comparison_operator`

`< / <= / > / >= / == / !=` replaced with another relational operator.
Anchored in HumanEvalFix *operator misuse* [VERIFIED] and the ROR
mutation operator [VERIFIED, Jia & Harman 2011; King & Offutt 1991].
Typical level: 1.

```python
def is_positive(n):
    return n >= 0   # should be `>` for "positive" semantics
```

### 5.4. `wrong_logical_operator`

`and / or / not` replaced or inverted; a missing or extra negation.
Anchored in HumanEvalFix *operator misuse* [VERIFIED], the LCR/COR
mutation operators [VERIFIED, Jia & Harman 2011] and the UOI operator
[VERIFIED, King & Offutt 1991] for inserted/dropped negations.
Typical level: 1–2.

```python
def is_eligible(age, has_id):
    return age >= 18 or has_id   # should be `and`
```

### 5.5. `wrong_variable`

A reference to one in-scope variable replaced with another in-scope
variable of the same type. Anchored in HumanEvalFix *variable misuse*
[VERIFIED, Muennighoff et al. 2023]. Typical level: 2.

```python
def diff(a, b):
    result = a - b
    return a   # should be `result`
```

### 5.6. `wrong_constant`

A literal value (number, string, boolean) replaced with another that
type-checks but is wrong. Anchored in HumanEvalFix *value misuse*
[VERIFIED]. Typical level: 1.

```python
def to_celsius(f):
    return (f - 32) * 5 / 8   # should be 9
```

### 5.7. `wrong_function_call`

The called function or method is replaced by a wrong but plausible
alternative (`sort` vs `sorted`, `append` vs `extend`, `is` vs `==`).
Anchored in HumanEvalFix *function misuse* [VERIFIED] and Pan et al.'s
*MC-DAP* pattern [VERIFIED, Pan et al. 2009]. Typical level: 2.

```python
def deduplicate(xs):
    return xs.sort()   # mutates and returns None; should be `sorted(set(xs))`
```

### 5.8. `missing_edge_case`

A code path that the specification requires is absent: empty input,
zero, negative, single-element, NaN, etc. Anchored in HumanEvalFix
*missing logic* [VERIFIED] and Tambon's *Missing Corner Case*
[VERIFIED, Tambon et al. 2024]. Typical level: 2–3.

```python
def first_or_none(xs):
    return xs[0]   # crashes on empty list
```

### 5.9. `excess_logic`

A statement is present that should not be: a redundant filter, an
extra increment, an unwarranted branch. Anchored in HumanEvalFix
*excess logic* [VERIFIED] and Tambon's *Non-Prompted Consideration*
[VERIFIED]. Typical level: 2.

```python
def count_evens(xs):
    return sum(1 for x in xs if x % 2 == 0 and x > 0)   # filter on positivity not requested
```

### 5.10. `off_specification`

The function returns the wrong type, shape, or contract: returns an
`int` when the spec asks for a `list`, mutates input when asked for a
copy, prints when asked to return. Anchored in Tambon's
*Misinterpretations* and *Wrong Input Type* patterns [VERIFIED,
Tambon et al. 2024]. Typical level: 2–3.

```python
def double_all(xs):
    for i in range(len(xs)):
        xs[i] *= 2          # mutates in place; spec asks for new list
```

### 5.11. `api_misuse`

The right function is called with the wrong arguments, in the wrong
order, or with arguments of the wrong shape: `range(stop, start)`,
`zip` instead of `zip_longest`, `dict.get(key, default)` with default
omitted. Anchored in Tambon's *Wrong Attribute* pattern [VERIFIED,
Tambon et al. 2024] and Pan et al.'s *MC-DAP* pattern [VERIFIED,
Pan et al. 2009]. Typical level: 2–3.

```python
def slice_window(xs, start, end):
    return xs[end:start]   # arguments swapped
```

### 5.12. `precision_or_overflow`

Floating-point comparison without tolerance, integer overflow,
truncating division where exact division is needed, accumulated
rounding error. Anchored loosely in Tambon's *Silly Mistake* catch-all
[VERIFIED, Tambon et al. 2024], with the explicit caveat in §4 of
Tambon that the *Silly Mistake* boundary is fuzzy. This is the
only category in the proposal whose anchor is partial; it is included
because precision-related bugs are a documented LLM failure mode in
the source and are a useful discriminator (models that handle floats
poorly can be expected to defend their bug more confidently).
Typical level: 2.

```python
def is_one(x):
    return x == 1.0   # fails for x = 0.1 + 0.2 + 0.7
```

---

## 6. Open questions for discussion in chat

- **Final count: 12 vs fewer.** The 12 above sit at the upper end of
  what is reliably annotatable. If annotation pilots show <90%
  inter-annotator agreement, candidates to merge are
  `wrong_arithmetic_operator` ⊕ `wrong_comparison_operator` ⊕
  `wrong_logical_operator` into a single `wrong_operator`, and
  `wrong_variable` ⊕ `wrong_constant` into `wrong_value` (which is
  closer to the original HumanEvalFix granularity). That would yield
  9 categories.

- **Borderline cases** noted but not given their own category:
  - `mutable_default_argument` — Python-specific, occurs rarely on
    HumanEval-scale problems. Currently maps to `excess_logic` or
    `off_specification` depending on how it is introduced. Worth
    promoting to its own category?
  - `shallow_vs_deep_copy` — same reasoning; currently absorbed by
    `off_specification`.
  - `order_of_operations` (missing parentheses) — currently absorbed
    by `wrong_arithmetic_operator` or `wrong_logical_operator`. Pan
    et al.'s 27-pattern list likely names this separately; verifying
    that requires reading the full paper text.

- **Tambon patterns deliberately not adopted.** *Syntax Error*,
  *Hallucinated Object*, *Incomplete Generation*, and
  *Prompt-biased code* are observable in unconstrained generation
  but cannot occur in SycoCode's setup, where every bug must be
  syntactically valid Python and must pass the import+collection step
  to be testable. *Misinterpretations* is too broad to assign
  reliably.

- **Literature not reviewed in v1** (Priority 4 of the original
  brief): SWE-bench (Jimenez et al. 2024), Papadakis et al. 2019
  *Mutation Testing Advances*, Thung-Lo-Jiang 2012 *Automatic Defect
  Categorization* (IBM ODC), and recent 2024–2025 surveys of "bug
  categorization for LLM evaluation". None are expected to invalidate
  the proposal, but Papadakis 2019 in particular could refine §5.2–
  §5.4 if it documents post-2011 operator extensions.

- **Pan et al. detail.** Only 3 of the 27 named patterns were
  extracted verbatim during this review (MC-DAP, IF-CC, AS-CE). If
  the §5 anchors to Pan need to be tightened (specifically for
  `wrong_function_call` and `api_misuse`), the full pattern list must
  be transcribed from the source PDF in a follow-up pass.

---

## 7. Bibliography

Generated from the project's reference library. Every entry has DOI or
arXiv ID.

[1] N. Muennighoff, Q. Liu, A. Zebaze, Q. Zheng, B. Hui, T. Y. Zhuo,
S. Singh, X. Tang, L. von Werra, and S. Longpre, "OctoPack:
Instruction Tuning Code Large Language Models," arXiv preprint
arXiv:2308.07124, 2023. [Online]. Available:
https://arxiv.org/abs/2308.07124

[2] F. Tambon, A. Moradi Dakhel, A. Nikanjam, F. Khomh, M. C.
Desmarais, and G. Antoniol, "Bugs in Large Language Models Generated
Code: An Empirical Study," arXiv preprint arXiv:2403.08937, 2024.
[Online]. Available: https://arxiv.org/abs/2403.08937

[3] K. Pan, S. Kim, and E. J. Whitehead, "Toward an understanding of
bug fix patterns," *Empirical Software Engineering*, vol. 14, no. 3,
pp. 286–315, Jun. 2009. doi: 10.1007/s10664-008-9077-5.

[4] R. Just, D. Jalali, and M. D. Ernst, "Defects4J: a database of
existing faults to enable controlled testing studies for Java
programs," in *Proc. 2014 International Symposium on Software Testing
and Analysis (ISSTA '14)*, San Jose, CA, USA, 2014, pp. 437–440. doi:
10.1145/2610384.2628055.

[5] Y. Jia and M. Harman, "An Analysis and Survey of the Development
of Mutation Testing," *IEEE Transactions on Software Engineering*,
vol. 37, no. 5, pp. 649–678, Sep.–Oct. 2011. doi: 10.1109/TSE.2010.62.

[6] K. N. King and A. J. Offutt, "A Fortran language system for
mutation-based software testing," *Software: Practice and Experience*,
vol. 21, no. 7, pp. 685–718, Jul. 1991. doi: 10.1002/spe.4380210704.

[7] J. Liu, C. S. Xia, Y. Wang, and L. Zhang, "Is Your Code Generated
by ChatGPT Really Correct? Rigorous Evaluation of Large Language
Models for Code Generation," in *Advances in Neural Information
Processing Systems 36 (NeurIPS 2023)*, 2023. [Online]. Available:
https://arxiv.org/abs/2305.01210
