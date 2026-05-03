"""
SecretsStack — creates and owns the Secrets Manager secrets used by the
Chef UI ECS Fargate service.

Design decisions
----------------
- Separate stack: secrets have a RETAIN removal policy and are credentials
  material; owning them in a dedicated stack means they are never accidentally
  destroyed when the ECS stack is torn down or redeployed.
- Resource policy with explicit ARN principal: the ECS task execution role ARN
  is passed as a parameter from ClusterStack. Granting access via a resource
  policy on the secret (add_to_resource_policy) allows the execution role to
  read secrets at task startup without requiring identity-based policy changes.
- Stack ordering: because EcsStack receives the secret construct as a parameter
  and references its ARN, CDK synthesises an automatic cross-stack dependency,
  guaranteeing SecretsStack is fully deployed before EcsStack.
"""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class SecretsStack(cdk.Stack):
    """CDK stack that creates and governs Secrets Manager secrets for Chef UI."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        secret_name: str,
        reader_role_arn: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------------------
        # Secrets Manager — Chainlit auth credentials
        #
        # Created with no initial value; the JSON object with the fields
        # CHAINLIT_AUTH_SECRET, CHEF_UI_USER, and CHEF_UI_PASSWORD must be
        # populated manually in the AWS console (or via CLI) after the first
        # deployment.
        #
        # Removal policy is always RETAIN — credentials must never be
        # accidentally destroyed on a stack teardown.
        # -------------------------------------------------------------------
        self.login_secret = secretsmanager.Secret(
            self,
            "ChefUiLoginSecret",
            secret_name=secret_name,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # -------------------------------------------------------------------
        # Resource policy — grant the ECS task execution role read access
        #
        # Using add_to_resource_policy() with an ArnPrincipal avoids the
        # mutable=False limitation on the imported execution role in EcsStack.
        # The policy is attached directly to the secret resource, ensuring it
        # is fully in place before EcsStack references the secret ARN.
        # -------------------------------------------------------------------
        if reader_role_arn:
            self.login_secret.add_to_resource_policy(
                iam.PolicyStatement(
                    sid="AllowEcsTaskExecutionRoleRead",
                    principals=[iam.ArnPrincipal(reader_role_arn)],
                    actions=[
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    resources=["*"],
                )
            )

        # -------------------------------------------------------------------
        # Outputs
        # -------------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "LoginSecretArn",
            value=self.login_secret.secret_arn,
            description="ARN of the Secrets Manager secret holding Chainlit auth credentials",
            export_name=f"{self.stack_name}-LoginSecretArn",
        )
