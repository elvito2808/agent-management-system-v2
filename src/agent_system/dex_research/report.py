"""Render transparent JSON and Markdown reports from DEX research results."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from .dex_registry import DexDeployment
from .service import VerifiedPoolResult


def _number(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def pool_result_record(result: VerifiedPoolResult, deployments: Iterable[DexDeployment]) -> dict[str, object]:
    pool = result.pool
    deployment = next((entry for entry in deployments
                        if entry.chain_id == pool.chain_id and entry.dex_id.lower() == pool.dex_id.lower()), None)
    verification = result.verification
    return {
        "network": "Metis Andromeda" if pool.chain_id == 1088 else f"chain_id:{pool.chain_id}",
        "chain_id": pool.chain_id,
        "dex_id": pool.dex_id,
        "pool_address": pool.pool_address,
        "token0": {"symbol": pool.token0.symbol, "address": pool.token0.address},
        "token1": {"symbol": pool.token1.symbol, "address": pool.token1.address},
        "liquidity_usd_reported": _number(pool.liquidity_usd),
        "volume_24h_usd_reported": _number(pool.volume_24h_usd),
        "source_url": pool.source_url,
        "fetched_at_utc": pool.fetched_at_utc,
        "explorer_url": f"https://andromeda-explorer.metis.io/address/{pool.pool_address}",
        "factory_address": deployment.factory_address if deployment else None,
        "factory_source_url": deployment.factory_source_url if deployment else None,
        "router_address": deployment.router_address if deployment else None,
        "router_source_url": deployment.router_source_url if deployment else None,
        "router_status": "documented_not_live_verified" if deployment and deployment.router_address else "unknown",
        "pool_onchain_verified": result.verified,
        "onchain_checks": list(verification.checks) if verification else [],
        "onchain_errors": list(verification.errors) if verification else [],
        "verification_error": result.error,
        "verification_rpc_url": verification.rpc_url if verification else None,
    }


def render_json_report(results: Iterable[VerifiedPoolResult], deployments: Iterable[DexDeployment],
                       *, generated_at_utc: str | None = None) -> str:
    now = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    deployment_list = list(deployments)
    records = [pool_result_record(item, deployment_list) for item in results]
    return json.dumps({
        "generated_at_utc": now,
        "network": "Metis Andromeda",
        "read_only": True,
        "results_count": len(records),
        "results": records,
        "limitations": [
            "Liquidity and volume are reported by a third-party indexer and are not independently priced or reserve-reconciled here.",
            "Router addresses are sourced from deployment documentation but are not marked live-verified by this report.",
            "A pool is on-chain verified only when the RPC verifier completed successfully."
        ]
    }, indent=2, ensure_ascii=False)


def render_markdown_report(results: Iterable[VerifiedPoolResult], deployments: Iterable[DexDeployment],
                           *, generated_at_utc: str | None = None) -> str:
    now = generated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    deployment_list = list(deployments)
    records = [pool_result_record(item, deployment_list) for item in results]
    lines = [
        "# Metis Andromeda DEX Stablecoin Pool Report", "",
        f"- Generated at (UTC): {now}", "- Mode: read-only", f"- Results: {len(records)}", "",
        "| DEX | Pair | Pool | Reported liquidity (USD) | 24h volume (USD) | On-chain check | Router |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for item in records:
        pair = f"{item['token0']['symbol'] or '?'} / {item['token1']['symbol'] or '?'}"
        liquidity = item["liquidity_usd_reported"] if item["liquidity_usd_reported"] is not None else "unknown"
        volume = item["volume_24h_usd_reported"] if item["volume_24h_usd_reported"] is not None else "unknown"
        verified = "verified" if item["pool_onchain_verified"] else "not verified"
        router = item["router_address"] or "unknown"
        lines.append(f"| {item['dex_id']} | {pair} | [{item['pool_address']}]({item['explorer_url']}) | {liquidity} | {volume} | {verified} | {router} |")
    lines += ["", "## Sources and verification", ""]
    for item in records:
        lines += [
            f"### {item['dex_id']} — {item['pool_address']}",
            f"- Source: {item['source_url'] or 'unknown'}",
            f"- Data fetched (UTC): {item['fetched_at_utc'] or 'unknown'}",
            f"- Factory: {item['factory_address'] or 'unknown'}",
            f"- Factory source: {item['factory_source_url'] or 'unknown'}",
            f"- Router source: {item['router_source_url'] or 'unknown'}",
            f"- RPC verification checks: {', '.join(item['onchain_checks']) or 'none'}",
            f"- RPC verification errors: {', '.join(item['onchain_errors']) or item['verification_error'] or 'none'}", ""
        ]
    lines += ["## Limitations", "",
              "- Liquidity and volume are reported by a third-party indexer and are not independently reserve-reconciled.",
              "- Router documentation is not the same as live on-chain verification; unknown router addresses remain unknown.",
              "- Missing metrics are shown as unknown, not zero.",
              "- This report does not submit transactions.", ""]
    return "\n".join(lines)
