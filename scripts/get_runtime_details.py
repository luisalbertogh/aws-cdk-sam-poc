#!/usr/bin/env python3
"""
Retrieve and display the current configuration of an AgentCore Runtime.

Prints role ARN, network configuration, current container URI, status, and
environment variables for the runtime associated with the given ECR repository.

Usage:
    python scripts/get_runtime_details.py <ecr-repo-name>

Example:
    python scripts/get_runtime_details.py chef-agent
"""

import json
import sys

import boto3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AWS_REGION = "eu-central-1"

# Maps ECR repository name → AgentCore Runtime ID.
# Populated after the first CDK deployment; update these values once the
# runtimes have been provisioned (visible in the CDK stack outputs or the
# AWS Console under Bedrock → AgentCore → Runtimes).
AGENT_RUNTIME_IDS: dict[str, str] = {
    "chef-agent":         "chef_agent-HbW7G4A5X5",
    "nutritionist-agent": "nutritionist_agent-UhY62L7bNf",
    "instructor-agent":   "instructor_agent-xkBt3o8M2S",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_runtime_id(ecr_repo_name: str) -> str:
    """Return the runtime ID for the given ECR repo name or exit with an error."""
    runtime_id = AGENT_RUNTIME_IDS.get(ecr_repo_name)
    if not runtime_id:
        print(
            f"ERROR: No AgentCore Runtime ID configured for ECR repo '{ecr_repo_name}'.\n"
            f"Known repos: {', '.join(AGENT_RUNTIME_IDS.keys())}\n"
            "Update the AGENT_RUNTIME_IDS dict in this script after the initial CDK deployment.",
            file=sys.stderr,
        )
        sys.exit(1)
    if runtime_id.startswith("<"):
        print(
            f"ERROR: Runtime ID for '{ecr_repo_name}' is still a placeholder.\n"
            "Update AGENT_RUNTIME_IDS with the real value from your CDK stack outputs.",
            file=sys.stderr,
        )
        sys.exit(1)
    return runtime_id


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def get_runtime_details(ecr_repo_name: str) -> dict:
    """Fetch and return AgentCore Runtime details for *ecr_repo_name*."""
    runtime_id = _resolve_runtime_id(ecr_repo_name)

    client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)
    response = client.get_agent_runtime(agentRuntimeId=runtime_id)

    artifact = response.get("agentRuntimeArtifact", {})
    container_uri = (
        artifact.get("containerConfiguration", {}).get("containerUri")
    )

    details = {
        "agentRuntimeId":      response["agentRuntimeId"],
        "agentRuntimeArn":     response["agentRuntimeArn"],
        "agentRuntimeVersion": response.get("agentRuntimeVersion"),
        "status":              response.get("status"),
        "roleArn":             response.get("roleArn"),
        "networkConfiguration": response.get("networkConfiguration"),
        "containerUri":        container_uri,
        "environmentVariables": response.get("environmentVariables", {}),
        "createdAt":           str(response.get("createdAt")),
        "lastUpdatedAt":       str(response.get("lastUpdatedAt")),
    }

    return details


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <ecr-repo-name>", file=sys.stderr)
        sys.exit(1)

    ecr_repo_name = sys.argv[1]

    print(f"Fetching AgentCore Runtime details for '{ecr_repo_name}'...")
    details = get_runtime_details(ecr_repo_name)

    print(json.dumps(details, indent=2, default=str))


if __name__ == "__main__":
    main()
