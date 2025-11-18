import grpc
import os
import asyncio
import logging
from app.generated.geyser_pb2 import GetVersionRequest
from app.generated.geyser_pb2_grpc import GeyserStub

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_grpc_channel(endpoint: str, token: str) -> grpc.aio.Channel:
    endpoint = endpoint.replace('http://', '').replace('https://', '')
    logging.info(f"Creating gRPC channel to {endpoint} with token: {token[:8]}...")
    auth_creds = grpc.metadata_call_credentials(
        lambda context, callback: callback((("x-token", token),), None)
    )
    ssl_creds = grpc.ssl_channel_credentials()
    options = (
        ('grpc.ssl_target_name_override', endpoint.split(':')[0]),
        ('grpc.default_authority', endpoint.split(':')[0]),
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.keepalive_permit_without_calls', 1),
    )
    combined_creds = grpc.composite_channel_credentials(ssl_creds, auth_creds)
    channel = grpc.aio.secure_channel(endpoint, combined_creds, options=options)
    logging.info(f"gRPC channel created: {endpoint}")
    return channel

async def test_grpc():
    grpc_url = os.getenv("GRPC_URL", "grpc.ams.shyft.to:443")
    grpc_token = os.getenv("GRPC_TOKEN", "30c7ef87-5bf0-4d70-be9f-3ea432922437")
    channel = create_grpc_channel(grpc_url, grpc_token)
    stub = GeyserStub(channel)
    try:
        response = await stub.GetVersion(GetVersionRequest())
        logging.info(f"Version: {response.version}")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        await channel.close()

if __name__ == "__main__":
    asyncio.run(test_grpc())
    
    
    