"""Match stablecoins by network-specific asset identifiers, never ticker alone."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).with_name("data") / "stablecoins.global.json"


def _norm(value: str) -> str:
    return value.strip().casefold()


def load_registry(path: str | Path | None = None) -> list[dict[str, Any]]:
    target = Path(path) if path else DATA_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load stablecoin registry {target}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("Stablecoin registry must be a JSON list")
    return [row for row in payload if isinstance(row, dict) and isinstance(row.get("asset_id"), str)]


def classify_pool(network: str, token0: dict[str, Any], token1: dict[str, Any],
                  registry: list[dict[str, Any]] | None = None) -> tuple[str, str | None, str | None]:
    """Return (status, matched symbol, evidence URL); unknowns remain unclassified."""
    entries = registry if registry is not None else load_registry()
    network_key = _norm(network)
    for token in (token0, token1):
        address = token.get("asset_id")
        if not isinstance(address, str) or not address.strip():
            continue
        for entry in entries:
            aliases = entry.get("network_aliases", [])
            if not isinstance(aliases, list):
                continue
            network_matches = network_key in {_norm(a) for a in aliases if isinstance(a, str)}
            if network_matches and _norm(address) == _norm(str(entry.get("asset_id", ""))):
                return "matched_registry", str(entry.get("symbol") or "unknown"), str(entry.get("source_url") or "")
    return "unclassified", None, None
