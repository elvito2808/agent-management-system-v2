import unittest
from decimal import Decimal

from agent_system.dex_research.models import (
    PoolCandidate,
    StablecoinEntry,
    TokenIdentity,
    candidate_from_dexscreener,
    filter_stablecoin_pools,
    stablecoin_match,
)


CHAIN_METIS = 1088
METIS = "0xDeadDeAddeAddEAddeadDEaDDEaDDeAD0000"
USDC = "0x1111111111111111111111111111111111111111"
USDT = "0x2222222222222222222222222222222222222222"
WETH = "0x3333333333333333333333333333333333333333"


def pool(address, token_a, symbol_a, token_b, symbol_b, liquidity="1000"):
    return PoolCandidate(
        chain_id=CHAIN_METIS,
        dex_id="netswap",
        pool_address=address,
        token0=TokenIdentity(CHAIN_METIS, token_a, symbol_a),
        token1=TokenIdentity(CHAIN_METIS, token_b, symbol_b),
        liquidity_usd=Decimal(liquidity) if liquidity is not None else None,
    )


class StablecoinFilterTests(unittest.TestCase):
    def setUp(self):
        self.registry = [
            StablecoinEntry(
                chain_id=CHAIN_METIS,
                address=USDC,
                symbol="m.USDC",
                source_url="https://example.org/official-token-list",
                reviewed_at_utc="2026-11-01T00:00:00Z",
            ),
            StablecoinEntry(
                chain_id=CHAIN_METIS,
                address=USDT,
                symbol="m.USDT",
                source_url="https://example.org/official-token-list",
                reviewed_at_utc="2026-11-01T00:00:00Z",
            ),
        ]

    def test_keeps_pair_matching_stablecoin_contract(self):
        candidate = pool("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                         METIS, "METIS", USDC, "m.USDC")
        self.assertIsNotNone(stablecoin_match(candidate, self.registry))
        self.assertEqual(filter_stablecoin_pools([candidate], self.registry), [candidate])

    def test_excludes_metis_weth_even_when_liquid(self):
        candidate = pool("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                         METIS, "METIS", WETH, "WETH", "500000")
        self.assertEqual(filter_stablecoin_pools([candidate], self.registry), [])

    def test_symbol_alone_does_not_make_a_stablecoin(self):
        fake_usdc = "0x4444444444444444444444444444444444444444"
        candidate = pool("0xcccccccccccccccccccccccccccccccccccccccc",
                         METIS, "METIS", fake_usdc, "USDC")
        self.assertEqual(filter_stablecoin_pools([candidate], self.registry), [])

    def test_same_address_on_wrong_chain_does_not_match(self):
        wrong_chain_entry = StablecoinEntry(
            chain_id=1, address=USDC, symbol="USDC",
            source_url="https://example.org/official-token-list",
            reviewed_at_utc="2026-11-01T00:00:00Z",
        )
        candidate = pool("0xdddddddddddddddddddddddddddddddddddddddd",
                         METIS, "METIS", USDC, "m.USDC")
        self.assertIsNone(stablecoin_match(candidate, [wrong_chain_entry]))

    def test_missing_liquidity_stays_unknown(self):
        candidate = pool("0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                         METIS, "METIS", USDC, "m.USDC", None)
        self.assertIsNone(candidate.liquidity_usd)

    def test_parser_keeps_missing_metrics_as_none(self):
        payload = {
            "dexId": "netswap",
            "pairAddress": "0xffffffffffffffffffffffffffffffffffffffff",
            "baseToken": {"address": METIS, "symbol": "METIS"},
            "quoteToken": {"address": USDC, "symbol": "m.USDC"},
        }
        candidate = candidate_from_dexscreener(
            payload,
            chain_id=CHAIN_METIS,
            source_url="https://api.dexscreener.com/example",
            fetched_at_utc="2026-11-01T00:00:00Z",
        )
        self.assertIsNone(candidate.liquidity_usd)
        self.assertIsNone(candidate.volume_24h_usd)


if __name__ == "__main__":
    unittest.main()
