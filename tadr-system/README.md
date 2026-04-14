# TADR System — Temperature-Aware Dynamic Resource Manager

> Kafka-driven controller that predicts VM temperatures using ensemble ML,
> then schedules tasks or scales EC2 instances based on **confidence** and
> **thermal velocity** — before a node overheats.

---

## Table of Contents
1. [Architecture](#architecture)
2. [How It Works End-to-End](#how-it-works)
3. [Prediction: Confidence & Velocity](#prediction)
4. [Decision Logic](#decision-logic)
5. [Project Structure](#project-structure)
6. [Local Setup](#local-setup)
7. [Train the Models](#train-the-models)
8. [AWS Setup](#aws-setup)
9. [Grafana Dashboard](#grafana-dashboard)
10. [Configuration Reference](#configuration-reference)

---

## Architecture

```
Worker VMs ──► Kafka (vm-metrics) ──►  Controller
Task Producer ► Kafka (task-queue) ──►     │
                                           ├─ predict()   → pred_temp, confidence, velocity
                                           ├─ decision()  → SCHEDULE | SCALE_OUT | IDLE
                                           ├─ schedule()  → redistribute tasks to cool VMs
                                           └─ scale_out() → new VM (local sim or AWS EC2)
                                                │
                                      Prometheus (port 8000)
                                                │
                                           Grafana (port 3000)
```

---

## How It Works

### Every Kafka message triggers this loop:

```
1. vm-metrics  →  vms[vm_id] = data          (update state)
   task-queue  →  tasks.append(data)

2. For each VM:
      pred_temp, confidence, velocity = predict(vm)

3. action = decision(vms)
      "SCHEDULE"  → schedule(tasks, vms)
      "SCALE_OUT" → scale_out(vms)
      "IDLE"      → pass

4. update_metrics(vms, tasks)  →  Prometheus
```

---

## Prediction

### Model
- **RandomForestRegressor** (100 trees, sklearn)
- Trained to predict temperature **30 minutes ahead**
- Features: `cpu%, gpu%, current_temp, prev_temp, delta_temp, hour_sin, hour_cos`
- Two models: `streaming_cpu.pkl` and `streaming_gpu.pkl`
- Combined: `pred_temp = cpu_pred × 0.6 + gpu_pred × 0.4`

### Confidence — Inverse-Uncertainty Mapping
```
confidence = 1 / (1 + σ)
```
Where **σ = std of individual tree predictions** in the ensemble.

> *"Prediction uncertainty is estimated using ensemble variance. Confidence
> is defined as an inverse function of the standard deviation, ensuring that
> higher disagreement among models results in lower confidence."*

- σ = 0   → confidence = 1.0  (all trees agree perfectly)
- σ = 1   → confidence = 0.5
- σ = 4   → confidence = 0.2  (high uncertainty, do not act)

### Velocity — Thermal Rate of Change
```
velocity = (pred_temp − current_temp) / horizon    [°C / min]
```
This is the **estimated mean thermal slope** over the prediction horizon.

- Positive velocity = VM is heating up
- Used to distinguish "already hot" from "rapidly getting hotter"
- Threshold `VELOCITY_SCHEDULE = 0.5 °C/min` → redistribute tasks
- Threshold `VELOCITY_SCALE    = 1.2 °C/min` → launch new VM

---

## Decision Logic

```
For each VM:
    at_risk = (pred_temp > 80°C OR temp > 80°C)
              AND confidence ≥ 0.60
              AND velocity   ≥ 0.5 °C/min

If ≥50% VMs at risk AND max_velocity ≥ 1.2 AND no cool VMs:
    → SCALE_OUT

If at least 1 VM at risk AND cool VMs exist:
    → SCHEDULE

Otherwise:
    → IDLE
```

A **60-second cooldown** prevents scale-out thrashing.

---

## Project Structure

```
tadr-system/
├── docker-compose.yml          Kafka + Zookeeper + Prometheus + Grafana
├── requirements.txt
├── README.md
│
├── config/
│   └── config.py               All thresholds and AWS settings
│
├── kafka/
│   └── topics.sh               Creates vm-metrics and task-queue topics
│
├── models/
│   ├── train_models.py         Train RandomForest models from dataset CSV
│   ├── streaming_cpu.pkl       Pre-trained CPU temperature model
│   └── streaming_gpu.pkl       Pre-trained GPU temperature model
│
├── worker/
│   ├── simulator.py            Physics-based VM metrics generator
│   ├── producer.py             Sends vm-metrics to Kafka
│   └── task_producer.py        Pushes tasks to task-queue topic
│
├── controller/
│   ├── main.py                 Main control loop
│   ├── consumer.py             Dual-topic Kafka consumer
│   ├── predictor.py            Ensemble prediction + confidence + velocity
│   ├── decision.py             SCHEDULE / SCALE_OUT / IDLE logic
│   ├── scheduler.py            Priority-aware task assignment
│   ├── scaler.py               Local sim + AWS EC2 scale-out/in
│   └── state.py                Shared vms dict and tasks list
│
├── monitoring/
│   ├── exporter.py             Prometheus metrics exporter
│   └── prometheus.yml          Scrape config
│
└── dashboard/
    └── grafana.json            Grafana dashboard (import manually)
```

---

## Local Setup

### Prerequisites
- Docker + Docker Compose
- Python 3.9+

### Step 1 — Clone and install dependencies
```bash
cd tadr-system
pip install -r requirements.txt
```

### Step 2 — Start infrastructure
```bash
docker-compose up -d
```
Starts: Kafka, Zookeeper, Prometheus, Grafana

### Step 3 — Create Kafka topics
```bash
chmod +x kafka/topics.sh
bash kafka/topics.sh
```

### Step 4 — Train models (skip if .pkl files already present)
```bash
python models/train_models.py --data /path/to/full_dataset_mar_dec_2021.csv
```

### Step 5 — Start the controller
```bash
python controller/main.py
```

### Step 6 — Start VM workers (separate terminals)
```bash
python worker/producer.py --vm-id vm-1
python worker/producer.py --vm-id vm-2
python worker/producer.py --vm-id vm-3
```

### Step 7 — Start task producer
```bash
python worker/task_producer.py
```

### Step 8 — Open dashboards
| Service    | URL                        | Credentials     |
|------------|----------------------------|-----------------|
| Prometheus | http://localhost:9090      | —               |
| Grafana    | http://localhost:3000      | admin / admin   |

To import the Grafana dashboard:
1. Open Grafana → **Dashboards → Import**
2. Upload `dashboard/grafana.json`
3. Select your Prometheus datasource → **Import**

---

## Train the Models

```bash
python models/train_models.py \
    --data full_dataset_mar_dec_2021.csv \
    --out-dir models/
```

This will:
- Build feature matrix from 440k rows (Mar–Dec 2021, 1-min intervals)
- Create shifted target: temperature at t + 30 min
- Train two RandomForest models (100 trees each)
- Print MAE and R² on held-out test set
- Save `models/streaming_cpu.pkl` and `models/streaming_gpu.pkl`

If model files are missing, `predictor.py` automatically falls back to a
physics-based heuristic (no error, just a warning in logs).

---

## AWS Setup

### Option A — Simple (Recommended for demo)
```
1 EC2 (t3.medium)  →  Kafka + Controller + Prometheus
2-3 EC2 (t3.small) →  Workers
```

### Option B — Production
```
Amazon MSK          →  Kafka (managed)
EC2 Auto Scaling    →  Workers
EC2 (t3.medium)     →  Controller + Prometheus
Amazon Managed Grafana (optional)
```

---

### Step-by-step AWS Setup

#### 1. Create IAM Role for the controller EC2

In AWS Console → IAM → Roles → Create Role:

- **Trusted entity**: EC2
- **Policy**: attach a custom inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    }
  ]
}
```
- **Role name**: `tadr-ec2-role`

Attach this role to the **controller EC2 instance** (not worker instances).

---

#### 2. Create Security Group

In EC2 → Security Groups → Create:

| Type       | Protocol | Port  | Source        | Purpose              |
|------------|----------|-------|---------------|----------------------|
| Custom TCP | TCP      | 9092  | VPC CIDR      | Kafka broker         |
| Custom TCP | TCP      | 8000  | VPC CIDR      | Prometheus exporter  |
| Custom TCP | TCP      | 3000  | Your IP       | Grafana UI           |
| Custom TCP | TCP      | 9090  | Your IP       | Prometheus UI        |
| SSH        | TCP      | 22    | Your IP       | Management           |

**Security Group name**: `tadr-sg`

---

#### 3. Launch Controller EC2

```bash
# From AWS Console or CLI:
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type t3.medium \
  --key-name YOUR_KEY_NAME \
  --security-group-ids sg-XXXXXXXXX \
  --subnet-id subnet-XXXXXXXXX \
  --iam-instance-profile Name=tadr-ec2-role \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=tadr-controller}]'
```

SSH in and set up:
```bash
ssh -i your-key.pem ec2-user@<controller-public-ip>

sudo yum update -y
sudo yum install -y python3 python3-pip docker git
sudo systemctl start docker
sudo usermod -aG docker ec2-user

# Re-login for docker group
exit && ssh -i your-key.pem ec2-user@<controller-public-ip>

# Clone project
git clone https://github.com/YOUR_ORG/tadr-system.git
cd tadr-system

pip3 install -r requirements.txt

# Start Kafka + Prometheus + Grafana
docker-compose up -d

# Create topics
bash kafka/topics.sh

# Copy your trained models
scp -i your-key.pem models/*.pkl ec2-user@<controller-ip>:~/tadr-system/models/

# Start controller
nohup python3 controller/main.py > logs/controller.log 2>&1 &
```

---

#### 4. Update config.py for AWS

Edit `config/config.py`:
```python
KAFKA_BOOTSTRAP    = "<controller-private-ip>:9092"   # private IP
EC2_AMI_ID         = "ami-0c02fb55956c7d316"           # Amazon Linux 2, us-east-1
EC2_INSTANCE_TYPE  = "t3.medium"
EC2_KEY_NAME       = "your-key-pair-name"
EC2_SECURITY_GROUP = "sg-XXXXXXXXXXXXXXXXX"            # from step 2
EC2_SUBNET_ID      = "subnet-XXXXXXXXXXXXXXXXX"
```

---

#### 5. Enable AWS mode in controller

```bash
export TADR_USE_AWS=true
python3 controller/main.py
```

When `SCALE_OUT` is triggered, the controller will call `boto3.ec2.run_instances()`
and launch a new worker that auto-bootstraps via the user-data script in `scaler.py`.

---

#### 6. Launch Worker EC2s (manual, for initial workers)

```bash
# On each worker EC2:
sudo yum install -y python3 git
pip3 install kafka-python numpy
git clone https://github.com/YOUR_ORG/tadr-system.git
cd tadr-system

python3 worker/producer.py --vm-id vm-1
```

Or use the same user-data script from `scaler.py` in your Launch Template.

---

## Configuration Reference

All values are in `config/config.py`:

| Parameter           | Default        | Description                                      |
|---------------------|----------------|--------------------------------------------------|
| `KAFKA_BOOTSTRAP`   | localhost:9092 | Kafka broker address                             |
| `PREDICTION_HORIZON`| 30             | Minutes ahead to predict temperature             |
| `CPU_TEMP_THRESHOLD`| 80.0 °C        | Above this → VM is "at risk"                     |
| `GPU_TEMP_THRESHOLD`| 82.5 °C        | GPU threshold (mid 80–85 band)                   |
| `CONFIDENCE_MIN`    | 0.60           | Minimum confidence to act on prediction          |
| `VELOCITY_SCHEDULE` | 0.5 °C/min     | Rising fast enough → schedule tasks away         |
| `VELOCITY_SCALE`    | 1.2 °C/min     | Rising very fast → scale out                     |
| `CPU_CAPACITY_MAX`  | 85.0 %         | CPU % hard cap for task assignment               |
| `SCALE_COOLDOWN`    | 60 sec         | Minimum seconds between scale-out events         |
| `EMIT_INTERVAL_SEC` | 5              | Seconds between metric emissions per worker      |
| `AWS_REGION`        | us-east-1      | AWS region for EC2 operations                    |
| `PROMETHEUS_PORT`   | 8000           | Port for Prometheus scraping                     |

---

## What You See in the Demo

```
Tasks arrive → Kafka task-queue
VMs emit metrics → Kafka vm-metrics
Controller predicts temp at t+30 min
  ↓
If velocity rising + confident:
  → Scheduler moves tasks to coolest VM
  → Grafana shows cpu redistribution
  ↓
If all VMs hot + high velocity:
  → New VM spawned (simulated or EC2)
  → VM count gauge increments
  → Queue drains as new VM absorbs tasks
```

Grafana panels show in real-time:
- `temp ↑` per VM (current + predicted dashed line)
- `confidence` band per VM
- `velocity` trend lines with threshold markers
- `queue depth` draining after scheduling
- `VM count` incrementing on scale-out
