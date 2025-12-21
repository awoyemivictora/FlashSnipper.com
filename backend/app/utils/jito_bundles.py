import asyncio
import json 
import base64
from typing import List, Dict, Optional
from jito_py_rpc import JitoJsonRpcSDK
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction
from solders.hash import Hash
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class JitoBundleManager:
    """Advanced Jito bundle management for profitable sniper execution"""
    
    def __init__(self, block_engine_url: str = settings.JITO_BLOCK_ENGINE_URL):
        self.block_engine_url = block_engine_url
        self.sdk = None
        self.solana_client = None 
        
    async def initialize(self):
        """Initialize Jito SDK and Solana client"""
        try:
            # Initialize Jito SDK
            if not self.sdk:
                self.sdk = JitoJsonRpcSDK(self.block_engine_url)
                logger.info(f"✅ Jito SDK initialized: {self.block_engine_url}")
            
            # Initialize Solana client
            if not self.solana_client:
                self.solana_client = AsyncClient(settings.SOLANA_RPC_URL)
                logger.info(f"✅ Solana client initialized: {settings.SOLANA_RPC_URL}")
            
            logger.info(f"✅ Jito Bundle Manager initialized: {self.block_engine_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Jito Bundle Manager: {e}")
            return False
        
    async def create_bundle_with_tip(
        self,
        transactions: List[str], # List of base64 encoded transactions
        user_keypair: Keypair,
        tip_amount_lamports: int = settings.JITO_MIN_TIP_LAMPORTS # 0.000005 SOL tip
    ) -> Dict:
        """Create a bundle with Jito tip for priority execution"""
        try:
            # Get a random tip account from Jito
            tip_account_str = self.sdk.get_random_tip_account()
            if not tip_account_str:
                raise Exception("Failed to get tip account from Jito")
            
            tip_account = Pubkey.from_string(tip_account_str)
            
            # Create tip instruction
            tip_ix = transfer(TransferParams(
                from_pubkey=user_keypair.pubkey(),
                to_pubkey=tip_account,
                lamports=tip_amount_lamports
            ))
            
            # Get recent blockhash
            recent_blockhash = await self.solana_client.get_latest_blockhash()
            
            # Create tip transaction
            tip_message = Message.new_with_blockhash(
                [tip_ix],
                user_keypair.pubkey(),
                recent_blockhash.value.blockhash
            )
            tip_transaction = Transaction.new_unsigned(tip_message)
            tip_transaction.sign([user_keypair], recent_blockhash.value.blockhash)
            
            # Serialize tip transaction
            serialized_tip = base64.b64encode(bytes(tip_transaction)).decode('ascii')
            
            # Add tip transaction to the beginning of bundle
            full_bundle = [serialized_tip] + transactions
            
            logger.info(f"📦 Created bundle with {len(full_bundle)} transactions (including tip)")
            logger.info(f"💰 Jito tip: {tip_amount_lamports} lamports to {tip_account_str[:8]}...")
            
            return {
                "bundle": full_bundle,
                "tip_account": tip_account_str,
                "tip_amount": tip_amount_lamports
            }
            
        except Exception as e:
            logger.error(f"Failed to create bundle with tip: {e}")
            raise
        
    async def send_bundle_with_retry(
        self,
        bundle: List[str],
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Dict:
        """Send bundle with retry logic and optimal tip adjustment"""
        for attempt in range(max_retries):
            try:
                logger.info(f"📤 Sending Jito bundle (attempt {attempt + 1}/{max_retries})")
                
                # FIX: Jito SDK expects just the bundle array, NOT with encoding parameter
                # According to the example.py, it should be: sdk.send_bundle(params)
                # where params is just the list of base64 transactions
                result = self.sdk.send_bundle(bundle)
                
                # FIX: Proper error handling for None response
                if result is None:
                    logger.error(f"Jito SDK returned None response")
                    raise Exception("Jito SDK returned None response")
                
                # FIX: Check if 'success' key exists
                if 'success' not in result:
                    logger.error(f"Invalid Jito response structure: {result}")
                    raise Exception(f"Invalid Jito response: {result}")
                
                if result['success']:
                    # FIX: Handle nested data structure properly
                    if 'data' in result and 'result' in result['data']:
                        bundle_id = result['data']['result']
                        logger.info(f"✅ Bundle sent successfully. Bundle ID: {bundle_id}")
                        
                        return {
                            "success": True,
                            "bundle_id": bundle_id,
                            "data": result,
                            "attempt": attempt + 1
                        }
                    else:
                        logger.error(f"Malformed Jito response (missing data.result): {result}")
                        raise Exception(f"Malformed Jito response: {result}")
                else:
                    # FIX: Extract error properly
                    error_msg = result.get('error', 'Unknown error')
                    if isinstance(error_msg, dict):
                        error_msg = json.dumps(error_msg)
                    
                    logger.warning(f"Bundle send failed (attempt {attempt + 1}): {error_msg}")
                    
                    # Check for specific errors
                    error_str = str(error_msg).lower()
                    if "insufficient balance for tip" in error_str:
                        raise Exception(f"Insufficient balance for Jito tip: {error_msg}")
                    elif "400" in error_str or "bad request" in error_str:
                        logger.error(f"Bad request error - likely wrong bundle format")
                        # Don't retry on bad request
                        raise Exception(f"Bad request: {error_msg}")
                    elif "429" in error_str or "too many requests" in error_str:
                        logger.warning(f"Rate limited, waiting before retry...")
                        await asyncio.sleep(5)  # Longer wait for rate limits
                    
                    # Wait before retry
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Bundle send error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"All {max_retries} retries failed: {e}")
                
                # Wait before retry
                await asyncio.sleep(retry_delay * (attempt + 1))
    
    async def check_bundle_status(
        self,
        bundle_id: str,
        max_attempts: int = 30,
        delay: float = 2.0
    ) -> str:
        """Check bundle status with comprehensive monitoring"""
        for attempt in range(max_attempts):
            try:
                logger.debug(f"Checking bundle status {bundle_id} (attempt {attempt + 1}/{max_attempts})")
                
                # FIX: Use list format as shown in example.py
                response = self.sdk.get_inflight_bundle_statuses([bundle_id])
                
                if response is None:
                    logger.warning(f"None response from get_inflight_bundle_statuses")
                    await asyncio.sleep(delay)
                    continue
                
                if not response.get('success', False):
                    error_msg = response.get('error', 'Unknown error')
                    logger.warning(f"Error checking bundle status: {error_msg}")
                    await asyncio.sleep(delay)
                    continue
                
                # FIX: Handle response structure properly
                if 'data' not in response or 'result' not in response['data']:
                    logger.warning("Unexpected response structure - missing data.result")
                    await asyncio.sleep(delay)
                    continue
                
                result = response['data']['result']
                
                # According to the example, result should have 'value' key
                if 'value' not in result or not result['value']:
                    logger.debug(f"Bundle {bundle_id} not found in response")
                    await asyncio.sleep(delay)
                    continue
                
                bundle_status = result['value'][0]
                status = bundle_status.get('status', 'Unknown')
                
                logger.debug(f"Bundle {bundle_id} status: {status}")
                
                if status == "Landed":
                    logger.info(f"✅ Bundle {bundle_id} has landed on-chain!")
                    # Confirm finalization
                    final_status = await self.confirm_landed_bundle(bundle_id)
                    return final_status
                elif status == 'Failed':
                    logger.warning(f"❌ Bundle {bundle_id} has failed")
                    return 'Failed'
                elif status == 'Invalid':
                    if attempt < 5:
                        logger.debug(f"Bundle {bundle_id} is currently invalid, checking again...")
                    else:
                        logger.error(f"Bundle {bundle_id} is invalid (not in system or outside 5-minute window)")
                        return 'Invalid'
                elif status == 'Pending':
                    logger.debug(f"Bundle {bundle_id} is still pending...")
                else:
                    logger.warning(f"Unknown status '{status}' for bundle {bundle_id}")
                
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error checking bundle status: {e}")
                await asyncio.sleep(delay)
        
        logger.warning(f"Max attempts reached for bundle {bundle_id}")
        return 'Timeout'
    
    async def confirm_landed_bundle(
        self,
        bundle_id: str,
        max_attempts: int = 60,
        delay: float = 2.0
    ) -> str:
        """Confirm bundle has been finalized on-chain"""
        for attempt in range(max_attempts):
            try:
                logger.debug(f"Confirming bundle {bundle_id} (attempt {attempt + 1}/{max_attempts})")
                
                response = self.sdk.get_bundle_statuses([bundle_id])
                
                if not response or not response.get('success', False):
                    await asyncio.sleep(delay)
                    continue
                
                if 'data' not in response or 'result' not in response['data']:
                    await asyncio.sleep(delay)
                    continue 
                
                result = response['data']['result']
                if 'value' not in result or not result['value']:
                    await asyncio.sleep(delay)
                    continue
                
                bundle_status = result['value'][0]
                if bundle_status.get('bundle_id') != bundle_id:
                    await asyncio.sleep(delay)
                    continue
                
                status = bundle_status.get('confirmation_status')
                
                if status == 'finalized':
                    logger.info(f"🎉 Bundle {bundle_id} has been FINALIZED on-chain!")
                    
                    # Extract transaction IDs
                    if 'transactions' in bundle_status and bundle_status['transactions']:
                        tx_ids = bundle_status['transactions']
                        for tx_id in tx_ids:
                            logger.info(f"📄 Transaction: https://solscan.io/tx/{tx_id}")
                    
                    return 'Finalized'
                elif status == 'confirmed':
                    logger.debug(f"Bundle {bundle_id} confirmed but not yet finalized...")
                elif status == 'processed':
                    logger.debug(f"Bundle {bundle_id} processed but not yet confirmed...")
                else:
                    logger.debug(f"Unexpected status '{status}' during confirmation")
                    
                # Check for errors
                err = bundle_status.get('err', {}).get('Ok')
                if err is not None:
                    logger.error(f"Error in bundle {bundle_id}: {err}")
                    return 'Failed'
                
                await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error confirming bundle: {e}")
                await asyncio.sleep(delay)
        
        logger.warning(f"Max confirmation attempts reached for bundle {bundle_id}")
        return 'Landed'
    
    async def execute_jupiter_swap_with_jito(
        self,
        signed_transaction_base64: str,
        user_keypair: Keypair,
        label: str = "JITO_SWAP"
    ) -> Dict:
        """Execute Jupiter swap with Jito bundle for guaranteed execution"""
        try:
            logger.info(f"🚀 Executing {label} with Jito bundle...")
            
            # Create bundle with the Jupiter transaction
            bundle_data = await self.create_bundle_with_tip(
                transactions=[signed_transaction_base64],
                user_keypair=user_keypair,
                tip_amount_lamports=10000   # 0.00001 SOL tip
            )
            
            # Send bundle
            send_result = await self.send_bundle_with_retry(
                bundle=bundle_data["bundle"],
                max_retries=2
            )
            
            if not send_result.get("success", False):
                raise Exception(f"Failed to send Jito bundle: {send_result.get('error')}")
            
            bundle_id = send_result["bundle_id"]
            
            # Monitor bundle status
            logger.info(f"⏳ Monitoring Jito bundle {bundle_id} for {label}...")
            final_status = await self.check_bundle_status(bundle_id, max_attempts=15)
            
            if final_status == 'Finalized':
                # Extract signature from the original transaction
                try:
                    # Decode the original transaction to get signature
                    import base64
                    from solders.transaction import VersionedTransaction
                    
                    tx_bytes = base64.b64decode(signed_transaction_base64)
                    tx = VersionedTransaction.from_bytes(tx_bytes)
                    signature = str(tx.signatures[0]) if tx.signatures else f"jito_bundle_{bundle_id[:16]}"
                except:
                    signature = f"jito_bundle_{bundle_id[:16]}"
                
                logger.info(f"✅ Jito bundle executed successfully for {label}")
                
                return {
                    "status": "success",
                    "signature": signature,
                    "bundle_id": bundle_id,
                    "method": "jito_bundle",
                    "tip_amount": bundle_data["tip_amount"],
                    "final_status": final_status
                }
            else:
                raise Exception(f"Jito bundle failed with status: {final_status}")
            
        except Exception as e:
            logger.error(f"Jito bundle execution failed: {e}")
            raise
        
    async def close(self):
        """Cleanup resources"""
        if self.solana_client:
            await self.solana_client.close()

# Global Jito bundle manager instance
jito_manager = None 

async def get_jito_manager() -> JitoBundleManager:
    """Get or create global Jito bundle manager"""
    global jito_manager
    if jito_manager is None:
        jito_manager = JitoBundleManager()
        initialized = await jito_manager.initialize()
        if not initialized:
            raise Exception("Failed to initialize Jito Bundle Manager")
    return jito_manager



