from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://bsc.publicnode.com', request_kwargs={'verify': False}))

addr = '0xc047e0BCee8876348B5290a85bD4C1F54c4621bD'

# Get block number
current_block = w3.eth.block_number
print(f"Current block: {current_block}")

# Try to get specific tx by getting logs
# Use get_logs to find any BNB transfer events
from_block = current_block - 1000  # last 1000 blocks

print(f"Checking blocks {from_block} to {current_block}")
print()

# Get balance now
bal = w3.eth.get_balance(addr)
print(f"Balance: {bal / 1e18:.6f} BNB")

# Get nonce
nonce = w3.eth.get_transaction_count(addr)
print(f"Nonce: {nonce}")

# Check if there are any recent blocks
for i in range(3):
    block = w3.eth.get_block(current_block - i)
    print(f"Block {current_block - i}: {block.timestamp} unix time")