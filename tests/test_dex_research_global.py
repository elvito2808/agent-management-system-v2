"""Offline tests for provider-independent global DEX research."""
from __future__ import annotations

import unittest
from decimal import Decimal

from agent_system.dex_research.global_service import research_token, render_markdown
from agent_system.dex_research.stablecoin_resolver import classify_pool
from agent_system.dex_research.stellar_expert_provider import StellarExpertProvider


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


class StellarExpertProviderTests(unittest.TestCase):
    def test_stellar_native_xlm_pool_and_stellar_usdc_identity_are_normalized(self):
        payload = {
            "_links": {"self": {"href": "/explorer/public/liquidity-pool?limit=2"}},
            "_embedded": {"records": [{
                "id": "pool-fixture-1",
                "assets": ["XLM", "USDC-GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN-1"],
                "total_value_locked_usd": "12345.67",
                "volume_24h_usd": "456.78",
                "paging_token": 1
            }]}
        }
        provider = StellarExpertProvider(fetch_json=lambda _url: payload, max_pages=1, page_size=2)
        report = research_token("XLM", providers=[provider])
        self.assertEqual(report.status, "data_found")
        self.assertEqual(len(report.pools), 1)
        pool_result = report.pools[0]
        self.assertEqual(pool_result.network, "stellar")
        self.assertEqual(pool_result.token0.symbol, "XLM")
        self.assertEqual(pool_result.token0.asset_id, "XLM")
        self.assertEqual(pool_result.liquidity_usd, Decimal("12345.67"))
        self.assertEqual(pool_result.volume_24h_usd, Decimal("456.78"))
        self.assertEqual(pool_result.stablecoin_status, "matched_registry")
        self.assertEqual(pool_result.stablecoin_symbol, "USDC")
        self.assertEqual(pool_result.verification_status, "indexed_only")

    def test_stellar_network_filter_does_not_leak_into_other_networks(self):
        provider = StellarExpertProvider(fetch_json=lambda _url: self.fail("must not call provider"))
        identities, pools = provider.search("XLM", network_filter="ethereum")
        self.assertEqual(identities, [])
        self.assertEqual(pools, [])

    def test_stellar_page_cursor_is_bounded_and_progresses(self):
        calls = []
        def fake_fetch(url):
            calls.append(url)
            if len(calls) == 1:
                return {"_links": {"next": {"href": "next"}},
                        "_embedded": {"records": [{"id": "not-match", "assets": ["AAA-GAAA", "BBB-GBBB"], "paging_token": 100}]}}
            return {"_embedded": {"records": [{"id": "match", "assets": ["XLM", "AAA-GAAA"], "paging_token": 200}]}}
        provider = StellarExpertProvider(fetch_json=fake_fetch, max_pages=2, page_size=1)
        identities, pools = provider.search("XLM")
        self.assertEqual(len(calls), 2)
        self.assertIn("cursor=100", calls[1])
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0]["pool_id"], "match")




    def test_stellar_expert_fixed_point_tvl_and_volume_are_converted(self):
        payload = {
            "_embedded": {"records": [{
                "id": "pool-fixed-point",
                "assets": [
                    {"asset": "XLM", "name": "XLM"},
                    {"asset": "USDC-GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN-1",
                     "code": "USDC", "name": "USD Coin"}
                ],
                "total_value_locked": 12345678900,
                "volume_value": {"1d": 45678900},
                "paging_token": 10
            }]}
        }
        provider = StellarExpertProvider(fetch_json=lambda _url: payload, max_pages=1, page_size=200)
        _, pools = provider.search("XLM")
        self.assertEqual(len(pools), 1)
        self.assertEqual(pools[0]["liquidity_usd"], Decimal("1234.56789"))
        self.assertEqual(pools[0]["volume_24h_usd"], Decimal("4.56789"))


    def test_exact_address_filter_disambiguates_duplicate_symbol_identities(self):
        identities = [
            token("Native Stellar Lumens", "XLM", "stellar", "XLM"),
            token("Issued XLM-like asset", "XLM", "stellar", "XLM-GISSUER-1"),
        ]
        report = research_token("XLM", providers=[FakeProvider(identities, [])],
                                network_filter="stellar", address_filter="XLM")
        self.assertEqual(len(report.identities), 1)
        self.assertEqual(report.identities[0].asset_id, "XLM")
        self.assertEqual(report.status, "insufficient_data")

if __name__ == "__main__":
    unittest.main()
