# Cloud POC - AWS CDK Architecture Documentation

## Executive Summary

This document describes the AWS infrastructure defined using AWS Cloud Development Kit (CDK) for the Cloud POC project. The infrastructure is organized into multiple CDK stacks, each responsible for a specific aspect of the overall architecture. The project includes both CDK-managed infrastructure and SAM-deployed Lambda functions that work together to provide a serverless Chef assistant API.

## System Context

The Cloud POC infrastructure provisions a serverless application environment on AWS, including networking, storage, container registry, secrets management, Step Functions orchestration, API Gateway, and AWS Lambda functions. The architecture follows AWS best practices for security, scalability, and operational excellence.

![Cloud POC Architecture](cloud-poc-architecture.svg)

## Architecture Overview

The infrastructure is organized into seven CDK stacks and two SAM-deployed Lambda functions:

### Active CDK Stacks (Currently Deployed)

1. **CloudPocNetworkStack**: Provides VPC networking infrastructure
2. **CloudPocStorageStack**: Provisions encrypted S3 bucket storage
3. **CloudPocClusterStack**: Creates ECS Fargate cluster (infrastructure ready)
4. **CloudPocRegistryStack**: Creates ECR repositories for container images
5. **CloudPocSecretsStack**: Manages application secrets via AWS Secrets Manager
6. **CloudPocOrchestrationStack**: Provisions Step Functions state machine for workflow orchestration
7. **CloudPocApiStack**: Provides API Gateway for HTTP access to Step Functions

### SAM-Deployed Lambda Functions

1. **ChefApp Lambda**: Mock chef agent that provides dish suggestions
2. **OFFAPI Lambda**: Invokes Open Food Facts API to retrieve nutritional information

### Inactive Stacks (Defined but Commented Out)

8. **CloudPocEcsStack**: Deploys Chef UI as an ECS Fargate service (infrastructure ready but not deployed)

The architecture diagram above illustrates all components, with active stacks highlighted in green and inactive (commented-out) stacks shown in gray with dashed borders.

## Component Architecture

### 1. Network Stack (CloudPocNetworkStack) - **ACTIVE**

**Purpose**: Provides the foundational networking infrastructure for the application.

**Components**:
- **VPC**: 10.0.0.0/27 CIDR block (smallest AWS-allowed VPC, 32 IPs)
- **Public Subnets**: Two /28 subnets across two Availability Zones (16 IPs each)
  - Subnet 1: AZ-1
  - Subnet 2: AZ-2
- **Internet Gateway**: Enables internet connectivity for public subnets
- **Security Group**: `chef-ui-sg` - Controls inbound/outbound traffic

**Design Decisions**:
- **Smallest possible VPC** (/27): Optimized for cost and simplicity; sufficient for POC workload
- **Public subnets only**: No NAT Gateway (~$35/month cost savings) since the application is internet-facing
- **Multi-AZ deployment**: Two availability zones for high availability
- **Internet Gateway**: Automatically provisioned by CDK for public subnet internet access
- **Security rules driven by configuration**: All firewall rules defined in `network_config.py`

**Key Configuration** (from `config/network_config.py`):
```python
vpc_cidr: "10.0.0.0/27"
max_azs: 2
nat_gateways: 0  # No NAT Gateway needed
```

### 2. Storage Stack (CloudPocStorageStack) - **ACTIVE**

**Purpose**: Provides secure, encrypted object storage for the application.

**Components**:
- **S3 Bucket**: Private, encrypted bucket with SSE-S3 (AES-256) encryption

**Design Decisions**:
- **No explicit bucket name**: CDK generates unique name to prevent collisions
- **SSE-S3 encryption**: AWS-managed keys for data at rest
- **Private access**: BlockPublicAccess.BLOCK_ALL + BUCKET_OWNER_ENFORCED
- **SSL enforcement**: Bucket policy denies non-HTTPS requests (S3.5 AWS security best practice)
- **No versioning**: Disabled per requirements
- **No lifecycle rules**: Intentionally omitted

**Security Features**:
- Encryption at rest (SSE-S3)
- Block all public access
- Enforce SSL/TLS for all requests
- Bucket owner enforced object ownership

### 3. Cluster Stack (CloudPocClusterStack) - **ACTIVE**

**Purpose**: Provides ECS Fargate cluster infrastructure (ready for future ECS services).

**Components**:
- **ECS Fargate Cluster**: Serverless container orchestration platform

**Design Decisions**:
- **Fargate serverless**: No EC2 instances to manage
- **Infrastructure ready**: Cluster created but no services deployed yet
- **Future ready**: Prepared for Chef UI ECS service deployment

### 4. Registry Stack (CloudPocRegistryStack) - **ACTIVE**

**Purpose**: Hosts Docker container images for the application components.

**Components**:
- **ECR Registry** containing four repositories:
  - `chef-ui`: Chef UI Chainlit application
  - `chef-agent`: Chef agent service
  - `nutritionist-agent`: Nutritionist agent service
  - `instructor-agent`: Instructor agent service

**Design Decisions**:
- **Explicit repository names**: Required for IAM policies and resource references
- **Tag immutability**: Prevents overwrite of existing tags (security best practice)
- **Image scan on push**: Automatic CVE scanning at no extra cost
- **Lifecycle policy**: Untagged images expire after 1 day (cleanup)
- **RETAIN removal policy**: Prevents accidental image loss on stack deletion

**Security Features**:
- Private repositories (no public access)
- Image scanning on push
- Tag immutability enabled
- Automatic lifecycle management

### 5. Secrets Stack (CloudPocSecretsStack) - **ACTIVE**

**Purpose**: Manages application credentials and secrets securely.

**Components**:
- **Secrets Manager Secret**: `chef-ui-login-passwords` for Chainlit authentication
  - Stores: CHAINLIT_AUTH_SECRET, CHEF_UI_USER, CHEF_UI_PASSWORD

