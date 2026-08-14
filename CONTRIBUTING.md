# Contributing

Use a focused branch and a Pull Request. Keep changes reproducible, covered by tests, and limited to public-safe medical-research tooling.

Before requesting review:

1. Run `python -m unittest discover -s tests -v`.
2. Run `python scripts/audit_repository.py .`.
3. Confirm no PHI, credentials, subscription full text, protected books, private datasets, or unpublished material were added.
4. Document the provenance and rights of every non-synthetic input or asset.
5. Update capability statements so the README describes only working, tested behavior.
6. Explain any network access, API terms, caching, rate limiting, and failure behavior.

Clinical eligibility decisions, Risk of Bias judgments, and scientific conclusions require accountable human review. Do not ask a reviewer to approve a PR containing patient or secret data; remove it safely first.
