"""
EcsStack — deploys the Chef UI as an ECS Fargate service.

Design decisions
----------------
- ECS Fargate (serverless compute): no EC2 instances to manage; AWS handles the
  control plane, scaling, and patching.
- ARM64 architecture: matches the Docker image platform (linux/arm64) built by
  the CI pipeline and offers ~20 % better price/performance than x86_64.
- 0.5 vCPU / 2 GB: matches the requirements spec; adequate for a Chainlit UI
  with low-to-moderate concurrent sessions.
- ECS task execution role: injected from ClusterStack; manages ECR pulls and
  CloudWatch Logs writes. Created explicitly as part of the infrastructure
  rather than relying on account defaults.
- Public subnet / public IP: the UI is Internet-facing and public subnets with
  an IGW already exist (provisioned by NetworkStack); no NAT Gateway is needed.
- assign_public_ip=True: required for Fargate tasks in public subnets to reach
  ECR and CloudWatch endpoints without a NAT Gateway.
- CloudWatch log group: 7-day retention as specified; log group is removed on
  stack deletion (removal_policy=DESTROY) because logs can be regenerated.
- No load balancer: a single task at desired_count=1 is sufficient for the POC.
  An ALB can be added later when multi-task HA is required.
- The chef-ui ECR repository is granted an additional resource policy allowing
  the task execution role to pull images (ecsTaskExecutionRole). This is
  implemented by calling repo.grant_pull() which emits the correct
  ecr:BatchGetImage / ecr:GetDownloadUrlForLayer / ecr:GetAuthorizationToken
  permissions.
"""

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from config.ecs_config import CHEF_UI_ECS_CONFIG


