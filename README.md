# OpenGRIS Demo on OCI

[OpenGRIS](https://github.com/finos/opengris) is a FINOS initiative for making distributed compute resources easier to share across applications. Its scope covers a grid resource scheduling standard and a set of open-source Python libraries. Applications describe work to execute; an execution runtime schedules that work across local processes, servers, or cloud resources.

The motivation comes from a familiar problem in large financial institutions: different teams have separate compute pools, demand varies through the day, and capacity assigned to one application can sit idle while another application needs more. OpenGRIS aims to make those resources more accessible through common interfaces and flexible execution backends. This applies to batch calculations and interactive analysis, including Monte Carlo pricing and risk calculations. See the project's [scope and original FINOS proposal](https://github.com/finos/community/issues/326).

**Citibank was an originating contributor**, including the initial Scaler implementation. For the wider collaboration across banks and technology providers, including Oracle, see the [FINOS announcement on an open HPC compute fabric](https://www.finos.org/press/banks-and-tech-providers-collaborate-on-open-fabric-for-high-performance-computing) (April 21, 2026).

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
3. [Examples](examples/README.md) — an introduction to tasks, workers, and container instances, followed by commands for pi, pricing calculations, and the scenario grid. For notebooks, follow [Jupyter and the SSH tunnel](examples/notebooks/README.md#open-an-ssh-tunnel-from-your-workstation).
4. [Troubleshooting](docs/troubleshooting.md) and [cleanup](docs/cleanup.md) — diagnose problems and remove demo resources.

## Learn more

- [OpenGRIS and the Python packages](docs/opengris.md)
- [Sources and attribution](docs/sources.md)
- [Source provenance](UPSTREAM.md)

This is a single-VM demo with local result files. The included Monte Carlo reducer preserves upstream's known antithetic confidence-interval limitation; see the [example guide](docs/running-examples.md).

## License

This project's original code and documentation are licensed under the [Apache License 2.0](LICENSE). Bundled OpenGRIS notebooks and diagrams also use Apache 2.0; their original notices are preserved in [NOTICE](NOTICE). Licensing of the copied Monte Carlo material remains unverified and is excluded from this declaration pending confirmation. See [source provenance](UPSTREAM.md) for details. Installed dependencies retain their own licenses.
