import json
import unittest
from unittest.mock import patch

from agent_system.dex_research.client import (
    DexScreenerError,
    fetch_token_pairs,
)
from agent_system.dex_research.models import StablecoinEntry, filter_stablecoin_pools

METIS = "0xDeadDeAddeAddEAddeadDEaDDEaDDeAD0000"
USDC = "0xEA32A96608495e54156Ae48931A7c20f0dcc1a21"
POOL = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def pair_row(**overrides):
    row = {
        "chainId": "metis",
        "dexId": "netswap",
        "url": "https://dexscreener.com/metis/netswap/example",
        "pairAddress": POOL,
        "baseToken": {"address": METIS, "symbol": "METIS"},
        "quoteToken": {"address": USDC, "symbol": "m.USDC"},
        "liquidity": {"usd": 1234.5},
        "volume": {"h24": 987.6},
    }
    row.update(overrides)
    return row


class DexScreenerClientTests(unittest.TestCase):
    def test_builds_candidate_and_keeps_source_metrics(self):
        def opener(request, timeout):
            self.assertIn("/token-pairs/v1/metis/", request.full_url)
            self.assertEqual(timeout, 5)
            return FakeResponse([pair_row()])

        result = fetch_token_pairs(METIS, timeout_seconds=5, opener=opener)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].pool_address, POOL)
        self.assertEqual(str(result[0].liquidity_usd), "1234.5")
        self.assertEqual(str(result[0].volume_24h_usd), "987.6")
        self.assertEqual(result[0].source_url, "https://dexscreener.com/metis/netswap/example")
        self.assertTrue(result[0].fetched_at_utc.endswith("Z"))

    def test_skips_wrong_chain_and_malformed_rows(self):
        rows = [
            pair_row(chainId="ethereum"),
            {"chainId": "metis", "dexId": "netswap"},
            pair_row(),
        ]
        result = fetch_token_pairs(METIS, opener=lambda request, timeout: FakeResponse(rows))
        self.assertEqual(len(result), 1)

    def test_invalid_json_raises_clear_error(self):
        class InvalidResponse(FakeResponse):
            def read(self):
                return b"not-json"

        with self.assertRaises(DexScreenerError):
            fetch_token_pairs(METIS, opener=lambda request, timeout: InvalidResponse([]))

    def test_empty_address_rejected_before_network_call(self):
        with self.assertRaises(ValueError):
            fetch_token_pairs("  ", opener=lambda *args, **kwargs: self.fail("network must not be called"))

    def test_registry_addresses_match_by_contract_not_symbol(self):
        stablecoins = [
            StablecoinEntry(
                chain_id=1088,
                address=USDC,
                symbol="m.USDC",
                source_url="https://www.metis.io/blog/technical-migration-guide-layerzero-v2-dvn-executor-on-metis-andromeda",
                reviewed_at_utc="2026-11-01T00:00:00Z",
            )
        ]
        pools = fetch_token_pairs(METIS, opener=lambda request, timeout: FakeResponse([pair_row()]))
        self.assertEqual(filter_stablecoin_pools(pools, stablecoins), pools)
        fake_symbol = pair_row(quoteToken={"address": "0x4444444444444444444444444444444444444444", "symbol": "m.USDC"})
        fake_pools = fetch_token_pairs(METIS, opener=lambda request, timeout: FakeResponse([fake_symbol]))
        self.assertEqual(filter_stablecoin_pools(fake_pools, stablecoins), [])


if __name__ == "__main__":
    unittest.main()
