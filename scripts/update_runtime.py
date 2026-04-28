#!/usr/bin/env python3
"""
Update an AgentCore Runtime to use a newly pushed Docker image.

The script fetches the current runtime configuration (role ARN, network
configuration, environment variables) and calls update_agent_runtime with
those preserved settings and the new container URI.  This ensures the update
never accidentally clobbers live configuration.

Usage:
    python scripts/update_runtime.py <ecr-repo-name> <new-image-uri>

Example:
    python scripts/update_runtime.py chef-agent \
        741881499996.dkr.ecr.eu-central-1.amazonaws.com/chef-agent:latest
"""

import json
import sys

import boto3
from botocore.exceptions import ClientError

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


def _build_network_config(raw: dict) -> dict:
    """
    Build a clean networkConfiguration dict accepted by update_agent_runtime.

    The describe response may contain read-only keys; only forward the fields
    that the update API accepts to avoid validation errors.
    """
    config: dict = {"networkMode": raw["networkMode"]}
    if "networkModeConfig" in raw:
        cfg = raw["networkModeConfig"]
        network_mode_config: dict = {}
        if "securityGroups" in cfg:
            network_mode_config["securityGroups"] = cfg["securityGroups"]
        if "subnets" in cfg:
            network_mode_config["subnets"] = cfg["subnets"]
        if network_mode_config:
            config["networkModeConfig"] = network_mode_config
    return config


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def update_runtime(ecr_repo_name: str, new_image_uri: str) -> dict:
    """
    Update the AgentCore Runtime for *ecr_repo_name* to use *new_image_uri*.

    Returns the response dict from update_agent_runtime on success.
    """
    runtime_id = _resolve_runtime_id(ecr_repo_name)

    client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)

    # ------------------------------------------------------------------
    # 1. Fetch current runtime config to preserve mutable settings
    # ------------------------------------------------------------------
    print(f"Fetching current runtime config for '{ecr_repo_name}' (ID: {runtime_id})...")
    try:
        current = client.get_agent_runtime(agentRuntimeId=runtime_id)
    except ClientError as exc:
        print(f"ERROR: Failed to fetch runtime details: {exc}", file=sys.stderr)
        sys.exit(1)

    role_arn = current["roleArn"]
    network_config = _build_network_config(current["networkConfiguration"])
    env_vars = current.get("environmentVariables", {})

    current_uri = (
        current.get("agentRuntimeArtifact", {})
               .get("containerConfiguration", {})
               .get("containerUri", "<unknown>")
    )

    print(f"  Runtime ID    : {runtime_id}")
    print(f"  Current image : {current_uri}")
    print(f"  New image     : {new_image_uri}")
    print(f"  Role ARN      : {role_arn}")
    print(f"  Network mode  : {network_config.get('networkMode')}")
    if env_vars:
        print(f"  Env vars      : {', '.join(env_vars.keys())}")

    # ------------------------------------------------------------------
    # 2. Call update_agent_runtime — preserve all settings, swap image
    # ------------------------------------------------------------------
    print(f"\nUpdating AgentCore Runtime '{runtime_id}'...")

    update_kwargs: dict = {
        "agentRuntimeId": runtime_id,
        "agentRuntimeArtifact": {
            "containerConfiguration": {
                "containerUri": new_image_uri,
            }
        },
        "roleArn": role_arn,
        "networkConfiguration": network_config,
    }

    # Only pass environmentVariables when the runtime has some; the API
    # treats an empty dict differently from the key being absent.
    if env_vars:
        update_kwargs["environmentVariables"] = env_vars

    try:
        response = client.update_agent_runtime(**update_kwargs)
    except ClientError as exc:
        print(f"ERROR: update_agent_runtime failed: {exc}", file=sys.stderr)
        sys.exit(1)

    result = {
        "agentRuntimeId":      response["agentRuntimeId"],
        "agentRuntimeArn":     response["agentRuntimeArn"],
        "agentRuntimeVersion": response.get("agentRuntimeVersion"),
        "status":              response.get("status"),
        "lastUpdatedAt":       str(response.get("lastUpdatedAt")),
    }

    print("\nUpdate successful:")
    print(json.dumps(result, indent=2))

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <ecr-repo-name> <new-image-uri>",
            file=sys.stderr,
        )
        sys.exit(1)

    ecr_repo_name = sys.argv[1]
    new_image_uri = sys.argv[2]

    update_runtime(ecr_repo_name, new_image_uri)


if __name__ == "__main__":
    main()
