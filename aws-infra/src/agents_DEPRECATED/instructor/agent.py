import asyncio
import os
from typing import Any, Dict, Optional

import boto3
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands_tools.browser import AgentCoreBrowser

app = FastAPI(title="Instructor Agent")


# 1. Credential Injection for Managed Environment (Step Functions/Runtime)
def setup_runtime_credentials():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    session = boto3.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()

    # Injecting directly into os.environ so the internal
    # bedrock-agentcore client finds them immediately.
    os.environ["AWS_ACCESS_KEY_ID"] = creds.access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds.secret_key
    if creds.token:
        os.environ["AWS_SESSION_TOKEN"] = creds.token

    return region


# Initialize credentials and global objects
current_region = setup_runtime_credentials()

# Use Nova-Pro if possible (lite may struggle with complex browser steps)
# but staying with Lite as per your original requirement.
nova_model = BedrockModel(model_id="eu.amazon.nova-2-lite-v1:0", streaming=False)

# Initialize Browser tool
agentcore_browser = AgentCoreBrowser(region=current_region)

# Create the Agent
instructor_agent = Agent(
    model=nova_model,
    system_prompt=(
        "You are a professional culinary instructor. When asked for a recipe, "
        "you MUST immediately use the browser tool to find results in https://en.wikibooks.org/wiki/Cookbook. "
        "Do not ask for permission. Do not explain your protocols. "
        "And at the end of your response give me references of the links in the format: [Web name/title](URL). "
        "MANDATORY: For the 'session_name' parameter, use for example 'paella-search-task'."
        "CRITICAL: When initiating a browser session, the session_name must "
        "ONLY contain lowercase letters, numbers, and hyphens. "
        "Do NOT use underscores or spaces in the session name."
    ),
    tools=[agentcore_browser.browser],
)


class InvocationRequest(BaseModel):
    inputText: Optional[str] = None
    input: Optional[Dict[str, Any]] = None


@app.post("/invocations")
async def invoke(request: InvocationRequest):
    prompt = request.inputText or (
        request.input.get("prompt") if request.input else None
    )

    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt")

    try:
        # CRITICAL: Use invoke_async as shown in the tutorial.
        # Browser tools are inherently asynchronous (Playwright/CDP).
        response = await instructor_agent.invoke_async(prompt)

        # Extract response text safely
        content_list = response.message.get("content", [])
        response_text = ""
        for item in content_list:
            if "text" in item:
                response_text += item["text"]

        return {"output": {"message": response_text}, "completion": response_text}
    except Exception as e:
        print(f"Agent Runtime Error: {str(e)}")
        # If running in Step Functions, logging the full error is helpful
        raise HTTPException(status_code=500, detail=f"Browser Agent Error: {str(e)}")


@app.get("/ping")
async def ping():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
