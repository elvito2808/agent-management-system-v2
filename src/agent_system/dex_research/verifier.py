"""Read-only on-chain checks for UniswapV2-compatible pool contracts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import PoolCandidate, normalize_address

METIS_RPC_URL = "https://andromeda.metis.io/?owner=1088"
METIS_CHAIN_ID = 1088
TOKEN0_SELECTOR = "0x0dfe1681"
TOKEN1_SELECTOR = "0xd21220a7"


class OnChainVerificationError(RuntimeError):
    """Raised when an RPC response cannot safely support verification."""


@dataclass(frozen=True)
class OnChainPoolVerification:
    verified: bool
    chain_id: int | None
    pool_has_code: bool
    token0_address: str | None
    token1_address: str | None
    token0_has_code: bool | None
    token1_has_code: bool | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]
    rpc_url: str


def _rpc_call(
    rpc_url: str,
    method: str,
    params: list[object],
    *,
    timeout_seconds: float,
    opener: Callable,
) -> object:
    request_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode("utf-8")
    request = Request(
        rpc_url,
        data=request_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise OnChainVerificationError(f"RPC request failed ({method}): {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OnChainVerificationError(f"RPC returned invalid JSON ({method})") from exc
    if not isinstance(payload, dict):
        raise OnChainVerificationError(f"RPC returned an unexpected response ({method})")
    if payload.get("error") is not None:
        raise OnChainVerificationError(f"RPC error ({method}): {payload['error']}")
    if "result" not in payload:
        raise OnChainVerificationError(f"RPC response is missing result ({method})")
    return payload["result"]


def _has_code(result: object, label: str) -> bool:
    if not isinstance(result, str) or not result.startswith("0x"):
        raise OnChainVerificationError(f"Invalid eth_getCode result for {label}")
    return len(result) > 2 and any(character != "0" for character in result[2:])


def _address_from_call(result: object, label: str) -> str:
    if not isinstance(result, str) or not result.startswith("0x"):
        raise OnChainVerificationError(f"Invalid {label}() response")
    raw = result[2:]
    if len(raw) != 64 or any(character not in "0123456789abcdefABCDEF" for character in raw):
        raise OnChainVerificationError(f"Invalid ABI-encoded address from {label}()")
    return "0x" + raw[-40:]


def verify_v2_pool_onchain(
    pool: PoolCandidate,
    *,
    rpc_url: str = METIS_RPC_URL,
    expected_chain_id: int = METIS_CHAIN_ID,
    timeout_seconds: float = 12.0,
    opener: Callable = urlopen,
) -> OnChainPoolVerification:
    """Verify chain, bytecode, and token0/token1 for a V2-compatible pool.

    This does not audit router configuration or prove that reported liquidity is
    economically meaningful; it verifies the pool's on-chain token references.
    """
    if not rpc_url.startswith("https://"):
        raise ValueError("rpc_url must use HTTPS")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    chain_result = _rpc_call(
        rpc_url, "eth_chainId", [], timeout_seconds=timeout_seconds, opener=opener
    )
    if not isinstance(chain_result, str) or not chain_result.startswith("0x"):
        raise OnChainVerificationError("RPC returned invalid eth_chainId")
    try:
        actual_chain_id = int(chain_result, 16)
    except ValueError as exc:
        raise OnChainVerificationError("RPC returned invalid eth_chainId") from exc

    checks: list[str] = []
    errors: list[str] = []
    if actual_chain_id == expected_chain_id == pool.chain_id:
        checks.append(f"chain_id_matches:{actual_chain_id}")
    else:
        errors.append(
            f"chain_id_mismatch:rpc={actual_chain_id},expected={expected_chain_id},pool={pool.chain_id}"
        )
        return OnChainPoolVerification(
            False, actual_chain_id, False, None, None, None, None,
            tuple(checks), tuple(errors), rpc_url
        )

    pool_code = _has_code(
        _rpc_call(rpc_url, "eth_getCode", [pool.pool_address, "latest"],
                  timeout_seconds=timeout_seconds, opener=opener),
        "pool",
    )
    if not pool_code:
        errors.append("pool_has_no_code")
        return OnChainPoolVerification(
            False, actual_chain_id, False, None, None, None, None,
            tuple(checks), tuple(errors), rpc_url
        )
    checks.append("pool_has_bytecode")

    token0 = _address_from_call(
        _rpc_call(rpc_url, "eth_call", [{"to": pool.pool_address, "data": TOKEN0_SELECTOR}, "latest"],
                  timeout_seconds=timeout_seconds, opener=opener),
        "token0",
    )
    token1 = _address_from_call(
        _rpc_call(rpc_url, "eth_call", [{"to": pool.pool_address, "data": TOKEN1_SELECTOR}, "latest"],
                  timeout_seconds=timeout_seconds, opener=opener),
        "token1",
    )
    expected = {normalize_address(pool.token0.address), normalize_address(pool.token1.address)}
    actual = {normalize_address(token0), normalize_address(token1)}
    if actual != expected or token0.lower() == token1.lower():
        errors.append("pool_token_addresses_do_not_match_discovered_pair")
    else:
        checks.append("pool_token_addresses_match_discovered_pair")

    token0_code = _has_code(
        _rpc_call(rpc_url, "eth_getCode", [token0, "latest"],
                  timeout_seconds=timeout_seconds, opener=opener),
        "token0",
    )
    token1_code = _has_code(
        _rpc_call(rpc_url, "eth_getCode", [token1, "latest"],
                  timeout_seconds=timeout_seconds, opener=opener),
        "token1",
    )
    if token0_code:
        checks.append("token0_has_bytecode")
    else:
        errors.append("token0_has_no_code")
    if token1_code:
        checks.append("token1_has_bytecode")
    else:
        errors.append("token1_has_no_code")

    return OnChainPoolVerification(
        verified=not errors,
        chain_id=actual_chain_id,
        pool_has_code=pool_code,
        token0_address=token0,
        token1_address=token1,
        token0_has_code=token0_code,
        token1_has_code=token1_code,
        checks=tuple(checks),
        errors=tuple(errors),
        rpc_url=rpc_url,
    )
