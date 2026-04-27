import json
from unittest.mock import MagicMock, patch

import pytest

from main import MockLambdaContext


MOCK_PRODUCTS_RESPONSE = {
    "products": [
        {
            "product_name": "Nutella",
            "brands": "Ferrero",
            "nutriments": {
                "energy-kcal_100g": 530.0,
                "fat_100g": 30.9,
                "sugars_100g": 56.3,
            },
        },
        {
            "product_name": "Nutella B-ready",
            "brands": "Ferrero",
            "nutriments": {
                "energy-kcal_100g": 496.0,
                "fat_100g": 24.1,
                "sugars_100g": 38.0,
            },
        },
    ]
}

MOCK_EMPTY_RESPONSE = {"products": []}


@pytest.fixture()
def mock_requests_get():
    """Patch requests.get used inside OpenFoodFactsAPI.search."""
    with patch("main.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = MOCK_PRODUCTS_RESPONSE
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture()
def context():
    return MockLambdaContext()


# ---------------------------------------------------------------------------
# lambda_handler tests
# ---------------------------------------------------------------------------

class TestLambdaHandlerArgumentsFormat:
    """MCP / AgentCore Gateway format: parameters inside 'arguments' key."""

    def test_returns_200_with_multiple_products(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"arguments": {"product_names": ["milk", "eggs"], "limit": 3}}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        
        # Check that both products exist as keys
        assert "milk" in body
        assert "eggs" in body
        assert len(body["milk"]["products"]) == 2
        # Ensure requests were made for each
        assert mock_requests_get.call_count == 2

    def test_backward_compatibility_single_product(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"arguments": {"product_name": "Nutella", "limit": 3}}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        
        # The key in the response dictionary will be the product name requested
        assert "Nutella" in body
        # Inside the product list, Pydantic uses the field name 'name' unless told otherwise
        assert body["Nutella"]["products"][0]["name"] == "Nutella"

    def test_default_limit_is_applied(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"arguments": {"product_name": "Nutella"}}
        lambda_handler(event, context)

        _, kwargs = mock_requests_get.call_args
        assert kwargs["params"]["page_size"] == 5

    def test_custom_limit_is_forwarded(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"arguments": {"product_name": "Nutella", "limit": 2}}
        lambda_handler(event, context)

        _, kwargs = mock_requests_get.call_args
        assert kwargs["params"]["page_size"] == 2


class TestLambdaHandlerDirectEventFormat:
    """Direct invocation / API Gateway proxy test (flat event body)."""

    def test_flat_event_falls_back_to_root_keys(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"product_names": ["milk"], "limit": 3}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "milk" in body

    def test_api_gateway_string_body_is_parsed(self, mock_requests_get, context):
        from main import lambda_handler

        event = {"body": json.dumps({"product_name": "Nutella", "limit": 2})}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 200


class TestLambdaHandlerValidation:
    """Input validation cases."""

    def test_missing_product_name_returns_400(self, context):
        from main import lambda_handler

        # Sent limit but no product_name or product_names
        event = {"arguments": {"limit": 5}}
        response = lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        # Check for the specific error message logic in your main.py
        assert "missing product_name" in body["error"].lower()

    def test_empty_arguments_and_no_product_name_returns_400(self, context):
        from main import lambda_handler

        # Completely empty event
        response = lambda_handler({}, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body


# ---------------------------------------------------------------------------
# OpenFoodFactsAPI.search tests
# ---------------------------------------------------------------------------

class TestOpenFoodFactsAPISearch:
    """Unit tests for the search method in isolation."""

    def test_returns_food_list_on_success(self, mock_requests_get):
        from main import OpenFoodFactsAPI

        api = OpenFoodFactsAPI("TestApp", "1.0", "test@example.com", is_staging=True)
        result = api.search("Nutella", limit=3)

        assert len(result.products) == 2
        # Use .name here because Pydantic alias maps 'product_name' to 'name'
        assert result.products[0].name == "Nutella"

    def test_returns_empty_list_on_request_exception(self):
        from main import OpenFoodFactsAPI

        with patch("main.requests.get", side_effect=Exception("Network error")):
            api = OpenFoodFactsAPI("TestApp", "1.0", "test@example.com", is_staging=True)
            result = api.search("Nutella")

        assert result.products == []

    def test_uses_staging_url_when_flagged(self, mock_requests_get):
        from main import OpenFoodFactsAPI

        api = OpenFoodFactsAPI("TestApp", "1.0", "test@example.com", is_staging=True)
        api.search("Nutella")

        url_called = mock_requests_get.call_args[0][0]
        assert "openfoodfacts.net" in url_called

    def test_uses_prod_url_when_not_staging(self, mock_requests_get):
        from main import OpenFoodFactsAPI

        api = OpenFoodFactsAPI("TestApp", "1.0", "test@example.com", is_staging=False)
        api.search("Nutella")

        url_called = mock_requests_get.call_args[0][0]
        assert "openfoodfacts.org" in url_called

    def test_search_term_is_forwarded_in_params(self, mock_requests_get):
        from main import OpenFoodFactsAPI

        api = OpenFoodFactsAPI("TestApp", "1.0", "test@example.com")
        api.search("Coca Cola", limit=10)

        _, kwargs = mock_requests_get.call_args
        assert kwargs["params"]["search_terms"] == "Coca Cola"
        assert kwargs["params"]["page_size"] == 10
