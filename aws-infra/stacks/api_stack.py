"""
ApiStack — deploys API Gateway for the Cloud POC.

Provisions:
- REST API Gateway with /chef endpoint
- API Key and Usage Plan for authentication
- IAM role for API Gateway to invoke Step Functions
- CloudWatch Log Group for API Gateway access logs
- X-Ray tracing integration
"""

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct

from config.api_config import CLOUD_API_CONFIG


class ApiStack(cdk.Stack):
    """CDK stack that provisions API Gateway for Step Functions integration."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        state_machine: sfn.StateMachine,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = CLOUD_API_CONFIG

        # ------------------------------------------------------------------ #
        # CloudWatch Log Group for API Gateway access logs                    #
        # ------------------------------------------------------------------ #
        self.log_group = logs.LogGroup(
            self,
            "ApiLogGroup",
            log_group_name=f"/aws/apigateway/{cfg.api_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cfg.removal_policy,
        )

        # ------------------------------------------------------------------ #
        # IAM Role for API Gateway to invoke Step Functions                   #
        # ------------------------------------------------------------------ #
        self.api_role = iam.Role(
            self,
            "ApiGatewayStepFunctionsRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            description="Allows API Gateway to start Step Functions executions",
        )

        # Grant permission to start executions on the specific state machine
        state_machine.grant_start_execution(self.api_role)

        # ------------------------------------------------------------------ #
        # REST API                                                             #
        # ------------------------------------------------------------------ #
        self.api = apigw.RestApi(
            self,
            "ChefApi",
            rest_api_name=cfg.api_name,
            description=cfg.api_description,
            deploy=True,
            deploy_options=apigw.StageOptions(
                stage_name=cfg.stage_name,
                throttling_rate_limit=cfg.throttle_rate_limit,
                throttling_burst_limit=cfg.throttle_burst_limit,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(self.log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
                tracing_enabled=True,  # Enable X-Ray tracing
            ),
            cloud_watch_role=True,  # Create CloudWatch role automatically
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        # ------------------------------------------------------------------ #
        # API Key and Usage Plan                                               #
        # ------------------------------------------------------------------ #
        self.api_key = self.api.add_api_key(
            "ChefApiKey",
            api_key_name=cfg.api_key_name,
            description=cfg.api_key_description,
        )

        self.usage_plan = self.api.add_usage_plan(
            "ChefApiUsagePlan",
            name=f"{cfg.api_name}UsagePlan",
            description="Usage plan for Chef API",
            throttle=apigw.ThrottleSettings(
                rate_limit=cfg.throttle_rate_limit,
                burst_limit=cfg.throttle_burst_limit,
            ),
        )

        self.usage_plan.add_api_key(self.api_key)
        self.usage_plan.add_api_stage(
            stage=self.api.deployment_stage,
        )

        # ------------------------------------------------------------------ #
        # Step Functions Integration                                           #
        # ------------------------------------------------------------------ #
        # Integration that starts Step Functions execution
        sfn_integration = apigw.AwsIntegration(
            service="states",
            action="StartExecution",
            integration_http_method="POST",
            options=apigw.IntegrationOptions(
                credentials_role=self.api_role,
                request_templates={
                    "application/json": f"""
#set($inputRoot = $input.path('$'))
{{
  "stateMachineArn": "{state_machine.state_machine_arn}",
  "input": "$util.escapeJavaScript($input.json('$'))"
}}
"""
                },
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": """
#set($inputRoot = $input.path('$'))
{
  "executionArn": "$inputRoot.executionArn",
  "startDate": "$inputRoot.startDate"
}
"""
                        },
                    ),
                    apigw.IntegrationResponse(
                        status_code="400",
                        selection_pattern="4\\d{2}",
                        response_templates={
                            "application/json": '{"error": "Bad Request"}'
                        },
                    ),
                    apigw.IntegrationResponse(
                        status_code="500",
                        selection_pattern="5\\d{2}",
                        response_templates={
                            "application/json": '{"error": "Internal Server Error"}'
                        },
                    ),
                ],
            ),
        )

        # ------------------------------------------------------------------ #
        # /chef Resource and POST Method                                       #
        # ------------------------------------------------------------------ #
        chef_resource = self.api.root.add_resource("chef")

        chef_resource.add_method(
            "POST",
            sfn_integration,
            api_key_required=True,
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_models={
                        "application/json": apigw.Model.EMPTY_MODEL,
                    },
                ),
                apigw.MethodResponse(status_code="400"),
                apigw.MethodResponse(status_code="500"),
            ],
        )

        # ------------------------------------------------------------------ #
        # Outputs                                                              #
        # ------------------------------------------------------------------ #
        cdk.CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            description="URL of the Chef API Gateway",
        )

        cdk.CfnOutput(
            self,
            "ApiEndpoint",
            value=f"{self.api.url}chef",
            description="Full endpoint URL for the /chef resource",
        )

        cdk.CfnOutput(
            self,
            "ApiKeyId",
            value=self.api_key.key_id,
            description="ID of the API Key (retrieve value from AWS Console or AWS CLI)",
        )

        cdk.CfnOutput(
            self,
            "ApiRoleArn",
            value=self.api_role.role_arn,
            description="IAM role ARN used by API Gateway to invoke Step Functions",
        )
