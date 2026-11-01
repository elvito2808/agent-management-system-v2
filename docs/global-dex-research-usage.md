# Global DEX research prototype: run and interpret

The first global research implementation is available on
`feature/global-multichain-dex-research`. It is read-only and accepts arbitrary
token names/symbols rather than a hardcoded token allowlist.

## Run locally

Python 3.12 is the repository baseline.

```bash
python -m pip install -c requirements.lock.txt -e .
python scripts/global_dex_research.py LINK
python scripts/global_dex_research.py LINK --format json --output reports/link.json
python scripts/global_dex_research.py USDC --network ethereum
python scripts/global_dex_research.py 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48 --address 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48 --format json
python -m unittest discover -s tests -p "test_dex_research*.py" -v
```

The token argument is passed directly to provider search endpoints. Optional
`--network` and `--address` filters narrow the results. Network names/slugs are
provider-specific.

## Providers and report fields

- **DEX Screener** global pair search.
- **GeckoTerminal** global pool search.
- Name/symbol/address candidates, network, DEX, pool link, reported USD liquidity,
  24-hour volume, retrieval timestamp, provider provenance and source errors.
- Markdown is the default; `--format json` emits a machine-readable report.
- Provider failures are isolated. The report status and error section distinguish
  partial/incomplete data from a successful search with rows.

## Stablecoin classification

The seed registry at
`src/agent_system/dex_research/data/stablecoins.global.json` matches both a
network alias and the exact token contract address. The initial list covers
selected USDC/USDT/DAI deployments on Ethereum, Base, Polygon, Arbitrum,
Optimism and BNB Smart Chain. It is intentionally not presented as exhaustive.
A matching entry includes a source URL. Ticker similarity alone never qualifies
a token as a stablecoin. Unknown assets remain `unclassified`.

Add registry entries only after checking the exact asset identifier and source;
keep bridged/canonical versions separate. The current resolver is EVM-focused
because the initial registry contains EVM addresses. Native and non-EVM asset
identifiers are supported by the shared models and provider adapters, but need
their own sourced registry entries for stablecoin classification.

## Important limitations

- Provider search endpoints are capped/indexer-dependent. Results do not prove
  that every network, DEX or pool worldwide has been discovered.
- The current implementation does **not** independently verify pools or reserves
  on-chain. `indexed_only` means precisely that; liquidity and volume are provider
  metrics, not chain-verified facts.
- Wrapped/bridged representations are surfaced only when providers return them;
  the implementation does not yet prove bridge provenance between two assets.
- GeckoTerminal's token metadata may be missing from a search response. Missing
  identifiers are kept unknown instead of fabricated.
- No API keys, private keys or transaction signing are required.

This is the first testable global-discovery milestone, not a claim that every
planned non-EVM verifier, exhaustive stablecoin registry, or scheduled refresh
has already been implemented.
