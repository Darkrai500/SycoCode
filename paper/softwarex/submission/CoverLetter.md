<!--
Cover letter para Editorial Manager (SoftwareX). La guide for authors NO la
exige; se incluye porque el envío tiene dos cosas que conviene declarar de
entrada y no caben en ningún campo del formulario: (i) la relación con el
Trabajo de Fin de Grado del primer autor y con un segundo manuscrito de
resultados en preparación, y (ii) el ámbito exacto de lo que se publica.
Se pega en el campo "Comments" o se sube como "Cover Letter".
Rellenar la fecha y el nombre del editor antes de enviar.
-->

**To the Editors of *SoftwareX***

Dear Editors,

We submit for your consideration the Original Software Publication
**"SycoCode: a Python platform for execution-grounded evaluation of sycophancy
in code-generating LLMs."**

Sycophancy — a model abandoning a correct answer because the user pushed back —
is normally measured on open-ended text, which forces two compromises: the
judgment of whether the model gave in is itself produced by a language model,
and the measurement is almost always monolingual. SycoCode removes both in the
one domain where they can be removed. Every pressure scenario is anchored to an
injected bug *defined* by the hidden tests it fails, so "did the model make its
code wrong?" is answered by running the code. The separate question of whether
the model *said* it was wrong cannot be grounded in execution, so it is
answered by a version-locked judge panel that is validated — and re-validatable
offline, at zero API cost — against a human-anchored gold set. Every scenario
is instantiated in English and in Spanish with otherwise identical content,
which gives a controlled language axis we believe was not previously available
for code tasks.

We think the software is a good fit for *SoftwareX* for a reason beyond its
subject matter. During development, the platform's two-layer redundancy and its
offline re-validation caught two instrumentation faults that a single-layer
benchmark would have published as findings: an early code extractor that scored
defensive demonstrations as capitulations and inverted the model ranking, and a
judge model silently withdrawn from its provider's API, after which the harness
reverted to an uncertified panel. Both are documented in the repository and the
superseded numbers are archived rather than erased. The design lesson — an
executable oracle and a locked, gold-validated judge panel, each auditing the
other — generalises to any evaluation where part of the behaviour is objectively
checkable and part is discursive, and it is the kind of contribution that lives
in the software rather than in a results table.

The platform is provider-agnostic (any OpenAI-compatible endpoint), resumable,
and testable end-to-end offline: six standalone scripts run 127 checks with no
network and no API keys, so a fresh clone can be verified before spending
anything. The full ten-model campaign ran unattended for roughly $370 in
generation spend, which puts replication within reach of individual
researchers.

**Declarations.** The manuscript is original, is not under consideration
elsewhere, and all four authors have approved the submission. The work
originates in the first author's undergraduate thesis (Universidad de Alcalá),
which under Elsevier's policy does not constitute prior publication. A separate
manuscript reporting the empirical *findings* of the ten-model campaign is in
preparation for another venue; the present submission is deliberately disjoint
from it and describes the platform, not the results — we measured the overlap
between the two body texts by n-gram diff rather than by inspection, and it is
0.00% at seven-word grams. The authors declare no competing interests. Funding
sources are disclosed in the Acknowledgements.

**Software availability.** The code is public at
<https://github.com/Darkrai500/SycoCode>, MIT-licensed, with the exact version
described in the metadata table tagged and released as `v1.0.0`
(<https://github.com/Darkrai500/SycoCode/tree/v1.0.0>). The repository contains
`README.md` and `LICENSE.txt` at its root. The benchmark dataset ships with the
code under CC BY 4.0 and is documented in `DATASHEET.md`.

Thank you for your consideration.

Yours sincerely,

**Antonio Garcia-Cabot** (corresponding author)
On behalf of Juan-Carlos Negrin-de-la-Fe, David de-Fitero-Dominguez,
Antonio Garcia-Cabot and Eva Garcia-Lopez
Departamento de Ciencias de la Computación, Universidad de Alcalá,
28801 Madrid, Spain
a.garciac@uah.es
