import json

import pytest

from main import MockLambdaContext


@pytest.fixture()
def context():
    """Provides a mock Lambda context for testing."""
    return MockLambdaContext()


# ---------------------------------------------------------------------------
# lambda_handler tests
# ---------------------------------------------------------------------------

class TestLambdaHandlerInputFormat:
    """Test the Lambda handler with different input formats."""

    def test_returns_200_with_dish_suggestions(self, context):
        """Test that the handler returns dish suggestions when 'plato' is in input."""
        from main import lambda_handler

        event = {"input": {"plato": "sugerencia para cenar"}}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        
        # Check that suggestions are present
        assert "sugerencias" in body
        assert isinstance(body["sugerencias"], list)
        assert len(body["sugerencias"]) == 3
        
        # Verify the expected dish suggestions
        assert "Pasta" in body["sugerencias"]
        assert "Paella" in body["sugerencias"]
        assert "Lentejas" in body["sugerencias"]

    def test_handles_body_with_json_string(self, context):
        """Test that the handler can parse JSON from body field."""
        from main import lambda_handler

        event = {
            "body": json.dumps({"plato": "comida rápida"})
        }
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "sugerencias" in body
        assert len(body["sugerencias"]) == 3

    def test_handles_direct_event_format(self, context):
        """Test backward compatibility with direct event format (no 'input' key)."""
        from main import lambda_handler

        event = {"plato": "desayuno saludable"}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "sugerencias" in body

    def test_preserves_input_in_response(self, context):
        """Test that the original input is included in the response."""
        from main import lambda_handler

        input_data = {"plato": "cena ligera"}
        event = {"input": input_data}
        response = lambda_handler(event, context)

        body = json.loads(response["body"])
        assert "plato" in body
        assert body["plato"] == input_data


class TestLambdaHandlerEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_input_returns_response(self, context):
        """Test handler behavior with empty input."""
        from main import lambda_handler

        event = {"input": {}}
        response = lambda_handler(event, context)

        # The function should handle this gracefully
        assert response["statusCode"] == 200

    def test_missing_input_key_uses_event_body(self, context):
        """Test that missing 'input' falls back to parsing body."""
        from main import lambda_handler

        event = {
            "body": json.dumps({"plato": "almuerzo"})
        }
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "sugerencias" in body
