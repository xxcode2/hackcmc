"""
Test transaction - send minimal BNB to self
"""
from web3 import Web3
from eth_account import Account
import os
os.environ['SSL_CERT_FILE'] = ''

PRIVATE_KEY = 'dfa72116b3d718212b4ac5f508d51240295a79ebcb3eccb0289b381c5a8e6dda'
TO_ADDRESS = '0xc047e0BCee8876348B5290a85bD4C1F54c4621bD'  # Self

w3 = Web3(Web3.HTTPProvider('https://bsc.publicnode.com', request_kwargs={'verify': False}))
account = Account.from_key(PRIVATE_KEY)
from_addr = account.address

print(f"From: {from_addr}")
print(f"To:   {TO_ADDRESS}")
print()

# Check balance
bal = w3.eth.get_balance(from_addr)
print(f"Balance: {bal / 1e18:.6f} BNB")

# Estimate gas for simple transfer
gas_estimate = 21000
gas_price = w3.eth.gas_price
print(f"Gas price: {gas_price / 1e9:.1f} gwei")
estimated_gas = gas_estimate * gas_price
print(f"Estimated gas (transfer): {estimated_gas / 1e18:.6f} BNB")

# Try to send minimal BNB
send_amount = 0.0001  # 0.0001 BNB = $0.058
total_cost = send_amount + (estimated_gas / 1e18)

print()
if bal < (send_amount + estimated_gas):
    print(f"INSUFFICIENT: need {total_cost:.6f} BNB, have {bal / 1e18:.6f} BNB")
    send_amount = max(0, (bal - estimated_gas) / 1e18 * 0.9)  # Leave some for gas
    print(f"Adjusted send amount: {send_amount:.6f} BNB")
else:
    print(f"Sending: {send_amount:.6f} BNB")
    print(f"Total cost: {total_cost:.6f} BNB")

print()

# Build transaction
nonce = w3.eth.get_transaction_count(from_addr)
tx = {
    'nonce': nonce,
    'to': TO_ADDRESS,
    'value': int(send_amount * 1e18),
    'gas': gas_estimate,
    'gasPrice': int(gas_price * 1.1),  # 10% buffer
    'chainId': 56,
    'type': 2,
    'maxFeePerGas': int(gas_price * 1.1),
    'maxPriorityFeePerGas': int(gas_price * 0.1),
}

print("Transaction params:")
for k, v in tx.items():
    if k == 'value':
        print(f"  {k}: {v} wei ({v/1e18} BNB)")
    elif k == 'gasPrice' or k == 'maxFeePerGas':
        print(f"  {k}: {v} wei ({v/1e9:.1f} gwei)")
    else:
        print(f"  {k}: {v}")

# Sign
signed = account.sign_transaction(tx)
print()
print(f"Signed tx hash: {signed.hash.hex()}")
print(f"Raw tx (first 50 chars): {signed.raw_transaction.hex()[:50]}...")

# Broadcast
try:
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print()
    print(f"=== BROADCAST SUCCESS ===")
    print(f"TX HASH: {tx_hash.hex()}")
    print(f"BSC Scan: https://bscscan.com/tx/{tx_hash.hex()}")
    
    # Wait for receipt
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print()
    print(f"Status: {'SUCCESS' if receipt.status == 1 else 'FAILED'}")
    print(f"Block: {receipt.blockNumber}")
    print(f"Gas used: {receipt.gasUsed}")
    
except Exception as e:
    print(f"ERROR: {e}")