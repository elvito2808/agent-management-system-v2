"""Read-only StellarExpert liquidity-pool index adapter.

The public endpoint is paginated and indexed. This adapter scans a bounded number
of pages, so it reports candidates found in that window rather than claiming
exhaustive Stellar-wide discovery.
"""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlencode

from .global_providers import _decimal, _http_json, utc_now

BASE_URL = "https://api.stellar.expert/explorer/public/liquidity-pool"
EXPLORER_URL = "https://stellar.expert/explorer/public/liquidity-pool"


def _asset_identity(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        asset_id = raw.strip()
        if not asset_id:
            return None
        if asset_id.upper() == "XLM":
            return {"name": "Stellar Lumens", "symbol": "XLM", "network": "stellar",
                    "asset_id": "XLM", "token_type": "native",
                    "source": "stellarexpert", "source_url": "https://stellar.expert/explorer/public"}
        # Stellar classic assets are represented as CODE-ISSUER[-TYPE].
        code = asset_id.split("-", 1)[0] if "-" in asset_id else asset_id
        return {"name": code, "symbol": code, "network": "stellar",
                "asset_id": asset_id, "token_type": "issued_asset" if "-" in asset_id else "unknown",
                "source": "stellarexpert", "source_url": "https://stellar.expert/explorer/public"}
    if not isinstance(raw, dict):
        return None
    asset_id = raw.get("asset") or raw.get("asset_id") or raw.get("id")
    code = raw.get("code") or raw.get("symbol")
    issuer = raw.get("issuer")
    if isinstance(asset_id, str) and asset_id:
        identity = _asset_identity(asset_id)
        if identity:
            identity["name"] = raw.get("name") if isinstance(raw.get("name"), str) else identity["name"]
            identity["symbol"] = code if isinstance(code, str) and code else identity["symbol"]
            return identity
    if isinstance(code, str) and code:
        canonical = code if code.upper() == "XLM" else f"{code}-{issuer}" if isinstance(issuer, str) and issuer else code
        identity = _asset_identity(canonical)
        if identity:
            identity["name"] = raw.get("name") if isinstance(raw.get("name"), str) else code
            return identity
    return None


def _pool_assets(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw_assets = record.get("assets")
    if not isinstance(raw_assets, list):
        raw_assets = record.get("asset")
    if not isinstance(raw_assets, list):
        return []
    assets = [_asset_identity(item) for item in raw_assets]
    return [item for item in assets if item is not None]


def _first_decimal(record: dict[str, Any], keys: tuple[str, ...]):
    for key in keys:
        value = _decimal(record.get(key))
        if value is not None:
            return value
    return None


class StellarExpertProvider:
    """Scan a bounded number of StellarExpert's public liquidity-pool pages."""

    name = "stellarexpert"

    def __init__(self, *, fetch_json: Callable[[str], Any] | None = None, max_pages: int = 5, page_size: int = 200):
        self._fetch_json = fetch_json or _http_json
        self.max_pages = max(1, min(int(max_pages), 10))
        self.page_size = max(1, min(int(page_size), 200))

    def search(self, query: str, *, network_filter: str | None = None,
               address_filter: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if network_filter and network_filter.casefold() not in {"stellar", "public", "stellar-public"}:
            return [], []
        query_norm = "".join(ch for ch in query.casefold() if ch.isalnum())
        timestamp = utc_now()
        identities: list[dict[str, Any]] = []
        pools: list[dict[str, Any]] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _ in range(self.max_pages):
            params = {"limit": self.page_size}
            if cursor:
                params["cursor"] = cursor
            url = f"{BASE_URL}?{urlencode(params)}"
            payload = self._fetch_json(url)
            if not isinstance(payload, dict):
                raise RuntimeError("StellarExpert returned an unexpected response shape")
            embedded = payload.get("_embedded") if isinstance(payload.get("_embedded"), dict) else {}
            records = embedded.get("records")
            if not isinstance(records, list):
                raise RuntimeError("StellarExpert response is missing _embedded.records")
            for record in records:
                if not isinstance(record, dict):
                    continue
                assets = _pool_assets(record)
                if len(assets) < 2:
                    continue
                for token in assets:
                    if query_norm in {
                        "".join(ch for ch in str(token.get("symbol") or "").casefold() if ch.isalnum()),
                        "".join(ch for ch in str(token.get("name") or "").casefold() if ch.isalnum()),
                        "".join(ch for ch in str(token.get("asset_id") or "").casefold() if ch.isalnum()),
                    } or (address_filter and address_filter.casefold() == str(token.get("asset_id") or "").casefold()):
                        identities.append(token)
                match = any(
                    query_norm in {
                        "".join(ch for ch in str(token.get("symbol") or "").casefold() if ch.isalnum()),
                        "".join(ch for ch in str(token.get("name") or "").casefold() if ch.isalnum()),
                        "".join(ch for ch in str(token.get("asset_id") or "").casefold() if ch.isalnum()),
                    } or (address_filter and address_filter.casefold() == str(token.get("asset_id") or "").casefold())
                    for token in assets
                )
                if not match:
                    continue
                if address_filter and not any(address_filter.casefold() == str(t.get("asset_id") or "").casefold() for t in assets):
                    continue
                pool_id = record.get("id") or record.get("pool_id") or record.get("address")
                pool_url = f"{EXPLORER_URL}/{pool_id}" if pool_id else EXPLORER_URL
                # Only fields explicitly denominated in USD are treated as USD.
                liquidity_usd = _first_decimal(record, ("total_value_locked_usd", "tvl_usd", "liquidity_usd"))
                volume_24h_usd = _first_decimal(record, ("volume_24h_usd", "volume24h_usd", "volume_24h"))
                dex_name = record.get("dex") or record.get("protocol") or "Stellar AMM"
                pools.append({
                    "network": "stellar", "dex_name": str(dex_name),
                    "pool_id": str(pool_id) if pool_id is not None else None,
                    "token0": assets[0], "token1": assets[1],
                    "liquidity_usd": liquidity_usd, "volume_24h_usd": volume_24h_usd,
                    "pool_url": pool_url, "source": self.name, "source_url": url,
                    "fetched_at_utc": timestamp, "verification_status": "indexed_only",
                })
            next_cursor = None
            if records:
                last = records[-1]
                if isinstance(last, dict) and last.get("paging_token") is not None:
                    next_cursor = str(last["paging_token"])
            links = payload.get("_links") if isinstance(payload.get("_links"), dict) else {}
            has_next = isinstance(links.get("next"), dict) or len(records) >= self.page_size
            if not has_next or not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        return identities, pools
