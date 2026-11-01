"""Network-agnostic models for global token and pool research.

Identifiers are strings by design: not every chain uses EVM integer chain IDs
or 20-byte contract addresses.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TokenIdentity:
    name: str | None
    symbol: str | None
    network: str
    asset_id: str | None
    token_type: str = "unknown"
    source: str = ""
    source_url: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.network.casefold(), (self.asset_id or f"{self.symbol or ''}:{self.name or ''}").casefold())


@dataclass(frozen=True)
class PoolCandidate:
    network: str
    dex_name: str
    pool_id: str | None
    token0: TokenIdentity
    token1: TokenIdentity
    liquidity_usd: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    pool_url: str | None = None
    source: str = ""
    source_url: str = ""
    fetched_at_utc: str = ""
    verification_status: str = "indexed_only"
    stablecoin_status: str = "unclassified"
    stablecoin_symbol: str | None = None
    stablecoin_evidence_url: str | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.network.casefold(), (self.pool_id or self.pool_url or "").casefold(), self.dex_name.casefold())


@dataclass(frozen=True)
class ProviderIssue:
    provider: str
    stage: str
    message: str


@dataclass
class ResearchReport:
    query: str
    generated_at_utc: str
    status: str
    identities: list[TokenIdentity]
    pools: list[PoolCandidate]
    providers_searched: list[str]
    networks_found: list[str]
    dexes_found: list[str]
    issues: list[ProviderIssue]
    coverage_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        def clean(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if hasattr(value, "__dataclass_fields__"):
                return {k: clean(v) for k, v in asdict(value).items()}
            if isinstance(value, list):
                return [clean(v) for v in value]
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            return value
        return clean(self)
