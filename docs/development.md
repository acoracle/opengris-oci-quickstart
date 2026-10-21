# Validation and publishing

[Back to README](../README.md)

Run shell commands from the repository root.

A local numerical test does not require OCI permissions:

```bash
bash opengris/run-example.sh --local-workers 2 --all-examples --parallelism 4
```

Developer checks (activate the environment first):

```bash
uv pip install --python "$VIRTUAL_ENV/bin/python" pytest==8.3.5
PYTHONPATH=app python -m pytest -q tests
```

The automated tests use mock OCI responses; they do not create IAM policies or cloud resources. A live OCI deployment is still required to validate the network, tenancy policies, image pull, and service quotas together.

To publish a local checkout with GitHub CLI after authenticating as `acoracle`:

```bash
gh auth login
gh repo create acoracle/opengris-oci-quickstart --private --source=. --remote=origin --push
```

Choose public visibility separately if you intend to share it publicly. Generated configs, logs, results, and key files are ignored. Review the staged content before pushing.

See [Recorded validation results](../VALIDATION.md) and [source provenance](../UPSTREAM.md).
