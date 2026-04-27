import aws_cdk as cdk
import aws_cdk.aws_bedrock_agentcore_alpha as agentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_python_alpha as lambda_python
from aws_cdk import aws_logs as logs
from config.compute_config import GATEWAY_CONFIG, OPENFOODFACTS_LAMBDA_CONFIG
from constructs import Construct


class ComputeStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, registry_stack, **kwargs: object
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Tool Setup (Existing Lambda + Gateway) ---

        cfg = OPENFOODFACTS_LAMBDA_CONFIG

        # openFoodFactsAPI Lambda Function
        self.search_function = lambda_python.PythonFunction(
            self,
            cfg.logical_id,  # Correlated with config
            entry="src/lambda/openfoodfacts_api",
            index="index.py",
            handler="lambda_handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            memory_size=cfg.memory_size,
            timeout=cdk.Duration.seconds(cfg.timeout_seconds),
        )

        # Ensure the removal policy is applied
        self.search_function.apply_removal_policy(cfg.removal_policy)

        # Create the AgentCore Gateway
        self.gateway = agentcore.Gateway(
            self,
            "AgentCoreGateway",
            gateway_name="ChefAssistantGateway",
            authorizer_configuration=agentcore.GatewayAuthorizer.using_aws_iam(),
            description="Gateway for Nutrition and Cooking tools",
        )

        # TO BE REMOVED
        # Apply the ToolSchema and SchemaDefinition structure
        # self.gateway.add_lambda_target(
        #     "OpenFoodFactsAPITarget",
        #     gateway_target_name="openfoodfactsapi-target",
        #     description="Searches for food products and retrieves nutritional info.",
        #     lambda_function=self.search_function,
        #     tool_schema=agentcore.ToolSchema.from_inline(
        #         [
        #             {
        #                 "name": "search_food",
        #                 "description": "Searches for food products and retrieves nutritional info.",
        #                 "inputSchema": agentcore.SchemaDefinition(
        #                     type=agentcore.SchemaDefinitionType.OBJECT,
        #                     properties={
        #                         "product_name": agentcore.SchemaDefinition(
        #                             type=agentcore.SchemaDefinitionType.STRING,
        #                             description="The name of the food product (e.g., 'Nutella')",
        #                         ),
        #                         "limit": agentcore.SchemaDefinition(
        #                             type=agentcore.SchemaDefinitionType.INTEGER,
        #                             description="Maximum number of results to return",
        #                         ),
        #                     },
        #                     required=["product_name"],
        #                 ),
        #             }
        #         ]
        #     ),
        # )

        # Wire up an external Lambda target if an ARN has been configured.
        # Set GATEWAY_CONFIG.external_lambda_arn in config/lambda_config.py
        # when the Lambda lives in a separate stack that is not available here.
        if GATEWAY_CONFIG.external_lambda_arn:
            external_fn = _lambda.Function.from_function_arn(
                self,
                "ExternalGatewayLambda",
                GATEWAY_CONFIG.external_lambda_arn,
            )
            self.gateway.add_lambda_target(
                "ExternalLambdaTarget",
                gateway_target_name="external-lambda-target",
                description="External Lambda target from a separate stack.",
                lambda_function=external_fn,
                tool_schema=agentcore.ToolSchema.from_inline(
                    [
                        {
                            "name": "search_food",
                            "description": "Searches for food products and retrieves nutritional info.",
                            "inputSchema": agentcore.SchemaDefinition(
                                type=agentcore.SchemaDefinitionType.OBJECT,
                                properties={
                                    "product_names": agentcore.SchemaDefinition(
                                        type=agentcore.SchemaDefinitionType.ARRAY,
                                        description="A list of names of food products (e.g., ['milk', 'eggs'])",
                                        # Define the type of items inside the array
                                        items=agentcore.SchemaDefinition(
                                            type=agentcore.SchemaDefinitionType.STRING
                                        )
                                    ),
                                    "limit": agentcore.SchemaDefinition(
                                        type=agentcore.SchemaDefinitionType.INTEGER,
                                        description="Maximum number of results to return",
                                    ),
                                },
                                required=["product_name"],
                            ),
                        }
                    ]
                ),
            )

        # Output the Gateway URL
        cdk.CfnOutput(self, "GatewayUrl", value=self.gateway.gateway_url)

        # --- Agents Setup (Bedrock Runtimes) ---

        # Define our three agents
        agent_configs = [
            ("Chef", registry_stack.repositories["chef-agent"]),
            ("Nutritionist", registry_stack.repositories["nutritionist-agent"]),
            ("Instructor", registry_stack.repositories["instructor-agent"]),
        ]

        # Define a common policy for Bedrock model invocation that ALL agents will need
        bedrock_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=[
                # Allows the Inference Profile in your region
                f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                # Allows the base Nova models in ANY region
                "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
                # Allows the base Anthropic models in ANY region
                "arn:aws:bedrock:*::foundation-model/anthropic.*",
            ],
        )

        self.runtimes = {}
        for prefix, repo in agent_configs:

            runtime_name = f"{prefix.lower()}_agent"

            # /aws/vendedlogs/ prefix is required: AWS automatically manages the
            # resource policy for this prefix, allowing the vended-logs delivery
            # service to write without a manually created resource policy.
            log_group = logs.LogGroup(
                self,
                f"{prefix}RuntimeLogGroup",
                log_group_name=f"/aws/vendedlogs/bedrock-agentcore/runtimes/{runtime_name}",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            )

            # Prepare environment variables
            env_vars = {"AWS_REGION": self.region, "PYTHONUNBUFFERED": "1"}

            # Add Gateway URL ONLY for the Nutritionist Agent
            if prefix == "Nutritionist":
                env_vars["AGENT_GATEWAY_URL"] = self.gateway.gateway_url

            # Create the AgentCore Runtime
            runtime = agentcore.Runtime(
                self,
                f"{prefix}Runtime",
                runtime_name=runtime_name,
                agent_runtime_artifact=agentcore.AgentRuntimeArtifact.from_ecr_repository(
                    repo, "latest"
                ),
                environment_variables=env_vars,
            )

            # ── Vended logs delivery pipeline ───────────────────────────────
            # AgentCore Runtimes emit application logs via the CloudWatch
            # vended-logs mechanism.  The runtime's IAM role does NOT write
            # directly; the CloudWatch Logs delivery service does, so
            # grant_write() on the runtime role is intentionally not used here.
            #
            # Three resources are required per runtime:
            #   1. DeliverySource  – identifies the producer (runtime ARN)
            #   2. DeliveryDestination – identifies the consumer (log group ARN)
            #   3. Delivery – wires source → destination

            delivery_source = logs.CfnDeliverySource(
                self,
                f"{prefix}RuntimeDeliverySource",
                name=f"{runtime_name}-logs-source",
                log_type="APPLICATION_LOGS",
                resource_arn=runtime.agent_runtime_arn,
            )

            delivery_destination = logs.CfnDeliveryDestination(
                self,
                f"{prefix}RuntimeDeliveryDestination",
                name=f"{runtime_name}-logs-destination",
                destination_resource_arn=log_group.log_group_arn,
                delivery_destination_type="CWL",
            )

            cfn_delivery = logs.CfnDelivery(
                self,
                f"{prefix}RuntimeDelivery",
                delivery_source_name=delivery_source.name,
                delivery_destination_arn=delivery_destination.attr_arn,
            )
            # delivery_source.name is a plain string, not a token, so
            # CloudFormation cannot infer ordering — make dependencies explicit.
            cfn_delivery.add_dependency(delivery_source)
            cfn_delivery.add_dependency(delivery_destination)

            if prefix == "Nutritionist":
                # Grant permissions to invoke the Gateway and its tools
                runtime.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["bedrock-agentcore:InvokeGateway"],
                        resources=[self.gateway.gateway_arn],
                    )
                )

                # Allow invoking any tool under the gateway
                runtime.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["bedrock:InvokeInlineAgent"],
                        resources=[
                            self.gateway.gateway_arn,
                            f"{self.gateway.gateway_arn}/*",
                        ],
                    )
                )

                self.gateway.grant_invoke(runtime)

            # The Instructor agent needs permissions to manage and use the Browser tool
            if prefix == "Instructor":
                runtime.add_to_role_policy(
                    iam.PolicyStatement(
                        sid="BedrockAgentCoreBrowserFullAccess",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "bedrock-agentcore:CreateBrowser",
                            "bedrock-agentcore:ListBrowsers",
                            "bedrock-agentcore:GetBrowser",
                            "bedrock-agentcore:DeleteBrowser",
                            "bedrock-agentcore:StartBrowserSession",
                            "bedrock-agentcore:ListBrowserSessions",
                            "bedrock-agentcore:GetBrowserSession",
                            "bedrock-agentcore:StopBrowserSession",
                            "bedrock-agentcore:UpdateBrowserStream",
                            "bedrock-agentcore:ConnectBrowserAutomationStream",
                            "bedrock-agentcore:ConnectBrowserLiveViewStream"
                        ],
                        # Dynamically use the stack's region and account
                        resources=[
                            # Allows browsers you create in your account
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:browser/*",
                            # Allows the AWS managed browser (aws.browser.v1)
                            f"arn:aws:bedrock-agentcore:{self.region}:aws:browser/*" 
                        ]
                    )
                )

            # Apply Model Permissions to ALL agents
            runtime.add_to_role_policy(bedrock_policy)

            self.runtimes[prefix] = runtime
            cdk.CfnOutput(self, f"{prefix}RuntimeArn", value=runtime.agent_runtime_arn)

        # To make it easy to find, output the ARN of the policy or the Runtime
        cdk.CfnOutput(
            self,
            f"{prefix}InvokePermission",
            value=f"Grant bedrock-agentcore:InvokeAgentRuntime on {runtime.agent_runtime_arn}*",
        )
