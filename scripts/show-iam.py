#!/usr/bin/env python3
"""Print dynamic-group rules and policies for an administrator to apply."""
import argparse
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('generator', Path(__file__).with_name('generate-scaler-config.py'))
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--network-compartment-id', help='subnet/VNIC compartment; defaults to VM compartment')
parser.add_argument('--registry-compartment-id', help='OCIR repository compartment; defaults to VM compartment')
args = parser.parse_args()
instance = generator.metadata('instance')
compartment = instance['compartmentId']
network = args.network_compartment_id or compartment
registry = args.registry_compartment_id or compartment
print(f"""Create dynamic group: scaler-scheduler
Matching rule:
ALL {{instance.id = '{instance['id']}'}}

Create dynamic group: scaler-container-pullers
Matching rule:
ALL {{resource.type = 'computecontainerinstance', resource.compartment.id = '{compartment}'}}

Create an IAM policy at tenancy root with these statements:
Allow dynamic-group scaler-scheduler to manage compute-container-family in compartment id {compartment}
Allow dynamic-group scaler-scheduler to use virtual-network-family in compartment id {network}
Allow dynamic-group scaler-container-pullers to read repos in compartment id {registry}

Subnet/VNIC compartment assumed: {network}
Registry compartment assumed: {registry}
Use identity-domain-qualified dynamic-group names if required by your tenancy.
The scheduler rule matches only this VM; update it when replacing the VM.
This command prints instructions; it makes no IAM changes.
""")
