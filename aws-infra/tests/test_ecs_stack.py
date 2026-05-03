"""
Unit tests for EcsStack.

Uses CDK assertions (fine-grained) to validate the synthesised
CloudFormation template without deploying to AWS.
"""

import aws_cdk as cdk
import pytest
from aws_cdk import assertions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam

from stacks import EcsStack, SecretsStack
from config.ecs_config import CHEF_UI_ECS_CONFIG


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_vpc(scope: cdk.Stack) -> ec2.Vpc:
    """Create a minimal VPC with one public subnet for testing."""
    return ec2.Vpc(
        scope,
        "TestVpc",
        ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/27"),
        max_azs=2,
        nat_gateways=0,
        subnet_configuration=[
            ec2.SubnetConfiguration(
                name="Public",
                subnet_type=ec2.SubnetType.PUBLIC,
                cidr_mask=28,
            )
        ],
    )


def _make_sg(scope: cdk.Stack, vpc: ec2.Vpc) -> ec2.SecurityGroup:
    """Create a minimal security group for testing."""
    sg = ec2.SecurityGroup(scope, "TestSg", vpc=vpc, allow_all_outbound=True)
    sg.add_ingress_rule(ec2.Peer.ipv4("0.0.0.0/0"), ec2.Port.tcp(8080))
    return sg


def _make_repo(scope: cdk.Stack) -> ecr.Repository:
    """Create a minimal ECR repository for testing."""
    return ecr.Repository(scope, "TestRepo")


def _make_cluster(scope: cdk.Stack, vpc: ec2.Vpc) -> ecs.Cluster:
    """Create a minimal ECS cluster for testing."""
    return ecs.Cluster(
        scope,
        "TestCluster",
        cluster_name="test-cluster",
        vpc=vpc,
    )


def _make_execution_role(scope: cdk.Stack) -> iam.Role:
    """Create a minimal ECS task execution role for testing."""
    return iam.Role(
        scope,
        "TestExecutionRole",
        assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        managed_policies=[
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        ],
    )


@pytest.fixture(scope="module")
def template() -> assertions.Template:
    """
    Synthesise the EcsStack and return the assertions template.
    
    Creates minimal mock dependencies using CDK's from_* import methods
    to avoid cross-stack reference cycles.
    """
    app = cdk.App()
    env = cdk.Environment(account="741881499996", region="us-east-1")

    # Create SecretsStack
    secrets_stack = SecretsStack(
        app,
        "TestSecretsStack",
        secret_name=CHEF_UI_ECS_CONFIG.login_secret_name,
        env=env,
    )

    # Create EcsStack
    ecs_stack = cdk.Stack(app, "TestEcsStack", env=env)
    
    # Create test dependencies directly in EcsStack to avoid cross-stack references
    vpc = _make_vpc(ecs_stack)
    sg = _make_sg(ecs_stack, vpc)
    cluster = _make_cluster(ecs_stack, vpc)
    execution_role = _make_execution_role(ecs_stack)
    repo = _make_repo(ecs_stack)
    
    # Now instantiate the actual EcsStack constructs by importing from the class
    # We'll create the EcsStack resources manually in our test stack
    from stacks.ecs_stack import EcsStack as EcsStackClass
    
    # Create a new instance that will use our test stack
    ecs_test_instance = EcsStackClass(
        app,
        "ActualTestEcsStack",
        vpc=vpc,
        security_group=sg,
        cluster=cluster,
        execution_role=execution_role,
        chef_ui_repository=repo,
        login_secret=secrets_stack.login_secret,
        state_machine_arn="arn:aws:states:us-east-1:741881499996:stateMachine:TestStateMachine",
        env=env,
    )
    
    return assertions.Template.from_stack(ecs_test_instance)


# ---------------------------------------------------------------------------
# Fargate Task Definition
# ---------------------------------------------------------------------------


class TestFargateTaskDefinition:
    def test_task_definition_is_created(self, template: assertions.Template) -> None:
        template.resource_count_is("AWS::ECS::TaskDefinition", 1)

    def test_cpu_and_memory(self, template: assertions.Template) -> None:
        """Task must be sized at 512 CPU units (0.5 vCPU) and 2048 MiB."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "Cpu": "512",
                "Memory": "2048",
            },
        )

    def test_arm64_architecture(self, template: assertions.Template) -> None:
        """Task must target linux/arm64 to match the Docker image platform."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "RuntimePlatform": {
                    "CpuArchitecture": "ARM64",
                    "OperatingSystemFamily": "LINUX",
                }
            },
        )

    def test_network_mode_awsvpc(self, template: assertions.Template) -> None:
        """Fargate requires awsvpc network mode."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {"NetworkMode": "awsvpc"},
        )

    def test_container_port_mapping(self, template: assertions.Template) -> None:
        """Container must expose port 8080/TCP."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "PortMappings": [
                                    {"ContainerPort": 8080, "Protocol": "tcp"}
                                ]
                            }
                        )
                    ]
                )
            },
        )

    def test_awslogs_log_driver(self, template: assertions.Template) -> None:
        """Container must use the awslogs log driver."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "LogConfiguration": {
                                    "LogDriver": "awslogs",
                                }
                            }
                        )
                    ]
                )
            },
        )


# ---------------------------------------------------------------------------
# ECS Fargate Service
# ---------------------------------------------------------------------------


class TestFargateService:
    def test_service_is_created(self, template: assertions.Template) -> None:
        template.resource_count_is("AWS::ECS::Service", 1)

    def test_launch_type_fargate(self, template: assertions.Template) -> None:
        template.has_resource_properties(
            "AWS::ECS::Service",
            {"LaunchType": "FARGATE"},
        )

    def test_desired_count(self, template: assertions.Template) -> None:
        template.has_resource_properties(
            "AWS::ECS::Service",
            {"DesiredCount": 1},
        )

    def test_public_ip_assigned(self, template: assertions.Template) -> None:
        """Tasks must receive a public IP so they can reach ECR/CloudWatch."""
        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "NetworkConfiguration": {
                    "AwsvpcConfiguration": {
                        "AssignPublicIp": "ENABLED",
                    }
                }
            },
        )


# ---------------------------------------------------------------------------
# CloudWatch Log Group
# ---------------------------------------------------------------------------


class TestLogGroup:
    def test_log_group_is_created(self, template: assertions.Template) -> None:
        template.resource_count_is("AWS::Logs::LogGroup", 1)

    def test_retention_7_days(self, template: assertions.Template) -> None:
        """Log group must have a 7-day retention period."""
        template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 7},
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


class TestOutputs:
    def test_cluster_name_output(self, template: assertions.Template) -> None:
        template.has_output("ClusterName", {})

    def test_service_name_output(self, template: assertions.Template) -> None:
        template.has_output("ServiceName", {})

    def test_log_group_name_output(self, template: assertions.Template) -> None:
        template.has_output("LogGroupName", {})
