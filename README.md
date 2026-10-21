# OpenGRIS Scaler on OCI

[OpenGRIS](https://github.com/finos/opengris) is a FINOS initiative for sharing distributed compute resources across applications. **Citi was an originating contributor**, including the initial Scaler implementation; see the [FINOS contribution record](https://github.com/finos/community/issues/326).

Its Python libraries cover three complementary roles:

| Package | Role |
|---|---|
| [Scaler](https://github.com/finos/opengris-scaler) | Schedules and executes distributed Python tasks. |
| [ParGraph](https://github.com/finos/opengris-pargraph) | Describes calculations and their dependencies as task graphs. |
| [Parfun](https://github.com/finos/opengris-parfun) | Splits function inputs into parallel work and combines results. |

This quickstart uses **Scaler directly on OCI**. A Compute VM runs the scheduler and worker manager; the `oci_raw` manager creates OCI Container Instances to execute tasks over the private network. It uses instance-principal authentication and private OCIR images. No Kubernetes cluster is required.

The Monte Carlo code and examples are included in this repository. ParGraph and Parfun are optional and are not needed for these examples.

## Get started

1. [Installation and OCI configuration](docs/installation.md) — create the VM, configure networking and IAM dynamic groups, install the environment, build the worker image, and generate configuration.
2. [Running examples](docs/running-examples.md) — start Scaler, verify workers, run the pricing examples and market-risk grid, and test scaling.
3. [Troubleshooting and cleanup](docs/troubleshooting.md) — diagnose permissions, image pulls, connectivity, and remove demo resources.

## Learn more

- [OpenGRIS, Citi, and the Python packages](docs/opengris.md)
- [Validation and publishing](docs/development.md)
- [Sources and attribution](docs/sources.md)
- [Monte Carlo source provenance](UPSTREAM.md)

This is a single-VM demo with local result files. The included Monte Carlo reducer preserves upstream's known antithetic confidence-interval limitation; see the [example guide](docs/running-examples.md).
