# Chef App Lambda

Mock chef agent that provides dish suggestions. This Lambda function is part of the Commission Chef Assistant POC.

## Project Setup

For `uv` installation see [here](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).

- Check available Python versions with `uv python list`
- Install a new Python version with `uv python install 3.12`
- Create virtual environment with specific Python version with `uv venv --python 3.12`
  - Alternatively, use `uv init` to kick off an empty Python project with a virtual environment.
- Activate virtual environment with `.venv/Scripts/activate`
- Check Python version with `python --version`
- Use `uv sync` to update Python dependencies defined under `pyproject.toml`

## Testing

Run the unit tests with:

```bash
uv run pytest tests/test_main.py -v
```

For test coverage:

```bash
uv run pytest tests/test_main.py --cov=src --cov-report=html
```

## Local Testing

You can test the Lambda function locally by running:

```bash
uv run python src/main.py
```

## AWS SAM Deployment

### Prerequisites

- [AWS SAM CLI installed](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- AWS credentials configured
- S3 bucket for deployment artifacts (will be created automatically during first deploy)

### Build

Build the Lambda function and layer:

```bash
sam build
```

### Deploy

Deploy to AWS using the configuration in `samconfig.toml`:

```bash
sam deploy
```

For first-time deployment or to customize settings:

```bash
sam deploy --guided
```

This will create:
- Lambda function: `AgentCorePocChefAppStack-ChefApp`
- IAM Role: `AgentCorePocChefAppStack-ChefAppRole`
- CloudWatch Log Group: `/aws/lambda/AgentCorePocChefAppStack-ChefApp`
- Lambda Layer: `chefapp-common-dependencies` (with aws-lambda-powertools and pydantic)

### Testing Deployed Lambda

Invoke the deployed Lambda function:

```bash
sam remote invoke ChefAppFunction --stack-name AgentCorePocChefAppStack \
  --event '{"input": {"plato": "cena ligera"}}'
```

Or using AWS CLI:

```bash
aws lambda invoke \
  --function-name AgentCorePocChefAppStack-ChefApp \
  --payload '{"input": {"plato": "comida vegetariana"}}' \
  response.json
```

### Cleanup

Delete the deployed stack:

```bash
sam delete --stack-name AgentCorePocChefAppStack
```

## Lambda Function Input/Output

### Input Format

The Lambda accepts input in multiple formats:

1. With `input` key (recommended):
```json
{
  "input": {
    "plato": "sugerencia para cenar"
  }
}
```

2. As JSON string in `body`:
```json
{
  "body": "{\"plato\": \"comida rápida\"}"
}
```

3. Direct event format:
```json
{
  "plato": "desayuno saludable"
}
```

### Output Format

```json
{
  "statusCode": 200,
  "body": "{\"plato\": {\"plato\": \"sugerencia para cenar\"}, \"sugerencias\": [\"Ensalada César con pollo a la parrilla\", \"Pasta al pesto con tomates cherry\", \"Salmón al horno con espárragos\"]}"
}
```