"""Load sourced DEX factory/router deployments for Metis Andromeda."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_REGISTRY = Path.cwd() / "config" / "dex_research" / "dexes_metis.json"
PACKAGED_REGISTRY = Path(__file__).resolve().parent / "data" / "dexes_metis.json"
DEFAULT_REGISTRY = REPOSITORY_REGISTRY if REPOSITORY_REGISTRY.is_file() else PACKAGED_REGISTRY


@dataclass(frozen=True)
class DexDeployment:
    chain_id: int
    dex_id: str
    name: str
    factory_address: str
    factory_source_url: str
    router_address: str | None
    router_source_url: str | None
    explorer_factory_url: str
    explorer_router_url: str | None
    confidence: str


def load_dex_registry(path: str | Path | None = None) -> list[DexDeployment]:
    """Load and validate DEX deployment addresses; unknown routers remain None."""
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY
    try:
        data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read DEX registry: {registry_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"DEX registry is not valid JSON: {registry_path}") from exc

    if not isinstance(data, dict):
        raise ValueError("DEX registry root must be a JSON object")
    chain_id = data.get("chain_id")
    rows = data.get("dexes")
    if not isinstance(chain_id, int) or isinstance(chain_id, bool) or chain_id <= 0:
        raise ValueError("DEX registry must contain a positive integer chain_id")
    if not isinstance(rows, list):
        raise ValueError("DEX registry dexes must be a list")

    result: list[DexDeployment] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each DEX registry entry must be an object")
        dex_id, name, factory = row.get("dex_id"), row.get("name"), row.get("factory_address")
        factory_source, explorer_factory = row.get("factory_source_url"), row.get("explorer_factory_url")
        if not all(isinstance(v, str) and v.strip() for v in (dex_id, name, factory, factory_source, explorer_factory)):
            raise ValueError("Each DEX entry needs id, name, factory address and source/explorer URLs")
        if not factory_source.startswith("https://") or not explorer_factory.startswith("https://"):
            raise ValueError("DEX factory source and explorer URLs must use HTTPS")
        router, router_source, explorer_router = (
            row.get("router_address"), row.get("router_source_url"), row.get("explorer_router_url")
        )
        if router is not None and (not isinstance(router, str) or not router.strip()):
            raise ValueError("router_address must be a non-empty string or null")
        if router is None and (router_source is not None or explorer_router is not None):
            raise ValueError("Router source/explorer must be null when router_address is unknown")
        if router is not None and (
            not isinstance(router_source, str) or not router_source.startswith("https://")
            or not isinstance(explorer_router, str) or not explorer_router.startswith("https://")
        ):
            raise ValueError("A known router must include HTTPS source and explorer URLs")
        confidence = row.get("confidence")
        if not isinstance(confidence, str) or not confidence.strip():
            raise ValueError("DEX entry must include confidence")
        result.append(DexDeployment(
            chain_id=chain_id,
            dex_id=dex_id.lower(),
            name=name,
            factory_address=factory,
            factory_source_url=factory_source,
            router_address=router,
            router_source_url=router_source,
            explorer_factory_url=explorer_factory,
            explorer_router_url=explorer_router,
            confidence=confidence,
        ))
    return result
