# Validation

Validated locally on 2026-10-21:

- 57 tests passed: 8 configuration/discovery tests, 8 repository/publishing tests, 13 cleanup tests, 21 upstream numerical tests, and 7 notebook/dependency tests (including a real Jupyter-to-Scaler worker check).
- The pi example completed 1,600,000 samples across 8 tasks on local Scaler workers and matched serial execution with identical seeds (pi estimate 3.139735).
- All five bundled pricing examples and all nine bundled market-risk scenarios completed through a local Scaler cluster without fetching source.
- The standalone Linux amd64 worker image built successfully from the bundled `app/montecarlo` source using Python 3.12.15, Scaler 2.9.0, NumPy 2.2.6, and OCI SDK 2.185.1.
- The image entrypoint, worker CLI, imports, and a 10,000-path Monte Carlo calculation passed a container smoke check.
- The installer recreated the environment inside a disposable Linux container.
- Cleanup was checked with mocked OCI responses for target matching, preview-only behavior, conditional deletion, and work-request failures; no live resources were deleted.
- VM-side registry publishing was checked with mocked OCI/Podman calls, including token handling and credential cleanup; no live OCIR push was performed.
- Notebook libraries were resolved and installed in the Linux amd64 worker image. The updated installer recreated the host environment with JupyterLab and registered its kernel in a disposable Linux container.
- The connection notebook and all four gallery parallel implementations completed through Jupyter and local Scaler workers on macOS with reduced workloads: AlphaResearch (64 stocks, 756 days, one variant), VolSurface (2 trades, vega disabled), SwapCVA (2 counterparties, 4 swaps, 16 scenarios), and XVA (256 paths, 24 timesteps, 3 trades per desk, 16 calibration iterations).
- The Linux emulation VM's 2 GB memory limit prevented the combined notebook execution test there; native macOS execution was used for that check. Full benchmark sizes and live OCI notebook execution have not been validated.
- Host packages are pinned in requirements-linux-amd64.lock; matching worker runtime packages are pinned in requirements-worker-linux-amd64.lock. Jupyter packages are host-only.

OCI IAM policies were checked against Oracle's published policy examples. Live resource creation, private-image authorization, networking, quota availability, and VM-specific metadata have not been exercised against a tenancy by this repository's automated checks. These notebook additions have not been pushed, so their GitHub Actions checks have not run. Reduced notebook runs establish integration, not financial-model accuracy; the upstream calculations can emit numerical warnings at reduced sizes.
