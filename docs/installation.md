# Installation and OCI configuration

[Back to README](../README.md)

Run shell commands from the repository root.

## 1. Create the scheduler VM and network

Use the OCI Console to create an **Oracle Linux 9 x86_64 VM**, for example `VM.Standard.E4.Flex` with 2 OCPUs and 16 GB RAM. Choose a compartment and subnet with space for the worker VNICs. Record the instance OCID. The generator later discovers the private IP, region, compartment, full availability-domain name, and subnet automatically.

Use an existing VCN or create one with appropriate routing. Workers default to the VM's subnet and compartment. The VM and workers need DNS and outbound HTTPS to OCI APIs, OCIR, Python package indexes, and Python/uv download hosts. A private subnet needs a NAT gateway or equivalent internet egress; a service gateway alone does not provide access to PyPI or GitHub. Confirm Container Instances quota and shape availability in your selected region and AD.


Configure the VM's subnet security list or attached NSG:

| Destination | Source | Protocol / destination port |
|---|---|---|
| Scheduler VM | Worker subnet CIDR | TCP 8516 and 8517 |
| Scheduler VM | Approved SSH/Bastion source | TCP 22 |

Allow corresponding worker egress to the scheduler. Use stateful rules, or configure return traffic explicitly for stateless rules. Keep Scaler ports reachable only from trusted compute: TCP transport in this demo does not authenticate clients.

For this demo, stop and disable `firewalld` on the scheduler VM:

```bash
sudo systemctl stop firewalld
sudo systemctl disable firewalld
```

This stops firewalld immediately and disables it at boot. OCI security lists and NSGs still apply; keep the network rules above restricted to the worker subnet and approved SSH sources.

**Production:** configure firewalld with the required ports and trusted source networks instead of disabling it, according to your organization's security requirements.

## 2. Clone this repository and install the environment

On the VM:

```bash
sudo dnf install -y git curl podman
git clone https://github.com/acoracle/opengris-oci-quickstart.git
cd opengris-oci-quickstart
bash scripts/install-environment.sh
source ~/scaler-py312/bin/activate
```

The installer installs uv and creates the OpenGRIS Scaler environment.

## 3. Give the scheduler VM permission through a dynamic group

An OCI administrator performs this section. The scheduler does not need permission to create IAM policies or dynamic groups.

First print the matching rules and policy statements with the VM's actual OCIDs:

```bash
python scripts/show-iam.py
```

This uses metadata only and works before the VM has OCI API permissions. It assumes the subnet/VNICs and OCIR repository are in the VM's compartment. If they are elsewhere, provide their **actual compartment OCIDs**:

```bash
python scripts/show-iam.py \
  --network-compartment-id NETWORK_COMPARTMENT_OCID \
  --registry-compartment-id REGISTRY_COMPARTMENT_OCID
```

