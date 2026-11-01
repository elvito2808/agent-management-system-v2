# Global Multi-Chain DEX Token Research Agent

## Product goal

Build a provider-driven research agent that accepts **any user-supplied token name or symbol**, not a fixed list of examples. Examples such as `X`, `Y`, `ADA`, `TRX`, or `LINK` illustrate the input format only and must not become an allowlist.

The agent must discover where the requested asset identity has liquidity across networks and DEXs, then produce sourced reports of relevant pools. Metis Andromeda, Netswap, and Tethys are only an existing prototype and must not define the global product boundary.

The ordinary input is a name or symbol. Users should not need to provide a chain, DEX, contract address, or stablecoin list. Optional address/network filters can be accepted to disambiguate results.

## Required user journey and research order

### 1. Resolve the requested name or symbol

- Search trusted token metadata and market-data sources for the requested string.
- Return plausible identities with name, symbol, network, token type (native asset or contract token), address/asset identifier, and source.
- A symbol is not a globally unique identifier. Never silently choose between different assets with the same symbol.
- If ambiguity cannot be resolved safely, show the candidates and mark the result as ambiguous rather than fabricating a single identity.
- Support native assets and non-EVM identifiers. For example, native ADA on Cardano and native TRX on Tron must not be treated as ordinary EVM contract tokens.
- Distinguish native assets, wrapped assets, and bridged representations. The same ticker on multiple chains does not by itself prove the assets are identical.

### 2. Discover every source-supported network and DEX with liquidity

- For each resolved token identity, query global market-data/indexer sources and discover candidate pools across **all networks returned by those sources**, not just the token's origin/issuance network.
- A token issued on one network may also have wrapped, bridged, or otherwise represented versions on other networks. Search these other networks too, while labelling the precise identity found on each network.
- Example output rows could include `Pair X/USDT on BSC`, `Pair X/USDT on Ethereum`, `Pair X/USDT on Polygon`, and `Pair X/USDT on Solana` if supported sources actually return those pools. These are illustrative examples, not claims that such pools exist for every token.
- For every discovered network, list the DEX name, pair/pool, both assets, liquidity, volume, and source. Do not restrict the DEX list to a hardcoded allowlist.
- Use pluggable provider adapters so data sources can be added or replaced without rewriting the core orchestrator.
- Maintain sourced, updateable chain/DEX metadata for protocol details and verification, but do not require manual registration of every DEX before the discovery layer can find it.
- Disclose the providers and networks searched and any known coverage gaps. Do not claim absolute exhaustive global coverage unless the available sources genuinely establish it.

### 3. Identify stablecoin pairs by real asset identity

- Identify stablecoins by chain-specific contract address or native-asset identifier and reliable metadata, not by ticker text alone.
- Support chain-specific variants such as canonical, bridged, and wrapped stablecoins; keep variants separate when their identities differ.
- Discover pools for each resolved token identity and keep pairs that match recognized stablecoins.
- Combine provider metadata with sourced chain-specific registries. Do not require every chain's registry to be manually populated before searches can run.
- If a quote asset cannot be classified confidently, mark it as unknown/unclassified instead of guessing it is a stablecoin.

### 4. Collect pool details and perform network-appropriate verification

For every discovered pool, collect as available:
- network name and chain/network identifier;
- token names, symbols, and contract or native-asset identifiers for both sides;
- stablecoin identity and evidence for its classification;
- DEX name and pool/pair identifier or contract address;
- reported USD liquidity and 24-hour volume;
- pool page and block-explorer URL;
- factory/router addresses and source links when applicable;
- source URLs, UTC retrieval time, and freshness indicators.

Use read-only verification adapters appropriate to the chain and pool type:
- EVM: JSON-RPC and applicable contract/factory/token/reserve checks;
- Cardano: Cardano-compatible asset and pool data interfaces;
- Tron: Tron-compatible APIs/RPC;
- other chains: appropriate adapters added incrementally.

Do not apply EVM address or JSON-RPC assumptions to non-EVM networks. Clearly distinguish third-party indexed liquidity/volume from facts verified on-chain; verifying a pool address does not by itself verify an indexer's USD liquidity or 24-hour volume.

Never invent token, pool, factory, router, or asset identifiers. Unknown values remain unknown.

### 5. Preserve partial results when a source fails

