# Dataset Strategy

Status: research complete as of 2026-08-29; sourced by live web search, not assumed from prior knowledge. Verify license/row-count details on each source's page immediately before downloading, since Kaggle/HF datasets can change without notice.

## 1. The core problem

Genuine candidate-job **relevance labels** — "this real candidate did/didn't get a callback for this real job" — are not freely available at any real scale; they're proprietary to ATS vendors and recruiters. Every public dataset below is either (a) resumes with a category label, not a job pairing, (b) job postings with no attached candidates, or (c) a small set of resume–JD pairs with a *fit* label of unknown provenance. None of these alone is sufficient; the strategy combines several plus a weak-supervision layer, and — critically — **every label in the system is tagged by source** so real, dataset-derived, and synthetic labels are never silently blended when metrics are reported.

## 2. Sources evaluated

### 2.1 `cnamuangtoun/resume-job-description-fit` (Hugging Face)
- **Format**: 8,000 rows, columns `resume_text`, `job_description_text`, `label` (3-way fit category). Pre-split into 6,240 train / 1,760 test.
- **Label availability**: yes — this is the only source found with a direct resume↔JD relevance label.
- **Caveat (important)**: only 642 unique resumes and 280 unique job descriptions are combined to produce 8,000 rows, and the dataset card does not document how the fit labels were generated (manual annotation vs. an LLM/heuristic pass is unstated). Treat these labels as **unverified provenance** — use them as an auxiliary/pretraining signal for the ML model, not as ground truth for the headline evaluation numbers reported in the README. No license is published on the dataset page at time of writing — confirm before any redistribution or commercial use.
- **Leakage risk**: with only 642×280 unique texts behind 8,000 rows, a naive random row split will leak the same resume or JD across train/test. Any split must be **grouped by resume text and job text**, not by row (Section 4).

