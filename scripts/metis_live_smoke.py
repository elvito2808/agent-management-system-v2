"""Live, read-only smoke test for Metis Andromeda DEX deployments and METIS pools."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from agent_system.dex_research.dex_registry import load_dex_registry
from agent_system.dex_research.report import render_json_report, render_markdown_report
from agent_system.dex_research.service import discover_and_verify_stablecoin_pools
from agent_system.dex_research.verifier import (
    METIS_RPC_URL, OnChainVerificationError, _rpc_call,
    verify_factory_pair, verify_router_factory_onchain,
)

METIS_TOKEN_ADDRESS = "0xDeadDeAddeAddEAddeadDEaDDEAdDeaDDeAD0000"
EXPECTED_CHAIN_ID = 1088
ARTIFACT_DIR = Path("artifacts")
TIMEOUT_SECONDS = 15.0
RPC_CANDIDATES = (
    METIS_RPC_URL,
    "https://metis-rpc.publicnode.com",
    "https://metis.drpc.org",
    "https://metis-andromeda.rpc.thirdweb.com",
)
ACTIVE_RPC_URL = METIS_RPC_URL

def rpc(method: str, params: list[object]) -> object:
    return _rpc_call(ACTIVE_RPC_URL, method, params,
                     timeout_seconds=TIMEOUT_SECONDS, opener=urlopen)

def has_code(address: str) -> bool:
    result = rpc("eth_getCode", [address, "latest"])
    if not isinstance(result, str) or not result.startswith("0x"):
        raise OnChainVerificationError(f"Invalid eth_getCode response for {address}")
    return len(result) > 2 and any(char != "0" for char in result[2:])

def main() -> int:
    global ACTIVE_RPC_URL
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    deployments = load_dex_registry()
    live_checks: list[dict[str, object]] = []
    discovery_error: str | None = None
    results = []

    rpc_attempts: list[dict[str, object]] = []
    selected_chain_id: int | None = None
    for endpoint in RPC_CANDIDATES:
        try:
            chain_raw = _rpc_call(endpoint, "eth_chainId", [],
                                  timeout_seconds=TIMEOUT_SECONDS, opener=urlopen)
            actual = int(chain_raw, 16) if isinstance(chain_raw, str) else None
            passed = actual == EXPECTED_CHAIN_ID
            rpc_attempts.append({"endpoint": endpoint, "chain_id": actual, "passed": passed})
            if passed:
                ACTIVE_RPC_URL = endpoint
                selected_chain_id = actual
                break
        except Exception as exc:
            rpc_attempts.append({"endpoint": endpoint, "passed": False, "error": str(exc)})
    live_checks.append({"check": "rpc_chain_id", "endpoint": ACTIVE_RPC_URL,
                        "expected": EXPECTED_CHAIN_ID, "actual": selected_chain_id,
                        "passed": selected_chain_id == EXPECTED_CHAIN_ID,
                        "attempts": rpc_attempts})

    try:
        token_code = has_code(METIS_TOKEN_ADDRESS)
        live_checks.append({"check": "metis_token_predeploy_bytecode",
                            "address": METIS_TOKEN_ADDRESS, "passed": token_code})
    except Exception as exc:
        token_code = False
        live_checks.append({"check": "metis_token_predeploy_bytecode",
                            "address": METIS_TOKEN_ADDRESS, "passed": False, "error": str(exc)})

    for deployment in deployments:
        try:
            code = has_code(deployment.factory_address)
            live_checks.append({"check": "factory_bytecode", "dex_id": deployment.dex_id,
                                "address": deployment.factory_address, "passed": code,
                                "source_url": deployment.factory_source_url,
                                "explorer_url": deployment.explorer_factory_url})
        except Exception as exc:
            live_checks.append({"check": "factory_bytecode", "dex_id": deployment.dex_id,
                                "address": deployment.factory_address, "passed": False,
                                "error": str(exc)})

        if deployment.router_address:
            try:
                checked = verify_router_factory_onchain(
                    deployment.router_address, deployment.factory_address,
                    rpc_url=ACTIVE_RPC_URL, timeout_seconds=TIMEOUT_SECONDS)
                live_checks.append({
                    "check": "router_factory_match", "dex_id": deployment.dex_id,
                    "router_address": deployment.router_address,
                    "expected_factory_address": deployment.factory_address,
                    "reported_factory_address": checked.reported_factory_address,
                    "router_has_code": checked.router_has_code, "passed": checked.verified,
                    "checks": list(checked.checks), "errors": list(checked.errors),
                    "source_url": deployment.router_source_url,
                    "explorer_url": deployment.explorer_router_url})
            except Exception as exc:
                live_checks.append({"check": "router_factory_match", "dex_id": deployment.dex_id,
                                    "router_address": deployment.router_address,
                                    "passed": False, "error": str(exc)})
        else:
            live_checks.append({"check": "router_factory_match", "dex_id": deployment.dex_id,
                                "passed": None, "status": "unknown_no_reliable_router_address"})

    try:
        results = discover_and_verify_stablecoin_pools(METIS_TOKEN_ADDRESS, rpc_url=ACTIVE_RPC_URL)
    except Exception as exc:
        discovery_error = f"{type(exc).__name__}: {exc}"

    pair_checks: dict[str, dict[str, object]] = {}
    for item in results:
        deployment = next((entry for entry in deployments
                           if entry.dex_id.lower() == item.pool.dex_id.lower()), None)
        if deployment is None:
            continue
        try:
            checked = verify_factory_pair(item.pool, deployment.factory_address,
                                           rpc_url=ACTIVE_RPC_URL,
                                           timeout_seconds=TIMEOUT_SECONDS)
            pair_checks[item.pool.pool_address.lower()] = {
                "dex_id": deployment.dex_id, "factory_address": checked.factory_address,
                "reported_pair_address": checked.reported_pair_address,
                "passed": checked.verified, "checks": list(checked.checks),
                "errors": list(checked.errors)}
        except Exception as exc:
            pair_checks[item.pool.pool_address.lower()] = {
                "dex_id": deployment.dex_id, "factory_address": deployment.factory_address,
                "passed": False, "error": f"{type(exc).__name__}: {exc}"}

    report = json.loads(render_json_report(results, deployments, generated_at_utc=now))
    report["input_token"] = {
        "symbol": "METIS", "address": METIS_TOKEN_ADDRESS,
        "address_source": "Metis official connection details: built-in L2 token predeploy",
        "explorer_url": "https://andromeda-explorer.metis.io/token/0xdeaddeaddeaddeaddeaddeaddeaddeaddead0000",
        "predeploy_has_bytecode": token_code}
    report["rpc_endpoint"] = ACTIVE_RPC_URL
    report["rpc_endpoint_attempts"] = rpc_attempts
    report["live_deployment_checks"] = live_checks
    report["factory_pair_checks"] = pair_checks
    report["discovery_error"] = discovery_error
    report["note"] = ("Live checks use read-only JSON-RPC calls. Liquidity and 24h volume are "
                      "third-party indexer values. No transaction is submitted.")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / "metis-live-smoke-report.json"
    markdown_path = ARTIFACT_DIR / "metis-live-smoke-report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown = render_markdown_report(results, deployments, generated_at_utc=now)
    markdown += "\n## Live deployment checks\n\n| Check | DEX | Address | Result | Detail |\n|---|---|---|---|---|\n"
    for check in live_checks:
        status = "PASS" if check.get("passed") is True else (
            "UNKNOWN" if check.get("passed") is None else "FAIL")
        detail = check.get("error") or check.get("status") or ", ".join(check.get("checks", [])) or ""
        address = check.get("address") or check.get("router_address") or "—"
        detail = str(detail).replace("|", "\\|")
        markdown += f"| {check.get('check', 'check')} | {check.get('dex_id', '—')} | {address} | {status} | {detail} |\n"
    markdown += "\n## Factory pair checks\n\n"
    if pair_checks:
        for address, check in pair_checks.items():
            detail = check.get("error") or ", ".join(check.get("checks", [])) or ", ".join(check.get("errors", []))
            markdown += (f"- {check['dex_id']} pool {address}: "
                         f"{'PASS' if check.get('passed') else 'FAIL'}; "
                         f"factory {check['factory_address']}; "
                         f"reported pair {check.get('reported_pair_address', 'unknown')}; details {detail}\n")
    else:
        markdown += "- No matching positive-liquidity stablecoin pools were returned by discovery.\n"
    markdown += f"\nDiscovery error: {discovery_error or 'none'}\n"
    markdown_path.write_text(markdown, encoding="utf-8")
    print("=== LIVE METIS DEX SMOKE TEST: MARKDOWN REPORT ===")
    print(markdown)
    print("=== LIVE METIS DEX SMOKE TEST: JSON REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Artifacts: {json_path} ; {markdown_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
