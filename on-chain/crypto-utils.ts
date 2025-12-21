import bs58 from 'bs58';

export class CryptoUtils {
    
    static decodeBase58PrivateKey(encodedKey: string): Uint8Array {
        try {
            const decoded = bs58.decode(encodedKey);
            if (decoded.length === 64) {
                return new Uint8Array(decoded);
            }
            throw new Error(`Invalid key length: ${decoded.length}, expected 64`);
        } catch (error) {
            throw new Error(`Failed to decode base58 private key: ${error.message}`);
        }
    }
    
    // Simple validation for base58 keys
    static isValidBase58Key(key: string): boolean {
        try {
            const decoded = bs58.decode(key);
            return decoded.length === 64;
        } catch {
            return false;
        }
    }
}

