import os
from typing import Any, Dict, Optional

import boto3
import uvicorn
from fastapi import FastAPI
from httpx_aws_auth import AwsCredentials, AwsSigV4Auth
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient


app = FastAPI(title="Nutritionist Agent")


def get_aws_auth():
    """Helper to get fresh IAM credentials from the compute environment."""
    region = os.environ.get("AWS_REGION", "eu-central-1")

    session = boto3.Session(region_name=region)
    print(f"Session created with region: {session.region_name}")
    print(f"Session: {session}")

    creds = session.get_credentials().get_frozen_credentials()
    print(
        f"Creds: Access Key: {creds.access_key}, Secret Key: {creds.secret_key}, Token: {creds.token}"
    )

    aws_creds = AwsCredentials(
        access_key=creds.access_key,
        secret_key=creds.secret_key,
        session_token=creds.token,  # Use 'session_token' for IAM roles
    )
    print("AWS credentials fetched and wrapped for SigV4Auth.")

    awssigv4 = AwsSigV4Auth(
        credentials=aws_creds,
        region=region,
        service="bedrock-agentcore",
    )
    print(f"AwsSigV4Auth created: {awssigv4}")

    return awssigv4


def query_agent(prompt, model_id):
    """Fetch tool definitions from the AgentCore Gateway."""
    gateway_url = os.environ.get("AGENT_GATEWAY_URL")
    print(f"Fetching MCP tools from gateway URL: {gateway_url}")

    if not gateway_url:
        print("AGENT_GATEWAY_URL not found in environment.")
        return []

    transport_factory = lambda: streamablehttp_client(
        url=gateway_url.rstrip("/"), auth=get_aws_auth()
    )
    print(
        f"Transport factory for MCPClient created with URL: {gateway_url.rstrip('/')}"
    )

    try:
        # We use list_tools_sync to populate the agent at startup
        with MCPClient(transport_factory) as client:
            print("Connected to MCP Gateway, fetching tools...")

            tools = client.list_tools_sync()
            print(f"Tools fetched: {tools}")

            for tool in tools:
                # Get the agent-facing name
                name = tool.tool_name

                # Get the full specification (Name, Description, Schema)
                spec = tool.tool_spec

                print(f"--- Tool: {name} ---")
                print(f"Description: {spec['description']}")
                print(f"Input Schema: {spec['inputSchema']['json']}")

            nova_model = BedrockModel(
                model_id=model_id,
                streaming=False,
            )

            strands_agent = Agent(
                model=nova_model,
                tools=tools,
                system_prompt=(
                    "You are a professional Nutritionist. Use the search_food tool "
                    "to provide nutritional information to the user."
                ),
            )
            try:
                return strands_agent(prompt)

            except Exception as run_err:
                print(f"Agent execution or tool invocation failed: {run_err}")
                return str(run_err)

    except Exception as e:
        print(f"Failed to fetch tools from gateway: {e}")
        return str(e)


class InvocationRequest(BaseModel):
    inputText: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    model_id: Optional[str] = "eu.amazon.nova-2-lite-v1:0"


@app.post("/invocations")
async def invoke(request: InvocationRequest):
    print("Invocation received with request:", request)

    # Support both Bedrock Agent and standard JSON formats
    prompt = request.inputText or (
        request.input.get("prompt") if request.input else None
    )
    print("Extracted prompt:", prompt)

    model_id = request.model_id or (
        request.input.get("model_id") if request.input else None
    )
    print(f"Extracted Model ID: {model_id}")

    result = query_agent(prompt, model_id)
    print("Agent result:", result)

    response_text = getattr(result, "content", str(result))
    print("Extracted response text:", response_text)

    return {
        "output": {"message": response_text, "model_id": model_id},
        "completion": response_text,
    }


@app.get("/ping")
async def ping():
    print("Ping received, returning healthy status.")
    return {"status": "healthy"}


if __name__ == "__main__":
    # Ensure port 8080 matches your Docker EXPOSE and CDK Runtime config
    uvicorn.run(app, host="0.0.0.0", port=8080)
