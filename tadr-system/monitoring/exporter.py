"""
monitoring/exporter.py
────────────────────────────────────────────────────────
Exposes per-VM metrics to Prometheus via HTTP on PROMETHEUS_PORT.

Gauges exported:
    tadr_vm_cpu_percent        {vm_id}
    tadr_vm_gpu_percent        {vm_id}
    tadr_vm_temperature        {vm_id}
    tadr_vm_pred_temperature   {vm_id}
    tadr_vm_confidence         {vm_id}
    tadr_vm_velocity           {vm_id}
    tadr_task_queue_depth      (gauge, no labels)
    tadr_vm_count              (gauge)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import logging
from prometheus_client import Gauge, start_http_server
from config.config import PROMETHEUS_PORT

log = logging.getLogger("exporter")

# ── Metric definitions ────────────────────────────────────────────────
_cpu_g    = Gauge("tadr_vm_cpu_percent",      "VM CPU usage (%)",               ["vm_id"])
_gpu_g    = Gauge("tadr_vm_gpu_percent",      "VM GPU usage (%)",               ["vm_id"])
_temp_g   = Gauge("tadr_vm_temperature",      "VM current temperature (°C)",    ["vm_id"])
_pred_g   = Gauge("tadr_vm_pred_temperature", "VM predicted temperature (°C)",  ["vm_id"])
_conf_g   = Gauge("tadr_vm_confidence",       "Prediction confidence (0-1)",    ["vm_id"])
_vel_g    = Gauge("tadr_vm_velocity",         "Thermal velocity (°C/min)",      ["vm_id"])
_queue_g  = Gauge("tadr_task_queue_depth",    "Pending tasks in queue")
_vmcnt_g  = Gauge("tadr_vm_count",            "Total registered VMs")


def start_prometheus():
    start_http_server(PROMETHEUS_PORT)
    log.info("✅ Prometheus exporter on :%d", PROMETHEUS_PORT)


def update_metrics(vms: dict, tasks: list):
    for vm in vms.values():
        vid = vm["vm_id"]
        _cpu_g.labels(vm_id=vid).set(vm.get("cpu",        0))
        _gpu_g.labels(vm_id=vid).set(vm.get("gpu",        0))
        _temp_g.labels(vm_id=vid).set(vm.get("temp",      0))
        _pred_g.labels(vm_id=vid).set(vm.get("pred_temp", vm.get("temp", 0)))
        _conf_g.labels(vm_id=vid).set(vm.get("confidence",0))
        _vel_g.labels(vm_id=vid).set(vm.get("velocity",   0))

    _queue_g.set(len(tasks))
    _vmcnt_g.set(len(vms))
