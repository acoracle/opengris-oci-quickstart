# Troubleshooting and cleanup

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

Stop Scaler with Ctrl-C and verify in OCI that its worker container instances were deleted. If the process was killed or the VM failed, manually remove remaining `scaler-worker-*` instances belonging to this demo. Only remove your own demo resources. Delete the VM, private image/repository, IAM rules, and network rules when no longer needed.

Return to [Running examples](running-examples.md).