- A timeout, unavailable RPC, DEX, provider, unsupported pool type, or missing metric must not abort the whole token report.
- Record the affected identity, network, DEX or pool, missing field, source, and error where useful.
- Use explicit statuses such as `data_found`, `partial_data`, `insufficient_data`, `unsupported_verification`, and `ambiguous_identity`.
- Continue with all other discovered identities, networks, DEXs, and providers.
- Do not interpret an API failure or absence from one indexer as proof that no pool exists.

## Report output

Generate Markdown and JSON reports with:
- requested query and report timestamp;
- candidate token identities and ambiguity notes;
- a coverage summary listing providers, networks, and DEXs actually searched;
- stablecoin pools grouped by network and DEX;
- each pair's two assets, pool address/identifier, reported liquidity, 24-hour volume, source, and timestamp;
- factory/router details and explorer links when known;
- verification state and explicit limitations for every incomplete section;
- a clear distinction between “no matching pool found in the sources searched” and “could not determine because data was unavailable.”

## Architecture requirements

Keep the system modular and network-agnostic:
- `token_resolver`: name/symbol to candidate token identities;
- `provider_adapters`: global market-data, token metadata, pool discovery, and DEX metadata providers;
- `chain_registry`: chain identifiers, explorers, capabilities, and native-asset identifiers;
- `dex_registry`: sourced DEX deployments and pool/factory/router capabilities per chain;
- `stablecoin_resolver`: chain-specific stablecoin identities and evidence;
- `chain_adapters`: optional chain-specific read-only verification;
- `research_orchestrator`: fans out across token identities, networks, DEXs, and providers while isolating errors;
- `report`: shared JSON/Markdown output independent of a single network.

The current Metis implementation should become one adapter within this architecture, not the global orchestrator.

## Implementation plan

### Phase A — Generic identity resolution and global pool discovery
1. Define shared models for token identity, network, DEX, pool, source provenance, and per-source errors without assuming all chains use integer EVM chain IDs or 20-byte addresses.
2. Implement token name/symbol resolution with multiple candidates and ambiguity handling.
3. Implement a global pool-discovery provider adapter that can return pairs across networks and DEXs; add a second independent provider where feasible.
4. Make the workflow accept any free-form token name/symbol, with optional network/address filters.
5. Test duplicate symbols, native assets, wrapped/bridged assets, unknown network identifiers, provider failures, and partial reports offline.

### Phase B — Multi-network stablecoin classification and DEX metadata
1. Add stablecoin classification using chain-specific identifiers and evidence.
2. Discover pools across every network/DEX returned by configured providers rather than a fixed DEX list.
3. Add provenance, coverage reporting, and deduplication across providers.

### Phase C — Chain-specific verification
1. Add verification adapters incrementally by network and pool type.
2. Support EVM networks first where practical, then non-EVM networks such as Cardano and Tron through appropriate data interfaces.
3. State which checks are supported per chain and pool type.

### Phase D — Reliability and operations
1. Add scheduled metadata refreshes and provider-health/coverage reporting.
2. Test that any one provider/network failure leaves the rest of the report available.
3. Publish JSON and Markdown report artifacts from the workflow.

## Acceptance criteria

- Any user-supplied name or symbol can be searched; examples in this document are not an allowlist.
- The user can enter a symbol alone and the agent resolves plausible identities before searching.
- Results include source-supported pools across networks other than the asset's original network, including wrapped/bridged representations when discovered and labelled accurately.
- For each network, results list DEX names and relevant stablecoin pairs with liquidity data when available.
- The workflow is not restricted to Metis, Netswap, or Tethys.
- Stablecoin matching uses chain-specific asset identities and evidence, not ticker-only matching.
- EVM and non-EVM assets are represented and verified using suitable chain-specific methods.
- Provider and RPC errors are isolated and reported; other research continues.
- Sources and coverage gaps are disclosed; the agent never claims unproven global completeness.
- Unknown addresses, metrics, routers, and verification results are never fabricated.
- Indexed market metrics are distinguished from independently verified on-chain facts.
- The system is read-only and never requests private keys or submits transactions.

## Current status

The existing implementation is a Metis-specific prototype. The new branch `feature/global-multichain-dex-research` is the development branch for this global scope. The implementation work must start with Phase A—generic identity resolution and global pool discovery—before the project can claim multi-chain support.
