FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

# Copy the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Optimization: Use the system python environment and compile to bytecode
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

# Use a cache mount to persist the uv cache between builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install \
    fastapi \
    uvicorn \
    pydantic \
    strands-agents \
    boto3

COPY agent.py .
EXPOSE 8080

CMD ["python", "agent.py"]