# Troubleshooting

[Back to README](../README.md)

Run shell commands from the repository root.

| Symptom | Check |
|---|---|
| `COPY ... no such file` during build | Build from the repository root, where `app/montecarlo/` is included. |
| OCI 400 on creation | Inspect the full AD name, subnet OCID, and shape settings in the config. |
| OCI 404 / `NotAuthorizedOrNotFound` | Dynamic-group membership, policy scope, region, resource OCIDs, IAM propagation. |
| Image cannot be pulled | Exact image URI/tag; private-repository compartment and container-puller policy; subnet egress. |
| Instance ACTIVE but futures hang | Worker logs; TCP 8516 **and** 8517 in OCI and host firewalls; advertised private IP. |
| Wrong package/source version | Rebuild and push image, use the correct tag/digest, and create fresh workers. |
| `.result()` error with `client.map()` | Scaler 2.9.0 `map()` returns result values; `submit()` returns futures. |

On the VM use `sudo ss -lntp` to verify listeners. In OCI Console inspect **Developer Services → Container Instances**, the container's logs, and work-request errors. Logs can become unavailable after deletion; capture them while the resource exists. OCI debug HTTP output can include signed headers: avoid posting it unredacted.

## Retrieve container logs with the OCI CLI

Run these commands on the scheduler VM using its instance-principal permissions. Use the **container OCID** (`ocid1.computecontainer...`), rather than the parent **container instance OCID** (`ocid1.computecontainerinstance...`). Replace the OCID and region placeholders with your deployment's values.

### Find the container OCID

In the OCI Console:

1. Select the region where Scaler creates workers, for example **Germany Central (Frankfurt)**.
2. Open **Developer Services → Containers & Artifacts → Container Instances**. You can also search for **Container Instances** in the Console.
3. Select the worker compartment and open the relevant `scaler-worker-...` instance. Match its name to the instance name in the Scaler worker-manager log.
4. In the instance details, find **Containers** and select the worker container.
5. Copy the **OCID** from the container details. It starts with `ocid1.computecontainer.`. The OCID on the parent instance page starts with `ocid1.computecontainerinstance.` and is not the ID required by `retrieve-logs`.

Paste the copied value into `CONTAINER_ID` in the command below. See [Oracle's Console navigation guide](https://docs.oracle.com/en-us/iaas/Content/container-instances/listing-container-instances.htm).

### Download and read the logs

```bash
CONTAINER_ID="ocid1.computecontainer.oc1..."
REGION="eu-frankfurt-1"

mkdir -p results/logs
oci container-instances container retrieve-logs \
  --container-id "$CONTAINER_ID" \
  --region "$REGION" \
  --auth instance_principal \
  --file results/logs/worker-container.log &&
cat results/logs/worker-container.log
```

The command downloads a snapshot of the most recent **256 KB** of container logs; it does not stream new output. To print directly in the terminal, use `--file -` instead of the file path. Run it again for a fresh snapshot; if prompted, confirm replacement of the existing file.

### Alternative: find the container OCID with the CLI

If you already have the parent instance OCID, list its containers:

```bash
COMPARTMENT_ID="ocid1.compartment.oc1..."
INSTANCE_ID="ocid1.computecontainerinstance.oc1..."

oci container-instances container list \
  --compartment-id "$COMPARTMENT_ID" \
  --container-instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --auth instance_principal \
  --all
```

Use the `id` of the matching container from the response as `CONTAINER_ID`.

### Logs unavailable or container still creating

Scaler can delete idle or failed container instances, so capture logs while the container exists. A response such as `409 Conflict: Container is in : Deleted` means that container's logs can no longer be retrieved through this command. Find the current container OCID if Scaler has provisioned a replacement.

If the container is still `CREATING`, application logs may not yet be available. Inspect its lifecycle details first:

```bash
oci container-instances container get \
  --container-id "$CONTAINER_ID" \
  --region "$REGION" \
  --auth instance_principal
```

Look at `lifecycle-state`, `lifecycle-details`, `image-url`, and `container-instance-id`. In OCI Console, open that parent container instance's work requests and inspect their errors and log messages for provisioning or image-pull failures.

## Cleanup

Follow the [cleanup guide](cleanup.md) to stop Scaler, preview matching worker instances, delete leftovers with `scripts/cleanup.py`, and remove the remaining demo resources.

Return to [Running examples](running-examples.md).
