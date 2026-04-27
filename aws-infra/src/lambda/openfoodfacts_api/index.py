import json
import logging
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, ConfigDict, Field


class FoodNutritionalInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None, alias="product_name")
    brand: Optional[str] = Field(None, alias="brands")
    calories_100g: Optional[float] = Field(None, alias="energy-kcal_100g")
    nutriments: Dict[str, float | int | str | None] = Field(default_factory=dict)


class FoodList(BaseModel):
    products: List[FoodNutritionalInfo]


class OpenFoodFactsAPI:
    PROD_URL = "https://world.openfoodfacts.org/cgi/search.pl"
    STAGING_URL = "https://world.openfoodfacts.net/cgi/search.pl"

    def __init__(
        self, app_name: str, version: str, email: str, is_staging: bool = True
    ):
        self.is_staging = is_staging
        self.url = self.STAGING_URL if is_staging else self.PROD_URL
        self.headers = {"User-Agent": f"{app_name}/{version} ({email})"}
        self.auth = ("off", "off") if is_staging else None

        # In Lambda, we use the root logger or get a specific one
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

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
            logging.error(f"Error fetching data: {e}")
            return FoodList(products=[])


# Global Initialization (Optimizes performance for warm starts)
searcher = OpenFoodFactsAPI(
    app_name="MyFitnessApp",
    version="1.0",
    email="admin@example.com",
    is_staging=True,  # Switch to False for production
)


# Lambda Handler
def lambda_handler(event, context):
    """
    Modified for AgentCore Gateway (MCP Protocol).
    The Gateway passes parameters inside an 'arguments' dictionary.
    Expects event: {"product_name": "Nutella", "limit": 5}
    """
    # Identify where the data is coming from
    # Gateway (MCP) format usually places tool arguments here:
    arguments = event.get("arguments", {})
    
    # Fallback for direct/API Gateway testing
    if not arguments:
        if isinstance(event.get("body"), str):
            arguments = json.loads(event["body"])
        else:
            arguments = event

    product_name = arguments.get("product_name")
    limit = arguments.get("limit", 5)

    if not product_name:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing product_name"}),
        }

    results = searcher.search(product_name, limit)

    # AgentCore expects a specific response structure for tools
    return {
        "statusCode": 200,
        "body": results.model_dump_json()
    }
