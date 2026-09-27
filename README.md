# When Do Agents Help? Data and reproduction package

This repository accompanies the paper *When Do Agents Help? Embedding, LLM and Agentic
Alignment of Classical Texts and Their Translations* (Máté Metzger). It contains the
dataset of 452 classical texts in Pāli, Sanskrit, Mishnaic Hebrew and Tibetan with
their human-aligned or corrected English translations (9,833 scored units), the outputs of the seven
systems compared in the paper, the judge-panel labels, and the code that reproduces the
paper's main results from them.

## Contents

```
data/tasks.jsonl          452 task inputs, exactly as given to the systems
data/references.jsonl     reference alignments, metadata and provenance (never shown to systems)
outputs/<system>.jsonl    main-run output of each system for every text
outputs/judge_labels.jsonl  labels of the three LLM judges for the 1,848 judged mismatches
code/                     scoring, validation, bootstrap, ceiling and reproduction scripts
licences/                 dated copies of the licence terms of the four corpora
```

## The task

Each text is a source segmented by its editors, paired segment by segment with an English
translation. The English passages are joined into one continuous string, so their
boundaries disappear. A system receives the source segments and the continuous English
(`data/tasks.jsonl`) and must return, for every segment, the corresponding English copied
from that string, in the output format of `code/schemas/result.schema.json`. The answer is
compared with the editors' pairing in `data/references.jsonl`.

A *unit* is a segment whose source text and reference English are both nonempty. Texts are
normalized with the profile in `code/normalize.py` (Unicode NFC, ASCII quotation marks and
ellipsis, whitespace); wording is never changed. `original_reference` gives each segment's
identifier in its source edition, and `provenance` gives the source repository, revision and
original file of every text. `development` is true for the 57 texts that were also used in
the pilot rounds or whose discourse was used in the published-text condition of the paper.

## Reproducing the results

Python 3.10 or later:

```
pip install -r requirements.txt
python code/reproduce.py            # about ten seconds
python code/reproduce.py --ceiling  # also the embedding ceiling
```

On Windows, run `code/validate.py` in Python's UTF-8 mode (`python -X utf8 code/validate.py ...`),
since the texts contain non-ASCII characters.

The script recomputes reference recovery for all seven systems by corpus, structural
validity, the three measures (primary, strict exact, valid-output), the paired
cluster-bootstrap contrasts, the judge-panel defect rates and their paired contrasts
(Table G11), the agreement between the judges (Table G12) and, optionally, the embedding
ceiling. It compares each of these 150 values with the results reported in the paper
(`code/expected.json`) and reports any mismatch.

In `outputs/judge_labels.jsonl`, `judge_item` names the input the three judges saw.
Workflows whose input was identical were judged once, so agreement is computed over the
1,303 unique items rather than the 1,848 labelled rows.

To score a new system, write one line per text, `{"text_id": ..., "result": {...}}`, and run

```
python code/score.py my_outputs.jsonl --family llm      # or --family embedding
python code/validate.py task.json result.json           # structural check of one output
python code/validate.py envelope.json audit.json --audit  # check of one auditor report
```

`code/validate.py` is the validator placed in every agent and auditor workspace as
`/work/validate.py`, copied unchanged together with `code/schemas/`, so the validation
commands printed in Appendix A of the paper run as given. It never reads a reference
alignment.

The prompts and the judge rubric are reproduced verbatim in
Appendices A and E of the paper, and the model and harness settings in Appendix C. The
agent harness itself, and the repeated runs are not part of this package.

## Licences

The texts remain under the terms of their publishers; `licences/` holds dated copies of
those terms, with SHA-256 hashes, in `licences/manifest.json`.

| Corpus | Source text | English translation |
|---|---|---|
| Bilara / SuttaCentral (Pāli) | Mahāsaṅgīti edition; public domain | Bhikkhu Sujato, Bhikkhu Brahmali; CC0 1.0 |
| Itihāsa (Sanskrit) | Apache License 2.0 | M. N. Dutt; Apache License 2.0 |
| Sefaria (Hebrew) | Vilna (Romm, 1913) edition; public domain | Joshua Kulp, *Mishnah Yomit*; CC BY 3.0 |
| 84000 (Tibetan) | translation memory; CC BY 4.0 | translation memory; CC BY 4.0 |

Per-text attribution is in the `provenance` field of `data/references.jsonl`. The code and
the material created for this study are licensed as described in `LICENSE.md`.

SuttaCentral's CC0 dedication places no legal restriction on use, but SuttaCentral asks
that its content not be used "in any way for the creation of datasets for generative AI or
similar". This package is released so that the paper's results can be reproduced and
checked, not for training generative AI. Although the request is not a licence term, please
take it into account when reusing the SuttaCentral material.

## Citation

Máté Metzger. When Do Agents Help? Embedding, LLM and Agentic Alignment of Classical Texts
and Their Translations.
