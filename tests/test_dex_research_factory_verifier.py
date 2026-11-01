import json
import unittest
from decimal import Decimal

from agent_system.dex_research.models import PoolCandidate, TokenIdentity
from agent_system.dex_research.verifier import (
    OnChainVerificationError,
    verify_factory_pair,
)

CHAIN = 1088
POOL = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
FACTORY = "0x70f51d68D16e8f9e418441280342BD43AC9Dff9f"
TOKEN_A = "0xDeadDeAddeAddEAddeadDEaDDeAD0000"
TOKEN_B = "0xEA32A96608495e54156Ae48931A7c20f0dcc1a21"


class FakeResponse:
    def __init__(self, result=None, error=None):
        self.payload = {"jsonrpc": "2.0", "id": 1}
        if error is not None:
            self.payload["error"] = error
        else:
            self.payload["result"] = result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def abi_address(address):
    return "0x" + address[2:].lower().rjust(64, "0")


def candidate():
    return PoolCandidate(
        chain_id=CHAIN, dex_id="netswap", pool_address=POOL,
        token0=TokenIdentity(CHAIN, TOKEN_A, "METIS"),
        token1=TokenIdentity(CHAIN, TOKEN_B, "m.USDC"),
        liquidity_usd=Decimal("1000"),
    )


class FactoryVerificationTests(unittest.TestCase):
    def opener_for(self, results):
        sequence = iter(results)
        def opener(request, timeout):
            return FakeResponse(next(sequence))
        return opener

    def test_factory_getpair_matches_discovered_pool(self):
        result = verify_factory_pair(
            candidate(), FACTORY,
            opener=self.opener_for(["0x440", "0x6000", abi_address(POOL)]),
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.reported_pair_address.lower(), POOL.lower())
        self.assertIn("factory_getPair_matches_discovered_pool", result.checks)

    def test_factory_getpair_mismatch_is_not_verified(self):
        other = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        result = verify_factory_pair(
            candidate(), FACTORY,
            opener=self.opener_for(["0x440", "0x6000", abi_address(other)]),
        )
        self.assertFalse(result.verified)
        self.assertIn("factory_getPair_does_not_match_discovered_pool", result.errors)

    def test_wrong_chain_stops_before_factory_query(self):
        result = verify_factory_pair(candidate(), FACTORY, opener=self.opener_for(["0x1"]))
        self.assertFalse(result.verified)
        self.assertIn("chain_id_mismatch:rpc=1,expected=1088,pool=1088", result.errors)

    def test_rpc_error_is_explicit(self):
        def opener(request, timeout):
            return FakeResponse(error={"code": -32000, "message": "offline"})
        with self.assertRaises(OnChainVerificationError):
            verify_factory_pair(candidate(), FACTORY, opener=opener)


if __name__ == "__main__":
    unittest.main()
