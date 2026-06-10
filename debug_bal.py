import requests
import json

# Use BSCScan API (free, no key for basic reads)
addr = '0xc047e0BCee8876348B5290a85bD4C1F54c4621bD'

# BSCScan API - free tier
url = f'https://api.bscscan.com/api?module=account&action=txlist&address={addr}&startblock=0&endblock=99999999&sort=desc&apikey=YourApiKeyToken'

try:
    resp = requests.get(url, timeout=10)
    data = resp.json()
    
    if data['status'] == '1':
        txs = data['result'][:10]  # Last 10 txs
        print(f"Last {len(txs)} transactions:")
        for tx in txs:
            print(f"  Hash: {tx['hash']}")
            print(f"  From: {tx['from']}")
            print(f"  To: {tx['to']}")
            print(f"  Value: {int(tx['value']) / 1e18:.6f} BNB")
            print(f"  Gas Used: {int(tx['gasUsed']):,}")
            print(f"  Status: {'Success' if tx['isError'] == '0' else 'Failed'}")
            print()
    else:
        print(f"API error: {data}")
except Exception as e:
    print(f"Error: {e}")
    print("Trying alternative...")

# Try BSC RPC directly for balance
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://bsc.publicnode.com', request_kwargs={'verify': False}))
bal = w3.eth.get_balance(addr)
print(f"Current BSC balance (RPC): {bal / 1e18:.6f} BNB")

# Get tx count
nonce = w3.eth.get_transaction_count(addr)
print(f"Transaction count (nonce): {nonce}")