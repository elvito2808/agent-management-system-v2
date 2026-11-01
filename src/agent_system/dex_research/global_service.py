"""Orchestrate provider-driven, cross-network token and pool discovery."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
import re

from .global_models import PoolCandidate, ProviderIssue, ResearchReport, TokenIdentity
from .global_providers import DexScreenerProvider, GeckoTerminalProvider, PoolProvider


def _identity(raw: dict[str, Any]) -> TokenIdentity:
    return TokenIdentity(
        name=raw.get("name"), symbol=raw.get("symbol"),
        network=str(raw.get("network") or "unknown"),
        asset_id=raw.get("asset_id"), token_type=str(raw.get("token_type") or "unknown"),
        source=str(raw.get("source") or ""), source_url=str(raw.get("source_url") or ""),
    )


def _pool(raw: dict[str, Any]) -> PoolCandidate:
    return PoolCandidate(
        network=str(raw.get("network") or "unknown"), dex_name=str(raw.get("dex_name") or "unknown"),
        pool_id=raw.get("pool_id"), token0=_identity(raw["token0"]), token1=_identity(raw["token1"]),
        liquidity_usd=raw.get("liquidity_usd"), volume_24h_usd=raw.get("volume_24h_usd"),
        pool_url=raw.get("pool_url"), source=str(raw.get("source") or ""),
        source_url=str(raw.get("source_url") or ""), fetched_at_utc=str(raw.get("fetched_at_utc") or ""),
        verification_status=str(raw.get("verification_status") or "indexed_only"),
    )


def _normal(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _query_matches_token(query: str, token: TokenIdentity) -> bool:
    needle = _normal(query)
    if not needle:
        return False
    return needle in {_normal(token.name), _normal(token.symbol), _normal(token.asset_id)}


def research_token(
    query: str,
    *,
    providers: Iterable[PoolProvider] | None = None,
    network_filter: str | None = None,
    address_filter: str | None = None,
) -> ResearchReport:
    """Search multiple global providers; one provider failure never aborts the report.

    The providers' search APIs may return a capped result set. Coverage is therefore
    explicitly provider-supported rather than a claim of exhaustive global indexing.
    """
    requested = query.strip()
    if not requested:
        raise ValueError("Token name or symbol must not be empty")
    adapters = list(providers) if providers is not None else [DexScreenerProvider(), GeckoTerminalProvider()]
    identities: dict[tuple[str, str], TokenIdentity] = {}
    pools: dict[tuple[str, str, str], PoolCandidate] = {}
    issues: list[ProviderIssue] = []
    searched: list[str] = []
    for provider in adapters:
        searched.append(provider.name)
        try:
            raw_identities, raw_pools = provider.search(
                requested, network_filter=network_filter, address_filter=address_filter
            )
            for raw in raw_identities:
                try:
                    identity = _identity(raw)
                    if not network_filter or identity.network.casefold() == network_filter.casefold():
                        identities.setdefault(identity.key, identity)
                except (TypeError, ValueError, KeyError):
                    continue
            for raw in raw_pools:
                try:
                    pool = _pool(raw)
                    if network_filter and pool.network.casefold() != network_filter.casefold():
                        continue
                    if address_filter and address_filter.casefold() not in {
                        (pool.token0.asset_id or "").casefold(), (pool.token1.asset_id or "").casefold()
                    }:
                        continue
                    # Avoid showing irrelevant search matches if the provider's search is broad.
                    if not ( _query_matches_token(requested, pool.token0)
                             or _query_matches_token(requested, pool.token1)
                             or (address_filter and address_filter.casefold() in {
                                 (pool.token0.asset_id or "").casefold(), (pool.token1.asset_id or "").casefold()
                             })):
                        continue
                    pools.setdefault(pool.key, pool)
                except (TypeError, ValueError, KeyError):
                    continue
        except Exception as exc:
            issues.append(ProviderIssue(provider=provider.name, stage="search", message=f"{type(exc).__name__}: {exc}"))

    # A pool returned by more than one provider is represented once; retain provenance
    # in source field when the duplicate source is encountered.
    status = "data_found" if pools else ("partial_data" if issues and identities else "insufficient_data")
    if issues and pools:
        status = "partial_data"
    networks = sorted({p.network for p in pools.values()}, key=str.casefold)
    dexes = sorted({p.dex_name for p in pools.values()}, key=str.casefold)
    notes = [
        "Pool and volume figures are third-party indexed metrics, not independently verified on-chain.",
        "Search endpoints may cap results; absence from these results is not proof that no pool exists.",
        "Stablecoin classification remains unclassified until a network-specific asset identifier matches a reviewed registry entry.",
        "DEX Screener and GeckoTerminal are the configured sources; networks unsupported or omitted by them are coverage gaps.",
    ]
    if not pools and issues:
        notes.append("No pool rows were returned and at least one provider failed; this is not evidence that the token has no liquidity.")
    return ResearchReport(
        query=requested,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        status=status, identities=sorted(identities.values(), key=lambda x: (x.network.casefold(), (x.symbol or "").casefold())),
        pools=sorted(pools.values(), key=lambda x: x.liquidity_usd or 0, reverse=True),
        providers_searched=searched, networks_found=networks, dexes_found=dexes,
        issues=issues, coverage_notes=notes,
    )


def render_markdown(report: ResearchReport) -> str:
    lines = [
        f"# Global DEX research: {report.query}", "",
        f"- Generated (UTC): {report.generated_at_utc}",
        f"- Status: **{report.status}**",
        f"- Providers queried: {', '.join(report.providers_searched) or 'none'}",
        f"- Networks found: {', '.join(report.networks_found) or 'none'}",
        f"- DEXs found: {', '.join(report.dexes_found) or 'none'}", "",
        "## Candidate identities", "",
    ]
    if not report.identities:
        lines.append("No candidate token identities were returned.")
    else:
        lines += ["| Network | Name | Symbol | Asset ID | Type | Source |", "|---|---|---|---|---|---|"]
        for item in report.identities:
            cells = [item.network, item.name or "unknown", item.symbol or "unknown", item.asset_id or "unknown", item.token_type, f"[{item.source}]({item.source_url})" if item.source_url else item.source or "unknown"]
            lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in cells) + " |")
    lines += ["", "## Pools", ""]
    if not report.pools:
        lines.append("No matching pool was returned by the providers searched.")
    else:
        lines += ["| Network | DEX | Pair | Pool | Liquidity USD | 24h volume USD | Stablecoin status | Verification | Source |", "|---|---|---|---|---:|---:|---|---|---|"]
        for p in report.pools:
            pair = f"{p.token0.symbol or p.token0.name or '?'} / {p.token1.symbol or p.token1.name or '?'}"
            values = [p.network, p.dex_name, pair, p.pool_id or "unknown", str(p.liquidity_usd) if p.liquidity_usd is not None else "unknown", str(p.volume_24h_usd) if p.volume_24h_usd is not None else "unknown", p.stablecoin_status, p.verification_status, f"[{p.source}]({p.source_url})" if p.source_url else p.source]
            lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in values) + " |")
            if p.pool_url:
                lines.append(f"  - Pool page: {p.pool_url}")
    lines += ["", "## Provider errors", ""]
    if report.issues:
        lines += [f"- **{i.provider}** ({i.stage}): {i.message}" for i in report.issues]
    else:
        lines.append("No provider errors were reported.")
    lines += ["", "## Coverage and limitations", ""] + [f"- {note}" for note in report.coverage_notes]
    lines += ["", "This report is read-only. Indexed metrics and discovered identifiers are not represented as on-chain verified unless an explicit verifier later confirms them.", ""]
    return "\n".join(lines)
