# Global Multi-Chain DEX Token Research Agent

## Product goal

The agent must accept a token name or symbol (for example `ADA`, `TRX`, `LINK`, or a full token name) and autonomously discover the relevant networks, token identities, active DEXs, and stablecoin-paired pools. Metis Andromeda, Netswap, and Tethys are only one supported example, not the product boundary.

The user should not need to supply a chain, DEX, stablecoin list, or contract address for ordinary symbol/name searches. A contract address and optional chain may be accepted as disambiguating inputs.

## Required end-to-end flow

1. **Resolve token identity**
   - Search trusted token metadata and market-data sources by name/symbol.
   - Return all plausible matches with chain, token type (native asset or contract token), contract/asset identifier, and source.
   - Never treat a ticker as globally unique.
   - If a name/symbol has multiple plausible matches and there is no safe way to identify the intended asset, report the ambiguity clearly; do not silently choose one.
   - Handle non-EVM identifiers and native assets. ADA on Cardano and TRX on Tron are not equivalent to ordinary EVM contract-address inputs. Wrapped or bridged versions on other chains must be represented as separate identities and labelled accordingly.

2. **Discover networks and DEXs**
   - Search global market-data/indexer sources for candidate pools and chain deployments.
   - Use provider adapters so additional data sources can be added without rewriting the report logic.
   - Maintain a sourced, updateable chain/DEX registry as a fallback and for protocol-specific metadata. The registry must not be a hardcoded allowlist that limits the agent to one chain.
   - Include all discovered networks and DEXs supported by reliable sources; disclose provider coverage limitations rather than implying exhaustive global coverage when sources are incomplete.

3. **Discover stablecoin pairs**
   - Identify stablecoins by chain-specific asset/contract identifiers, not ticker text alone.
   - Support network-specific stablecoin representations and distinguish canonical, bridged, and wrapped variants when reliable metadata is available.
   - Discover candidate pools for each resolved token identity, then retain pools paired with recognized stablecoins.
   - Do not require every chain's stablecoin registry to be manually populated before a search can run. Use provider metadata and sourced registries together, and mark unclassified assets as unknown rather than guessing that they are stablecoins.

4. **Collect pool and DEX details**
   For each pool, collect when available:
   - network name and chain ID / network identifier;
   - token name, symbol, and native-asset identifier or contract address for both sides;
   - stablecoin identity and why it was classified as a stablecoin;
   - DEX and pool/pair identifier or contract address;
   - reported USD liquidity and 24-hour volume;
   - pool URL and block explorer URL;
   - factory/router addresses and source links when applicable;
   - provider/source URLs, UTC fetch time, and data freshness.

5. **Verify without overstating certainty**
   - Use chain-specific read-only verification adapters where supported: EVM JSON-RPC, Cardano-compatible data sources, Tron-compatible APIs/RPC, and future adapters as needed.
   - Verify pool identity, token identities, factory relationships, and bytecode/reserves only when the chain and pool type support those checks.
   - Clearly separate third-party indexed metrics from on-chain verification. A successful pool-address check does not independently prove an indexer's USD liquidity or 24-hour volume is correct.
   - Never invent token, pool, factory, or router addresses. Unknown values remain unknown.
   - Do not require every verification to succeed before producing the report.

6. **Partial results are first-class**
   - A timeout, unavailable RPC, unavailable DEX, unsupported pool type, missing metric, or provider error must not abort the entire token report.
   - Record the affected token identity, network, DEX or pool and the missing data, with a status such as `data_found`, `partial_data`, `insufficient_data`, `unsupported_verification`, or `ambiguous_identity`.
   - Continue with other discovered networks and DEXs.
   - Do not interpret an API failure or lack of indexed results as proof that no pool exists.

## Report output

Generate Markdown and JSON reports with:
- the requested name/symbol and report timestamp;
- token identity matches and any ambiguity;
- a coverage summary of data providers, networks, and DEXs checked;
- discovered stablecoin pools grouped by network and DEX;
- liquidity and volume values with source and timestamp;
- contract/pool/factory/router details and explorer links where known;
- verification status and exact limitations for every incomplete section;
- explicit distinction between “no matching pool found in searched sources” and “could not determine because data was unavailable.”

## Architecture requirements

Keep the system modular:
- `token_resolver`: name/symbol to candidate token identities;
- `provider_adapters`: market-data, token metadata, pool discovery, and DEX metadata sources;
- `chain_registry`: chain identifiers, explorers, RPC/data capabilities, and native-asset identifiers;
- `dex_registry`: sourced DEX deployments and pool/factory/router capabilities per chain;
- `stablecoin_resolver`: chain-specific stablecoin identities and evidence;
- `chain_adapters`: optional chain-specific read-only verification;
- `research_orchestrator`: fans out across identities, chains, and DEXs while isolating per-source failures;
- `report`: common JSON/Markdown output independent of any single network.

The current Metis implementation should be refactored into one chain/DEX adapter rather than treated as the global orchestrator.

## Implementation plan

### Phase A — Global discovery and token resolution
- Define common schemas for token identities, chain identifiers, DEXs, pools, provider provenance, and per-source errors.
- Implement symbol/name resolution and expose ambiguous matches.
- Implement at least one global pool-discovery provider adapter and a second independent source where feasible.
- Make the workflow accept a token name/symbol, with optional chain/address filters.
- Add offline tests for duplicate symbols, native assets, bridged/wrapped identities, provider failures, and partial reports.

### Phase B — Multi-chain stablecoin and DEX discovery
- Add chain-specific stablecoin classification and sourced metadata.
- Discover pools across every network returned by the configured providers, not only a fixed list of DEX IDs.
- Add coverage reporting and safeguards against duplicate pools from multiple providers.

### Phase C — Chain-specific verification
- Add independent verification adapters incrementally by chain and pool type.
- Start with EVM networks, then add non-EVM networks such as Cardano and Tron using suitable data interfaces.
- Keep verification capability explicit per chain/pool type; do not apply EVM address/RPC assumptions to non-EVM chains.

### Phase D — Operational hardening
- Add scheduled registry refreshes and provider health/coverage reporting.
- Test partial failure paths and ensure any single network/provider failure leaves the rest of the report available.
- Publish JSON and Markdown workflow artifacts.

## Acceptance criteria

- A user can submit only `ADA` or `TRX` and receive a report that resolves candidate identities and searches all networks/DEXs discoverable through configured sources.
- The workflow is not restricted to Metis, Netswap, or Tethys.
- Token identity is chain-aware and does not rely on symbol matching alone.
- Pools are filtered by chain-specific stablecoin identity, not merely by symbol.
- Provider and RPC errors are isolated; the report contains useful partial results and says exactly what could not be completed.
- No unsupported claim of exhaustive global coverage is made: sources and coverage gaps are disclosed.
- Unknown addresses, metrics, routers, and verification results are never fabricated.
- Reports distinguish indexed market metrics from independently verified on-chain facts.
- The workflow is read-only and never requests private keys or submits transactions.

## Current status

The existing implementation is a Metis-specific prototype. Its Metis/Netswap/Tethys configuration and workflow do not yet satisfy the global multi-chain requirements above. The next implementation work must establish token resolution and provider-driven multi-chain discovery before describing the project as globally capable.
