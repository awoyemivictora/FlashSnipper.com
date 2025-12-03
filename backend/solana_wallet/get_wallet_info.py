# get_wallet_info.py
import json
import base58
import sys
import os

def get_wallet_info(wallet_path):
    """Get wallet public and private key from keypair file"""
    
    try:
        with open(wallet_path, 'r') as f:
            data = json.load(f)
        
        print(f"📁 Wallet file: {wallet_path}")
        print("=" * 50)
        
        # Handle different Solana keypair formats
        if isinstance(data, list):
            # Format 1: Array of numbers [1,2,3,...]
            print("Format: Array (old format)")
            private_key_bytes = bytes(data)
            
            # Derive public key (we'll generate it)
            from solders.keypair import Keypair
            keypair = Keypair.from_bytes(list(data))
            pubkey = str(keypair.pubkey())
            
        elif 'pubkey' in data and 'secret_key' in data:
            # Format 2: Object with pubkey and secret_key
            print("Format: Object with pubkey/secret_key")
            pubkey = data['pubkey']
            secret_key = data['secret_key']
            
            if isinstance(secret_key, list):
                private_key_bytes = bytes(secret_key)
            else:
                private_key_bytes = bytes(secret_key, 'utf-8') if isinstance(secret_key, str) else bytes(secret_key)
                
        else:
            print("❌ Unknown wallet format")
            return
        
        # Convert to base58
        private_key_base58 = base58.b58encode(private_key_bytes).decode('utf-8')
        
        print(f"🔑 Public Key: {pubkey}")
        print(f"🔐 Private Key (base58): {private_key_base58}")
        print(f"📏 Length: {len(private_key_base58)} characters")
        
        # Show first/last for verification
        print(f"\n📋 First 50 chars: {private_key_base58[:50]}...")
        print(f"📋 Last 50 chars: ...{private_key_base58[-50:]}")
        
        print("\n📝 ADD TO YOUR .env FILE:")
        print(f"BOT_OWNER_WALLET={pubkey}")
        print(f"BOT_OWNER_PRIVATE_KEY={private_key_base58}")
        
        return pubkey, private_key_base58
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    # Try different possible paths
    paths_to_try = [
        '/Users/user/.config/solana/fee_wallet.json',
        '/Users/user/.config/solana/id.json',
        'fee_wallet.json',
        os.path.expanduser('~/.config/solana/id.json')
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            print(f"✅ Found wallet at: {path}")
            get_wallet_info(path)
            break
    else:
        print("❌ No wallet found. Creating new one...")
        
        # Create new wallet
        from solders.keypair import Keypair
        keypair = Keypair()
        pubkey = str(keypair.pubkey())
        private_key_bytes = bytes(keypair)
        private_key_base58 = base58.b58encode(private_key_bytes).decode()
        
        # Save to file
        wallet_data = list(private_key_bytes)
        with open('fee_wallet.json', 'w') as f:
            json.dump(wallet_data, f)
        
        print(f"\n✅ Created new wallet: fee_wallet.json")
        print(f"🔑 Public Key: {pubkey}")
        print(f"🔐 Private Key: {private_key_base58}")
        
        print("\n📝 ADD TO .env:")
        print(f"BOT_OWNER_WALLET={pubkey}")
        print(f"BOT_OWNER_PRIVATE_KEY={private_key_base58}")
        
        
        