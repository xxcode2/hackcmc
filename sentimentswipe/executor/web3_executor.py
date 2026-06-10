"""
SENTIMENTSWIPE V2 - Web3 Direct Executor
Fallback executor using web3.py when TWAK is unavailable
Handles PancakeSwap swaps, balance checks, and tx management
"""

import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from eth_typing import Address
from web3 import Web3
from web3.eth import Eth
from web3.contract import Contract
from web3.exceptions import TransactionNotFound

logger = logging.getLogger(__name__)

# BSC PancakeSwap V2 Router (mainnet)
PANCAKE_ROUTER_V2 = "0x10ED43C718714eb63d5aA78B2710c5853D4Bd5E3"
PANCAKE_FACTORY_V2 = "0xcA143ce32Fe78f1f7019d7d551a6402fC5350c73"

# BSC RPC endpoints
BSC_RPCS = [
    "https://bsc.publicnode.com",
    "https://rpc.ankr.com/bsc",
    "https://bsc-dataseed.binance.org",
]

# BSC Chain ID
BSC_CHAIN_ID = 56

# Trading tokens
WRAPPED_BNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDT = "0x55d398326f99059fF775485246999027B3197955"
USDC = "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
FDUSD = "0x6c5b6Fa69820CCF20b8707B8F2F12d2e3a8B3e1A"

