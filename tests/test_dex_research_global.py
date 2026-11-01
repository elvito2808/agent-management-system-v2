"""Offline tests for provider-independent global DEX research."""
from __future__ import annotations

import unittest
from decimal import Decimal

from agent_system.dex_research.global_service import research_token, render_markdown
from agent_system.dex_research.stablecoin_resolver import classify_pool


class FakeProvider:
    name = "fake-provider"

    def __init__(self, identities=None, pools=None, error=None):
        self.identities = identities or []
        self.pools = pools or []
        self.error = error

    def search(self, query, *, network_filter=None, address_filter=None):
        if self.error:
            raise RuntimeError(self.error)
        return self.identities, self.pools


def token(name, symbol, network, address, source="fixture"):
    return {"name": name, "symbol": symbol, "network": network, "asset_id": address,
            "token_type": "contract" if address else "unknown", "source": source,
            "source_url": "https://example.invalid/source"}


def pool(network="cardano", dex="ExampleSwap", address="pool-abc", liquidity="1250.5"):
    return {"network": network, "dex_name": dex, "pool_id": address,
            "token0": token("Any Token", "ANY", network, "asset1"),
            "token1": token("USD Coin", "USDC", network, "native-or-policy.asset2"),
            "liquidity_usd": Decimal(liquidity), "volume_24h_usd": None,
            "pool_url": "https://example.invalid/pool", "source": "fixture",
            "source_url": "https://example.invalid/search", "fetched_at_utc": "2026-01-01T00:00:00Z",
            "verification_status": "indexed_only"}


class GlobalResearchTests(unittest.TestCase):
    def test_arbitrary_symbol_and_non_evm_identifier_are_supported(self):
        identity = token("Any Token", "ANY", "cardano", "asset1")
        report = research_token("ANY", providers=[FakeProvider([identity], [pool()])])
        self.assertEqual(report.status, "data_found")
        self.assertEqual(report.pools[0].network, "cardano")
        self.assertEqual(report.pools[0].token0.asset_id, "asset1")
        self.assertEqual(report.pools[0].verification_status, "indexed_only")

    def test_provider_failure_does_not_hide_other_provider_results(self):
        matching_pool = pool(network="base", address="0xpool")
        matching_pool["token0"] = token("Any Token", "ANY", "base", "0xabc")
        good = FakeProvider([token("Any Token", "ANY", "base", "0xabc")], [matching_pool])
        bad = FakeProvider(error="simulated timeout")
        bad.name = "unavailable"
        report = research_token("ANY", providers=[bad, good])
        self.assertEqual(report.status, "partial_data")
        self.assertEqual(len(report.pools), 1)
        self.assertEqual(report.issues[0].provider, "unavailable")

    def test_no_result_is_not_reported_as_proof_of_no_liquidity(self):
        report = research_token("UNKNOWN", providers=[FakeProvider()])
        self.assertEqual(report.status, "insufficient_data")
        self.assertTrue(any("not proof" in note for note in report.coverage_notes))

    def test_network_filter_is_applied(self):
        identity = token("Any Token", "ANY", "ethereum", "0xabc")
        report = research_token("ANY", providers=[FakeProvider([identity], [pool(network="ethereum")])],
                                network_filter="base")
        self.assertEqual(report.pools, [])

    def test_address_filter_matches_identifiers_not_tickers(self):
        report = research_token("ANY", providers=[FakeProvider([], [pool()])], address_filter="asset1")
        self.assertEqual(len(report.pools), 1)
        report2 = research_token("ANY", providers=[FakeProvider([], [pool()])], address_filter="ANY")
        self.assertEqual(report2.pools, [])

    def test_markdown_discloses_indexed_status_and_coverage(self):
        report = research_token("ANY", providers=[FakeProvider([], [pool()])])
        markdown = render_markdown(report)
        self.assertIn("indexed_only", markdown)
        self.assertIn("Coverage and limitations", markdown)
        self.assertIn("not independently verified on-chain", markdown)

    def test_stablecoin_match_requires_network_and_exact_address(self):
        status, symbol, evidence = classify_pool(
            "ethereum",
            {"asset_id": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"},
            {"asset_id": "0xother"},
        )
        self.assertEqual(status, "matched_registry")
        self.assertEqual(symbol, "USDC")
        self.assertIn("etherscan.io", evidence)

        spoofed, _, _ = classify_pool(
            "base",
            {"asset_id": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"},
            {"asset_id": "0xother"},
        )
        self.assertEqual(spoofed, "unclassified")


    def test_duplicate_symbols_are_marked_ambiguous(self):
        identities = [
            token("Same Name", "DUP", "ethereum", "0xaaa"),
            token("Same Name", "DUP", "base", "0xbbb"),
        ]
        pools = [
            pool(network="ethereum", address="0xpool1"),
            pool(network="base", address="0xpool2"),
        ]
        pools[1]["token0"] = token("Same Name", "DUP", "base", "0xbbb")
        report = research_token("DUP", providers=[FakeProvider(identities, pools)])
        self.assertEqual(report.status, "ambiguous_identity")
        self.assertGreaterEqual(len(report.identities), 2)

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            research_token("  ", providers=[])


if __name__ == "__main__":
    unittest.main()
