# Journal requirements and manuscript-style evidence

## Requirement record

Store one atomic claim per row:

| Field | Rule |
|---|---|
| `journal_id` | Stable identifier; do not rely on ambiguous abbreviations |
| `article_type` | Exact official label |
| `requirement` | One normalized requirement only |
| `value` | Limit, yes/no, controlled term, or short text |
| `official_url` | Exact journal/publisher page |
| `evidence_location` | Heading, accordion label, table row, or quoted fragment within copyright limits |
| `verified_at` | UTC date |
| `status` | `verified`, `stale`, `conflicting`, or `pending_verification` |
| `source_id` | Link to one `official_journal_requirements` source-ledger record with requested/final URLs and frozen-response checksum |

Never copy a publisher-family rule to a journal without checking the journal page. A redirect to generic instructions is evidence only for the fields actually covered there. Treat third-party summaries and spreadsheet inheritance as discovery hints. The offline validator also uses a conservative reviewed authority-domain registry: an official journal hosted elsewhere remains `pending_verification` until its real publisher/society domain is added by code review. This is a safety default, not a claim that an unlisted journal is illegitimate.

## Fields to verify

Scope; accepted article types; structured/unstructured abstract; word, reference, table, figure, supplement and title limits; required headings; reporting checklists; registration; protocol/SAP access; ethics and consent; patient-identifying material; data/code statements; conflicts/funding; authorship/contributorship; generative-AI/LLM disclosure and authorship rules; preprints; prior publication; anonymized review; file formats; reference style; graphical abstract/highlights; fees and waivers; open-access licences; repository/deposition requirements; and submission-system links.

## Style profile from papers

Use at least five distinct recent, relevant papers per article type when rights allow; report the actual sample size and coverage. For each observation save a unique DOI and source-ledger ID, year, article type, licence, full-text source, and page/section/paragraph. Do not count multiple copies or versions of the same paper as separate style observations.

Profile only observable features: section order, abstract shape, typical title construction, table/figure density, outcome presentation, effect measures, uncertainty reporting, appendices, protocol/SAP links, data statements, and reference patterns. Distinguish:

- `explicit_requirement` — official instruction;
- `observed_common` — appears in a clear majority of the authorized sample;
- `observed_variable` — practice differs;
- `insufficient_evidence` — sample or access is inadequate.

Published papers show editorial and scientific practice at a point in time; they do not prove why a manuscript was accepted and cannot estimate acceptance probability.
