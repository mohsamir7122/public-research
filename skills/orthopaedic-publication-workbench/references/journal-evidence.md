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

Never copy a publisher-family rule to a journal without checking the journal page. A redirect to generic instructions is evidence only for the fields actually covered there. Treat third-party summaries and spreadsheet inheritance as discovery hints.

## Fields to verify

Scope; accepted article types; structured/unstructured abstract; word, reference, table, figure, supplement and title limits; required headings; reporting checklists; registration; protocol/SAP access; ethics and consent; patient-identifying material; data/code statements; conflicts/funding; authorship/contributorship; generative-AI/LLM disclosure and authorship rules; preprints; prior publication; anonymized review; file formats; reference style; graphical abstract/highlights; fees and waivers; open-access licences; repository/deposition requirements; and submission-system links.

## Style profile from papers

Use at least five recent, relevant papers per article type when rights allow; report the actual sample size and coverage. For each observation save DOI, year, article type, licence, full-text source, and page/section/paragraph.

Profile only observable features: section order, abstract shape, typical title construction, table/figure density, outcome presentation, effect measures, uncertainty reporting, appendices, protocol/SAP links, data statements, and reference patterns. Distinguish:

- `explicit_requirement` — official instruction;
- `observed_common` — appears in a clear majority of the authorized sample;
- `observed_variable` — practice differs;
- `insufficient_evidence` — sample or access is inadequate.

Published papers show editorial and scientific practice at a point in time; they do not prove why a manuscript was accepted and cannot estimate acceptance probability.
