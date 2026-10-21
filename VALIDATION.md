# Validation

Validated locally on 2026-10-21:

- 29 tests passed: 8 configuration/discovery tests and 21 upstream numerical tests.
- All five bundled pricing examples and all nine bundled market-risk scenarios completed through a local Scaler cluster without fetching source.
- The standalone Linux amd64 worker image built successfully from the bundled `app/montecarlo` source using Python 3.12.15, Scaler 2.9.0, NumPy 2.2.6, and OCI SDK 2.185.1.
- The image entrypoint, worker CLI, imports, and a 10,000-path Monte Carlo calculation passed a container smoke check.
- The installer recreated the environment inside a disposable Linux container.
- Dependency versions were exported from the Linux image into requirements-linux-amd64.lock.

OCI IAM policies were checked against Oracle's published policy examples. Live resource creation, private-image authorization, networking, quota availability, and VM-specific metadata have not been exercised against a tenancy by this repository's automated checks. GitHub Actions has not run until the repository is published.
