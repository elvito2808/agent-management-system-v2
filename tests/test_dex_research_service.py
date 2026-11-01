import unittest
from decimal import Decimal

from agent_system.dex_research.models import PoolCandidate, StablecoinEntry, TokenIdentity
from agent_system.dex_research.service import (
    VerifiedPoolResult,
    discover_and_verify_stablecoin_pools,
    discover_stablecoin_pools,
)
from agent_system.dex_research.verifier import OnChainPoolVerification

CHAIN = 1088
TOKEN = "0xDeadDeAddeAddEAddeadDEaDDEaDDeAD0000"
USDC = "0xEA32A96608495e54156Ae48931A7c20f0dcc1a21"
WETH = "0x420000000000000000000000000000000000000A"


def make_pool(dex, quote_address, quote_symbol, liquidity):
    return PoolCandidate(
        chain_id=CHAIN,
        dex_id=dex,
        pool_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        token0=TokenIdentity(CHAIN, TOKEN, "METIS"),
        token1=TokenIdentity(CHAIN, quote_address, quote_symbol),
        liquidity_usd=Decimal(str(liquidity)) if liquidity is not None else None,
    )


class DiscoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.registry = [
            StablecoinEntry(
                chain_id=CHAIN,
                address=USDC,
                symbol="m.USDC",
                source_url="https://www.metis.io/blog/technical-migration-guide-layerzero-v2-dvn-executor-on-metis-andromeda",
                reviewed_at_utc="2026-11-01T00:00:00Z",
            )
        ]

    def test_returns_only_supported_dex_stablecoin_pools_with_positive_liquidity(self):
        pools = [
            make_pool("netswap", USDC, "m.USDC", 5000),
            make_pool("tethys", USDC, "m.USDC", 3000),
            make_pool("unlisted-dex", USDC, "m.USDC", 9000),
            make_pool("netswap", WETH, "WETH", 100000),
            make_pool("tethys", USDC, "m.USDC", 0),
            make_pool("netswap", USDC, "m.USDC", None),
        ]
        result = discover_stablecoin_pools(
            TOKEN,
            registry=self.registry,
            fetcher=lambda address: pools,
        )
        self.assertEqual([pool.dex_id for pool in result], ["netswap", "tethys"])
        self.assertEqual([pool.liquidity_usd for pool in result], [Decimal("5000"), Decimal("3000")])

    def test_can_include_unknown_liquidity_for_diagnostics(self):
        unknown = make_pool("netswap", USDC, "m.USDC", None)
        result = discover_stablecoin_pools(
            TOKEN,
            registry=self.registry,
            require_positive_liquidity=False,
            fetcher=lambda address: [unknown],
        )
        self.assertEqual(result, [unknown])

    def test_rejects_empty_dex_allowlist(self):
        with self.assertRaises(ValueError):
            discover_stablecoin_pools(
                TOKEN, registry=self.registry, dex_ids=(),
                fetcher=lambda address: [],
            )


    def test_combines_discovery_with_onchain_verification(self):
        candidate = make_pool("netswap", USDC, "m.USDC", 5000)
        verification = OnChainPoolVerification(
            verified=True, chain_id=CHAIN, pool_has_code=True,
            token0_address=TOKEN, token1_address=USDC,
            token0_has_code=True, token1_has_code=True,
            checks=("chain_id_matches:1088", "pool_token_addresses_match_discovered_pair"),
            errors=(), rpc_url="https://rpc.example",
        )
        result = discover_and_verify_stablecoin_pools(
            TOKEN,
            registry=self.registry,
            fetcher=lambda address: [candidate],
            verifier=lambda pool, rpc_url: verification,
        )
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], VerifiedPoolResult)
        self.assertTrue(result[0].verified)

    def test_records_rpc_errors_per_pool(self):
        from agent_system.dex_research.verifier import OnChainVerificationError
        candidate = make_pool("netswap", USDC, "m.USDC", 5000)
        def broken_verifier(pool, rpc_url):
            raise OnChainVerificationError("RPC unavailable")
        result = discover_and_verify_stablecoin_pools(
            TOKEN,
            registry=self.registry,
            fetcher=lambda address: [candidate],
            verifier=broken_verifier,
        )
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].verified)
        self.assertEqual(result[0].error, "RPC unavailable")


if __name__ == "__main__":
    unittest.main()
