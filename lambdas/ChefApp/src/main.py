import json
from dataclasses import dataclass, field

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# AWS Lambda Powertools Logger setup
logger = Logger()


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Mock a chef agent. 
    """    
    input = event.get("input", {})
    if not input:
        input = json.loads(event["body"]) if isinstance(event.get("body"), str) else event

    final_results = {}
    if "plato" in input:
        logger.info("El cliente me ha pedido una sugerencia de plato. Le voy a dar tres opciones.")
        final_results = {
            "plato": input,
            "sugerencias": [
                "Paella",
                "Pasta",
                "Lentejas"
            ]
        }
    elif input:
        logger.info(f"El cliente quiere comer: {input}")
        final_results = {
            "plato": input
        }

    return {
        "statusCode": 200,
        "body": json.dumps(final_results)
    }


@dataclass
class MockLambdaContext:
    """Minimal Lambda context for local testing."""
    function_name: str = "chefapp-local"
    function_version: str = "$LATEST"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:chefapp-local"
    aws_request_id: str = field(default_factory=lambda: "local-request-id")
    log_group_name: str = "/aws/lambda/chefapp-local"
    log_stream_name: str = "2024/01/01/[$LATEST]local"


def main():
    """Testing with multiple products."""
    event = {
        "input": "Sugiereme un plato para cenar esta noche, por favor..."
    }
    response = lambda_handler(event, MockLambdaContext())
    print(json.dumps(json.loads(response["body"]), indent=2))


if __name__ == "__main__":
    main()