In **Identity & Security → Domains → your domain → Dynamic groups** (or the tenancy's Dynamic Groups page), create:

**`scaler-scheduler`**, matching this scheduler VM only:

```text
ALL {instance.id = 'SCHEDULER_INSTANCE_OCID'}
```

**`scaler-container-pullers`**, matching container instances in the worker compartment:

```text
ALL {resource.type = 'computecontainerinstance', resource.compartment.id = 'WORKER_COMPARTMENT_OCID'}
```

Create an IAM policy at tenancy root, substituting actual compartment OCIDs:

```text
Allow dynamic-group scaler-scheduler to manage compute-container-family in compartment id WORKER_COMPARTMENT_OCID
Allow dynamic-group scaler-scheduler to use virtual-network-family in compartment id NETWORK_COMPARTMENT_OCID
Allow dynamic-group scaler-scheduler to manage repos in compartment id REGISTRY_COMPARTMENT_OCID
Allow dynamic-group scaler-container-pullers to read repos in compartment id REGISTRY_COMPARTMENT_OCID
```

In an identity-domain tenancy, qualify dynamic-group names with the domain when required, for example `'Default'/'scaler-scheduler'`. Use the exact names from your tenancy. If the VM's VNIC is in a different compartment from the worker subnet, also grant the scheduler `read vnics` in that VNIC compartment so the configuration generator can read it.

The first statement covers creating, inspecting, stopping, deleting, and retrieving logs from container instances. The second allows their VNIC/subnet operations and lets the generator inspect the VM's VNIC. The third lets the **scheduler VM create repositories and push images** in the registry compartment. The fourth lets the **container instances themselves** pull those private images. These are separate permissions: publishing access on the VM does not grant worker image-pull access.

The networking policy follows Oracle's documented launch example and grants access across the named network compartment. The container-puller group includes all container instances in its compartment; use a dedicated demonstration compartment if that is too broad for an existing shared compartment. See [Container Instances IAM policies](https://docs.oracle.com/en-us/iaas/Content/container-instances/permissions/policy-reference.htm).

Allow time for IAM propagation. [Rule changes can take about an hour](https://docs.oracle.com/en-us/iaas/Content/Identity/dynamicgroups/Updating_Dynamic_Groups.htm) to be effective. When replacing the VM, update the `instance.id` matching rule.

## 4. Use the included Monte Carlo examples

The calculation code is included under `app/montecarlo/`, and the five pricing inputs and nine-scenario market-risk grid are under `examples/`. They are available immediately after cloning this repository; no additional checkout or fetch step is required.

These files come from upstream commit `c0068ccba6cd004944afbd2f1bc3ba54291cfecf`. The runner and worker image use these local copies. See [UPSTREAM.md](../UPSTREAM.md) for provenance.

## 5. Create the private repository, build, and push from the VM

Run this on the scheduler VM in the activated environment:

```bash
python scripts/build-and-push.py --repository opengris --tag montecarlo-v1
```

The script uses the VM's **instance principal** to:

1. Discover the VM's region and compartment through metadata.
2. Create a private OCIR repository, or reuse an existing private repository with the same name in the selected compartment.
3. Obtain the tenancy namespace from the repository response and construct the image URI.
4. Build the Linux amd64 worker image from this repository's `container/Dockerfile`.
5. Request a short-lived OCIR bearer token, authenticate Podman, and push the image.
6. Save the image tag, pushed digest reference, and repository OCID to `results/worker-image.json`.

No user API key, federated username, permanent auth token, OCI CLI, or external credential helper is needed. The short-lived Podman credentials are stored in a temporary directory and removed when publishing finishes or fails. The `manage repos` permission from step 3 covers repository creation and publishing; the worker pull policy remains required.

By default, the repository is created in the VM's compartment. If your registry compartment differs, use the same OCID used in the policy:

```bash
python scripts/build-and-push.py \
  --registry-compartment-id REGISTRY_COMPARTMENT_OCID \
  --repository opengris --tag montecarlo-v1
```

The registry hostname is derived from the VM region; `--registry-host fra.ocir.io` can select its regional alias explicitly. This script targets commercial OCI regions. It refuses an existing public repository and never changes repository visibility. Repository names are tenancy-wide within a region: if the name belongs to another compartment, specify that compartment or choose a different name. Reusing a tag updates it in a mutable repository; use a new tag if the repository is immutable.

Load the pushed digest for the next step:

```bash
IMAGE="$(python -c 'import json; print(json.load(open("results/worker-image.json"))["image_digest_ref"])')"
```

The Dockerfile installs Python and dependencies during the build and copies the included Monte Carlo code. Workers reuse compatible installed dependencies at startup. The script always supplies the repository root as the build context, even if invoked from another directory. Build failures can leave the newly created private repository available for a retry; failed pushes do not write new success metadata.

See Oracle's [instance-principal OCIR authentication guide](https://docs.oracle.com/en/learn/cred-helper/index.html) and [registry bearer-token explanation](https://www.ateam-oracle.com/authentication-mechanisms-for-oci-container-registry-ocir).

## 6. Generate the VM-specific configuration

From the activated environment:

```bash
python scripts/generate-scaler-config.py \
  --container-image "$IMAGE" \
  --max-task-concurrency 16 \
  --output config-montecarlo.toml
cat config-montecarlo.toml
```

The generator defaults to **`auth_type = "instance_principal"`**. No `~/.oci/config` or user API signing key is required. It reads IMDSv2, then uses `GetVnic` to discover the subnet. It normalizes the region and keeps the tenancy-prefixed availability-domain name. Existing output is backed up before replacement. To retain user API-key authentication instead:

```bash
python scripts/generate-scaler-config.py --container-image "$IMAGE" \
  --auth-type config_file --profile DEFAULT
```

The default size is 4 OCPUs and 30 GB per container instance. `--max-task-concurrency 16` permits up to four such instances. It is a ceiling, not a request to prestart four instances. Container instances incur charges while provisioned.


Next: [Start Scaler and run the examples](running-examples.md).
