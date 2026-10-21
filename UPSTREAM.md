# Source provenance

The files in `app/montecarlo/`, the JSON inputs in `examples/`, and the numerical/storage tests copied into `tests/` come from [dezma/oci-monte-carlo-quickstart](https://github.com/dezma/oci-monte-carlo-quickstart/tree/c0068ccba6cd004944afbd2f1bc3ba54291cfecf), commit `c0068ccba6cd004944afbd2f1bc3ba54291cfecf`.

**License status:** no license grant was found in the upstream repository or the copied source. The Apache 2.0 declaration for this demo's original work does not relicense these files. Permission or an explicit compatible license from the copyright holders is still required to establish redistribution rights. This applies to the copied engine, JSON inputs, and numerical/storage tests.

They are included directly so the application can run after a single clone. The numerical engine and reducer were copied unchanged. Scaler integration lives in `opengris/`; VM setup lives in `scripts/`.

The upstream reducer's antithetic standard-error limitation remains unchanged. No additional checkout is performed during setup, tests, image builds, or example runs.

## OpenGRIS notebooks

`examples/notebooks/AlphaResearch.ipynb`, `VolSurface.ipynb`, `SwapCVA.ipynb`, `XVA.ipynb`, and their SVG diagrams come from [finos/opengris-scaler](https://github.com/finos/opengris-scaler/tree/dc492943c939d4f7ee06425d5db79f37b51fadfa/examples/notebooks), commit `dc492943c939d4f7ee06425d5db79f37b51fadfa`.

Modifications for this demo: scheduler/data-service defaults point at the VM's loopback ports with environment overrides; XVA uses the existing scheduler instead of starting local workers; Parfun nested tasks use their worker-side connection; kernel metadata selects this demo's environment; saved outputs are removed; and an OCI usage note is added. Original computational benchmark sizes are retained. The local `00_Check_OCI.ipynb` is an additional connection/import check written for this demo.

The copied notebook source is covered by the upstream Apache License 2.0. Its [license](examples/notebooks/LICENSE.txt) and [copyright notices](examples/notebooks/NOTICE.txt) are included.
