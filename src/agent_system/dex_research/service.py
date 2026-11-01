"""High-level read-only service for Metis stablecoin-pool discovery."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .client import fetch_token_pairs
from .models import PoolCandidate, StablecoinEntry, filter_stablecoin_pools
from .registry import load_stablecoin_registry


DEFAULT_METIS_DEX_IDS = ("netswap", "tethys")


def discover_stablecoin_pools(
    token_address: str,
    *,
    registry: Iterable[StablecoinEntry] | None = None,
    registry_path: str | Path | None = None,
    dex_ids: Iterable[str] = DEFAULT_METIS_DEX_IDS,
    require_positive_liquidity: bool = True,
    fetcher: Callable[..., list[PoolCandidate]] = fetch_token_pairs,
) -> list[PoolCandidate]:
    """Find indexed pools on configured DEXs paired with a known stablecoin.

    By default, only rows with positive reported USD liquidity are returned.
    This is a third-party indexer signal, not an on-chain reserve verification.
    """
    entries = list(registry) if registry is not None else load_stablecoin_registry(registry_path)
    allowed_dex_ids = {dex_id.strip().lower() for dex_id in dex_ids if dex_id.strip()}
    if not allowed_dex_ids:
        raise ValueError("At least one DEX ID must be configured")

    candidates = fetcher(token_address)
    candidates = [
        pool for pool in candidates
        if pool.dex_id.strip().lower() in allowed_dex_ids
    ]
    candidates = filter_stablecoin_pools(candidates, entries)
    if require_positive_liquidity:
        candidates = [
            pool for pool in candidates
            if pool.liquidity_usd is not None and pool.liquidity_usd > 0
        ]
    return sorted(
        candidates,
        key=lambda pool: pool.liquidity_usd if pool.liquidity_usd is not None else 0,
        reverse=True,
    )
