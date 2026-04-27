"""AWS Step Functions client helpers for the Chef UI application.

Provides:
- :class:`StepFunctionsClient` — thin wrapper around ``boto3`` that starts an
  execution, polls asynchronously until it finishes, and extracts the chef's
  answer from the execution output.
"""

import asyncio
import json
import uuid

import boto3

from logging_config import get_logger

logger = get_logger(__name__)

# Seconds to wait between describe_execution calls while polling.
_POLL_INTERVAL: float = 5.0

# Terminal Step Functions execution statuses (anything other than RUNNING).
_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}


class StepFunctionsClient:
    """Async-friendly wrapper around the AWS Step Functions boto3 client.

    Args:
        region: AWS region name (e.g. ``"eu-central-1"``).
    """

    def __init__(self, region: str) -> None:
        self._client = boto3.client("stepfunctions", region_name=region)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start_execution(
        self,
        state_machine_arn: str,
        session_id: str,
        prompt: str,
    ) -> str:
        """Start a new Step Functions execution and return its ARN.

        Args:
            state_machine_arn: Full ARN of the target state machine.
            session_id: Chainlit session identifier used to build a unique
                execution name.
            prompt: The user's message to pass as workflow input.

        Returns:
            The execution ARN of the newly started execution.

        Raises:
            botocore.exceptions.ClientError: On any AWS API error.
        """
        execution_name = f"chef-ui-{session_id[:8]}-{uuid.uuid4().hex[:8]}"
        payload = json.dumps(
            {
                "input": {
                    "prompt": prompt,
                    "session_id": session_id,
                }
            }
        )

        logger.info(
            "Starting Step Functions execution",
            extra={
                "execution_name": execution_name,
                "state_machine_arn": state_machine_arn,
            },
        )

        response = self._client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=payload,
        )

        execution_arn: str = response["executionArn"]
        logger.info(
            "Execution started",
            extra={"execution_arn": execution_arn},
        )
        return execution_arn

    async def poll_until_complete(self, execution_arn: str) -> dict:
        """Poll ``describe_execution`` until the execution leaves RUNNING state.

        Uses :func:`asyncio.sleep` between polls so the Chainlit event loop
        remains responsive during the wait.

        Args:
            execution_arn: ARN of the execution to monitor.

        Returns:
            The final ``describe_execution`` response dict, with ``status``
            set to one of ``SUCCEEDED``, ``FAILED``, ``TIMED_OUT``, or
            ``ABORTED``.
        """
        logger.info(
            "Polling for execution completion",
            extra={"execution_arn": execution_arn},
        )

        while True:
            response = self._client.describe_execution(executionArn=execution_arn)
            status: str = response["status"]

            logger.debug(
                "Execution poll tick",
                extra={"execution_arn": execution_arn, "status": status},
            )

            if status in _TERMINAL_STATUSES:
                logger.info(
                    "Execution reached terminal status",
                    extra={"execution_arn": execution_arn, "status": status},
                )
                return response

            await asyncio.sleep(_POLL_INTERVAL)

    def extract_result(self, execution: dict) -> str | None:
        """Extract the chef's answer from a completed execution response.

        Tries several common output keys in order:
        ``completion`` → ``message`` → ``output.message`` → raw JSON dump.

        Args:
            execution: The ``describe_execution`` response dict returned by
                :meth:`poll_until_complete`.

        Returns:
            The chef's answer string, or ``None`` if the execution did not
            succeed.
        """
        status: str = execution.get("status", "UNKNOWN")

        if status != "SUCCEEDED":
            logger.warning(
                "Execution did not succeed",
                extra={
                    "status": status,
                    "cause": execution.get("cause"),
                    "error": execution.get("error"),
                },
            )
            return None

        raw_output = execution.get("output", "{}")
        try:
            output: dict = json.loads(raw_output)
        except json.JSONDecodeError:
            logger.error(
                "Could not parse execution output as JSON",
                extra={"raw_output": raw_output},
            )
            return raw_output

        answer = (
            output.get("completion")
            or output.get("message")
            or (output.get("output") or {}).get("message")
        )

        if answer is None:
            logger.warning(
                "No recognised answer field in execution output; returning raw JSON",
                extra={"output_keys": list(output.keys())},
            )
            return json.dumps(output)

        return answer
