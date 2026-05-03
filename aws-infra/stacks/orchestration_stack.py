import os

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from config.orchestration_config import CLOUD_ORCHESTRATION_CONFIG
from constructs import Construct


class OrchestrationStack(cdk.Stack):
    """
    Step Functions orchestration stack for the Cloud POC.

    Provisions:
    - CloudWatch Log Group for state machine execution logging
    - IAM execution role with least-privilege permissions:
        * CloudWatch Logs delivery (required for SF logging)
        * X-Ray tracing
    - A "Hello World" state machine that demonstrates the orchestration pattern
      (Pass → Pass → Succeed) and is ready to be extended with Cloud tasks
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = CLOUD_ORCHESTRATION_CONFIG

        # ------------------------------------------------------------------ #
        # CloudWatch Log Group                                                 #
        # ------------------------------------------------------------------ #
        self.log_group = logs.LogGroup(
            self,
            "StateMachineLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cfg.removal_policy,
        )

        # ------------------------------------------------------------------ #
        # IAM Execution Role                                                   #
        # ------------------------------------------------------------------ #
        self.execution_role = iam.Role(
            self,
            "StateMachineExecutionRole",
            assumed_by=iam.ServicePrincipal(
                "states.amazonaws.com",
                conditions={
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:states:{self.region}:{self.account}:stateMachine:*"
                    }
                },
            ),
            description="Execution role for the Cloud Hello World state machine",
        )

        # CloudWatch Logs — all actions required by Step Functions for log delivery
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogsDelivery",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:DeleteLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:PutLogEvents",
                    "logs:PutResourcePolicy",
                    "logs:DescribeResourcePolicies",
                    "logs:DescribeLogGroups",
                ],
                resources=["*"],
            )
        )

        # X-Ray tracing
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowXRayTracing",
                effect=iam.Effect.ALLOW,
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )

        # Lambda invocation — allow state machine to invoke Lambda functions
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowLambdaInvocation",
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[
                    f"arn:aws:lambda:{self.region}:{self.account}:function:*"
                ],
            )
        )

        # ------------------------------------------------------------------ #
        # State Machine Definition — loaded from ASL JSON template            #
        #                                                                      #
        # The workflow definition path is configured in                        #
        # config/orchestration_config.py                                       #
        # ------------------------------------------------------------------ #
        _asl_path = os.path.join(
            os.path.dirname(__file__), "..", "config", cfg.workflow_definition_path
        )

        # ------------------------------------------------------------------ #
        # State Machine                                                        #
        # ------------------------------------------------------------------ #
        self.state_machine = sfn.StateMachine(
            self,
            cfg.state_machine_name,
            state_machine_name=cfg.state_machine_name,
            definition_body=sfn.DefinitionBody.from_file(_asl_path),
            role=self.execution_role,
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=self.log_group,
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
            removal_policy=cfg.removal_policy,
        )

        # ------------------------------------------------------------------ #
        # Outputs                                                              #
        # ------------------------------------------------------------------ #
        cdk.CfnOutput(
            self,
            "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description=f"ARN of the {cfg.state_machine_name} state machine",
        )
        cdk.CfnOutput(
            self,
            "StateMachineLogGroupName",
            value=self.log_group.log_group_name,
            description="CloudWatch Log Group for state machine executions",
        )
        cdk.CfnOutput(
            self,
            "ExecutionRoleArn",
            value=self.execution_role.role_arn,
            description="IAM execution role ARN for the state machine",
        )
