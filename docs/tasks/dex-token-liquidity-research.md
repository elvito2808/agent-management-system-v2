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
