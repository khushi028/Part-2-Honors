# ─────────────────────────────────────────────
#  TADR System — Central Configuration
# ─────────────────────────────────────────────

# ── Kafka ──────────────────────────────────────
KAFKA_BOOTSTRAP = "localhost:9092"
TOPIC_VM_METRICS = "vm-metrics"
TOPIC_TASK_QUEUE = "task-queue"
KAFKA_GROUP_ID   = "tadr-controller"

# ── Prediction ─────────────────────────────────
PREDICTION_HORIZON = 30          # minutes ahead to predict
N_ESTIMATORS       = 10          # ensemble size (RandomForest trees used for variance)
CPU_MODEL_PATH     = "models/streaming_model_cpu.pkl"
GPU_MODEL_PATH     = "models/streaming_model_gpu.pkl"

# ── Decision thresholds ────────────────────────
CPU_TEMP_THRESHOLD  = 80.0       # °C  — triggers scheduling/scaling
GPU_TEMP_THRESHOLD  = 82.5       # °C  — mid-point of 80-85 band
CONFIDENCE_MIN      = 0.60       # below this → do not trust prediction
VELOCITY_SCHEDULE   = 0.5        # °C/min — rising trend → schedule tasks away
VELOCITY_SCALE      = 1.2        # °C/min — fast rise → scale out
CPU_CAPACITY_MAX    = 85.0       # % — hard cap before considering a VM "full"

# ── Scaler ─────────────────────────────────────
AWS_REGION          = "us-east-1"
EC2_AMI_ID          = "ami-0c02fb55956c7d316"   # Amazon Linux 2 (us-east-1)
EC2_INSTANCE_TYPE   = "t3.medium"
EC2_KEY_NAME        = "tadr-key"                 # your EC2 key pair name
EC2_SECURITY_GROUP  = "sg-0f5cf1a50a36d2afd"     # replace with your SG id
EC2_SUBNET_ID       = "subnet-xxxxxxxxxxxxxxxxx" # replace with your subnet id
EC2_TAG_NAME        = "tadr-worker"

# ── Monitoring ─────────────────────────────────
PROMETHEUS_PORT     = 8000

# ── Simulator ──────────────────────────────────
EMIT_INTERVAL_SEC   = 5          # seconds between metric emissions per worker
N_WORKERS           = 3          # number of simulated VMs (local mode)



# VPC_ID = "vpc-097f5716ca8c001de"
# SUBNET_ID = "subnet-070ea47ef51210651"
# SECURITY_GROUP = "sg-0f5cf1a50a36d2afd"

# IP =  103.215.237.5
# SSH RULE
# {
#     "Return": true,
#     "SecurityGroupRules": [
#         {
#             "SecurityGroupRuleId": "sgr-07e8861c380407430",
#             "GroupId": "sg-0f5cf1a50a36d2afd",
#             "GroupOwnerId": "844347864523",
#             "IsEgress": false,
#             "IpProtocol": "tcp",
#             "FromPort": 22,
#             "ToPort": 22,
#             "CidrIpv4": "103.215.237.5/32",
#             "SecurityGroupRuleArn": "arn:aws:ec2:us-east-1:844347864523:security-group-rule/sgr-07e8861c380407430"
#         }
#     ]
# }
# # Kafka
# {
#     "Return": true,
#     "SecurityGroupRules": [
#         {
#             "SecurityGroupRuleId": "sgr-049a74688e87d648c",
#             "GroupId": "sg-0f5cf1a50a36d2afd",
#             "GroupOwnerId": "844347864523",
#             "IsEgress": false,
#             "IpProtocol": "tcp",
#             "FromPort": 9092,
#             "ToPort": 9092,
#             "ReferencedGroupInfo": {
#                 "GroupId": "sg-0f5cf1a50a36d2afd",
#                 "UserId": "844347864523"
#             },
#             "SecurityGroupRuleArn": "arn:aws:ec2:us-east-1:844347864523:security-group-rule/sgr-049a74688e87d648c"
#         }
#     ]
# }
# # prom scraper
# {
#     "Return": true,
#     "SecurityGroupRules": [
#         {
#             "SecurityGroupRuleId": "sgr-04b91fe20d25f8797",
#             "GroupId": "sg-0f5cf1a50a36d2afd",
#             "GroupOwnerId": "844347864523",
#             "IsEgress": false,
#             "IpProtocol": "tcp",
#             "FromPort": 8000,
#             "ToPort": 8000,
#             "ReferencedGroupInfo": {
#                 "GroupId": "sg-0f5cf1a50a36d2afd",
#                 "UserId": "844347864523"
#             },
#             "SecurityGroupRuleArn": "arn:aws:ec2:us-east-1:844347864523:security-group-rule/sgr-04b91fe20d25f8797"
#         }
#     ]
# }
# # grafana
# {
#     "Return": true,
#     "SecurityGroupRules": [
#         {
#             "SecurityGroupRuleId": "sgr-0a25407dbcd2bf3d0",
#             "GroupId": "sg-0f5cf1a50a36d2afd",
#             "GroupOwnerId": "844347864523",
#             "IsEgress": false,
#             "IpProtocol": "tcp",
#             "FromPort": 3000,
#             "ToPort": 3000,
#             "CidrIpv4": "103.215.237.5/32",
#             "SecurityGroupRuleArn": "arn:aws:ec2:us-east-1:844347864523:security-group-rule/sgr-0a25407dbcd2bf3d0"
#         }
#     ]
# }

# # prom
# {
#     "Return": true,
#     "SecurityGroupRules": [
#         {
#             "SecurityGroupRuleId": "sgr-05b9ea2ce0eb37406",
#             "GroupId": "sg-0f5cf1a50a36d2afd",
#             "GroupOwnerId": "844347864523",
#             "IsEgress": false,
#             "IpProtocol": "tcp",
#             "FromPort": 9090,
#             "ToPort": 9090,
#             "CidrIpv4": "103.215.237.5/32",
#             "SecurityGroupRuleArn": "arn:aws:ec2:us-east-1:844347864523:security-group-rule/sgr-05b9ea2ce0eb37406"
#         }
#     ]
# }

# {
#     "Role": {
#         "Path": "/",
#         "RoleName": "tadr-ec2-role",
#         "RoleId": "AROA4JFYN6XF77Q4ZNMP7",
#         "Arn": "arn:aws:iam::844347864523:role/tadr-ec2-role",
#         "CreateDate": "2026-03-28T07:38:23+00:00",
#         "AssumeRolePolicyDocument": {
#             "Version": "2012-10-17",
#             "Statement": [
#                 {
#                     "Effect": "Allow",
#                     "Principal": {
#                         "Service": "ec2.amazonaws.com"
#                     },
#                     "Action": "sts:AssumeRole"
#                 }
#             ]
#         }
#     }
# }

# {
#     "InstanceProfile": {
#         "Path": "/",
#         "InstanceProfileName": "tadr-ec2-profile",
#         "InstanceProfileId": "AIPA4JFYN6XFUXJKLJPP7",
#         "Arn": "arn:aws:iam::844347864523:instance-profile/tadr-ec2-profile",
#         "CreateDate": "2026-03-28T07:39:56+00:00",
#         "Roles": []
#     }
# }

# ami-05024c2628f651b80

# instance id : i-0c907742df5109a57

# instance public, private ip : 44.222.128.198, 172.31.79.4

# i-0a5ec2e8b3deffa7c , 3.239.115.126