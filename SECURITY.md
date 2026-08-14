# Security Policy

Report suspected credential exposure, patient-data leakage, unsafe scraping, or dependency vulnerabilities privately to the repository owner. Do not open a public issue containing the secret or sensitive data.

The repository accepts public metadata and synthetic fixtures only. Secrets must be supplied at runtime through environment variables and must never be printed. Network collectors must use rate limits, caching, identifiable user agents where required, and the terms of the source service.

Before release, run the unit tests and `python scripts/audit_repository.py .`. This scanner is a guardrail, not proof that a repository is safe.
