FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

# Install uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_SYSTEM_PYTHON=1

# Install dependencies using a cache mount for ultra-fast subsequent builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
    fastapi \
    uvicorn \
    pydantic \
    strands-agents \
    mcp \
    boto3 \
    mcp-proxy-for-aws \
    httpx-aws-auth

COPY agent.py .
EXPOSE 8080
CMD ["python", "agent.py"]