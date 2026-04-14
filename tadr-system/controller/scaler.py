"""
controller/scaler.py
────────────────────────────────────────────────────────
Handles horizontal scaling.

LOCAL MODE  — adds a simulated VM directly to the vms dict.
AWS MODE    — calls boto3 to launch a real EC2 instance.
             Requires IAM role with ec2:RunInstances permission.

User-data script on the new EC2 bootstraps and starts
worker/producer.py automatically so the new VM immediately
begins streaming metrics into Kafka.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
import time

from config.config import (
    AWS_REGION,
    EC2_AMI_ID,
    EC2_INSTANCE_TYPE,
    EC2_KEY_NAME,
    EC2_SECURITY_GROUP,
    EC2_SUBNET_ID,
    EC2_TAG_NAME,
    KAFKA_BOOTSTRAP,
)

log = logging.getLogger("scaler")

# ── EC2 bootstrap script (runs on new instance at launch) ────────────
def _user_data_script(vm_id: str) -> str:
    return f"""#!/bin/bash
set -e
yum update -y
yum install -y python3 python3-pip git
pip3 install kafka-python numpy

# Clone / copy your project (adjust to your repo URL)
git clone https://github.com/YOUR_ORG/tadr-system.git /opt/tadr
cd /opt/tadr
pip3 install -r requirements.txt

# Start producer as a background service
nohup python3 worker/producer.py --vm-id {vm_id} \
    > /var/log/tadr-producer.log 2>&1 &
"""


# ── AWS scale-out ─────────────────────────────────────────────────────
def _aws_scale_out(vms: dict) -> dict:
    try:
        import boto3
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
    except ImportError:
        log.error("boto3 not installed — cannot use AWS mode")
        return vms

    vm_id = f"vm-ec2-{int(time.time())}"
    import base64
    script = _user_data_script(vm_id)
    user_data_b64 = base64.b64encode(script.encode()).decode()

    try:
        resp = ec2.run_instances(
            ImageId          = EC2_AMI_ID,
            InstanceType     = EC2_INSTANCE_TYPE,
            MinCount         = 1,
            MaxCount         = 1,
            KeyName          = EC2_KEY_NAME,
            SecurityGroupIds = [EC2_SECURITY_GROUP],
            SubnetId         = EC2_SUBNET_ID,
            UserData         = user_data_b64,
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name",    "Value": EC2_TAG_NAME},
                    {"Key": "tadr-id", "Value": vm_id},
                ],
            }],
            IamInstanceProfile={"Name": "tadr-ec2-role"},   # see AWS setup
        )
        instance_id = resp["Instances"][0]["InstanceId"]
        log.info("🚀 Launched EC2 %s as %s", instance_id, vm_id)

        # Pre-register VM with low load (metrics will follow once booted)
        vms[vm_id] = {
            "vm_id":     vm_id,
            "cpu":       15.0,
            "gpu":       10.0,
            "temp":      42.0,
            "prev_temp": 42.0,
            "timestamp": time.time(),
            "instance_id": instance_id,
        }
    except Exception as exc:
        log.error("EC2 launch failed: %s", exc)

    return vms


# ── Local simulation scale-out ────────────────────────────────────────
def _local_scale_out(vms: dict) -> dict:
    vm_id = f"vm-{len(vms) + 1}"
    vms[vm_id] = {
        "vm_id":     vm_id,
        "cpu":       15.0,
        "gpu":       10.0,
        "temp":      42.0,
        "prev_temp": 42.0,
        "timestamp": time.time(),
    }
    log.info("➕ Simulated new VM: %s  (total VMs: %d)", vm_id, len(vms))
    return vms


# ── Public API ────────────────────────────────────────────────────────
def scale_out(vms: dict, use_aws: bool = False) -> dict:
    """
    Add a VM — simulated locally or on AWS.
    Returns the updated vms dict.
    """
    if use_aws:
        return _aws_scale_out(vms)
    return _local_scale_out(vms)


def scale_in(vms: dict, use_aws: bool = False) -> dict:
    """
    Remove the least-loaded VM (cost optimisation).
    Terminates EC2 instance if AWS mode.
    """
    if len(vms) <= 1:
        log.info("scale_in skipped — only 1 VM remaining")
        return vms

    # Pick coolest / least loaded VM
    target = min(vms.values(), key=lambda v: v.get("cpu", 100))
    vm_id  = target["vm_id"]

    if use_aws and "instance_id" in target:
        try:
            import boto3
            ec2 = boto3.client("ec2", region_name=AWS_REGION)
            ec2.terminate_instances(InstanceIds=[target["instance_id"]])
            log.info("🗑️  Terminated EC2 %s (%s)", target["instance_id"], vm_id)
        except Exception as exc:
            log.error("EC2 terminate failed: %s", exc)

    del vms[vm_id]
    log.info("➖ Removed VM: %s  (total VMs: %d)", vm_id, len(vms))
    return vms
