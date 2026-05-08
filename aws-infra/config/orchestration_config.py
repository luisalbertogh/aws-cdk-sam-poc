from dataclasses import dataclass, field

import aws_cdk as cdk


@dataclass(frozen=True)
class OrchestrationConfig:
    """Configuration for the Step Functions orchestration stack."""

    # CloudWatch log retention in days
    log_retention_days: int = 7
    # Removal policy for all resources in this stack
    removal_policy: cdk.RemovalPolicy = cdk.RemovalPolicy.DESTROY
    # Path to the Step Functions workflow definition (ASL JSON file)
    # Relative to the config directory
    workflow_definition_path: str = "step_functions/hello_world_workflow.asl.json"
    # Name of the Step Functions state machine
    state_machine_name: str = "HelloWorldStateMachine"
    # Lambda function names (deployed via SAM)
    chef_lambda_name: str = "CloudCorePocChefAppStack-ChefApp"
    offapi_lambda_name: str = "CloudPocOpenFoodFactsAPIStack-OFFAPICaller"


CLOUD_ORCHESTRATION_CONFIG = OrchestrationConfig()
