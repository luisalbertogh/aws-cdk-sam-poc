from dataclasses import dataclass
import aws_cdk as cdk


@dataclass(frozen=True)
class LambdaConfig:
    """Configuration for the OpenFoodFactsAPI Lambda function."""

    logical_id: str = "openFoodFactsAPI"
    runtime_name: str = "PYTHON_3_12"
    handler: str = "index.lambda_handler"
    timeout_seconds: int = 30
    memory_size: int = 256  # MB
    # Map string to actual CDK RemovalPolicy
    removal_policy: cdk.RemovalPolicy = cdk.RemovalPolicy.DESTROY


OPENFOODFACTS_LAMBDA_CONFIG = LambdaConfig()


@dataclass(frozen=True)
class GatewayConfig:
    """Configuration for the AgentCore Gateway.

    Set ``external_lambda_arn`` to the ARN of a Lambda function that lives in
    a separate CDK stack (or an externally-managed stack) before deploying.
    When non-empty, the Compute stack will import that function and wire it up
    as an additional Gateway target.
    """

    # ARN of a Lambda created in a separate stack.
    # Example: "arn:aws:lambda:eu-central-1:123456789012:function:my-function"
    external_lambda_arn: str = "arn:aws:lambda:eu-central-1:442042532301:function:AgentCorePocOpenFoodFactsAPIStack-OFFAPICaller"


GATEWAY_CONFIG = GatewayConfig()