**Design Decisions**:
- **Separate stack**: Secrets have RETAIN policy to prevent accidental deletion
- **Resource policy**: Grants ECS task execution role read access
- **Manual population**: Secret created empty; values populated post-deployment
- **RETAIN removal policy**: Credentials never destroyed on stack teardown

**Security Features**:
- AWS Secrets Manager encryption
- Resource-based access policy
- Retain on deletion

### 6. Orchestration Stack (CloudPocOrchestrationStack) - **ACTIVE**

**Purpose**: Provides workflow orchestration using AWS Step Functions that coordinates Lambda function invocations.

**Components**:
- **Step Functions State Machine**: "HelloWorldStateMachine" workflow
  - Invokes ChefApp Lambda function first
  - Conditionally checks response for "sugerencias" field
  - If present: Returns suggestions directly
  - If not present: Invokes OFFAPI Lambda function for nutritional data
- **CloudWatch Log Group**: State machine execution logs (7-day retention)
- **IAM Execution Role**: Permissions for CloudWatch Logs, X-Ray, and Lambda invocation

**Workflow Logic**:
1. **InvokeChefLambda**: Calls ChefApp Lambda with user input
2. **CheckSuggestions**: Validates if response contains "sugerencias" field
3. **ReturnSuggestions**: Returns Chef suggestions if present (success path)
4. **InvokeNextLambda**: Calls OFFAPI Lambda with Chef response (alternative path)
5. **ReturnFinalResult**: Returns nutritional information from OFFAPI

**Design Decisions**:
- **ASL JSON definition**: Workflow defined in `config/step_functions/hello_world_workflow.asl.json`
- **Dynamic ARN substitution**: Lambda ARNs injected at deployment via `definition_substitutions`
- **X-Ray tracing**: Enabled for distributed tracing
- **CloudWatch logging**: ALL level with execution data included
- **Retry logic**: 3 attempts with exponential backoff for Lambda invocations
- **Error handling**: Catch blocks for graceful failure handling

**Lambda Function Integration**:
- **ChefApp Lambda**: `CloudCorePocChefAppStack-ChefApp`
- **OFFAPI Lambda**: `CloudPocOpenFoodFactsAPIStack-OFFAPICaller`

**Current Status**: Fully active and integrated with API Gateway

### 7. API Stack (CloudPocApiStack) - **ACTIVE**

**Purpose**: Provides public REST API for invoking the Step Functions workflow via HTTP.

**Components**:
- **REST API Gateway**: `CloudPocChefApi`
  - **Endpoint**: `/chef` (POST method)
  - **Stage**: `prod`
  - **Authentication**: API Key required
- **API Key**: `CloudPocChefApiKey`
- **Usage Plan**: Rate limiting and throttling configuration
- **IAM Role**: Grants API Gateway permission to start Step Functions executions
- **CloudWatch Log Group**: `/aws/apigateway/CloudPocChefApi` (7-day retention)

**Design Decisions**:
- **REST API**: Classic REST API (not HTTP API) for Step Functions integration features
- **API Key authentication**: Simple authentication mechanism for POC
- **Direct Step Functions integration**: Uses AWS Service integration (no Lambda proxy)
- **X-Ray tracing enabled**: Full distributed tracing across API → Step Functions → Lambda
- **CloudWatch logging**: INFO level with access logs in JSON format
- **Throttling**: 10 requests/second rate limit, 20 burst limit
- **CORS enabled**: Allow requests from all origins for development flexibility

**Integration Details**:
- **Request transformation**: Wraps incoming JSON payload for Step Functions
- **Response transformation**: Returns execution ARN and start date
- **Error handling**: Maps 4xx and 5xx errors with appropriate messages

**Security Features**:
- API Key required for all requests
- Usage plan with rate limiting
- CloudWatch role automatically created
- IAM least-privilege for Step Functions invocation

**Current Status**: Fully active and publicly accessible

## SAM-Deployed Lambda Functions

### ChefApp Lambda (SAM Stack: AgentCorePocChefAppStack)

**Purpose**: Mock chef agent that provides dish suggestions based on user input.

**Configuration**:
- **Runtime**: Python 3.12 (ARM64 architecture)
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Function Name**: `CloudCorePocChefAppStack-ChefApp`

**Functionality**:
- Accepts input with "plato" field
- Returns three dish suggestions
- Response includes "sugerencias" array

**Input Format**:
```json
{
  "input": "Sugiereme un plato para cenar esta noche, por favor..."
}
```

**Output Format**:
```json
{
  "statusCode": 200,
  "body": {
    "plato": {...},
    "sugerencias": [
      "Ensalada César con pollo a la parrilla",
      "Pasta al pesto con tomates cherry",
      "Salmón al horno con espárragos"
    ]
  }
}
```

**Resources**:
- Lambda Layer: `chefapp-common-dependencies` (aws-lambda-powertools, pydantic)
- IAM Role: With CloudWatch Logs and X-Ray permissions
- CloudWatch Log Group: 7-day retention

### OFFAPI Lambda (SAM Stack: AgentCorePocOpenFoodFactsAPIStack)

**Purpose**: Queries Open Food Facts API to retrieve nutritional information for food products.

**Configuration**:
- **Runtime**: Python 3.12 (ARM64 architecture)
- **Memory**: 256 MB
- **Timeout**: 30 seconds
- **Function Name**: `CloudPocOpenFoodFactsAPIStack-OFFAPICaller`

**Functionality**:
- Accepts product names list and limit parameter
- Calls Open Food Facts API (staging environment)
- Returns nutritional data including calories, fat, sugars, etc.

**Input Format** (from Step Functions):
```json
{
  "product_names": ["leche"],
  "limit": 3
}
```

**Output Format**:
```json
{
  "statusCode": 200,
  "body": {
    "leche": {
      "products": [
        {
          "name": "Leche Entera",
          "brand": "Marca",
          "calories_100g": 65,
          "nutriments": {...}
        }
      ]
    }
  }
}
```

