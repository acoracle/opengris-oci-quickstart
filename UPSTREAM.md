# Monte Carlo source provenance

The files in `app/montecarlo/`, the JSON inputs in `examples/`, and the numerical/storage tests copied into `tests/` come from [dezma/oci-monte-carlo-quickstart](https://github.com/dezma/oci-monte-carlo-quickstart/tree/c0068ccba6cd004944afbd2f1bc3ba54291cfecf), commit `c0068ccba6cd004944afbd2f1bc3ba54291cfecf`.

They are included directly so the application can run after a single clone. The numerical engine and reducer were copied unchanged. Scaler integration lives in `opengris/`; VM setup lives in `scripts/`.

The upstream reducer's antithetic standard-error limitation remains unchanged. No additional checkout is performed during setup, tests, image builds, or example runs.
