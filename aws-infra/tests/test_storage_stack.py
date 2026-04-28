"""
Unit tests for StorageStack.

Uses CDK assertions (fine-grained) to validate the synthesised
CloudFormation template without deploying to AWS.
"""

import aws_cdk as cdk
import pytest
from aws_cdk import assertions

from stacks import StorageStack


@pytest.fixture(scope="module")
def template() -> assertions.Template:
    """Synthesise the StorageStack and return the assertions template."""
    app = cdk.App()
    stack = StorageStack(
        app,
        "TestStorageStack",
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return assertions.Template.from_stack(stack)


class TestS3BucketProperties:
    def test_bucket_is_created(self, template: assertions.Template) -> None:
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_encryption_at_rest(self, template: assertions.Template) -> None:
        """Bucket must use SSE-S3 (AES256) encryption."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {
                            "ServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256"
                            }
                        }
                    ]
                }
            },
        )

    def test_versioning_disabled(self, template: assertions.Template) -> None:
        """Versioning must NOT be enabled."""
        # CDK only emits VersioningConfiguration when versioning is enabled;
        # if it's absent the bucket has no versioning — which is what we want.
        buckets = template.find_resources("AWS::S3::Bucket")
        for bucket in buckets.values():
            props = bucket.get("Properties", {})
            versioning = props.get("VersioningConfiguration", {})
            status = versioning.get("Status", "Suspended")
            assert status != "Enabled", "Versioning must not be enabled"

    def test_public_access_blocked(self, template: assertions.Template) -> None:
        """All four public-access block settings must be True."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                }
            },
        )

    def test_object_ownership_bucket_owner_enforced(
        self, template: assertions.Template
    ) -> None:
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {"OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}},
        )


class TestBucketPolicy:
    def test_ssl_deny_policy_exists(self, template: assertions.Template) -> None:
        """A bucket policy denying non-HTTPS requests must be present."""
        template.resource_count_is("AWS::S3::BucketPolicy", 1)

    def test_ssl_deny_statement(self, template: assertions.Template) -> None:
        """The bucket policy must contain an explicit DENY on aws:SecureTransport=false."""
        template.has_resource_properties(
            "AWS::S3::BucketPolicy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with(
                        [
                            assertions.Match.object_like(
                                {
                                    "Action": "s3:*",
                                    "Effect": "Deny",
                                    "Condition": {
                                        "Bool": {"aws:SecureTransport": "false"}
                                    },
                                }
                            )
                        ]
                    )
                }
            },
        )


class TestOutputs:
    def test_bucket_name_output(self, template: assertions.Template) -> None:
        template.has_output("BucketName", {})

    def test_bucket_arn_output(self, template: assertions.Template) -> None:
        template.has_output("BucketArn", {})
