"""
worker/producer.py
────────────────────────────────────────────────────────
Runs a simulated VM, emits metrics to Kafka topic 'vm-metrics'
every EMIT_INTERVAL_SEC seconds.

Usage:
    python worker/producer.py --vm-id vm-1
    python worker/producer.py --vm-id vm-2
    python worker/producer.py --vm-id vm-3
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import json
import time
import logging

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from worker.simulator import VMSimulator
from config.config import KAFKA_BOOTSTRAP, TOPIC_VM_METRICS, EMIT_INTERVAL_SEC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] producer/%(name)s — %(message)s",
)
log = logging.getLogger("producer")


def make_producer(retries: int = 10) -> KafkaProducer:
    for attempt in range(1, retries + 1):
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            log.info("✅ Connected to Kafka at %s", KAFKA_BOOTSTRAP)
            return p
        except NoBrokersAvailable:
            log.warning("Kafka not ready, retry %d/%d …", attempt, retries)
            time.sleep(3)
    raise RuntimeError("Could not connect to Kafka after %d attempts" % retries)


def main(vm_id: str):
    sim      = VMSimulator(vm_id)
    producer = make_producer()

    log.info("🚀 Starting VM producer for %s", vm_id)

    while True:
        metrics = sim.tick()
        producer.send(TOPIC_VM_METRICS, metrics)
        log.info(
            "📤 %s | cpu=%.1f%%  gpu=%.1f%%  temp=%.1f°C",
            vm_id, metrics["cpu"], metrics["gpu"], metrics["temp"],
        )
        time.sleep(EMIT_INTERVAL_SEC)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vm-id", default="vm-1", help="Unique VM identifier")
    args = parser.parse_args()
    main(args.vm_id)