**Resources**:
- Lambda Layer: `common-dependencies` (requests, pydantic, aws-lambda-powertools)
- IAM Role: With CloudWatch Logs and X-Ray permissions
- CloudWatch Log Group: 7-day retention
- Environment Variables: OFF_PROD_URL, OFF_STAGING_URL

### 8. ECS Stack (CloudPocEcsStack) - **COMMENTED OUT**

### 8. ECS Stack (CloudPocEcsStack) - **COMMENTED OUT**

**Purpose**: Runs the Chef UI Chainlit application as a containerized service.

**Components**:
- **ECS Fargate Cluster**: Serverless compute platform (already provisioned by ClusterStack)
- **ECS Service**: Chef UI service with the following specifications:
  - **Platform**: ARM64 architecture
  - **Resources**: 0.5 vCPU (512 CPU units), 2 GB RAM
  - **Desired Count**: 1 task
  - **Network**: Public subnet with public IP assignment
  - **Container Port**: 8080
- **CloudWatch Log Group**: `/aws/ecs/chef-ui` (7-day retention)
- **IAM Task Role**: `chef-ui-task-role` with Step Functions permissions
- **IAM Task Execution Role**: Reuses existing `ecsTaskExecutionRole`

**Design Decisions**:
- **Fargate serverless**: No EC2 instances to manage
- **ARM64 architecture**: ~20% better price/performance than x86_64
- **Public subnet + public IP**: Required for internet access without NAT Gateway
- **Reuse existing execution role**: Avoids IAM duplication
- **No load balancer**: Single task sufficient for POC (ALB can be added later)
- **Step Functions integration**: Task role allows starting and monitoring state machine executions

**Current Status**: Defined in code but commented out in `app.py` (lines 86-97)

**Dependencies**:
- NetworkStack (VPC, Security Group)
- ClusterStack (ECS Cluster)
- RegistryStack (chef-ui ECR repository)
- SecretsStack (Chainlit credentials)
- OrchestrationStack (Step Functions ARN)

## Deployment Architecture

### Current Active Infrastructure

The currently active infrastructure consists of:

```
Internet Users
    ↓
API Gateway (/chef endpoint)
    ↓ (requires API Key)
Step Functions State Machine
    ↓
┌─────────────────────┬─────────────────────┐
│                     │                     │
│   ChefApp Lambda    │   OFFAPI Lambda     │
│   (provides dishes) │   (nutritional data)│
└─────────────────────┴─────────────────────┘

Supporting Infrastructure:
├─ VPC (10.0.0.0/27)
│  ├─ Internet Gateway
│  ├─ Public Subnet 1 (AZ-1)
│  ├─ Public Subnet 2 (AZ-2)
│  └─ Security Group
├─ S3 Bucket (encrypted, private)
├─ ECS Cluster (ready, no services)
├─ ECR Registry
│  ├─ chef-ui repository
│  ├─ chef-agent repository
│  ├─ nutritionist-agent repository
│  └─ instructor-agent repository
└─ Secrets Manager
   └─ chef-ui-login-passwords
```

### API Request Flow

1. **User Request**: Client sends POST request to API Gateway `/chef` endpoint with API key
2. **API Gateway**: Validates API key, starts Step Functions execution
3. **Step Functions**: Orchestrates workflow:
   - Invokes ChefApp Lambda with user input
   - Checks response for "sugerencias" field
   - If suggestions exist: Returns them
   - If not: Invokes OFFAPI Lambda for nutritional data
4. **Response**: API Gateway returns execution details to client

### Data Flow

**Scenario 1: Chef Suggestions Found**
```
User → API Gateway → Step Functions → ChefApp Lambda → Step Functions → API Gateway → User
                                       (returns suggestions)
```

**Scenario 2: Nutritional Data Needed**
```
User → API Gateway → Step Functions → ChefApp Lambda → Step Functions → OFFAPI Lambda → Step Functions → API Gateway → User
                                       (no suggestions)      (calls Open Food Facts API)
```

## Deployment Instructions

### Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **AWS CDK** installed (`npm install -g aws-cdk`)
3. **AWS SAM CLI** installed
4. **Python 3.12+** for Lambda development
5. **Docker** for SAM builds

### Deployment Order

#### Phase 1: Deploy Lambda Functions (SAM)

1. **Deploy ChefApp Lambda**:
```bash
cd lambdas/ChefApp
sam build
sam deploy --guided
# Stack name: AgentCorePocChefAppStack
```

2. **Deploy OFFAPI Lambda**:
```bash
cd lambdas/OFFAPI
sam build
sam deploy --guided
# Stack name: AgentCorePocOpenFoodFactsAPIStack
```

#### Phase 2: Deploy CDK Infrastructure

Update Lambda function names in `aws-infra/config/orchestration_config.py` if needed, then:

```bash
cd aws-infra
cdk bootstrap  # First time only
cdk deploy --all
```

This deploys all active stacks:
- CloudPocNetworkStack
- CloudPocStorageStack
- CloudPocClusterStack
- CloudPocRegistryStack
- CloudPocSecretsStack
- CloudPocOrchestrationStack (references Lambda ARNs)
- CloudPocApiStack

#### Phase 3: Retrieve API Key

```bash
aws apigateway get-api-keys --include-values \
  --query "items[?name=='CloudPocChefApiKey'].value" --output text
```

### Testing the API

```bash
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/chef \
  -H "x-api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"input": "Sugiereme un plato para cenar esta noche"}'
```

Response:
```json
{
  "executionArn": "arn:aws:states:...",
  "startDate": "2026-05-08T..."
}
```

## Non-Functional Requirements Analysis

### Scalability

