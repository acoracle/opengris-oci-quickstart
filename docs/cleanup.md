# Cleanup

[Back to README](../README.md)

Run commands from the repository root with your Scaler environment activated.

## Stop Scaler

Press **Ctrl-C** in the terminal running `scaler config-montecarlo.toml`. The worker manager normally deletes its container instances during shutdown. Stop any clients submitting new work as well.

If the scheduler or VM was killed unexpectedly, workers can remain provisioned and incur charges. Use the script below to inspect and remove matching leftover workers. Keep Scaler stopped throughout cleanup so it does not create replacement capacity. Save any container logs you need before deleting the instances.

## Preview leftover worker instances

```bash
python scripts/cleanup.py --config config-montecarlo.toml
```

This command is read-only. It lists instance names, OCIDs, and lifecycle states, using the region, compartment, and authentication from the configuration. With the generated configuration it authenticates as the VM's instance principal. The existing container-management and networking policies cover this operation.

An instance is selected only when its name starts with `scaler-worker-` **and** its subnet, container image, scheduler address, worker-manager ID, and OCI Raw worker command match the configuration. This targets the configured worker pool; it is not proof of ownership of an individual job. Do not clean up a shared pool while other users are running work.

Workers already deleting or deleted are skipped. Workers created with an older image, subnet, or scheduler address will not match: use the configuration that created them, or inspect those resources separately in OCI Console.

## Delete the matching workers

After reviewing the preview:

```bash
python scripts/cleanup.py --config config-montecarlo.toml --delete
```

The script rechecks each target, requests deletion, and waits for the OCI deletion work request to succeed. It exits with a nonzero status if an operation fails or times out. The default timeout is 600 seconds per instance; use `--wait-seconds` to change it. A timeout does not cancel the OCI deletion: check the work request in the Console before retrying.

For a file containing several OCI Raw managers, select one explicitly:

```bash
python scripts/cleanup.py --config config-montecarlo.toml \
  --worker-manager-id wm-oci-raw --delete
```

Rerun the preview and check Container Instances in OCI Console to confirm the demo's workers are gone. An empty preview means no workers match this configuration; it does not rule out instances created with other settings or instances still being deleted.

## Remove the remaining demo resources

The script retains the following resources so you can rerun the demo:

| Resource | How to remove it when the demo is finished |
|---|---|
| OCIR image/repository | Find the repository OCID in `results/worker-image.json`; delete the demo image or repository in Container Registry after checking it is not shared. |
| Scheduler VM | Terminate it in Compute after worker cleanup. Choose whether to delete its boot volume or retain it for reuse. |
| Dynamic groups and policies | An IAM administrator can remove the demo's statements and groups once neither the VM nor workers need them. Keep unrelated statements in shared policies. |
| Network rules | Remove only the demo's ingress rules for ports 8516 and 8517; retain rules needed by other applications. |
| Local results and images | Archive or remove this checkout's `results/` directory and the demo's local Podman image if no longer needed. |

Remove the worker instances before terminating the VM or revoking its permissions, since the VM's identity is used for cleanup. VCNs, subnets, gateways, and other shared infrastructure are not removed by the script.

If you disabled firewalld for the demo and plan to keep the VM, configure the required rules and restore the service according to your environment's requirements with `sudo systemctl enable --now firewalld`.

See [Oracle's Container Instances API reference](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/container_instances/client/oci.container_instances.ContainerInstanceClient.html) for deletion and work-request operations.
