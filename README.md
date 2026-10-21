# Demoing OpenGRIS on OCI

[OpenGRIS](https://github.com/finos/opengris) is a FINOS initiative for sharing distributed compute resources across applications. **Citibank was an originating contributor**, including the initial Scaler implementation; see the [FINOS contribution record](https://github.com/finos/community/issues/326).

Its Python libraries cover three complementary roles:

| Package | Role |
|---|---|
| [Scaler](https://github.com/finos/opengris-scaler) | Schedules and executes distributed Python tasks. |
| [ParGraph](https://github.com/finos/opengris-pargraph) | Describes calculations and their dependencies as task graphs. |
| [Parfun](https://github.com/finos/opengris-parfun) | Splits function inputs into parallel work and combines results. |

This quickstart uses **Scaler directly on OCI**. A Compute VM runs the scheduler and worker manager; the `oci_raw` manager creates OCI Container Instances to execute tasks over the private network. It uses instance-principal authentication and private OCIR images. No Kubernetes cluster is required.

The Monte Carlo code and examples are included in this repository. The command-line examples use Scaler directly; the included notebook gallery also demonstrates ParGraph and Parfun.

## Get started

1. [Installation and OCI configuration](docs/installation.md) — create the VM, configure networking and IAM dynamic groups, install the environment, create the OCIR repository and publish the worker image from the VM.
2. [Start Scaler](docs/running-examples.md) — generate the VM-specific configuration, verify worker execution, and learn how tasks are distributed.
3. [Examples](examples/README.md) — descriptions and commands for pi, pricing calculations, and the scenario grid. For notebooks, follow [Jupyter and the SSH tunnel](examples/notebooks/README.md#open-an-ssh-tunnel-from-your-workstation).
4. [Troubleshooting](docs/troubleshooting.md) and [cleanup](docs/cleanup.md) — diagnose problems and remove demo resources.

## Learn more

- [OpenGRIS, Citi, and the Python packages](docs/opengris.md)
- [Validation and publishing](docs/development.md)
- [Sources and attribution](docs/sources.md)
- [Source provenance](UPSTREAM.md)

This is a single-VM demo with local result files. The included Monte Carlo reducer preserves upstream's known antithetic confidence-interval limitation; see the [example guide](docs/running-examples.md).

## License

This project's original code and documentation are licensed under the [Apache License 2.0](LICENSE). Bundled OpenGRIS notebooks and diagrams also use Apache 2.0; their original notices are preserved in [NOTICE](NOTICE). Licensing of the copied Monte Carlo material remains unverified and is excluded from this declaration pending confirmation. See [source provenance](UPSTREAM.md) for details. Installed dependencies retain their own licenses.
