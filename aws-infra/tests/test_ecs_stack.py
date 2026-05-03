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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def template() -> assertions.Template:
    """
    Synthesise the EcsStack and return the assertions template.
    
    Uses imported/mocked resources (vpc, cluster, execution_role, repo) created
    within a helper stack scope. Imported resources don't create CloudFormation
    resources, so they avoid cross-stack dependencies.
    """
    app = cdk.App()
    env = cdk.Environment(account="741881499996", region="us-east-1")

    # Create a helper stack just for imported resources (required by CDK)
    import_stack = cdk.Stack(app, "ImportStack", env=env)
    
    # Create imported resources within the import_stack scope
    vpc = ec2.Vpc.from_vpc_attributes(
        import_stack, "ImportedVpc",
        vpc_id="vpc-12345",
        availability_zones=["us-east-1a", "us-east-1b"],
        public_subnet_ids=["subnet-111", "subnet-222"],
    )
    
    security_group = ec2.SecurityGroup.from_security_group_id(
        import_stack, "ImportedSg", "sg-12345"
    )
    
    cluster = ecs.Cluster.from_cluster_attributes(
        import_stack, "ImportedCluster",
        cluster_name="test-cluster",
        vpc=vpc,
        security_groups=[],
    )
    
    chef_ui_repository = ecr.Repository.from_repository_arn(
        import_stack, "ImportedRepo",
        "arn:aws:ecr:us-east-1:741881499996:repository/test-repo",
    )

    # Create SecretsStack
    secrets_stack = SecretsStack(
        app,
        "TestSecretsStack",
        secret_name=CHEF_UI_ECS_CONFIG.login_secret_name,
        env=env,
    )

    # Create EcsStack with imported resources
    # Note: execution_role is now imported by ARN within EcsStack itself
    ecs_stack = EcsStack(
        app,
        "TestEcsStack",
        vpc=vpc,
        security_group=security_group,
        cluster=cluster,
        chef_ui_repository=chef_ui_repository,
        login_secret=secrets_stack.login_secret,
        state_machine_arn="arn:aws:states:us-east-1:741881499996:stateMachine:TestStateMachine",
        env=env,
    )
    
    return assertions.Template.from_stack(ecs_stack)


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
    def test_service_name_output(self, template: assertions.Template) -> None:
        template.has_output("ServiceName", {})

    def test_log_group_name_output(self, template: assertions.Template) -> None:
        template.has_output("LogGroupName", {})