**Current Architecture**:
- **API Gateway**: Automatically scales to handle request volume (throttled at 10 req/s)
- **Step Functions**: Scales automatically, supports up to 5,000 concurrent executions per account
- **Lambda Functions**: Auto-scales to handle concurrent invocations (default: 1,000 concurrent)
- **VPC**: Sufficient IP space for current workload; can be expanded if needed

**Scalability Enhancements** (if ECS stack is enabled):
- ECS Service can scale horizontally with auto-scaling policies
- Application Load Balancer can distribute traffic across multiple tasks

### Performance

**Latency Characteristics**:
- API Gateway: ~50ms overhead
- Step Functions: ~100ms per state transition
- ChefApp Lambda: ~200ms cold start, ~50ms warm
- OFFAPI Lambda: ~300ms cold start + external API call time (~500-1000ms)
- Total end-to-end: 1-2 seconds typical

**Optimizations**:
- ARM64 architecture for Lambda (faster execution)
- Lambda layers for shared dependencies
- Provisioned concurrency can eliminate cold starts (additional cost)

### Security

**Implemented Security Controls**:
- **API Authentication**: API Key required for all API Gateway requests
- **Network Isolation**: VPC with security groups
- **Encryption at Rest**: S3 bucket with SSE-S3, Secrets Manager
- **Encryption in Transit**: HTTPS enforced on API Gateway and S3
- **Least Privilege IAM**: Each service has minimal required permissions
- **X-Ray Tracing**: Enabled for security audit trails
- **CloudWatch Logging**: All services log to CloudWatch for monitoring
- **ECR Image Scanning**: Automatic vulnerability scanning on push
- **Private ECR**: Container images not publicly accessible

**Additional Security Recommendations**:
- Implement AWS WAF on API Gateway
- Enable GuardDuty for threat detection
- Use AWS Secrets Manager rotation for credentials
- Implement VPC endpoints for private AWS service access
- Enable CloudTrail for API audit logging

### Reliability

**High Availability**:
- Multi-AZ VPC deployment
- API Gateway: 99.95% SLA
- Lambda: 99.95% SLA
- Step Functions: 99.9% SLA
- S3: 99.99% availability

**Fault Tolerance**:
- Lambda retry logic: 3 attempts with exponential backoff
- Step Functions error handling with catch blocks
- API Gateway integration error mapping

**Monitoring & Observability**:
- X-Ray distributed tracing
- CloudWatch Logs (7-day retention)
- CloudWatch Metrics for all services
- Step Functions execution history

### Maintainability

**Infrastructure as Code**:
- CDK for infrastructure (TypeScript-like Python)
- SAM for Lambda functions
- Configuration externalized in config files
- Version controlled in Git

**Operational Excellence**:
- Separate stacks for isolation
- Stack outputs for easy reference
- Descriptive resource names
- Comprehensive documentation

### Cost Efficiency

**Monthly Cost Estimate** (assuming moderate usage):

| Service | Configuration | Estimated Cost |
|---------|--------------|----------------|
| API Gateway | 1M requests/month | $3.50 |
| Step Functions | 10K executions/month | $0.25 |
| Lambda (ChefApp) | 10K invocations, 256MB, 200ms avg | $0.40 |
| Lambda (OFFAPI) | 5K invocations, 256MB, 500ms avg | $0.25 |
| VPC | No NAT Gateway | $0.00 |
| S3 | 10GB storage, 1K requests | $0.23 |
| ECR | 5GB storage | $0.50 |
| CloudWatch Logs | 1GB ingestion, 7-day retention | $0.50 |
| Secrets Manager | 1 secret | $0.40 |
| **Total** | | **~$6.00/month** |

**Cost Optimization**:
- No NAT Gateway saves ~$35/month
- ARM64 Lambda ~20% cheaper than x86
- 7-day log retention reduces storage costs
- Serverless architecture: pay only for usage

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API Key exposure | High | Rotate keys regularly, implement AWS WAF, consider Cognito |
| Lambda cold starts | Medium | Use provisioned concurrency for critical paths |
| Step Functions throttling | Medium | Request service quota increase if needed |
| External API dependency (Open Food Facts) | Medium | Implement caching, fallback responses |
| No automated backups | Low | S3 versioning can be enabled if needed |
| Single region deployment | Medium | Multi-region can be added for DR |

## Technology Stack

**AWS Services**:
- API Gateway (REST API)
- AWS Step Functions (Standard Workflows)
- AWS Lambda (Python 3.12, ARM64)
- VPC, Internet Gateway, Security Groups
- S3 (SSE-S3 encryption)
- ECR (container registry)
- ECS Fargate (infrastructure ready)
- Secrets Manager
- CloudWatch (Logs, Metrics, X-Ray)

**Development Tools**:
- AWS CDK (Python)
- AWS SAM
- Python 3.12 (aws-lambda-powertools, pydantic, requests)
- Docker
- Git

## Next Steps

1. **Enable ECS Stack**: Uncomment EcsStack in `app.py` to deploy Chef UI
2. **Implement Caching**: Add ElastiCache or DynamoDB for API response caching
3. **Add Authentication**: Replace API Key with Amazon Cognito
4. **Monitoring Dashboard**: Create CloudWatch dashboard for metrics visualization
5. **CI/CD Pipeline**: Implement GitHub Actions for automated deployments
6. **Multi-Region**: Extend to multiple AWS regions for disaster recovery
7. **Load Testing**: Perform load testing to validate scalability assumptions

