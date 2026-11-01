"""Small, dependency-free models and filters for DEX pool discovery.

This module intentionally does not fetch live data or verify contracts on-chain.
Pool candidates are discovery results until a separate verifier checks them.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping


def normalize_address(address: str | None) -> str | None:
    """Normalize a hex address for case-insensitive comparison; do not invent one."""
    if not address:
        return None
    value = address.strip()
    if not value:
        return None
    return value.lower()


@dataclass(frozen=True)
class TokenIdentity:
    chain_id: int
    address: str
    symbol: str | None = None

    def __post_init__(self) -> None:
        if self.chain_id <= 0:
            raise ValueError("chain_id must be a positive integer")
        if normalize_address(self.address) is None:
            raise ValueError("token address must not be empty")


@dataclass(frozen=True)
class StablecoinEntry:
    chain_id: int
    address: str
    symbol: str
    source_url: str
    reviewed_at_utc: str

    def __post_init__(self) -> None:
        if self.chain_id <= 0:
            raise ValueError("chain_id must be a positive integer")
        if normalize_address(self.address) is None:
            raise ValueError("stablecoin address must not be empty")
        if not self.symbol.strip():
            raise ValueError("stablecoin symbol must not be empty")
        if not self.source_url.strip():
            raise ValueError("stablecoin source_url must not be empty")
        if not self.reviewed_at_utc.strip():
            raise ValueError("stablecoin reviewed_at_utc must not be empty")


@dataclass(frozen=True)
class PoolCandidate:
    chain_id: int
    dex_id: str
    pool_address: str
    token0: TokenIdentity
    token1: TokenIdentity
    liquidity_usd: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    source_url: str | None = None
    fetched_at_utc: str | None = None

    def __post_init__(self) -> None:
        if self.chain_id <= 0:
            raise ValueError("chain_id must be a positive integer")
        if not self.dex_id.strip():
            raise ValueError("dex_id must not be empty")
        if normalize_address(self.pool_address) is None:
            raise ValueError("pool_address must not be empty")
        if self.token0.chain_id != self.chain_id or self.token1.chain_id != self.chain_id:
            raise ValueError("both pool tokens must belong to the pool's chain")


def stablecoin_match(
    pool: PoolCandidate,
    registry: Iterable[StablecoinEntry],
) -> StablecoinEntry | None:
    """Return a matching stablecoin only when chain and contract address both match."""
    entries = tuple(registry)
    for token in (pool.token0, pool.token1):
        token_address = normalize_address(token.address)
        for entry in entries:
            if entry.chain_id == pool.chain_id and normalize_address(entry.address) == token_address:
                return entry
    return None


def filter_stablecoin_pools(
    pools: Iterable[PoolCandidate],
    registry: Iterable[StablecoinEntry],
) -> list[PoolCandidate]:
    """Keep pools with one token matching a configured stablecoin contract."""
    entries = tuple(registry)
    return [pool for pool in pools if stablecoin_match(pool, entries) is not None]


def candidate_from_dexscreener(
    payload: Mapping[str, object],
    *,
    chain_id: int,
    source_url: str,
    fetched_at_utc: str,
) -> PoolCandidate:
    """Convert one DEX Screener-like pair object; absent numeric values stay None."""
    def mapping(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    base = mapping(payload.get("baseToken"))
    quote = mapping(payload.get("quoteToken"))
    liquidity = mapping(payload.get("liquidity"))
    volume = mapping(payload.get("volume"))

    def token(value: Mapping[str, object]) -> TokenIdentity:
        address = value.get("address")
        symbol = value.get("symbol")
        if not isinstance(address, str):
            raise ValueError("pair token is missing a contract address")
        return TokenIdentity(chain_id=chain_id, address=address,
                             symbol=symbol if isinstance(symbol, str) else None)

    def decimal_or_none(value: object) -> Decimal | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    dex_id = payload.get("dexId")
    pool_address = payload.get("pairAddress")
    if not isinstance(dex_id, str) or not isinstance(pool_address, str):
        raise ValueError("pair is missing dexId or pairAddress")

    return PoolCandidate(
        chain_id=chain_id,
        dex_id=dex_id,
        pool_address=pool_address,
        token0=token(base),
        token1=token(quote),
        liquidity_usd=decimal_or_none(liquidity.get("usd")),
        volume_24h_usd=decimal_or_none(volume.get("h24")),
        source_url=source_url,
        fetched_at_utc=fetched_at_utc,
    )
