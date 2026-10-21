#!/usr/bin/env python3
"""Generate the user's Monte Carlo Scaler configuration on an OCI Compute VM.

Requires Python 3.11+ and the OCI Python SDK (already included in Scaler's
OCI extra). Reads IMDSv2 and the VNIC API; does not provision cloud resources.
Uses the VM's compartment, region, AD, and primary VNIC subnet for workers.
Defaults to instance principal authentication; --container-image is required.
Existing output files are backed up automatically before replacement.

Example:
  python scripts/generate-scaler-config.py --container-image YOUR_OCIR_IMAGE --output config-montecarlo.toml
  scaler config-montecarlo.toml

On a multi-VNIC VM, --vnic-id selects the interface whose IP and subnet to use.
--advertise-ip can override the scheduler IP if a different address is needed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import tomllib
import urllib.error
import urllib.request


IMDS = "http://169.254.169.254/opc/v2/"


def metadata(resource):
    # IMDS must bypass HTTP_PROXY/HTTPS_PROXY configured on the host.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        IMDS + resource + "/", headers={"Authorization": "Bearer Oracle"}
    )
    for attempt in range(3):
        try:
            with opener.open(request, timeout=5) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"IMDSv2 {resource}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise RuntimeError(
                    "Cannot reach OCI IMDSv2. Run this script on the scheduler's OCI Compute VM."
                ) from exc
        time.sleep(attempt + 1)


def discover(args):
    import oci

    instance = metadata("instance")
    vnics = metadata("vnics")
    region = (instance.get("canonicalRegionName")
              or instance.get("regionInfo", {}).get("regionIdentifier"))
    if not region:
        raise RuntimeError("IMDS did not return a canonical region identifier")
    region = region.lower()
    if args.auth_type == "instance_principal":
        client = oci.core.VirtualNetworkClient(
            {"region": region},
            signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner(),
            timeout=(5, 30),
        )
    else:
        config = oci.config.from_file(profile_name=args.profile)
        config["region"] = region
        client = oci.core.VirtualNetworkClient(config, timeout=(5, 30))

    if not isinstance(vnics, list) or not vnics:
        raise RuntimeError("IMDS returned no attached VNICs")
    if args.vnic_id:
        candidates = [v for v in vnics if v.get("vnicId") == args.vnic_id]
        if not candidates:
            raise RuntimeError("--vnic-id is not a VNIC attached to this VM")
    else:
        candidates = vnics

    selected = None
    for item in candidates:
        vnic = client.get_vnic(item["vnicId"]).data
        if args.vnic_id or vnic.is_primary:
            selected = vnic
            break
    if selected is None:
        raise RuntimeError("No primary VNIC found; select an attached interface with --vnic-id")
    if not selected.subnet_id:
        raise RuntimeError("Selected VNIC has no subnet OCID (a VLAN VNIC cannot be used here)")
    private_ip = str(ipaddress.IPv4Address(selected.private_ip))
    advertised_ip = str(ipaddress.IPv4Address(args.advertise_ip or private_ip))
    for key in ("compartmentId", "availabilityDomain"):
        if not instance.get(key):
            raise RuntimeError(f"IMDS is missing {key}")
    return {
        "instance_id": instance.get("id", "unknown"),
        "private_ip": private_ip,
        "advertised_ip": advertised_ip,
        "vnic_id": selected.id,
        "region": region,
        "compartment_id": instance["compartmentId"],
        "availability_domain": instance["availabilityDomain"],
        "subnet_id": selected.subnet_id,
    }


def render(info, args):
    # JSON basic strings are compatible with TOML for the values used here.
    def quote(value):
        return json.dumps(str(value), ensure_ascii=False)

    lines = [
        "# Generated from this OCI VM by generate-scaler-config.py",
        "# Worker placement uses the VM's compartment, availability domain, and selected VNIC subnet.",
        "[object_storage_server]",
        'bind_address = "tcp://0.0.0.0:8517"',
        "", "[scheduler]",
        'bind_address = "tcp://0.0.0.0:8516"',
        'object_storage_address = "tcp://127.0.0.1:8517"',
        "", "[[worker_manager]]",
        f"auth_type = {quote(args.auth_type)}",
        f"oci_profile = {quote(args.profile)}",
        'type = "oci_raw"',
        'scheduler_address = "tcp://127.0.0.1:8516"',
        f"worker_scheduler_address = {quote('tcp://' + info['advertised_ip'] + ':8516')}",
        f"object_storage_address = {quote('tcp://' + info['advertised_ip'] + ':8517')}",
        'worker_manager_id = "wm-oci-raw"',
        f"oci_region = {quote(info['region'])}",
        f"compartment_id = {quote(info['compartment_id'])}",
        f"availability_domain = {quote(info['availability_domain'])}",
        f"subnet_id = {quote(info['subnet_id'])}",
        f"container_image = {quote(args.container_image)}",
        'python_version = "3.12.15"',
        'requirements_txt = """',
        "opengris-scaler[oci]==2.9.0", "numpy==2.2.6", '"""',
        f"instance_ocpus = {args.instance_ocpus}",
        f"instance_memory_gb = {args.instance_memory_gb}",
    ]
    if args.max_task_concurrency is not None:
        lines.append(f"max_task_concurrency = {args.max_task_concurrency}")
    text = "\n".join(lines) + "\n"
    tomllib.loads(text)
    return text


def save(path, text):
    path = Path(path).expanduser().absolute()
    if not path.parent.is_dir():
        raise RuntimeError(f"Output directory does not exist: {path.parent}")
    if path.is_symlink():
        raise RuntimeError("Output is a symlink; choose a regular output file")
    backup = None
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            if path.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup = path.with_name(path.name + ".bak-" + stamp)
                shutil.copy2(path, backup)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    return path, backup


def positive_number(value):
    import math
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return result


def concurrency(value):
    result = int(value)
    if result != -1 and result < 1:
        raise argparse.ArgumentTypeError("must be positive, or -1 for unlimited")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default="config-montecarlo.toml")
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--auth-type", choices=("config_file", "instance_principal"),
                        default="instance_principal")
    parser.add_argument("--container-image", required=True)
    parser.add_argument("--instance-ocpus", type=positive_number, default=4.0)
    parser.add_argument("--instance-memory-gb", type=positive_number, default=30.0)
    parser.add_argument("--max-task-concurrency", type=concurrency)
    parser.add_argument("--vnic-id", help="select an attached VNIC instead of the primary VNIC")
    parser.add_argument("--advertise-ip", help="override the advertised scheduler IPv4 address")
    parser.add_argument("--stdout", action="store_true", help="print TOML without writing a file")
    args = parser.parse_args()
    try:
        info = discover(args)
        text = render(info, args)
        if args.stdout:
            print(text, end="")
        else:
            path, backup = save(args.output, text)
            if backup:
                print(f"Previous config backed up to {backup}", file=sys.stderr)
            print(f"Wrote {path}", file=sys.stderr)
        print("Detected VM settings: " + json.dumps(info, sort_keys=True), file=sys.stderr)
        return 0
    except ImportError as exc:
        print(f"ERROR: missing dependency: {exc}. Activate your Scaler OCI environment "
              "or run: python -m pip install oci", file=sys.stderr)
    except Exception as exc:
        # ServiceError.message avoids dumping signed HTTP headers/config details.
        message = getattr(exc, "message", str(exc))
        status = getattr(exc, "status", None)
        if status in (401, 403, 404):
            message = f"OCI API HTTP {status}: {message}. Check profile credentials and permission to read the VM's VNICs."
        print(f"ERROR: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