## References

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [AWS Step Functions Best Practices](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)
- [AWS Lambda Powertools](https://docs.powertools.aws.dev/lambda/python/)
- [Open Food Facts API](https://world.openfoodfacts.org/data)

When the commented-out stacks are activated, the complete architecture would be:

```
Internet Users
    ↓ HTTPS
Internet
    ↓
Internet Gateway
    ↓
Public Subnets (in VPC)
    ↓
ECS Fargate Service (Chef UI)
    ├─ Pulls images from ECR
    ├─ Reads secrets from Secrets Manager
    ├─ Sends logs to CloudWatch
    └─ Invokes Step Functions workflows
         ↓
    Step Functions State Machine
         └─ Sends logs to CloudWatch

CI/CD (GitHub Actions)
    └─ Pushes images to ECR
```

## Data Flow

### Current State (Active Stacks Only)

1. **CI/CD Pipeline** (GitHub Actions):
   - Builds Docker images
   - Pushes images to ECR repositories
   - Images are scanned for vulnerabilities on push

2. **Storage**:
   - S3 bucket available for application data storage
   - All access must use SSL/TLS

### Future State (With ECS and Orchestration Stacks)

1. **User Request Flow**:
   - Internet users → Internet Gateway → Public Subnet → ECS Fargate Task
   - ECS task serves Chef UI Chainlit application

2. **Application Startup**:
   - ECS task execution role pulls image from ECR
   - Task reads credentials from Secrets Manager
   - Task starts on assigned public IP

3. **Workflow Execution**:
   - Chef UI invokes Step Functions state machine
   - State machine executes workflow steps
   - Execution logs sent to CloudWatch

4. **Logging**:
   - ECS tasks → CloudWatch Logs (`/aws/ecs/chef-ui`)
   - Step Functions → CloudWatch Logs (state machine log group)

## Key Workflows

### Sequence: ECS Task Startup (When Enabled)

```
[GitHub Actions] → [ECR Repository]: Push Docker image
[ECS Service] → [ECR Repository]: Pull image
[ECS Service] → [Secrets Manager]: Read credentials
[ECS Service] → [Public Subnet]: Start task with public IP
[ECS Task] → [CloudWatch Logs]: Send application logs
```

### Sequence: Step Functions Invocation (When Enabled)

```
[Chef UI Task] → [Step Functions]: Start execution (with input)
[Step Functions] → [Workflow Steps]: Execute state machine
[Step Functions] → [CloudWatch Logs]: Log execution details
[Step Functions] → [Chef UI Task]: Return execution status
```

## Non-Functional Requirements Analysis

### Scalability

**Current Implementation**:
- Multi-AZ VPC provides foundation for horizontal scaling
- ECR supports unlimited image pulls
- S3 scales automatically

**When ECS Stack is Enabled**:
- ECS Fargate auto-scales tasks based on demand
- Stateless container design enables horizontal scaling
- Can add Application Load Balancer for multi-task distribution
- Step Functions supports high throughput (thousands of concurrent executions)

**Limitations**:
- Single ECS task (desired_count=1) is not highly available
- No auto-scaling policies defined
- VPC is small (/27) - only 32 IPs total

**Recommendations**:
- Increase desired task count to 2+ for HA
- Add Application Load Balancer
- Implement auto-scaling policies
- Consider larger VPC if more services are added

### Performance

**Network**:
- Multi-AZ deployment reduces latency for geographically distributed users
- Direct internet connectivity (no NAT Gateway) minimizes network hops
- Fargate networking (awsvpc mode) provides dedicated ENI per task

**Compute**:
- ARM64 architecture offers better price/performance
- 0.5 vCPU / 2GB RAM adequate for low-moderate load
- Fargate removes hypervisor overhead

**Optimization Opportunities**:
- Add CloudFront CDN for static assets
- Implement caching layer (ElastiCache)
- Use read replicas for database (if added)

### Security

**Network Security**:
- ✅ VPC isolation
- ✅ Security groups for traffic filtering
- ✅ Public subnets only (appropriate for internet-facing app)
- ❌ No WAF (AWS Web Application Firewall)
- ❌ No VPC Flow Logs

**Data Security**:
- ✅ S3 encryption at rest (SSE-S3)
- ✅ S3 SSL enforcement
- ✅ S3 block public access
- ✅ Secrets Manager for credentials
- ✅ ECR private repositories
- ✅ ECR image scanning

**IAM Security**:
- ✅ Least-privilege IAM roles
- ✅ Resource-based policies (Secrets Manager)
- ✅ Task execution role reuse (minimizes IAM surface)
- ✅ Explicit role permissions (no wildcards)

**Container Security**:
- ✅ Immutable image tags
- ✅ Automated CVE scanning
- ✅ Lifecycle policy removes untagged images

**Compliance**:
- Follows AWS Foundational Security Best Practices
- SSL/TLS enforced
- Encryption at rest enabled

**Security Gaps**:
- No AWS WAF for DDoS protection
- No GuardDuty threat detection
- No VPC Flow Logs
- No AWS Config for compliance monitoring
- Secrets created empty (must be manually populated)

### Reliability

**Current Design**:
- ✅ Multi-AZ VPC (spans 2 AZs)
- ✅ ECR lifecycle policy prevents storage exhaustion
- ✅ CloudWatch logging enabled
- ⚠️ Single ECS task (no redundancy when enabled)
- ❌ No health checks defined
- ❌ No auto-recovery mechanisms

**Availability**:
- **Current SLA**: N/A (no compute running)
- **With single ECS task**: ~99.5% (single point of failure)
- **With multi-task + ALB**: ~99.9% (recommended)

**Disaster Recovery**:
- **RTO (Recovery Time Objective)**: ~5-10 minutes (redeploy from IaC)
- **RPO (Recovery Point Objective)**: 0 (stateless application)
- **Backup Strategy**: 
  - S3 has RETAIN policy (survives stack deletion)
  - ECR has RETAIN policy (images preserved)
  - Secrets Manager has RETAIN policy
  - Infrastructure is code (can be redeployed)

**Recommendations**:
- Increase ECS desired count to 2+
- Add Application Load Balancer with health checks
- Enable CloudWatch alarms for critical metrics
- Implement automated rollback on deployment failures

### Maintainability

**Infrastructure as Code**:
- ✅ CDK provides type-safe, reusable constructs
- ✅ Configuration externalized in `config/` modules
- ✅ Clear separation of concerns (one stack per responsibility)
- ✅ Comprehensive inline documentation
- ✅ Cross-stack references managed by CDK

**Operational Visibility**:
- ✅ CloudWatch logging integrated
- ✅ X-Ray tracing enabled (Step Functions)
- ⚠️ No centralized dashboard
- ⚠️ No alerting configured

**Deployment**:
- CDK deployment via `cdk deploy`
- Environment-agnostic (configurable account/region)
- Global tags applied to all resources

**Code Organization**:
```
aws-infra/
├── app.py                  # CDK app entry point
├── stacks/                 # Stack definitions
│   ├── network_stack.py
│   ├── storage_stack.py
│   ├── registry_stack.py
│   ├── secrets_stack.py
│   ├── orchestration_stack.py
│   └── ecs_stack.py
└── config/                 # Configuration modules
    ├── network_config.py
    ├── s3_config.py
    ├── ecr_config.py
    ├── ecs_config.py
    └── orchestration_config.py
```

**Maintainability Strengths**:
- Clean separation between stacks
- Reusable configuration modules
- Self-documenting code
- Minimal hard-coded values

**Improvement Opportunities**:
- Add automated testing (CDK assertions)
- Implement CI/CD for infrastructure
- Create operational runbooks
- Add CloudWatch dashboards

## Phased Development

### Phase 1: Foundation (Current - ACTIVE)

**Objective**: Establish core infrastructure foundation.

**Deployed Components**:
- ✅ VPC with networking (NetworkStack)
- ✅ S3 storage (StorageStack)
- ✅ ECR repositories (RegistryStack)
- ✅ Secrets management (SecretsStack)

**Status**: Fully deployed and operational

**Benefits**:
- Infrastructure foundation ready
- CI/CD can push images to ECR
- Security and networking baseline established

### Phase 2: Application Runtime (Planned - COMMENTED OUT)

**Objective**: Deploy the Chef UI application and workflow orchestration.

**Components to Enable**:
- Uncomment OrchestrationStack (lines 57-62 in `app.py`)
- Uncomment EcsStack (lines 64-75 in `app.py`)
- Populate Secrets Manager secret with credentials

**Steps to Activate**:

1. **Populate Secrets**:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id chef-ui-login-passwords \
     --secret-string '{
       "CHAINLIT_AUTH_SECRET": "<generate-random-value>",
       "CHEF_UI_USER": "<username>",
       "CHEF_UI_PASSWORD": "<password>"
     }'
   ```

2. **Uncomment Stacks in app.py**:
   ```python
   orchestration_stack = OrchestrationStack(
       app,
       "CloudPocOrchestrationStack",
       env=env,
       description="Cloud POC — Hello World Step Functions workflow",
   )

   EcsStack(
       app,
       "CloudPocEcsStack",
       vpc=network_stack.vpc,
       security_group=network_stack.security_group,
       chef_ui_repository=registry_stack.repositories["chef-ui"],
       login_secret=secrets_stack.login_secret,
       state_machine_arn=orchestration_stack.state_machine.state_machine_arn,
       env=env,
       description="Cloud POC — Chef UI ECS Fargate service",
   )
   ```

3. **Deploy**:
   ```bash
   cdk deploy CloudPocOrchestrationStack CloudPocEcsStack
   ```

4. **Push Docker Image**:
   ```bash
   # Build and push chef-ui image
   docker build -t <account>.dkr.ecr.<region>.amazonaws.com/chef-ui:latest ./chef-ui
   docker push <account>.dkr.ecr.<region>.amazonaws.com/chef-ui:latest
   ```

**Outcome**: Fully functional Chef UI application accessible via public IP

### Migration Path

**Phase 1 → Phase 2 Migration**:
- No infrastructure changes required in Phase 1 stacks
- Phase 2 stacks reference Phase 1 resources via cross-stack references
- Zero downtime (no existing services to impact)
- Rollback: Simply delete Phase 2 stacks; Phase 1 remains intact

**Future Phases** (Potential):
- **Phase 3**: Add Application Load Balancer, increase task count, implement auto-scaling
- **Phase 4**: Add CloudFront CDN, WAF, Route 53 DNS
- **Phase 5**: Add database layer, caching, monitoring/alerting

## Risks and Mitigations

### Risk 1: Single Point of Failure (ECS Task)

**Risk Level**: High  
**Impact**: Application unavailability during task failures  
**Probability**: Medium (Fargate is reliable, but failures happen)

**Mitigation**:
- Increase `desired_count` to 2 or more
- Add Application Load Balancer with health checks
- Implement auto-scaling policies
- Enable ECS Circuit Breaker for deployment protection

### Risk 2: Small VPC Address Space

**Risk Level**: Medium  
**Impact**: Unable to add more resources if VPC runs out of IPs  
**Probability**: Low (sufficient for POC, but limiting for growth)

**Mitigation**:
- Current /27 VPC provides 32 IPs (sufficient for POC)
- Monitor IP utilization
- Plan VPC expansion or secondary VPC if more services needed
- Each Fargate task uses 1 IP per subnet

### Risk 3: No Secrets Rotation

**Risk Level**: Medium  
**Impact**: Stale credentials increase security risk  
**Probability**: High (no rotation configured)

**Mitigation**:
- Enable AWS Secrets Manager automatic rotation
- Implement periodic manual rotation policy
- Use short-lived tokens where possible

### Risk 4: No Cost Controls

**Risk Level**: Medium  
**Impact**: Unexpected AWS costs  
**Probability**: Medium (no billing alarms or budgets)

**Mitigation**:
- Set AWS Budgets with alerts
- Implement CloudWatch billing alarms
- Add cost allocation tags (already applied globally)
- Monitor Cost Explorer regularly
- Use Fargate Spot for non-production workloads

### Risk 5: No Disaster Recovery Plan

**Risk Level**: Low  
**Impact**: Extended recovery time during major incidents  
**Probability**: Low (AWS region failures are rare)

**Mitigation**:
- Document recovery procedures
- Maintain infrastructure as code (CDK)
- Test stack redeployment regularly
- Consider multi-region deployment for critical workloads
- Ensure S3, ECR, and Secrets have RETAIN policy

### Risk 6: Manual Secret Population

**Risk Level**: Low  
**Impact**: Deployment incomplete without manual step  
**Probability**: High (current design requires manual secret setup)

**Mitigation**:
- Document secret population in deployment guide
- Implement automated secret creation in CI/CD
- Use AWS CDK Custom Resources for secret initialization
- Add validation checks before deploying ECS stack

### Risk 7: No Monitoring/Alerting

**Risk Level**: High  
**Impact**: Undetected issues, delayed incident response  
**Probability**: High (no alarms configured)

**Mitigation**:
- Create CloudWatch dashboards for key metrics
- Implement CloudWatch alarms for:
  - ECS task health
  - Step Functions execution failures
  - High error rates
  - Resource utilization
- Set up SNS topics for alert notifications
- Integrate with incident management system

## Technology Stack Recommendations

### Current Stack

| Component | Technology | Version/Config | Justification |
|-----------|-----------|----------------|---------------|
| IaC Framework | AWS CDK | Python 3.x | Type-safe, reusable constructs; superior to CloudFormation templates |
| Networking | Amazon VPC | /27 CIDR, 2 AZs | Cost-optimized, multi-AZ for availability |
| Storage | Amazon S3 | SSE-S3 encryption | Fully managed, scalable object storage |
| Container Registry | Amazon ECR | Private, scan-on-push | Native AWS integration, built-in security scanning |
| Secrets Management | AWS Secrets Manager | RETAIN policy | Secure credential storage, AWS service integration |
| Compute (inactive) | AWS Fargate | ARM64, 0.5 vCPU, 2GB | Serverless, no infrastructure management |
| Orchestration (inactive) | AWS Step Functions | ASL JSON | Managed workflow engine, visual monitoring |

### Recommendations for Phase 2

| Component | Recommended Technology | Justification |
|-----------|----------------------|---------------|
| Load Balancing | Application Load Balancer | Layer 7 routing, health checks, SSL termination |
| DNS | Amazon Route 53 | AWS-native DNS, health checks, routing policies |
| CDN | Amazon CloudFront | Global edge caching, DDoS protection |
| WAF | AWS WAF | Application-level firewall, rate limiting |
| Monitoring | CloudWatch + X-Ray | Native AWS integration, distributed tracing |
| Alerting | CloudWatch Alarms + SNS | Real-time alerting, multi-channel notifications |

### Recommendations for Future Phases

| Component | Recommended Technology | Use Case |
|-----------|----------------------|----------|
| Database | Amazon RDS (PostgreSQL) or Aurora Serverless | Persistent data storage |
| Caching | Amazon ElastiCache (Redis) | Session management, API response caching |
| Queue | Amazon SQS | Asynchronous task processing |
| Service Mesh | AWS App Mesh | Microservices communication, observability |
| CI/CD | GitHub Actions + AWS CodePipeline | Automated deployment pipeline |

## Cost Estimate

### Current Monthly Costs (Phase 1 - Active Stacks Only)

| Service | Component | Estimated Cost |
|---------|-----------|----------------|
| VPC | 2 public subnets, IGW | **Free** (no data transfer) |
| S3 | Standard storage (assuming 10 GB) | **$0.23/month** (at $0.023/GB) |
| ECR | 4 repositories, 10 GB storage | **$1.00/month** (at $0.10/GB) |
| Secrets Manager | 1 secret | **$0.40/month** (at $0.40/secret) |
| **Total Phase 1** | | **~$1.63/month** |

### Projected Monthly Costs (Phase 2 - All Stacks Enabled)

| Service | Component | Estimated Cost |
|---------|-----------|----------------|
| VPC | (same as Phase 1) | **Free** |
| S3 | (same as Phase 1) | **$0.23/month** |
| ECR | (same as Phase 1) | **$1.00/month** |
| Secrets Manager | (same as Phase 1) | **$0.40/month** |
| ECS Fargate | 1 task, 0.5 vCPU, 2 GB RAM, ARM64 | **~$10.80/month** * |
| Step Functions | 1,000 state transitions/month | **$0.025/month** (first 4,000 free) |
| CloudWatch Logs | 2 log groups, 1 GB ingestion | **$0.50/month** |
| Data Transfer | 10 GB outbound (IGW) | **$0.90/month** (at $0.09/GB) |
| **Total Phase 2** | | **~$13.90/month** |

**Cost Calculation Notes**:
- *Fargate cost: (0.5 vCPU × $0.03238/hour + 2 GB × $0.00356/hour) × 730 hours/month
- Fargate ARM64 is ~20% cheaper than x86_64
- Assumes single task running continuously
- Does not include NAT Gateway (~$32.40/month) - not used
- Costs based on us-east-1 region pricing (May 2026)
- Free tier benefits not included (may reduce actual costs)

### Cost Optimization Opportunities

1. **Use Fargate Spot** (non-production):
   - Up to 70% cost reduction
   - Suitable for dev/test environments
   - Not recommended for production (task interruption possible)

2. **Right-size resources**:
   - Monitor actual CPU/memory usage
   - Adjust task sizing if over-provisioned
   - Current 0.5 vCPU / 2 GB is already minimal

3. **Implement auto-scaling**:
   - Scale to zero during off-hours (dev environments)
   - Scale based on actual demand

4. **ECR lifecycle policies**:
   - Already implemented (untagged images deleted after 1 day)
   - Consider pruning old tagged images (e.g., keep last 10)

5. **CloudWatch Logs retention**:
   - Already set to 7 days (cost-optimized)
   - Archive older logs to S3 if needed ($0.03/GB vs $0.50/GB)

6. **S3 lifecycle policies**:
   - Transition infrequent access data to S3-IA
   - Use S3 Intelligent-Tiering for unknown patterns

### Total Cost of Ownership (TCO)

| Phase | Monthly Cost | Annual Cost | Notes |
|-------|--------------|-------------|-------|
| Phase 1 (Current) | ~$1.63 | ~$19.56 | Infrastructure foundation only |
| Phase 2 (with ECS) | ~$13.90 | ~$166.80 | Single-task deployment |
| Phase 3 (with HA) | ~$30-35 | ~$360-420 | Multi-task + ALB + monitoring |
| Production (scaled) | ~$50-100+ | ~$600-1200+ | Auto-scaling, multi-AZ, observability |

**Note**: All costs are estimates based on AWS pricing as of May 2026 and assume typical usage patterns. Actual costs may vary based on traffic, data transfer, and scaling behavior.

## Next Steps

### Immediate Actions (Phase 1 - Completed)

- ✅ Deploy NetworkStack
- ✅ Deploy StorageStack
- ✅ Deploy RegistryStack
- ✅ Deploy SecretsStack

### Short-term Actions (Phase 2 - To Activate Application)

1. **Populate Secrets Manager Secret**:
   - Generate secure credentials
   - Use AWS CLI or Console to populate secret
   - Validate secret structure

2. **Build and Push Docker Image**:
   - Build chef-ui Docker image
   - Push to ECR repository
   - Tag as `latest` or specific version

3. **Uncomment and Deploy Application Stacks**:
   - Uncomment OrchestrationStack in `app.py`
   - Uncomment EcsStack in `app.py`
   - Run `cdk deploy --all` to deploy remaining stacks

4. **Verify Deployment**:
   - Check ECS task is running
   - Access Chef UI via public IP
   - Test Step Functions integration
   - Verify CloudWatch logs

### Medium-term Actions (Phase 3 - Enhance for Production)

1. **Add High Availability**:
   - Increase ECS desired count to 2+
   - Add Application Load Balancer
   - Implement health checks
   - Configure auto-scaling policies

2. **Implement Monitoring**:
   - Create CloudWatch dashboards
   - Configure CloudWatch alarms (task health, error rates, resource utilization)
   - Set up SNS notification topics
   - Integrate with incident management

3. **Enhance Security**:
   - Enable VPC Flow Logs
   - Add AWS WAF
   - Enable AWS GuardDuty
   - Implement AWS Config rules
   - Enable Secrets Manager rotation

4. **Optimize Costs**:
   - Set up AWS Budgets
   - Configure billing alarms
   - Review and optimize resource sizing
   - Implement cost allocation tags

### Long-term Actions (Phase 4+ - Scale and Mature)

1. **Add CDN and Global Distribution**:
   - Deploy Amazon CloudFront
   - Configure Route 53 DNS
   - Implement geo-routing

2. **Enhance Application Architecture**:
   - Add database layer (RDS/Aurora)
   - Implement caching (ElastiCache)
   - Add message queues (SQS)
   - Implement service mesh (App Mesh)

3. **Implement Infrastructure CI/CD**:
   - Automate CDK deployments via GitHub Actions
   - Add automated testing (CDK assertions)
   - Implement multi-environment strategy (dev/staging/prod)
   - Add infrastructure validation gates

4. **Disaster Recovery**:
   - Document and test DR procedures
   - Implement multi-region deployment
   - Set up automated backups
   - Create operational runbooks

## References

### AWS Services Used

- [Amazon VPC](https://aws.amazon.com/vpc/) - Virtual Private Cloud networking
- [Amazon S3](https://aws.amazon.com/s3/) - Object storage service
- [Amazon ECR](https://aws.amazon.com/ecr/) - Elastic Container Registry
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) - Secrets management service
- [Amazon ECS](https://aws.amazon.com/ecs/) - Elastic Container Service (Fargate)
- [AWS Step Functions](https://aws.amazon.com/step-functions/) - Workflow orchestration
- [Amazon CloudWatch](https://aws.amazon.com/cloudwatch/) - Monitoring and logging
- [AWS IAM](https://aws.amazon.com/iam/) - Identity and Access Management

### AWS CDK Documentation

- [AWS CDK Developer Guide](https://docs.aws.amazon.com/cdk/latest/guide/home.html)
- [AWS CDK Python API Reference](https://docs.aws.amazon.com/cdk/api/latest/python/index.html)
- [AWS CDK Best Practices](https://docs.aws.amazon.com/cdk/latest/guide/best-practices.html)

### AWS Well-Architected Framework

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html)
- [Performance Efficiency Pillar](https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html)
- [Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html)
- [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)

### AWS Architecture Patterns

- [ECS Fargate Reference Architecture](https://github.com/aws-samples/ecs-refarch-continuous-deployment)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)
- [Container Security Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/security.html)

### Project-Specific Documentation

- [CDK Application Entry Point](../aws-infra/app.py)
- [Network Configuration](../aws-infra/config/network_config.py)
- [ECS Configuration](../aws-infra/config/ecs_config.py)
- [Orchestration Configuration](../aws-infra/config/orchestration_config.py)

---

## Generate Architecture Diagram

To generate the SVG image from the D2 diagram, ensure D2 is installed and run:

```bash
d2 --layout=elk docs/cloud-poc-architecture.d2
```

This will create `cloud-poc-architecture.svg` in the same directory.

### Install D2

If D2 is not installed, follow the instructions at: https://github.com/terrastruct/d2

**Windows (via Chocolatey)**:
```powershell
choco install d2
```

**macOS**:
```bash
brew install d2
```

**Linux**:
```bash
curl -fsSL https://d2lang.com/install.sh | sh
```

---

**Document Version**: 1.0  
**Last Updated**: May 2, 2026  
**Author**: AWS CDK Infrastructure Analysis  
**Status**: Active (Phase 1 deployed, Phase 2 ready for activation)
