"""TWAK Native Executor - Deep TWAK integration"""
import subprocess, json, logging, os, shlex

logger = logging.getLogger(__name__)

def _run(args: list) -> dict:
    cmd = "twak " + " ".join(shlex.quote(str(a)) for a in args)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if r.returncode == 0:
        try:
            return json.loads(r.stdout)
        except Exception:
            pass
    return {"error": r.stderr[:200] if r.stderr else "failed", "returncode": r.returncode}

def twak_auth_status() -> dict:
    return _run(["auth", "status", "--json"])

def twak_wallet_status() -> dict:
    return _run(["wallet", "status", "--json"])

def twak_get_price(token: str, chain: str = "bsc") -> dict:
    return _run(["price", "--chain", chain, "--json", token])

def twak_swap_quote(from_token: str, to_token: str, amount: str, chain: str = "bsc") -> dict:
    return _run(["swap", "--chain", chain, "--quote-only", "--json", amount, from_token, to_token])

def twak_swap_execute(from_token: str, to_token: str, amount: str, password: str, chain: str = "bsc", slippage: float = 1.0) -> dict:
    return _run(["swap", "--chain", chain, "--slippage", str(slippage), "--password", password, "--json", amount, from_token, to_token])

def twak_swap_usd(usd_amount: str, to_token: str, password: str, chain: str = "bsc", slippage: float = 1.0) -> dict:
    return _run(["swap", "--chain", chain, "--usd", usd_amount, "--slippage", str(slippage), "--password", password, "--json", usd_amount, to_token])

def twak_balance(address: str, chain: str = "bsc") -> dict:
    return _run(["balance", "--chain", chain, "--address", address, "--json"])

def twak_get_trending(category: str = "all", chain: str = "bsc") -> list:
    r = _run(["trending", "--chain", chain, "--json", "--category", category])
    return r if isinstance(r, list) else []

def twak_search_tokens(query: str, chain: str = "bsc") -> list:
    r = _run(["search", "--chain", chain, "--json", query])
    return r if isinstance(r, list) else []

def twak_risk_check(asset_id: str) -> dict:
    return _run(["risk", "--json", asset_id])

def twak_add_dca(from_token: str, to_token: str, amount: str, frequency: str, password: str, chain: str = "bsc") -> dict:
    return _run(["automate", "add", "--chain", chain, "--type", "dca", "--from", from_token, "--to", to_token, "--amount", amount, "--frequency", frequency, "--password", password, "--json"])

def twak_add_limit(from_token: str, to_token: str, amount: str, price: str, password: str, chain: str = "bsc") -> dict:
    return _run(["automate", "add", "--chain", chain, "--type", "limit", "--from", from_token, "--to", to_token, "--amount", amount, "--price", price, "--password", password, "--json"])

def twak_list_automations(chain: str = "bsc") -> list:
    r = _run(["automate", "list", "--chain", chain, "--json"])
    return r if isinstance(r, list) else []

def twak_delete_automation(automation_id: str, password: str) -> bool:
    r = _run(["automate", "delete", "--password", password, "--json", automation_id])
    return r.get("returncode", 1) == 0

def twak_compete_register(password: str) -> dict:
    return _run(["compete", "register", "--password", password, "--json"])

def twak_compete_status() -> dict:
    return _run(["compete", "status", "--json"])

def twak_history(chain: str = "bsc", limit: int = 50) -> list:
    r = _run(["history", "--chain", chain, "--json", "--limit", str(limit)])
    return r if isinstance(r, list) else []

def twak_validate_address(address: str, chain: str = "bsc") -> bool:
    r = _run(["validate", "--chain", chain, address])
    return r.get("returncode", 1) == 0

def twak_chains() -> list:
    r = _run(["chains", "--json"])
    return r if isinstance(r, list) else []

def twak_transfer(to_address: str, amount: str, token: str = "BNB", password: str = "", chain: str = "bsc") -> dict:
    args = ["transfer", "--chain", chain, "--json"]
    if password:
        args.extend(["--password", password])
    args.extend([amount, token, to_address])
    return _run(args)

def twak_get_wallet_address(chain: str = "bsc") -> str:
    r = _run(["wallet", "address", "--chain", chain, "--json"])
    if isinstance(r, dict):
        return r.get("address", "")
    return ""

def twak_x402_quote(url: str) -> dict:
    return _run(["x402", "quote", "--json", url])

def twak_x402_request(url: str, password: str) -> dict:
    return _run(["x402", "request", "--password", password, "--json", url])

def twak_pause_automation(automation_id: str, password: str) -> bool:
    r = _run(["automate", "pause", "--password", password, "--json", automation_id])
    return r.get("returncode", 1) == 0

def twak_resume_automation(automation_id: str, password: str) -> bool:
    r = _run(["automate", "resume", "--password", password, "--json", automation_id])
    return r.get("returncode", 1) == 0

def twak_start_watcher(password: str, interval: str = "60s") -> subprocess.Popen:
    cmd = f"twak serve --watch --watch-interval={interval} --password {shlex.quote(password)}"
    return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
