#!/bin/bash
# ─────────────────────────────────────────────
#  Create Kafka topics for TADR system
#  Run AFTER docker-compose up
# ─────────────────────────────────────────────

KAFKA_CONTAINER="tadr-kafka"
BROKER="localhost:9092"

echo "⏳ Waiting for Kafka to be ready..."
sleep 8

echo "📌 Creating topic: vm-metrics"
docker exec $KAFKA_CONTAINER kafka-topics \
  --create --if-not-exists \
  --bootstrap-server $BROKER \
  --topic vm-metrics \
  --partitions 3 \
  --replication-factor 1

echo "📌 Creating topic: task-queue"
docker exec $KAFKA_CONTAINER kafka-topics \
  --create --if-not-exists \
  --bootstrap-server $BROKER \
  --topic task-queue \
  --partitions 3 \
  --replication-factor 1

echo ""
echo "✅ Topics created. Current list:"
docker exec $KAFKA_CONTAINER kafka-topics \
  --list --bootstrap-server $BROKER
