"""
API Gateway configuration for the Cloud POC infrastructure.

Centralizes all API Gateway settings including API keys, throttling,
logging, and integration configuration.
"""

from dataclasses import dataclass

import aws_cdk as cdk


@dataclass(frozen=True)
class ApiGatewayConfig:
    """Immutable configuration for the Cloud POC API Gateway."""

    # ---------------------------------------------------------------------------
    # API Gateway settings
    # ---------------------------------------------------------------------------
    # Name of the REST API
    api_name: str = "CloudPocChefApi"
    
    # API description
    api_description: str = "Cloud POC Chef API - Invokes Step Functions workflow"
    
    # API stage name
    stage_name: str = "prod"
    
    # ---------------------------------------------------------------------------
    # API Key settings
    # ---------------------------------------------------------------------------
    # Name of the API key
    api_key_name: str = "CloudPocChefApiKey"
    
    # API key description
    api_key_description: str = "API key for accessing the Chef API"
    
    # ---------------------------------------------------------------------------
    # Throttling settings
    # ---------------------------------------------------------------------------
    # Rate limit (requests per second)
    throttle_rate_limit: int = 10
    
    # Burst limit (maximum concurrent requests)
    throttle_burst_limit: int = 20
    
    # ---------------------------------------------------------------------------
    # CloudWatch Logs settings
    # ---------------------------------------------------------------------------
    # Log retention in days
    log_retention_days: int = 7
    
    # ---------------------------------------------------------------------------
    # Resource settings
    # ---------------------------------------------------------------------------
    # Removal policy for all resources in this stack
    removal_policy: cdk.RemovalPolicy = cdk.RemovalPolicy.DESTROY


CLOUD_API_CONFIG = ApiGatewayConfig()
