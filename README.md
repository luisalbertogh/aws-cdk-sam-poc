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

## Improvements

### Integration with chat application

1. Create a new API method that invokes a Lambda function via a GET REST API method.
2. The Lambda function will check the Step Function status. If finished, it will retrieve the output. If not, it will indicate that the work is still in progress.
3. The REST API method will return the output of the Lambda function to the caller.
4. Our client will invoke the REST API method to check the status of the process and retrieve the output if finished.
