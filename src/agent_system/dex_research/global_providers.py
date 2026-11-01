"""Public read-only adapters for global DEX discovery.

Provider payloads are indexed data, never independent on-chain verification.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _http_json(url: str, timeout: float = 15.0) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "agent-management-system-v2/0.7"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {url} failed: {type(exc).__name__}: {exc}") from exc


class PoolProvider(Protocol):
    name: str
    def search(self, query: str, *, network_filter: str | None = None, address_filter: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...


def _dex_token(raw: Any, network: str, provider: str, source_url: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    address = raw.get("address")
    name = raw.get("name")
    symbol = raw.get("symbol")
    if not any(isinstance(x, str) and x.strip() for x in (address, name, symbol)):
        return None
    return {"name": name if isinstance(name, str) else None,
            "symbol": symbol if isinstance(symbol, str) else None,
            "network": network or "unknown",
            "asset_id": address.strip() if isinstance(address, str) and address.strip() else None,
            "token_type": "contract" if isinstance(address, str) and address.strip() else "unknown",
            "source": provider, "source_url": source_url}


class DexScreenerProvider:
    name = "dexscreener"
    base_url = "https://api.dexscreener.com/latest/dex/search"

    def search(self, query: str, *, network_filter: str | None = None, address_filter: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        url = f"{self.base_url}/?q={quote(query, safe='')}"
        payload = _http_json(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("pairs"), list):
            raise RuntimeError("DEX Screener returned an unexpected response shape")
        timestamp = utc_now()
        pools: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for row in payload["pairs"]:
            if not isinstance(row, dict):
                continue
            network = str(row.get("chainId") or "unknown")
            if network_filter and network.casefold() != network_filter.casefold():
                continue
            url_pool = row.get("url") if isinstance(row.get("url"), str) else url
            base = _dex_token(row.get("baseToken"), network, self.name, url_pool)
            quote_token = _dex_token(row.get("quoteToken"), network, self.name, url_pool)
            if base:
                identities.append(base)
            if quote_token:
                identities.append(quote_token)
            if not base or not quote_token:
                continue
            if address_filter and address_filter.casefold() not in {
                (base.get("asset_id") or "").casefold(), (quote_token.get("asset_id") or "").casefold()
            }:
                continue
            liquidity = row.get("liquidity") if isinstance(row.get("liquidity"), dict) else {}
            volume = row.get("volume") if isinstance(row.get("volume"), dict) else {}
            dex = row.get("dexId") if isinstance(row.get("dexId"), str) else "unknown"
            pools.append({
                "network": network, "dex_name": dex, "pool_id": row.get("pairAddress"),
                "token0": base, "token1": quote_token,
                "liquidity_usd": _decimal(liquidity.get("usd")),
                "volume_24h_usd": _decimal(volume.get("h24")),
                "pool_url": url_pool, "source": self.name, "source_url": url,
                "fetched_at_utc": timestamp, "verification_status": "indexed_only",
            })
        return identities, pools


class GeckoTerminalProvider:
    """Second independent provider; missing token metadata stays unknown."""
    name = "geckoterminal"
    base_url = "https://api.geckoterminal.com/api/v2/search/pools"

    def search(self, query: str, *, network_filter: str | None = None, address_filter: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        url = f"{self.base_url}?query={quote(query, safe='')}&page=1&include=base_token,quote_token,dex,network"
        payload = _http_json(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("GeckoTerminal returned an unexpected response shape")
        included = payload.get("included") if isinstance(payload.get("included"), list) else []
        included_by_id = {item.get("id"): item for item in included if isinstance(item, dict) and isinstance(item.get("id"), str)}
        timestamp = utc_now()
        pools: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        for row in payload["data"]:
            if not isinstance(row, dict):
                continue
            attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
            rels = row.get("relationships") if isinstance(row.get("relationships"), dict) else {}
            network_rel = rels.get("network") if isinstance(rels.get("network"), dict) else {}
            network_data = network_rel.get("data") if isinstance(network_rel.get("data"), dict) else {}
            network = str(network_data.get("id") or attrs.get("network") or "unknown")
            if network_filter and network.casefold() != network_filter.casefold():
                continue
            def related_token(key: str) -> dict[str, Any] | None:
                rel = rels.get(key) if isinstance(rels.get(key), dict) else {}
                data = rel.get("data") if isinstance(rel.get("data"), dict) else {}
                item = included_by_id.get(data.get("id"), {})
                a = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
                address = a.get("address")
                token_url = f"https://www.geckoterminal.com/{network}/pools/{attrs.get('address', '')}"
                token = {"name": a.get("name") if isinstance(a.get("name"), str) else None,
                         "symbol": a.get("symbol") if isinstance(a.get("symbol"), str) else None,
                         "network": network,
                         "asset_id": address if isinstance(address, str) and address else None,
                         "token_type": "contract" if isinstance(address, str) and address else "unknown",
                         "source": self.name, "source_url": token_url}
                return token if any(token[k] for k in ("name", "symbol", "asset_id")) else None
            token0 = related_token("base_token")
            token1 = related_token("quote_token")
            if token0:
                identities.append(token0)
            if token1:
                identities.append(token1)
            if not token0 or not token1:
                continue
            if address_filter and address_filter.casefold() not in {
                (token0.get("asset_id") or "").casefold(), (token1.get("asset_id") or "").casefold()
            }:
                continue
            dex_rel = rels.get("dex") if isinstance(rels.get("dex"), dict) else {}
            dex_data = dex_rel.get("data") if isinstance(dex_rel.get("data"), dict) else {}
            dex_item = included_by_id.get(dex_data.get("id"), {})
            dex_attrs = dex_item.get("attributes") if isinstance(dex_item.get("attributes"), dict) else {}
            pool_address = attrs.get("address")
            pool_url = f"https://www.geckoterminal.com/{network}/pools/{pool_address}" if pool_address else None
            pools.append({
                "network": network, "dex_name": str(dex_attrs.get("name") or dex_data.get("id") or "unknown"),
                "pool_id": pool_address, "token0": token0, "token1": token1,
                "liquidity_usd": _decimal(attrs.get("reserve_in_usd")),
                "volume_24h_usd": _decimal((attrs.get("volume_usd") or {}).get("h24") if isinstance(attrs.get("volume_usd"), dict) else None),
                "pool_url": pool_url, "source": self.name, "source_url": url,
                "fetched_at_utc": timestamp, "verification_status": "indexed_only",
            })
        return identities, pools
