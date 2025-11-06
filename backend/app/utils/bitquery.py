#-------- Utility functions for API calls -----------
import requests
from datetime import datetime 
from typing import Dict, Any
import os
from dotenv import load_env

load_env()

BITQUERY_WSS_URL = "https://streaming.bitquery.io/graphql"
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")


def fetch_bitquery_data(query: str, variables: Dict[str, Any]) -> Dict:
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": BITQUERY_API_KEY,
    }
    response = requests.post(
        BITQUERY_WSS_URL,
        json={"query": query, "variables": variables},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def format_timestamp(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))



