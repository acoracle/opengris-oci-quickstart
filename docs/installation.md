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

The installer installs uv if needed, obtains Python **3.12.15**, and creates `~/scaler-py312`. It installs `opengris-scaler[oci]==2.9.0` and `numpy==2.2.6`; Scaler's OCI extra supplies the compatible SDK. It does not depend on Oracle Linux's system Python or a C++ compiler when a compatible wheel is available. Additional packages such as ParGraph can be added when your application uses them; the included Monte Carlo tasks do not need them.

On a new or replacement VM, clone this repository and run the same installer. No export from the previous VM is needed. The repository already contains:

- `.python-version`: the Python version to install.
- `requirements-linux-amd64.lock`: the pinned package versions used by both the installer and worker image.
- `requirements.txt`: the direct application dependencies.

The dependency lock targets Linux x86_64. To use another environment directory, set `SCALER_ENV_DIRECTORY`. To override the Python patch release, set `SCALER_PYTHON_VERSION`; keep host and worker releases aligned. If the environment already exists, its Python must be 3.12.

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
Allow dynamic-group scaler-container-pullers to read repos in compartment id REGISTRY_COMPARTMENT_OCID
```

In an identity-domain tenancy, qualify dynamic-group names with the domain when required, for example `'Default'/'scaler-scheduler'`. Use the exact names from your tenancy. If the VM's VNIC is in a different compartment from the worker subnet, also grant the scheduler `read vnics` in that VNIC compartment so the configuration generator can read it.

The first statement covers creating, inspecting, stopping, deleting, and retrieving logs from container instances. The second allows their VNIC/subnet operations and lets the generator inspect the VM's VNIC. The third lets the **container instances themselves** pull private images. Podman login on the scheduler does not grant image-pull permission to the workers.

The networking policy follows Oracle's documented launch example and grants access across the named network compartment. The container-puller group includes all container instances in its compartment; use a dedicated demonstration compartment if that is too broad for an existing shared compartment. See [Container Instances IAM policies](https://docs.oracle.com/en-us/iaas/Content/container-instances/permissions/policy-reference.htm).

Allow time for IAM propagation. [Rule changes can take about an hour](https://docs.oracle.com/en-us/iaas/Content/Identity/dynamicgroups/Updating_Dynamic_Groups.htm) to be effective. When replacing the VM, update the `instance.id` matching rule.

## 4. Use the included Monte Carlo examples

The calculation code is included under `app/montecarlo/`, and the five pricing inputs and nine-scenario market-risk grid are under `examples/`. They are available immediately after cloning this repository; no additional checkout or fetch step is required.

These files come from upstream commit `c0068ccba6cd004944afbd2f1bc3ba54291cfecf`. The runner and worker image use these local copies. See [UPSTREAM.md](../UPSTREAM.md) for provenance.

## 5. Build and push your private worker image

An OCI administrator should create a **private OCIR repository** named `opengris` in the registry compartment used in step 3. Pre-create it in the intended compartment; automatic creation during push can place a repository in the tenancy root.

The human account used for Podman needs repository write permission. For an administrator-managed publisher group, a policy example is:

```text
Allow group IMAGE_PUBLISHERS to manage repos in compartment id REGISTRY_COMPARTMENT_OCID
```

Qualify the group with its identity domain where required. This publishing identity is separate from the scheduler VM's instance principal. Obtain the Object Storage namespace from the tenancy details in the Console, or run `oci os ns get --query data --raw-output` in OCI Cloud Shell with suitable permissions. This namespace is part of OCIR image names; this demo does not create a bucket.

Set values for your tenancy and region. Frankfurt is shown as an example; the namespace below must be yours:

```bash
export OCIR_HOST='fra.ocir.io'
export OCIR_NAMESPACE='YOUR_TENANCY_NAMESPACE'
export IMAGE="$OCIR_HOST/$OCIR_NAMESPACE/opengris:montecarlo-v1"
export OCIR_USER='YOUR_IDENTITY_DOMAIN/YOUR_USERNAME'

podman login "$OCIR_HOST" --username "$OCIR_NAMESPACE/$OCIR_USER"
```

At the password prompt, enter an **OCI auth token**, not your Console password. A federated username might be `OracleIdentityCloudService/username@example.com`; login syntax is `<namespace>/<identity-domain>/<username>`. Do not put the auth token into this repository or into a command argument.

Run the build **from this repository's root**:

```bash
podman build --platform linux/amd64 \
  -f container/Dockerfile -t "$IMAGE" .
podman push "$IMAGE"
```

The Dockerfile builds its own OCI Raw worker launcher, installs Python and dependencies during the build, and copies the upstream Monte Carlo package into the image. Startup checks the worker-manager requirements and reuses installed dependencies where compatible. No dependency on a personal prebuilt `opengris:latest` image is required. It still needs network access at startup. For stronger repeatability, use a pushed image digest in the generated configuration.

## 6. Generate the VM-specific configuration

From the activated environment:

```bash
python scripts/generate-scaler-config.py \
  --container-image "$IMAGE" \
  --max-task-concurrency 16 \
  --output config-montecarlo.toml
cat config-montecarlo.toml
```

The generator defaults to **`auth_type = "instance_principal"`**. No `~/.oci/config` or user API signing key is required. It reads IMDSv2, then uses `GetVnic` to discover the subnet. It normalizes the region and keeps the tenancy-prefixed availability-domain name. Existing output is backed up before replacement.

By default workers use the VM's compartment, AD, and primary VNIC subnet. On multi-VNIC hosts, select `--vnic-id OCID`. Use `--advertise-ip IPv4` only when workers should connect to a different reachable address. The generated object-storage listener binds to all interfaces on 8517, the scheduler binds on 8516, and remote workers receive the private IP for both services. Internal scheduler/manager connections remain on loopback.

The default size is 4 OCPUs and 30 GB per container instance. `--max-task-concurrency 16` permits up to four such instances. It is a ceiling, not a request to prestart four instances. Container instances incur charges while provisioned.

To retain user API-key authentication instead:

```bash
python scripts/generate-scaler-config.py --container-image "$IMAGE" \
  --auth-type config_file --profile DEFAULT
```

Next: [Start Scaler and run the examples](running-examples.md).
