"""Load explicitly sourced stablecoin addresses for supported networks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import StablecoinEntry


REPOSITORY_METIS_REGISTRY = (
    Path.cwd() / "config" / "dex_research" / "stablecoins_metis.json"
)
PACKAGED_METIS_REGISTRY = Path(__file__).resolve().parent / "data" / "stablecoins_metis.json"
DEFAULT_METIS_REGISTRY = (
    REPOSITORY_METIS_REGISTRY
    if REPOSITORY_METIS_REGISTRY.is_file()
    else PACKAGED_METIS_REGISTRY
)


def load_stablecoin_registry(path: str | Path | None = None) -> list[StablecoinEntry]:
    """Load stablecoin entries from the repository's reviewed JSON registry."""
    registry_path = Path(path) if path is not None else DEFAULT_METIS_REGISTRY
    try:
        data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read stablecoin registry: {registry_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stablecoin registry is not valid JSON: {registry_path}") from exc

    if not isinstance(data, dict):
        raise ValueError("Stablecoin registry root must be a JSON object")
    chain_id = data.get("chain_id")
    reviewed_at = data.get("reviewed_at_utc")
    source_url = data.get("source_url")
    tokens = data.get("tokens")
    if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
        raise ValueError("Stablecoin registry must contain a positive integer chain_id")
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise ValueError("Stablecoin registry must contain reviewed_at_utc")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("Stablecoin registry must contain an HTTPS source_url")
    if not isinstance(tokens, list):
        raise ValueError("Stablecoin registry tokens must be a list")

    entries: list[StablecoinEntry] = []
    for token in tokens:
        if not isinstance(token, dict):
            raise ValueError("Each stablecoin registry entry must be an object")
        address = token.get("address")
        symbol = token.get("symbol")
        if not isinstance(address, str) or not isinstance(symbol, str):
            raise ValueError("Each stablecoin registry entry needs address and symbol")
        entries.append(
            StablecoinEntry(
                chain_id=chain_id,
                address=address,
                symbol=symbol,
                source_url=source_url,
                reviewed_at_utc=reviewed_at,
            )
        )
    return entries
