from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from strands import Agent
from strands.models import BedrockModel
import uvicorn

app = FastAPI(title="Chef Agent")

# Strands will automatically look for AWS credentials in the environment
nova_model = BedrockModel(
    model_id="eu.amazon.nova-lite-v1:0",
    streaming=False  # This prevents the 'InvokeModelWithResponseStream' requirement
)

strands_agent = Agent(
    model=nova_model,
    system_prompt="You are a professional Master Chef. Help users giving a list of three recipes."
)

class InvocationRequest(BaseModel):
    inputText: Optional[str] = None
    input: Optional[Dict[str, Any]] = None

@app.post("/invocations")
async def invoke(request: InvocationRequest):
    prompt = request.inputText or (request.input.get("prompt") if request.input else None)
    
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing prompt in inputText or input.prompt")
    
    try:
        result = strands_agent(prompt)
        response_text = getattr(result, "content", str(result))
        
        return {
            "output": {
                "message": response_text, 
            },
                "completion": response_text
        }
    except Exception as e:
        # Catching potential Strands/Bedrock API issues
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

@app.get("/ping")
async def ping(): 
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
