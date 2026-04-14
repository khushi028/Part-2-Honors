"""
controller/consumer.py
────────────────────────────────────────────────────────
Subscribes to vm-metrics AND task-queue topics.
Yields (topic, payload) tuples to the main control loop.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import logging
import time

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from config.config import (
    KAFKA_BOOTSTRAP,
    TOPIC_VM_METRICS,
    TOPIC_TASK_QUEUE,
    KAFKA_GROUP_ID,
)

log = logging.getLogger("consumer")


def get_stream(retries: int = 15):
    """
    Generator — yields (topic: str, payload: dict) indefinitely.
    Blocks until a message arrives; auto-retries on connection loss.
    """
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                TOPIC_VM_METRICS,
                TOPIC_TASK_QUEUE,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            log.info("✅ Consumer subscribed to [%s, %s]", TOPIC_VM_METRICS, TOPIC_TASK_QUEUE)
            for msg in consumer:
                yield msg.topic, msg.value
        except NoBrokersAvailable:
            log.warning("Kafka not ready, retry %d/%d …", attempt, retries)
            time.sleep(4)
        except Exception as exc:
            log.error("Consumer error: %s — reconnecting …", exc)
            time.sleep(3)

    raise RuntimeError("Kafka unavailable after %d retries" % retries)
