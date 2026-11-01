# DEX Token Liquidity Research — Phase 1

## Scope

The first target network is Metis Andromeda (chain ID 1088). Initial DEXs: Netswap and Tethys.

This document is an implementation plan, not a claim that live data or on-chain checks are already implemented.

## Phase 1 goal

Create a safe, read-only discovery workflow for a token address. Discover candidate pools using DEX Screener, then filter them using an explicit stablecoin contract registry for Metis. Do not submit transactions or request private keys.

## Data source

Use the official DEX Screener API documentation:
https://docs.dexscreener.com/api/reference

Token-pairs endpoint:
GET https://api.dexscreener.com/token-pairs/v1/{chainId}/{tokenAddress}

Use chain ID / chain slug expected by the API as documented. Confirm API requirements during implementation. Treat responses as discovery data, not proof of on-chain validity.

## Required rules

- Identify a token by network and contract address, not symbol alone.
- Stablecoin matching must use the exact token contract address on Metis, not only symbols such as USDT or USDC.
- Exclude non-stablecoin pairs such as METIS/WETH.
- Keep pool address, token addresses, and router address as separate fields.
- Never guess a router address. Resolve it from official DEX documentation or verified deployment data.
- Record report time in UTC, source URL, and fetch time.
- Unknown values remain unknown; they must not be silently replaced with zero.
- If API data is stale, missing, or fails, report that limitation rather than claiming no pools exist.
- This initial workflow is read-only; it must not sign or send transactions.

## Report fields

For each candidate pool, return:
- DEX name and network
- pool/pair contract address
- both token symbols and contract addresses
- stablecoin match and registry source
- reported USD liquidity and 24h volume, when available
- last activity timestamp, only when supported by a reliable source
- router address and source, or "unverified"
- explorer URL
- source URL, fetch time, and verification status

## Implementation stages

1. Add data models and offline tests for token identity, candidate pools, stablecoin registry, and verification status.
2. Add a DEX Screener API client with timeout, error handling, and mocked tests.
3. Add a sourced Metis stablecoin registry and filter candidates by contract address.
4. Add read-only RPC checks for contract code and pool token addresses.
5. Add separate router verification based on official Netswap/Tethys deployment information.
6. Connect the workflow to the Agent Management System task runner only after the standalone tests pass.

## Acceptance criteria for Phase 1

- A pair is accepted only when the stablecoin contract address matches the configured registry on the selected network.
- A pair like METIS/WETH is excluded from stablecoin results.
- Missing fields and API errors are surfaced explicitly.
- Unit tests do not need internet access.
- No router or contract address is fabricated.


## Implementation status (2026-11-01)

Completed on `feature/dex-research-agent`:
- Read-only DEX Screener client for token-address pair discovery using the documented `/token-pairs/v1/{chainId}/{tokenAddress}` endpoint.
- Sourced Metis Andromeda registry entries for canonical-bridge m.USDC and m.USDT, with the official Metis technical migration guide recorded as the source.
- Registry loader with input validation.
- Offline unit tests for API parsing/error cases and exact-address stablecoin filtering.
- GitHub Actions workflow running the DEX research unit tests on pushes and pull requests.
- High-level discovery service combining API fetching, exact-address stablecoin filtering, Netswap/Tethys allowlisting, and positive reported-liquidity filtering.
- Read-only Metis JSON-RPC verifier checks chain ID, deployed bytecode, and V2-compatible pool token0/token1 addresses against the discovered pair.
- Sourced DEX deployment registry: Netswap factory/router are documented in the protocol's exchange-contracts repository; Tethys factory is listed in a historical security audit report. Tethys router remains unknown and is deliberately null.
- Factory verifier checks whether a V2-compatible factory's getPair(token0, token1) matches the discovered pool address.
- Router verifier checks bytecode and router.factory() against the sourced factory address when a router address is known.
- JSON and Markdown report renderers include sources, UTC freshness, reported metrics, explorer links, and verification status; unknown metrics/routers remain explicit.
- Orchestration function combines discovery with per-pool on-chain verification and preserves RPC errors per candidate.

Still incomplete:
- The dedicated DEX research test workflow has passed on recent commits; confirm the latest run after report and router-verifier changes before merging.
- These RPC checks are implemented and mock-tested but have not been run against live mainnet RPC in this workflow.
- Netswap router is sourced from protocol repository and explorer constructor metadata; the router is not yet confirmed by a live RPC call in this workflow.
- Tethys factory is sourced from a historical audit report; verify live bytecode and getPair behavior before production use. Tethys router remains unknown and must not be guessed.
- Repository-wide Core CI has failed in two installer tests (`test_doctor_detects_release_tampering_and_missing_db` and `test_install_then_doctor_and_existing_install_preserves_state`) because expected installed-release migration files are missing; recheck latest Core CI and handle separately before merging.
- No token-symbol-to-contract discovery; callers must currently provide the token contract address.
- Registry is intentionally limited to canonical-bridge m.USDC and m.USDT, not all assets marketed as stablecoins on Metis.
