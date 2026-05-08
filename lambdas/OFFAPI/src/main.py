import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import requests
from pydantic import BaseModel, ConfigDict, Field

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# AWS Lambda Powertools Logger setup
logger = Logger()

class FoodNutritionalInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, alias="product_name")
    brand: Optional[str] = Field(None, alias="brands")
    calories_100g: Optional[float] = Field(None, alias="energy-kcal_100g")
    nutriments: Dict[str, float | int | str | None] = Field(default_factory=dict)


class FoodList(BaseModel):
    products: List[FoodNutritionalInfo]


class OpenFoodFactsAPI:
    PROD_URL = os.environ.get("OFF_PROD_URL", "https://es.openfoodfacts.org/cgi/search.pl")
    STAGING_URL = os.environ.get("OFF_STAGING_URL", "https://es.openfoodfacts.net/cgi/search.pl")

    def __init__(self, app_name: str, version: str, email: str, is_staging: bool = True):
        self.is_staging = is_staging
        self.url = self.STAGING_URL if is_staging else self.PROD_URL
        self.headers = {"User-Agent": f"{app_name}/{version} ({email})"}
        self.auth = ("off", "off") if is_staging else None

    def search(self, product_name: str, limit: int = 5) -> FoodList:
        params = {
            "search_terms": product_name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
            "fields": "product_name,brands,nutriments",
        }

        try:
            response = requests.get(
                self.url, headers=self.headers, params=params, auth=self.auth
            )
            response.raise_for_status()
            data = response.json()
            return FoodList(**data)
        except Exception as e:
            return FoodList(products=[])


# Global Initialization
searcher = OpenFoodFactsAPI(
    app_name="MyCloudFitnessApp",
    version="1.0",
    email="admin@example.com",
    is_staging=True,
)


@logger.inject_lambda_context
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Handles multiple product names. 
    Accepts: {"product_names": ["milk", "bread"], "limit": 3} 
    or backward compatible: {"product_name": "milk", "limit": 3}
    """    
    arguments = event.get("arguments", {})
    if not arguments:
        arguments = json.loads(event["body"]) if isinstance(event.get("body"), str) else event

    # Extract names: handle both 'product_name' (str) and 'product_names' (list)
    raw_names = arguments.get("product_names") or arguments.get("product_name")
    limit = arguments.get("limit", 5)

    if not raw_names:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing product_name or product_names"}),
        }

    # Normalize to a list for uniform processing
    product_list = [raw_names] if isinstance(raw_names, str) else raw_names
    
    # Process each product
    final_results = {}
    for name in product_list:
        search_data = searcher.search(name, limit)
        final_results[name] = search_data.model_dump()

    return {
        "statusCode": 200,
        "body": json.dumps(final_results)
    }


@dataclass
class MockLambdaContext:
    """Minimal Lambda context for local testing."""
    function_name: str = "offapi-local"
    function_version: str = "$LATEST"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:offapi-local"
    aws_request_id: str = field(default_factory=lambda: "local-request-id")
    log_group_name: str = "/aws/lambda/offapi-local"
    log_stream_name: str = "2024/01/01/[$LATEST]local"


def main():
    """Testing with multiple products."""
    event = {
        "arguments": {
            "product_names": ["milk", "eggs"],
            "limit": 2,
        }
    }
    response = lambda_handler(event, MockLambdaContext())
    print(json.dumps(json.loads(response["body"]), indent=2))


if __name__ == "__main__":
    main()