# Minimal ABIs
ERC20_ABI = [
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
    {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
    {"constant":False,"inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"name":"approve","outputs":[{"name":"","type":"bool"}],"type":"function"},
    {"constant":True,"inputs":[{"name":"owner","type":"address"},{"name":"spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}
]

ROUTER_ABI = [
    {"inputs":[{"name":"amountIn","type":"uint256"},{"name":"path","type":"address[]"}],"name":"getAmountsOut","outputs":[{"name":"amounts","type":"uint256[]"}],"type":"function"},
    {"inputs":[{"name":"amountIn","type":"uint256"},{"name":"amountOutMin","type":"uint256"},{"name":"path","type":"address[]"},{"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],"name":"swapExactTokensForTokens","outputs":[{"name":"amounts","type":"uint256[]"}],"type":"function"},
    {"inputs":[{"name":"amountOutMin","type":"uint256[]"},{"name":"path","type":"address[]"},{"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],"name":"swapExactBNBForTokens","outputs":[{"name":"amounts","type":"uint256[]"}],"type":"function"},
    {"inputs":[{"name":"amountIn","type":"uint256"},{"name":"amountOutMin","type":"uint256"},{"name":"path","type":"address[]"},{"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],"name":"swapExactTokensForBNB","outputs":[{"name":"amounts","type":"uint256[]"}],"type":"function"},
    {"inputs":[],"name":"WETH","outputs":[{"name":"","type":"address"}],"type":"function"}
]


@dataclass
class SwapResult:
    success: bool
    tx_hash: Optional[str]
    error: Optional[str]
    gas_used: Optional[float] = None
    token_out_received: Optional[float] = None


@dataclass
class BalanceResult:
    token: str
    balance: float
    decimals: int


class Web3Executor:
    """
    Direct web3 executor for BSC PancakeSwap.
    Used as fallback when TWAK CLI is not available.
    Features:
    - Direct BSC RPC (with SSL bypass for ISP interception)
    - PancakeSwap V2 router integration
    - Token approval management
    - Gas optimization
    """

    def __init__(self, private_key: str, seed_capital: float = 100.0):
        self.private_key = private_key
        self.seed_capital = seed_capital
        
        # Connect to BSC
        self.w3 = self._connect_bsc()
        self.account = self.w3.eth.account.from_key(private_key)
        self.address = self.account.address
        
        # Load contracts
        self.router: Contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(PANCAKE_ROUTER_V2),
            abi=ROUTER_ABI
        )
        
        logger.info(f"Web3Executor initialized | Address: {self.address}")
    
    def _connect_bsc(self) -> Web3:
        """Connect to BSC with SSL bypass for ISP interception"""
        for rpc in BSC_RPCS:
            try:
                w3 = Web3(Web3.HTTPProvider(
                    rpc,
                    request_kwargs={"verify": False}
                ))
                if w3.is_connected():
                    logger.info(f"BSC connected via {rpc} | Block: {w3.eth.block_number}")
                    return w3
            except Exception as e:
                logger.warning(f"RPC {rpc} failed: {e}")
        
        raise ConnectionError("All BSC RPCs failed")
    
    def get_wallet_address(self) -> str:
        return self.address
    
    def get_balance(self, token_addr: str = "BNB") -> BalanceResult:
        """Get token balance for wallet"""
        if token_addr == "BNB" or token_addr == "":
            bal = self.w3.eth.get_balance(self.address)
            return BalanceResult(token="BNB", balance=bal / 1e18, decimals=18)
        
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_addr),
            abi=ERC20_ABI
        )
        bal = token.functions.balanceOf(self.address).call()
        decimals = token.functions.decimals().call()
        symbol = token.functions.symbol().call()
        
        return BalanceResult(
            token=symbol,
            balance=bal / (10 ** decimals),
            decimals=decimals
        )
    
    def get_balances(self) -> Dict[str, float]:
        """Get all relevant token balances"""
        tokens = {
            "BNB": "BNB",
            "USDT": USDT,
            "USDC": USDC,
            "FDUSD": FDUSD,
        }
        
        balances = {}
        for name, addr in tokens.items():
            try:
                result = self.get_balance(addr if addr != "BNB" else "")
                balances[name] = result.balance
            except:
                balances[name] = 0.0
        
        return balances
    
    def _get_gas_price(self) -> int:
        """Get current gas price in gwei"""
        gas = self.w3.eth.gas_price
        # Add 10% buffer for BSC congestion
        return int(gas * 1.1)
    
    def _ensure_approval(self, token_addr: str, amount: int) -> bool:
        """Ensure token approval for router"""
        token = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_addr),
            abi=ERC20_ABI
        )
        
        allowance = token.functions.allowance(self.address, PANCAKE_ROUTER_V2).call()
        
        if allowance < amount:
            symbol = token.functions.symbol().call()
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = self._get_gas_price()
            
            approve_tx = token.functions.approve(
                PANCAKE_ROUTER_V2,
                2**256 - 1  # Max approval
            ).build_transaction({
                "from": self.address,
                "gasPrice": gas_price,
                "nonce": nonce
            })
            
            signed = self.account.sign_transaction(approve_tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt.status == 1:
                logger.info(f"Approved {symbol} for PancakeSwap")
                return True
            else:
                logger.error(f"Approval failed for {symbol}")
                return False
        
        return True
    
    def get_swap_amount_out(self, amount_in: float, token_in: str, token_out: str) -> float:
        """Get expected output amount for a swap"""
        path = self._get_swap_path(token_in, token_out)
        
        amount_in_wei = self._to_wei(amount_in, token_in)
        amounts = self.router.functions.getAmountsOut(amount_in_wei, path).call()
        
        return self._from_wei(amounts[-1], token_out)
    
    def _get_swap_path(self, token_in: str, token_out: str) -> list:
        """Get PancakeSwap path for token pair"""
        token_in_addr = self._resolve_token(token_in)
        token_out_addr = self._resolve_token(token_out)
        
        # If either is BNB, wrap it
        if token_in_addr == "BNB":
            token_in_addr = WRAPPED_BNB
        if token_out_addr == "BNB":
            token_out_addr = WRAPPED_BNB
        
        # Direct path
        return [token_in_addr, token_out_addr]
    
    def _resolve_token(self, symbol: str) -> str:
        """Resolve symbol to address"""
        mapping = {
            "BNB": "BNB",
            "WBNB": WRAPPED_BNB,
            "USDT": USDT,
            "USDC": USDC,
            "FDUSD": FDUSD,
            "BTC": "0x7130d2A12B9BCbFAe4f2634d864A1BCeD8Ad6E89",
            "ETH": "0x2170Ed0880ac9A755c803f350D1D2d5Fc2fB6D81",
            "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        }
        return mapping.get(symbol.upper(), symbol.upper())
    
    def _to_wei(self, amount: float, token: str) -> int:
        """Convert to wei/smallest unit"""
        if token == "BNB" or token == "WBNB":
            return int(amount * 1e18)
        return int(amount * 1e18)  # All our tokens are 18 decimals
    
    def _from_wei(self, amount: int, token: str) -> float:
        """Convert from wei to token amount"""
        return amount / 1e18
    
    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        slippage: float = 0.5,
        gas_gwei: int = 5
    ) -> SwapResult:
        """
        Execute a swap on PancakeSwap V2
        
        Args:
            token_in: Input token symbol (BNB, USDT, etc.)
            token_out: Output token symbol
            amount_in: Amount to swap
            slippage: Slippage tolerance (%)
            gas_gwei: Max gas price in gwei
        
        Returns:
            SwapResult with tx_hash or error
        """
        try:
            token_in_addr = self._resolve_token(token_in)
            token_out_addr = self._resolve_token(token_out)
            
            # Get amounts
            path = self._get_swap_path(token_in, token_in_addr)
            amount_in_wei = self._to_wei(amount_in, token_in)
            
            amounts_out = self.router.functions.getAmountsOut(amount_in_wei, path).call()
            amount_out_min = int(amounts_out[-1] * (1 - slippage / 100))
            
            deadline = int(time.time()) + 600  # 10 minutes
            nonce = self.w3.eth.get_transaction_count(self.address)
            gas_price = gas_gwei * 1e9
            
            # Build transaction
            if token_in_addr == "BNB" or token_in == "BNB":
                # Swap BNB for token
                value = amount_in_wei
                tx = self.router.functions.swapExactBNBForTokens(
                    amount_out_min,
                    path,
                    self.address,
                    deadline
                )
                tx_params = {
                    "from": self.address,
                    "value": value,
                    "gasPrice": gas_price,
                    "nonce": nonce
                }
            elif token_out_addr == WRAPPED_BNB or token_out == "BNB":
                # Swap token for BNB
                if not self._ensure_approval(token_in_addr, amount_in_wei):
                    return SwapResult(False, None, "Approval failed")
                
                tx = self.router.functions.swapExactTokensForBNB(
                    amount_in_wei,
                    amount_out_min,
                    path,
                    self.address,
                    deadline
                )
                tx_params = {
                    "from": self.address,
                    "gasPrice": gas_price,
                    "nonce": nonce
                }
            else:
                # Token to token
                if not self._ensure_approval(token_in_addr, amount_in_wei):
                    return SwapResult(False, None, "Approval failed")
                
                tx = self.router.functions.swapExactTokensForTokens(
                    amount_in_wei,
                    amount_out_min,
                    path,
                    self.address,
                    deadline
                )
                tx_params = {
                    "from": self.address,
                    "gasPrice": gas_price,
                    "nonce": nonce
                }
            
            # Estimate gas
            try:
                gas_estimate = tx.estimate_gas(tx_params)
                tx_params["gas"] = int(gas_estimate * 1.2)  # 20% buffer
            except:
                tx_params["gas"] = 500000
            
            # Build and sign
            built_tx = tx.build_transaction(tx_params)
            signed = self.account.sign_transaction(built_tx)
            
            # Send
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            hex_hash = tx_hash.hex()
            
            logger.info(f"SWAP: {amount_in} {token_in} → {token_out} | tx: {hex_hash}")
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                return SwapResult(
                    success=True,
                    tx_hash=hex_hash,
                    gas_used=receipt.gas_used
                )
            else:
                return SwapResult(
                    success=False,
                    tx_hash=hex_hash,
                    error=f"Tx failed, status 0"
                )
        
        except Exception as e:
            logger.error(f"Swap error: {e}")
            return SwapResult(False, None, str(e))
    
    def get_tx_status(self, tx_hash: str) -> Dict:
        """Get transaction status"""
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                "confirmed": receipt.status == 1,
                "failed": receipt.status == 0,
                "block": receipt.blockNumber,
                "gas_used": receipt.gasUsed,
                "tx_hash": tx_hash
            }
        except TransactionNotFound:
            return {"pending": True}
        except Exception as e:
            return {"error": str(e)}
    
    def wait_for_confirmation(self, tx_hash: str, timeout: int = 120) -> bool:
        """Wait for tx confirmation"""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            return receipt.status == 1
        except:
            return False
    
    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value in USD"""
        balances = self.get_balances()
        total = 0.0
        
        for token, balance in balances.items():
            if token == "BNB":
                price = prices.get("BNB", prices.get("BTC", 0) * 0.0095)  # Rough BNB/BTC ratio
            else:
                price = prices.get(token, 1.0)  # Stablecoins = $1
            total += balance * price
        
        return total