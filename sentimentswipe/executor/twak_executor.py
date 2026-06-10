"""
SENTIMENTSWIPE V2 - TWAK Executor
Handles transaction signing and broadcasting via Trust Wallet Agent Kit
"""

import json
import logging
import subprocess
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TxResult:
    """Result of a transaction"""
    success: bool
    tx_hash: Optional[str]
    error: Optional[str]
    gas_used: Optional[float] = None
    gas_price_gwei: Optional[float] = None

class TWAKExecutor:
    """
    Trust Wallet Agent Kit integration for autonomous trading.
    Supports: CLI, MCP, REST, x402
    """
    
    def __init__(self, private_key: str, chain_id: int = 56):
        self.private_key = private_key
        self.chain_id = chain_id  # 56 = BSC Mainnet
        self.wallet_address = self._derive_address()
        
    def _derive_address(self) -> str:
        """Derive wallet address from private key"""
        # In real implementation, use web3.py or similar
        # For now, returns placeholder
        # TODO: Implement properly with web3
        return "0x0000000000000000000000000000000000000000"
    
    def _run_twak(self, args: list) -> Tuple[bool, str]:
        """Run TWAK CLI command"""
        cmd = ["twak"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
        except FileNotFoundError:
            logger.error("TWAK CLI not found. Install from: portal.trustwallet.com")
            return False, "TWAK CLI not installed"
        except subprocess.TimeoutExpired:
            return False, "TWAK command timed out"
        except Exception as e:
            return False, str(e)
    
    # === COMPETITION REGISTRATION ===
    
    def register_competition(self) -> TxResult:
        """
        Register agent wallet for Track 1 competition
        Uses: twak compete register
        """
        success, output = self._run_twak(["compete", "register"])
        if success:
            # Parse tx hash from output
            tx_hash = self._parse_tx_hash(output)
            logger.info(f"Competition registered: {tx_hash}")
            return TxResult(success=True, tx_hash=tx_hash)
        else:
            return TxResult(success=False, tx_hash=None, error=output)
    
    # === TRADE EXECUTION ===
    
    def swap_tokens(self, token_in: str, token_out: str, amount_in: float) -> TxResult:
        """
        Execute token swap on PancakeSwap/BSC
        
        Args:
            token_in: Input token symbol (e.g., "USDT")
            token_out: Output token symbol (e.g., "BNB")
            amount_in: Amount of token_in to swap (in base units)
        
        Returns:
            TxResult with tx_hash or error
        """
        # TWAK autonomous swap
        args = [
            "swap",
            "--from", token_in,
            "--to", token_out,
            "--amount", str(amount_in),
            "--chain", str(self.chain_id),
            "--autonomous"  # Agent signs without manual approval
        ]
        
        success, output = self._run_twak(args)
        
        if success:
            tx_hash = self._parse_tx_hash(output)
            logger.info(f"SWAP: {amount_in} {token_in} → {token_out} | tx: {tx_hash}")
            return TxResult(success=True, tx_hash=tx_hash)
        else:
            logger.error(f"SWAP FAILED: {output}")
            return TxResult(success=False, tx_hash=None, error=output)
    
    def swap_with_x402(self, token_in: str, token_out: str, amount_in: float,
                       x402_payment: str) -> TxResult:
        """
        Execute swap with x402 payment for TWAK services
        Uses native x402 for pay-per-call (special prize criteria)
        """
        args = [
            "swap",
            "--from", token_in,
            "--to", token_out,
            "--amount", str(amount_in),
            "--chain", str(self.chain_id),
            "--autonomous",
            "--x402", x402_payment
        ]
        
        success, output = self._run_twak(args)
        
        if success:
            tx_hash = self._parse_tx_hash(output)
            logger.info(f"SWAP+x402: {amount_in} {token_in} → {token_out} | tx: {tx_hash}")
            return TxResult(success=True, tx_hash=tx_hash)
        else:
            return TxResult(success=False, tx_hash=None, error=output)
    
    # === PORTFOLIO MANAGEMENT ===
    
    def get_balance(self, token: str) -> float:
        """Get token balance for wallet"""
        args = ["balance", "--token", token, "--chain", str(self.chain_id)]
        success, output = self._run_twak(args)
        
        if success:
            try:
                # Parse balance from output
                return float(output.strip())
            except:
                return 0.0
        return 0.0
    
    def get_balances(self) -> Dict[str, float]:
        """Get all token balances"""
        args = ["balances", "--chain", str(self.chain_id)]
        success, output = self._run_twak(args)
        
        if success:
            try:
                return json.loads(output)
            except:
                return {}
        return {}
    
    def transfer(self, token: str, to_address: str, amount: float) -> TxResult:
        """Transfer tokens to another address"""
        args = [
            "transfer",
            "--token", token,
            "--to", to_address,
            "--amount", str(amount),
            "--chain", str(self.chain_id),
            "--autonomous"
        ]
        
        success, output = self._run_twak(args)
        
        if success:
            tx_hash = self._parse_tx_hash(output)
            logger.info(f"TRANSFER: {amount} {token} → {to_address[:10]}... | tx: {tx_hash}")
            return TxResult(success=True, tx_hash=tx_hash)
        else:
            return TxResult(success=False, tx_hash=None, error=output)
    
    # === TX STATUS ===
    
    def get_tx_status(self, tx_hash: str) -> Dict:
        """Get transaction status from BSC"""
        args = ["tx", tx_hash, "--chain", str(self.chain_id)]
        success, output = self._run_twak(args)
        
        if success:
            try:
                return json.loads(output)
            except:
                return {"status": "unknown"}
        return {"status": "failed", "error": output}
    
    def wait_for_confirmation(self, tx_hash: str, timeout: int = 60) -> bool:
        """Wait for tx to be confirmed on chain"""
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            status = self.get_tx_status(tx_hash)
            if status.get("confirmed"):
                return True
            elif status.get("failed"):
                return False
            time.sleep(5)
        
        return False
    
    # === UTILITY ===
    
    def _parse_tx_hash(self, output: str) -> Optional[str]:
        """Parse tx hash from TWAK output"""
        # Look for 0x... pattern (tx hash)
        import re
        match = re.search(r'0x[a-fA-F0-9]{64}', output)
        if match:
            return match.group(0)
        
        # Try JSON output
        try:
            data = json.loads(output)
            return data.get("tx_hash") or data.get("hash")
        except:
            pass
        
        return None
    
    def get_wallet_address(self) -> str:
        """Get the agent's wallet address"""
        return self.wallet_address
    
    def verify_setup(self) -> Dict:
        """Verify TWAK is properly configured"""
        checks = {
            "twak_installed": False,
            "private_key_set": bool(self.private_key),
            "wallet_address": None,
            "network": "BSC Mainnet" if self.chain_id == 56 else f"Chain {self.chain_id}"
        }
        
        # Check TWAK installation
        success, _ = self._run_twak(["--version"])
        checks["twak_installed"] = success
        
        # Get wallet address
        if checks["twak_installed"] and checks["private_key_set"]:
            address = self._derive_address()
            checks["wallet_address"] = address
        
        return checks

# === FALLBACK: Direct web3 executor ===
class Web3Executor:
    """
    Fallback executor using web3.py directly
    Used if TWAK CLI is not available
    """
    
    def __init__(self, private_key: str, rpc_url: str, chain_id: int = 56):
        self.private_key = private_key
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        # TODO: Initialize web3 with RPC
    
    def swap_pancakeswap(self, token_in: str, token_out: str, amount_in: float) -> TxResult:
        """Direct PancakeSwap swap via web3"""
        # TODO: Implement with web3.py + PancakeSwap ABI
        logger.warning("Web3Executor swap not implemented - use TWAKExecutor")
        return TxResult(success=False, tx_hash=None, error="Not implemented")