### 2.2 Kaggle `dataturks/resume-entities-for-ner`
- **Format**: resume documents with NER span annotations (entity types include skills, degree, name, and similar resume fields — confirm exact schema on download, Kaggle's page did not expose full field-level detail to automated fetch).
- **Use**: trains/evaluates the *information extraction* component (Section 6 of `ARCHITECTURE.md`), not the matching/scoring component. This is a different job from the fit dataset above and should not be conflated with it.
- **License**: per-dataset on Kaggle; verify the license tab before use, especially if the repo will be public.

### 2.3 Kaggle resume-classification datasets (e.g. `hassnainzaidi/resume-classification-dataset-for-nlp`, `saugataroyarghya/resume-dataset`)
- **Format**: resumes labeled by job category (e.g. "Data Science", "HR", "Web Designer").
- **Use**: useful for sanity-checking the resume section detector and skill extractor across varied real-world resume formats/layouts (the brief explicitly requires robustness to layout variation), and as a source of category-diverse resumes for building the weak-supervision negative-sampling pool (Section 3). Not a source of relevance labels.
- **Known bias**: this dataset family skews heavily toward IT/software/technical categories — factor this into any claim about how well the system generalizes to non-technical resumes.

### 2.4 Kaggle `arshkon/linkedin-job-postings` (2023–2024)
- **Format**: large real-world job postings corpus with descriptions; exact column list (skills, seniority, experience level fields) should be confirmed against the current data dictionary on download, as Kaggle's metadata did not expose full schema to automated fetch at research time.
- **Use**: (a) realistic, large-scale Job Description text for stress-testing the JD parser beyond hand-written examples; (b) the pool of "unrelated" postings used for weak-supervision negative sampling (Section 3); (c) a corpus for validating the required-vs-preferred classifier at scale.
- **Bias**: LinkedIn-sourced postings skew toward corporate/white-collar and tech-sector roles, and toward US/English listings — the system's job-side coverage inherits this skew unless supplemented.

### 2.5 O*NET Database (U.S. Department of Labor) — **confirmed CC BY 4.0 license**
- **Format**: Excel/CSV/JSON/relational-DB dump, and a live Web Services API. Contains, per occupation: essential skills, technology skills, tasks, work activities, education/experience requirements.
- **Use**: authoritative seed data for the skill taxonomy (`skills` table) and for occupation-level "does this skill plausibly belong to this job family" validation — a useful sanity check against skill-normalization false positives. Explicit attribution required ("O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration"), which is trivial to satisfy and should go in `data/README.md`.
- **Limitation**: occupation-level, not resume/job-posting-level — it describes what a "Software Developer" typically needs, not what any specific job posting says. It complements, not replaces, the JD parser.

### 2.6 ESCO (EU Skills/Competences/Qualifications/Occupations)
- **Format**: CSV/RDF/TTL/JSON-LD download, plus a REST API. Free access; the formal reuse/redistribution terms should be re-confirmed on esco.ec.europa.eu at download time (the page states free-of-charge use but directs formal licensing questions to their contact form rather than stating a named license inline).
- **Use**: a second, larger, multilingual skill/occupation taxonomy with explicit essential-vs-optional skill relations per occupation — a good cross-check against O*NET for skill importance weighting, and broader coverage outside the US labor market frame.

## 3. Weak-supervision strategy (since real labels don't exist at scale)

Every weak-supervision-produced row is written to `training_labels` with an explicit `label_source`, and the evaluation report always breaks metrics out by source — a model's headline NDCG@5 is never computed by mixing weak and real labels into one number.

**Positive pairs**: pair resumes with job postings from the *same or an adjacent O*NET/ESCO occupation family* as the resume's inferred primary occupation (via its most frequent job titles/skills). This is distant supervision, not ground truth — it assumes occupation-family alignment correlates with relevance, which is a reasonable but imperfect proxy.

**Negative pairs**: randomly sample job postings from *unrelated* occupation families as presumed non-matches (the standard negative-sampling approach used in job-recommendation literature, e.g. the design pattern popularized by the 2012 CareerBuilder Kaggle job-recommendation challenge — cited here as a known precedent for this technique, not as a dataset this project depends on, since its long-term availability wasn't verified).

**Rule-based-score-derived labels**: once the rule-based scorer (Section 8 of `ARCHITECTURE.md`) exists, it can generate a coarse relevance tier for arbitrary resume/job pairs at zero marginal labeling cost. These rows are tagged `label_source = 'weak_supervision_rule_based'` and are explicitly *not* eligible to be the sole training signal for a model whose entire purpose is to improve on the rule-based baseline — they're useful for pretraining/regularization, not for the final reported comparison.

**Small human-annotated gold set (recommended, not yet collected)**: manually label roughly 100–200 resume/job pairs (a mix of the user's own resume against varied real JDs, plus a few volunteers) as the *only* labels used for final held-out evaluation. This is the one label source trusted enough to appear in the headline `evaluate.py` output; everything else trains, this alone validates.

## 4. Preprocessing

- Deduplicate near-identical resume/JD text (the fit dataset in particular has heavy row-level duplication behind few unique documents).
- Normalize encoding/whitespace; strip embedded PII columns not needed for modeling before any data leaves local storage.
- Run the same resume/JD parsers built for the product itself over dataset text, so training-time features are computed by the exact same code path as inference-time features (a common source of train/serve skew if avoided).
- Keep original casing for embedding inputs (transformer tokenizers handle case); lowercase/lemmatize only for the classical/rule-based matching path.

## 5. Train/validation/test split — avoiding leakage

- **Group, don't row-split**: split by unique `resume_id` *and* unique `job_id` such that no resume and no job text appears in more than one split. This directly addresses the `cnamuangtoun` dataset's 642×280 duplication problem (Section 2.1) — a row-level random split would let the model memorize a resume it already saw in training, inflating test metrics.
- **Temporal split where timestamps exist** (LinkedIn postings): train on older postings, validate/test on more recent ones, to approximate real deployment drift rather than an IID assumption that doesn't hold for a job market that changes over time.
- **Stratify by label** to preserve class balance across splits where the fit-label dataset is used.
- The gold human-annotated set (Section 3) is held out entirely — never touched during training or hyperparameter selection, only for the final reported numbers.

## 6. Biases to document explicitly in the README

- Resume-classification datasets skew IT/software-heavy; expect weaker extraction/matching quality on non-technical resumes until validated otherwise.
- LinkedIn-sourced JD corpus skews corporate/white-collar, US/English-language.
- O*NET is a US-labor-market taxonomy; ESCO is EU-centric — combining them gives broader coverage but the two taxonomies don't always align cleanly on occupation granularity.
- The one dataset with direct fit labels has undocumented label provenance — this is a real, stated limitation of any model trained partly on it, not something to gloss over in the eventual writeup.

## 7. Licensing summary

| Source | License status |
|---|---|
| O*NET Database | CC BY 4.0, confirmed — attribution required, commercial use permitted |
| ESCO | Free to use; formal redistribution terms not stated inline — reconfirm before redistributing |
| `cnamuangtoun/resume-job-description-fit` (HF) | No license published at time of writing — confirm before commercial/redistribution use |
| Kaggle datasets (NER, classification, LinkedIn postings) | Per-uploader license — check each dataset's license tab individually; do not assume CC0 |

Practice for this repo: raw dataset files are **not committed to git**. `data/README.md` documents the exact source URL, version/date accessed, and license for each dataset used, plus a small download script — respecting each source's own redistribution terms rather than re-hosting their data.
