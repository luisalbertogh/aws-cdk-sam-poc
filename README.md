# aws-cdk-poc

PoC con AWS CDK y AWS SAM para curso de Introducción al Cloud

## Project Setup

### AWS Account

1. Set up GitHub OIDC identity provider.
2. Create federated IAM role.

### GitHub Repository

1. New `AWS_ACCOUNT_ID` repository variable with AWS account ID number.

## Usage

### How to invoke the API

```
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/prod/chef \
  -H "x-api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"input": "Sugiereme un plato para cenar esta noche, por favor..."}'
```
