# Orthopaedics and sports-medicine journal registry

`orthopaedics_sports_2023_snapshot.jsonl` contains 319 journal-level discovery records recovered from the user-supplied 2023 SCImago category workbook. The source workbook stores most values in drawing-layer text boxes rather than normal spreadsheet cells, so the snapshot was reconciled against the readable PDF counterpart before import.

The quartile and rank are historical discovery metadata only. They are not current journal status, scientific-quality measures, submission requirements, or acceptance probabilities. Every record begins with `current_journal_status=unverified` and `author_requirements_status=pending_live_verification`.

Do not copy requirements between journals based on publisher family. A record may move to `verified` only after an official journal/publisher page has been opened and its exact URL, verification date, and evidence locations have been captured. Validate the registry with:

```bash
python scripts/validate_journal_registry.py \
  data/journals/orthopaedics_sports_2023_snapshot.jsonl \
  --expected-count 319
```

The supplied “Publishability Factor v4” workbook was used as an audit target, not as authoritative journal guidance. It covered 152/319 journals; 130/152 depended on publisher-family inheritance, and formula errors could return scope text as an official URL, compare the wrong title-fit fields, and let a high score compensate for an out-of-scope journal. This implementation uses non-compensatory hard gates.
