"""Read-only DEX Screener client for token-pair discovery.

Results are third-party indexer data, not independent on-chain verification.
The client deliberately accepts a token contract address, not a symbol.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import PoolCandidate, candidate_from_dexscreener

API_BASE = "https://api.dexscreener.com"
METIS_CHAIN_SLUG = "metis"
METIS_CHAIN_ID = 1088


class DexScreenerError(RuntimeError):
    """Raised when the DEX Screener API cannot provide usable pair data."""


def fetch_token_pairs(
    token_address: str,
    *,
    chain_slug: str = METIS_CHAIN_SLUG,
    chain_id: int = METIS_CHAIN_ID,
    timeout_seconds: float = 12.0,
    opener: Callable = urlopen,
) -> list[PoolCandidate]:
    """Fetch indexed pairs for one contract address and convert valid pair rows.

    The API returns a JSON array. Missing liquidity/volume remain unknown (None).
    This function performs no transactions and does not verify contracts on-chain.
    """
    address = token_address.strip()
    if not address:
        raise ValueError("token_address must be a contract address, not an empty string")
    if not chain_slug.strip():
        raise ValueError("chain_slug must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    endpoint = f"{API_BASE}/token-pairs/v1/{chain_slug}/{address}"
    request = Request(endpoint, headers={"Accept": "application/json", "User-Agent": "agent-management-system-v2"})
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise DexScreenerError(f"DEX Screener request failed: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DexScreenerError("DEX Screener returned invalid JSON") from exc
    if not isinstance(payload, list):
        raise DexScreenerError("DEX Screener returned an unexpected response shape")

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    candidates: list[PoolCandidate] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        reported_chain = row.get("chainId")
        if isinstance(reported_chain, str) and reported_chain.lower() != chain_slug.lower():
            continue
        pair_url = row.get("url")
        source_url = pair_url if isinstance(pair_url, str) and pair_url.startswith("https://") else endpoint
        try:
            candidates.append(
                candidate_from_dexscreener(
                    row,
                    chain_id=chain_id,
                    source_url=source_url,
                    fetched_at_utc=fetched_at,
                )
            )
        except (ValueError, TypeError):
            # Skip malformed rows rather than fabricate missing contract identities.
            continue
    return candidates
