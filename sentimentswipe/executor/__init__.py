"""
SENTIMENTSWIPE V2 - Executor Package
Unified interface: TWAK preferred, Web3 fallback
"""

from .twak_executor import TWAKExecutor, TxResult
from .web3_executor import Web3Executor, SwapResult, BSC_CHAIN_ID, USDT, USDC, FDUSD, WRAPPED_BNB

__all__ = [
    "TWAKExecutor", "TxResult",
    "Web3Executor", "SwapResult",
    "BSC_CHAIN_ID", "USDT", "USDC", "FDUSD", "WRAPPED_BNB"
]


def get_executor(private_key: str = None, seed_capital: float = 100.0):
    """
    Get best available executor.
    Tries TWAK first, falls back to Web3.
    """
    # Try TWAK first
    twak = TWAKExecutor(private_key) if private_key else None
    if twak:
        setup = twak.verify_setup()
        if setup.get("twak_installed"):
            print("Using TWAK Executor")
            return twak
    
    # Fallback to Web3
    print("Using Web3 Executor (TWAK not available)")
    return Web3Executor(private_key, seed_capital) if private_key else None