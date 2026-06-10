from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://bsc.publicnode.com', request_kwargs={'verify': False}))
addr = '0xc047e0BCee8876348B5290a85bD4C1F54c4621bD'
bal = w3.eth.get_balance(addr)
print(f'BSC balance: {bal / 1e18:.6f} BNB')
print(f'USD (~$585): ${bal / 1e18 * 585:.2f}')