from dataclasses import dataclass, field

import aws_cdk as cdk


@dataclass(frozen=True)
class OrchestrationConfig:
    """Configuration for the Step Functions orchestration stack."""

    # CloudWatch log retention in days
    log_retention_days: int = 7
    # Removal policy for all resources in this stack
    removal_policy: cdk.RemovalPolicy = cdk.RemovalPolicy.DESTROY


AGENTCORE_ORCHESTRATION_CONFIG = OrchestrationConfig()
