"""
SENTIMENTSWIPE V2 - TWAK MCP Client
Connects to local TWAK MCP REST server for deep wallet integration

Run the MCP server first:
  twak serve --rest --port 3000 --password "SentimentSwipe2026!"

The server provides 50+ tools including:
- Wallet: get_address, wallet_balance, token_balance, switch_wallet_mode
- Trading: swap, get_swap_quote, transfer, transfer_token
- Data: get_token_price, get_trending_tokens, check_token_risk
- Automation: create_automation, list_automations, run_automation_now
- Competition: competition_register, competition_status
- x402: x402_quote, x402_request (micropayments)
- ERC standards: erc8004 (AI identity), erc8183 (job escrow)
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)

# TWAK MCP Server config
MCP_SERVER_URL = os.getenv("TWAK_MCP_URL", "http://127.0.0.1:3000")

# TWAK Wallet (BSC main address for competition)
# Created: 2026-06-10, Password: SentimentSwipe2026!
TWAK_WALLET_ADDRESS_BSC = "0xc1Ee4085239D86eB55a3BE5Ba0e83b3c3283381A"

# Load HMAC secret from credentials file
CREDS_FILE = os.path.expanduser("~/.twak/credentials.json")
if os.path.exists(CREDS_FILE):
    try:
        with open(CREDS_FILE, "r") as f:
            creds = json.load(f)
            TWAK_HMAC_SECRET = creds.get("hmacSecret", "")
    except Exception:
        pass

class TWAKMCPClient:
    """Client for TWAK MCP REST API server"""
    
    def __init__(self, server_url: str = MCP_SERVER_URL):
        self.server_url = server_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {TWAK_HMAC_SECRET}",
            "Content-Type": "application/json"
        })
        self._wallet_mode = None
        self._wallet_addresses = None
        
    def _post(self, action: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make authenticated POST request to MCP server"""
        url = f"{self.server_url}/actions/{action}"
        try:
            r = self.session.post(url, json=data or {}, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 401:
                return {"error": "Unauthorized — check HMAC secret"}
            else:
                return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except requests.exceptions.ConnectionError:
            return {"error": f"Cannot connect to MCP server at {self.server_url}. Is twak serve running?"}
        except Exception as e:
            return {"error": str(e)}
    
    # ─── Wallet Operations ───────────────────────────────────────
    
    def switch_wallet_mode(self, mode: str = "local") -> Dict[str, Any]:
        """
        Switch wallet mode. Options:
        - "local": Use TWAK agent wallet (default, keys stay local)
        - "walletconnect": Sign via Trust Wallet mobile app
        
        Returns wallet binding status
        """
        result = self._post("switch_wallet_mode", {"mode": mode})
        if result.get("state") == "local":
            self._wallet_mode = "local"
            self._wallet_addresses = None  # Clear cached addresses
        return result
    
    def get_address(self, chain: str = "bsc") -> str:
        """Get wallet address for a specific chain"""
        result = self._post("get_address", {"chain": chain})
        if "address" in result:
            return result["address"]
        return None
    
    def list_addresses(self) -> Dict[str, str]:
        """Get wallet addresses for all supported chains"""
        if self._wallet_addresses:
            return self._wallet_addresses
        result = self._post("list_addresses", {})
        if "addresses" in result:
            self._wallet_addresses = result["addresses"]
            return self._wallet_addresses
        return {}
    
    def wallet_balance(self, chain: str = "bsc") -> Dict[str, Any]:
        """Get native coin balance (BNB on BSC, ETH on Ethereum, etc.)"""
        return self._post("wallet_balance", {"chain": chain})
    
    def get_balance(self, chain: str, token_address: str = None, asset_id: str = None) -> Dict[str, Any]:
        """
        Get token balance for any chain.
        - Native coin: omit tokenAddress / use assetId like "c714" for BNB
        - ERC-20: provide tokenAddress
        """
        data = {"chain": chain}
        if token_address:
            data["tokenAddress"] = token_address
        if asset_id:
            data["assetId"] = asset_id
        return self._post("get_balance", data)
    
    # ─── Trading Operations ──────────────────────────────────────
    
    def get_token_price(self, chain: str, token: str) -> float:
        """
        Get current USD price for a token.
        token: token symbol like "BTC", "ETH", "BNB", "USDT"
        """
        result = self._post("get_token_price", {"chain": chain, "token": token})
        if "priceUsd" in result:
            return float(result["priceUsd"])
        return None
    
    def get_swap_quote(self, from_token: str, to_token: str, amount: float, chain: str = "bsc") -> Dict[str, Any]:
        """
        Get swap quote without executing.
        Example: from_token="BNB", to_token="BTC", amount=0.1
        """
        return self._post("get_swap_quote", {
            "fromToken": from_token,
            "toToken": to_token,
            "amount": str(amount),
            "chain": chain
        })
    
    def swap(self, from_token: str, to_token: str, amount: float, chain: str = "bsc") -> Dict[str, Any]:
        """
        Execute a token swap. Requires wallet to be unlocked.
        WARNING: This broadcasts a real transaction!
        """
        return self._post("swap", {
            "fromToken": from_token,
            "toToken": to_token,
            "amount": str(amount),
            "chain": chain
        })
    
    def transfer(self, to_address: str, amount: float, chain: str = "bsc", token: str = None) -> Dict[str, Any]:
        """Transfer native coins or tokens to an address"""
        data = {"to": to_address, "amount": str(amount), "chain": chain}
        if token:
            data["token"] = token
        return self._post("transfer", data)
    
    # ─── Automation ──────────────────────────────────────────────
    
    def create_automation(self, automation_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a DCA or limit order automation.
        
        DCA example:
          create_automation("dca", {
            "fromToken": "USDT", "toToken": "BTC",
            "amount": "5", "frequency": "1h", "chain": "bsc"
          })
        
        Limit order example:
          create_automation("limit", {
            "type": "buy", "fromToken": "USDT", "toToken": "BNB",
            "amount": "100", "price": "500", "chain": "bsc"
          })
        """
        return self._post("create_automation", {
            "type": automation_type,
            **config
        })
    
    def list_automations(self) -> List[Dict[str, Any]]:
        """List all automation rules (DCA and limit orders)"""
        result = self._post("list_automations", {})
        return result.get("automations", [])
    
    def delete_automation(self, automation_id: str) -> Dict[str, Any]:
        """Delete an automation rule"""
        return self._post("delete_automation", {"id": automation_id})
    
    def run_automation_now(self, automation_id: str) -> Dict[str, Any]:
        """Execute an automation immediately (no need to wait for schedule)"""
        return self._post("run_automation_now", {"id": automation_id})
    
    # ─── Competition ─────────────────────────────────────────────
    
    def competition_status(self) -> Dict[str, Any]:
        """Check BNB Hackathon competition registration status"""
        return self._post("competition_status", {})
    
    def competition_register(self) -> Dict[str, Any]:
        """
        Register agent wallet for BNB Hack competition.
        Idempotent — if already registered, returns success.
        """
        return self._post("competition_register", {})
    
    # ─── Token Info ──────────────────────────────────────────────
    
    def get_trending_tokens(self, chain: str = "bsc") -> List[Dict[str, Any]]:
        """Get trending tokens by market activity"""
        result = self._post("get_trending_tokens", {"chain": chain})
        return result.get("tokens", [])
    
    def check_token_risk(self, chain: str, token_address: str = None) -> Dict[str, Any]:
        """Check security and risk for a token (honeypot, audit, etc.)"""
        data = {"chain": chain}
        if token_address:
            data["tokenAddress"] = token_address
        return self._post("check_token_risk", data)
    
    def search_assets(self, query: str) -> List[Dict[str, Any]]:
        """Search for tokens by name, symbol, or address"""
        result = self._post("search_assets", {"query": query})
        return result.get("assets", [])
    
    # ─── x402 Micropayments ──────────────────────────────────────
    
    def x402_quote(self, endpoint: str, max_payment: str = None) -> Dict[str, Any]:
        """
        Preview payment requirements for an x402-gated endpoint.
        Returns available payment options.
        """
        data = {"endpoint": endpoint}
        if max_payment:
            data["maxPaymentAtomic"] = max_payment
        return self._post("x402_quote", data)
    
    def x402_request(self, endpoint: str, max_payment: str, prefer_chain: str = None,
                     prefer_token: str = None) -> Dict[str, Any]:
        """Make a payment-gated HTTP request with automatic payment signing"""
        data = {"endpoint": endpoint, "maxPaymentAtomic": max_payment}
        if prefer_chain:
            data["preferNetwork"] = prefer_chain
        if prefer_token:
            data["preferAsset"] = prefer_token
        return self._post("x402_request", data)
    
    # ─── ERC Standards ───────────────────────────────────────────
    
    def erc8004_register(self, agent_uri: str, metadata: Dict = None) -> Dict[str, Any]:
        """
        Mint an ERC-8004 AI agent identity on-chain.
        agent_uri: URL to agent registration JSON
        """
        data = {"agentUri": agent_uri}
        if metadata:
            data["metadata"] = metadata
        return self._post("erc8004_register", data)
    
    def erc8004_show(self, agent_id: str) -> Dict[str, Any]:
        """Read on-chain state of an ERC-8004 agent identity"""
        return self._post("erc8004_show", {"agentId": agent_id})
    
    def erc8183_create_job(self, description: str, payment_token: str, 
                           budget: str, evaluator: str = None) -> Dict[str, Any]:
        """Create an ERC-8183 job for AI-to-AI work escrow"""
        data = {
            "description": description,
            "paymentToken": payment_token,
            "budget": budget
        }
        if evaluator:
            data["evaluator"] = evaluator
        return self._post("erc8183_create_job", data)


# ─── Convenience Functions ──────────────────────────────────────

def get_mcp_client() -> TWAKMCPClient:
    """Get a connected MCP client instance"""
    return TWAKMCPClient()


def init_wallet(client: TWAKMCPClient) -> Dict[str, Any]:
    """Initialize wallet mode and return status"""
    result = client.switch_wallet_mode("local")
    if result.get("state") == "local":
        addresses = client.list_addresses()
        bsc_addr = client.get_address("bsc")
        balance = client.wallet_balance("bsc")
        return {
            "status": "ready",
            "mode": "local",
            "addresses": addresses,
            "bsc_address": bsc_addr,
            "bsc_balance": balance
        }
    return {"status": "error", "detail": result}


if __name__ == "__main__":
    # Test MCP client
    print("=== TWAK MCP Client Test ===")
    
    client = TWAKMCPClient()
    
    # Test competition status (no wallet needed)
    print("\n1. Competition Status:")
    r = client.competition_status()
    print(json.dumps(r, indent=2))
    
    # Initialize wallet
    print("\n2. Wallet Init:")
    init = init_wallet(client)
    print(json.dumps(init, indent=2))
    
    # Test prices (no wallet needed)
    print("\n3. Token Price (BNB):")
    price = client.get_token_price("bsc", "BNB")
    print(f"BNB = ${price}" if price else "Failed")
    
    print("\n4. Trending Tokens (BSC):")
    trending = client.get_trending_tokens("bsc")
    for t in trending[:5]:
        print(f"  {t.get('symbol')}: ${t.get('priceUsd')}")
    
    print("\n=== MCP CLIENT TEST DONE ===")