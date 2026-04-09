from algosdk.v2client import algod
from algosdk import account
from algosdk.transaction import PaymentTxn
import json
import os

# Connect to AlgoNode free public testnet API (Requires no auth token)
ALGOD_ADDRESS = "https://testnet-api.algonode.cloud"
ALGOD_TOKEN = ""

client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS)

# Manage the server wallet (which pays the 0.001 ALGO fee)
WALLET_FILE = os.path.join(os.path.dirname(__file__), "data", "algo_wallet.json")

def get_or_create_wallet():
    if os.path.exists(WALLET_FILE):
        with open(WALLET_FILE) as f:
            data = json.load(f)
            return data["address"], data["private_key"]
    else:
        private_key, address = account.generate_account()
        os.makedirs(os.path.dirname(WALLET_FILE), exist_ok=True)
        with open(WALLET_FILE, "w") as f:
            json.dump({"address": address, "private_key": private_key}, f, indent=2)
        print("\n" + "="*70)
        print("🚨 NEW ALGORAND TESTNET WALLET GENERATED 🚨")
        print(f"➜ Server Address: {address}")
        print("To broadcast models, this wallet needs test ALGO to pay the small network fee.")
        print("Please visit: https://bank.testnet.algorand.network/ OR https://dispenser.testnet.aws.algodev.network/")
        print("Paste the address above and click Dispense before registering models!")
        print("="*70 + "\n")
        return address, private_key

ADDRESS, PRIVATE_KEY = get_or_create_wallet()

def broadcast_hash_to_algorand(model_id, model_name, model_hash, owner):
    """
    Sends a 0-ALGO transaction to oneself.
    The payload is stored in the immutable `note` field of the transaction.
    """
    try:
        # Check balance
        account_info = client.account_info(ADDRESS)
        balance = account_info.get('amount', 0)
        
        if balance < 1000:
             return {"success": False, "error": f"Blockchain Wallet Empty! Please fund address {ADDRESS} at https://bank.testnet.algorand.network/"}
             
        params = client.suggested_params()
        
        payload = {
            "id": model_id,
            "name": model_name,
            "hash": model_hash,
            "owner": owner
        }
        
        # Max note size in Algorand is 1024 bytes (1KB), our payload is ~150 bytes.
        note = json.dumps(payload).encode()
        
        # A 0-value transaction to ourselves just to securely log the note metadata into the ledger
        txn = PaymentTxn(
            sender=ADDRESS,
            sp=params,
            receiver=ADDRESS,
            amt=0,
            note=note
        )
        
        signed_txn = txn.sign(PRIVATE_KEY)
        txid = client.send_transaction(signed_txn)
        
        # Wait for confirmation (Algorand block time is ~3 seconds!)
        import time
        max_retries = 10
        confirmed_round = None
        for _ in range(max_retries):
            txinfo = client.pending_transaction_info(txid)
            if txinfo.get("confirmed-round") and txinfo.get("confirmed-round") > 0:
                confirmed_round = txinfo.get("confirmed-round")
                break
            time.sleep(1)
            
        if not confirmed_round:
            return {"success": False, "error": "Transaction sent but confirmation timed out."}
            
        return {
            "success": True,
            "txid": txid,
            "round": confirmed_round
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
