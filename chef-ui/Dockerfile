# Use an appropriate base image, e.g., python:3.10-slim
FROM ghcr.io/astral-sh/uv:0.11.6-python3.12-alpine

# Set environment variables (e.g., set Python to run in unbuffered mode)
ENV PYTHONUNBUFFERED=1
# Tell uv to install into the system Python instead of creating a virtualenv.
# This is the recommended approach for Docker containers.
ENV UV_SYSTEM_PYTHON=1

# Set the working directory
WORKDIR /app

# Copy uv files
COPY pyproject.toml ./

# Install dependencies directly into the system Python (no virtualenv)
RUN uv pip install --no-cache .

# Copy your application code into the container
ADD src/public /app/public
ADD src/.chainlit /app/.chainlit
ADD src/templates /app/templates
COPY src/* /app/

EXPOSE 8080

CMD ["python", "-m", "chainlit", "run", "app.py", "-h", "--host", "0.0.0.0", "--port", "8080"]