import { Keypair } from '@solana/web3.js';
import { apiService } from './api';
import { Buffer } from 'buffer';
import nacl from 'tweetnacl';
import { encrypt } from '@/utils/crypto';

// Request tracking to prevent duplicates
const pendingRequests = new Map<string, Promise<any>>();

// Fetch nonce from backend
export const getNonce = async (): Promise<{ nonce_id: string; nonce: string }> => {
  const cacheKey = 'get-nonce';
  
  // Return existing pending request if any
  if (pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey)!;
  }

  try {
    const request = apiService.request('/auth/get-nonce', {
      method: 'GET',
    });
    
    pendingRequests.set(cacheKey, request);
    const response = await request;
    console.log('Nonce response:', response);
    return response;
  } catch (error) {
    console.error('Failed to fetch nonce:', error);
    throw new Error(`Failed to fetch nonce: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    pendingRequests.delete(cacheKey);
  }
};

// Verify wallet by signing the nonce
export const verifyWallet = async (
  walletAddress: string,
  privateKey: Uint8Array,
  nonceData: { nonce_id: string; nonce: string }
): Promise<void> => {
  const cacheKey = `verify-${walletAddress}-${nonceData.nonce_id}`;
  
  if (pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey)!;
  }

  try {
    const message = new TextEncoder().encode(nonceData.nonce);
    const keypair = Keypair.fromSecretKey(privateKey);
    const signature = nacl.sign.detached(message, keypair.secretKey);
    const signatureHex = Buffer.from(signature).toString('hex');

    // SEND AS JSON BODY — NOT QUERY STRING
    const request = apiService.request('/auth/verify-wallet', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        wallet_address: walletAddress,
        signature: signatureHex,
        nonce_id: nonceData.nonce_id,
      }),
    });

    pendingRequests.set(cacheKey, request);
    const response = await request;
    console.log('Wallet verified successfully:', response);
  } catch (error) {
    console.error('Wallet verification error:', error);
    throw new Error(`Wallet verification failed: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    pendingRequests.delete(cacheKey);
  }
};

// Register wallet with encrypted private key
export const registerWallet = async (walletAddress: string, privateKey: Uint8Array): Promise<void> => {
  const cacheKey = `register-${walletAddress}`;
  
  // Return existing pending request if any
  if (pendingRequests.has(cacheKey)) {
    return pendingRequests.get(cacheKey)!;
  }

  try {
    const { key_id, key } = await apiService.request('/auth/get-frontend-encryption-key', {
      method: 'GET',
    });
    console.log('Encryption key fetched:', { key_id });

    const privateKeyBase64 = Buffer.from(privateKey).toString('base64');
    const encryptedPrivateKey = await encrypt(privateKeyBase64, key);

    const request = apiService.request('/auth/register-or-login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        wallet_address: walletAddress,
        encrypted_private_key_bundle: encryptedPrivateKey,
        key_id,
      }),
    });

    pendingRequests.set(cacheKey, request);
    const response = await request;
    console.log('Wallet registration response:', response);

    localStorage.setItem('authToken', response.access_token);
  } catch (error) {
    console.error('Wallet registration error:', error);
    throw new Error(`Wallet registration failed: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    pendingRequests.delete(cacheKey);
  }
};