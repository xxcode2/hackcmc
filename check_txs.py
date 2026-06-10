from web3 import Web3
import requests

w3 = Web3(Web3.HTTPProvider('https://bsc.publicnode.com', request_kwargs={'verify': False}))
addr = '0xc047e0BCee8876348B5290a85bD4C1F54c4621bD'

# Get tx count
nonce = w3.eth.get_transaction_count(addr)
print(f'Total txs: {nonce}')
print(f'Balance: {w3.eth.get_balance(addr) / 1e18:.6f} BNB')
print()

# BSCScan API for tx history (free API key needed for detailed)
# Try public RPC logs
print(f'BSC Scan: https://bscscan.com/address/{addr}')