class EcsStack(cdk.Stack):
    """CDK stack that deploys the Chef UI Chainlit app on ECS Fargate."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        security_group: ec2.ISecurityGroup,
        cluster: ecs.ICluster,
        chef_ui_repository: ecr.IRepository,
        login_secret: secretsmanager.ISecret,
        state_machine_arn: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = CHEF_UI_ECS_CONFIG

        removal_policy = (
            cdk.RemovalPolicy.RETAIN
            if cfg.removal_policy == "RETAIN"
            else cdk.RemovalPolicy.DESTROY
        )

        # -------------------------------------------------------------------
        # ECS task execution role — imported by ARN
        #
        # The execution role is created in ClusterStack with a known name.
        # We import it here by constructing its ARN, avoiding a direct
        # stack dependency. The role must exist at deploy time or CloudFormation
        # will fail.
        # -------------------------------------------------------------------
        execution_role = iam.Role.from_role_arn(
            self,
            "ImportedExecutionRole",
            f"arn:aws:iam::{self.account}:role/chef-ui-ecs-task-execution-role",
        )

        # Grant the execution role ECR pull access on the chef-ui repository.
        # grant_pull() adds ecr:BatchGetImage + ecr:GetDownloadUrlForLayer to
        # the repository resource policy.
        chef_ui_repository.grant_pull(execution_role)

        # -------------------------------------------------------------------
        # Chef UI ECS task role
        #
        # This role is assumed by the running container (not the ECS control
        # plane).  No policies are attached here intentionally — add managed
        # or inline policies below as the application's AWS access requirements
        # grow (e.g. Bedrock, S3, Secrets Manager, etc.).
        # -------------------------------------------------------------------
        self.task_role = iam.Role(
            self,
            "ChefUiTaskRole",
            role_name="chef-ui-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role assumed by the chef-ui ECS Fargate task",
        )

        # Step Functions — allow the container to start and monitor executions
        # of any state machine / execution in the same account and region.
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowStepFunctionsOrchestration",
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:StartExecution",
                    "states:DescribeExecution",
                ],
                resources=[
                    # State machines in the same account & region
                    f"arn:aws:states:{self.region}:{self.account}:stateMachine:*",
                    # Executions of any state machine in the same account & region
                    f"arn:aws:states:{self.region}:{self.account}:execution:*:*",
                ],
            )
        )
        # --- attach managed policies here when needed, for example: ---
        # self.task_role.add_managed_policy(
        #     iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
        # )

        # -------------------------------------------------------------------
        # Secrets Manager — Chainlit auth credentials
        #
        # The secret is owned and governed by SecretsStack (created before this
        # stack).  It is received here as an injected parameter; the cross-stack
        # reference to its ARN is what makes CDK enforce SecretsStack →
        # EcsStack deployment ordering automatically.
        # -------------------------------------------------------------------
        self.login_secret = login_secret

        # -------------------------------------------------------------------
        # CloudWatch log group
        # -------------------------------------------------------------------
        log_group = logs.LogGroup(
            self,
            "ChefUiLogGroup",
            log_group_name="/aws/ecs/chef-ui",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=removal_policy,
        )

        # -------------------------------------------------------------------
        # ECS cluster — injected from app.py
        #
        # The cluster is created independently in app.py before this stack
        # to ensure it exists before SecretsStack and other dependent
        # resources are provisioned.
        # -------------------------------------------------------------------
        self.cluster = cluster

        # -------------------------------------------------------------------
        # Fargate task definition
        # -------------------------------------------------------------------
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "ChefUiTaskDef",
            cpu=cfg.cpu,
            memory_limit_mib=cfg.memory_limit_mib,
            # ARM64 matches the linux/arm64 Docker image platform.
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.ARM64,
            ),
            execution_role=execution_role,
            task_role=self.task_role,
        )

        # -------------------------------------------------------------------
        # Container definition
        # -------------------------------------------------------------------
        container = self.task_definition.add_container(
            "ChefUiContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                chef_ui_repository, tag=cfg.image_tag
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="chef-ui",
                log_group=log_group,
            ),
            environment={
                "PYTHONUNBUFFERED": "1",
                "AWS_REGION": self.region,
                "ORCHESTRATION_STATE_MACHINE_ARN": state_machine_arn,
            },
            secrets={
                # Each entry reads a single JSON field from the Secrets Manager
                # secret at task startup.  The ECS agent decrypts and injects
                # them as plain environment variables inside the container.
                "CHAINLIT_AUTH_SECRET": ecs.Secret.from_secrets_manager(
                    self.login_secret, "CHAINLIT_AUTH_SECRET"
                ),
                "CHEF_UI_USER": ecs.Secret.from_secrets_manager(
                    self.login_secret, "CHEF_UI_USER"
                ),
                "CHEF_UI_PASSWORD": ecs.Secret.from_secrets_manager(
                    self.login_secret, "CHEF_UI_PASSWORD"
                ),
            },
        )

        # host_port=80 → container_port=8080.
        # WARNING: Fargate (awsvpc network mode) requires host_port == container_port.
        # If this stack targets Fargate, set cfg.host_port = cfg.container_port (8080)
        # or CloudFormation will reject the task definition at deploy time.
        container.add_port_mappings(
            ecs.PortMapping(
                host_port=cfg.host_port,
                container_port=cfg.container_port,
                protocol=ecs.Protocol.TCP,
            )
        )

        # -------------------------------------------------------------------
        # ECS Fargate service
        #
        # deployed into the public subnets; assign_public_ip=True allows the
        # task to reach ECR / CloudWatch without a NAT Gateway.
        # -------------------------------------------------------------------
        self.service = ecs.FargateService(
            self,
            "ChefUiService",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=cfg.desired_count,
            assign_public_ip=True,
            security_groups=[security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
        )

        # -------------------------------------------------------------------
        # Outputs
        # -------------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "TaskRoleName",
            value=self.task_role.role_name,
            description="IAM task role assumed by the chef-ui container",
            export_name=f"{self.stack_name}-TaskRoleName",
        )

        cdk.CfnOutput(
            self,
            "ServiceName",
            value=self.service.service_name,
            description="Name of the Chef UI ECS Fargate service",
            export_name=f"{self.stack_name}-ServiceName",
        )

        cdk.CfnOutput(
            self,
            "LogGroupName",
            value=log_group.log_group_name,
            description="CloudWatch log group for Chef UI container logs",
            export_name=f"{self.stack_name}-LogGroupName",
        )
