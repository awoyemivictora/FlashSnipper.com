// src/utils/crypto.ts
import { Buffer } from 'buffer';

// Helper: Convert URL-safe base64 to standard base64
const urlSafeToStandard = (input: string): string => {
  return input.replace(/-/g, '+').replace(/_/g, '/');
};

// Helper: Add padding if missing
const fixPadding = (input: string): string => {
  const padding = input.length % 4;
  if (padding) {
    return input + '='.repeat(4 - padding);
  }
  return input;
};

export const encrypt = async (message: string, fernetKeyBase64: string): Promise<string> => {
  console.log('Encrypting message:', { messageLength: message.length });

  try {
    // FIX: Handle URL-safe base64 from backend
    const cleanKey = fixPadding(urlSafeToStandard(fernetKeyBase64));
    const keyData = Uint8Array.from(atob(cleanKey), c => c.charCodeAt(0));

    if (keyData.length !== 32) {
      throw new Error(`Invalid key length: ${keyData.length} bytes (expected 32)`);
    }

    const signingKey = keyData.slice(0, 16);
    const encryptionKey = keyData.slice(16);

    const iv = crypto.getRandomValues(new Uint8Array(16));
    const timestamp = Math.floor(Date.now() / 1000);
    const timestampBytes = new Uint8Array(8);
    new DataView(timestampBytes.buffer).setBigUint64(0, BigInt(timestamp), false);

    const encoder = new TextEncoder();
    const data = encoder.encode(message);

    // PKCS7 padding
    const blockSize = 16;
    const padding = blockSize - (data.length % blockSize);
    const padded = new Uint8Array(data.length + padding);
    padded.set(data);
    padded.fill(padding, data.length);

    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      encryptionKey,
      { name: 'AES-CBC' },
      false,
      ['encrypt']
    );

    const ciphertext = new Uint8Array(
      await crypto.subtle.encrypt(
        { name: 'AES-CBC', iv },
        cryptoKey,
        padded
      )
    );

    // Build pre-HMAC payload
    const version = new Uint8Array([0x80]);
    const preHmac = new Uint8Array(version.length + timestampBytes.length + iv.length + ciphertext.length);
    let offset = 0;
    preHmac.set(version, offset); offset += 1;
    preHmac.set(timestampBytes, offset); offset += 8;
    preHmac.set(iv, offset); offset += 16;
    preHmac.set(ciphertext, offset);

    // HMAC-SHA256
    const hmacKey = await crypto.subtle.importKey(
      'raw',
      signingKey,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const signature = new Uint8Array(await crypto.subtle.sign('HMAC', hmacKey, preHmac));

    // Combine all
    const token = new Uint8Array(preHmac.length + signature.length);
    token.set(preHmac, 0);
    token.set(signature, preHmac.length);

    // Base64URL encode (Fernet standard)
    const base64Url = btoa(String.fromCharCode(...token))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');

    console.log('Fernet token generated (valid):', base64Url.substring(0, 60) + '...');
    return base64Url;

  } catch (error) {
    console.error('Encryption failed:', error);
    throw error;
  }
};