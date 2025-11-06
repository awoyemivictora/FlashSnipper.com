import requests
import os
from dotenv import load_env

load_env()

BITQUERY_WSS_URL = "https://streaming.bitquery.io/graphql"
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY")


def fetch_bitquery_data(query: str, variables: dict = {}):
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }

    # Define the payload for the request
    payload = {
        "query": query,
        "variables": variables
    }

    response = requests.post(BITQUERY_API_URL, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()  # Returns the data in JSON format
    else:
        raise Exception(f"Failed to fetch data: {response.status_code} - {response.text}")
