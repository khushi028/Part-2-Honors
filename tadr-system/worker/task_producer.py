"""
worker/task_producer.py
────────────────────────────────────────────────────────
Generates synthetic tasks and pushes them to Kafka topic
'task-queue' every few seconds.

Each task carries:
  task_id   — unique identifier
  cpu_req   — CPU % units this task needs
  gpu_req   — GPU % units this task needs
  priority  — "high" | "normal" | "low"
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import time
import random
import logging


from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from config.config import KAFKA_BOOTSTRAP, TOPIC_TASK_QUEUE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] task_producer — %(message)s",
)
log = logging.getLogger("task_producer")

PRIORITIES = ["high", "normal", "normal", "normal", "low"]   # weighted distribution


def make_producer(retries: int = 10) -> KafkaProducer:
    for attempt in range(1, retries + 1):
        try:
            p = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
            )
            log.info("✅ Connected to Kafka")
            return p
        except NoBrokersAvailable:
            log.warning("Kafka not ready, retry %d/%d …", attempt, retries)
            time.sleep(3)
    raise RuntimeError("Kafka unavailable")


def main():
    producer = make_producer()
    task_id  = 0
    log.info("🚀 Task producer running …")

    while True:
        task = {
            "task_id":  f"t{task_id:05d}",
            "cpu_req":  random.randint(5, 22),
            "gpu_req":  random.randint(3, 18),
            "priority": random.choice(PRIORITIES),
            "submitted": time.time(),
        }
        producer.send(TOPIC_TASK_QUEUE, task)
        log.info("📋 Task %s | cpu_req=%d  gpu_req=%d  priority=%s",
                 task["task_id"], task["cpu_req"], task["gpu_req"], task["priority"])
        task_id += 1
        time.sleep(random.uniform(2, 5))   # variable arrival rate


if __name__ == "__main__":
    main()
