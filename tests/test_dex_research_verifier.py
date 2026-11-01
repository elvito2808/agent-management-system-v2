import json
import unittest
from decimal import Decimal

from agent_system.dex_research.models import PoolCandidate, TokenIdentity
from agent_system.dex_research.verifier import (
    OnChainVerificationError,
    verify_v2_pool_onchain,
)

CHAIN = 1088
POOL = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN_A = "0xDeadDeAddeAddEAddeadDEaDDEaDDeAD0000"
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
    return "0x" + ("0" * 24) + address[2:].lower().rjust(40, "0")


def pool():
    return PoolCandidate(
        chain_id=CHAIN,
        dex_id="netswap",
        pool_address=POOL,
        token0=TokenIdentity(CHAIN, TOKEN_A, "METIS"),
        token1=TokenIdentity(CHAIN, TOKEN_B, "m.USDC"),
        liquidity_usd=Decimal("1000"),
    )


class PoolVerificationTests(unittest.TestCase):
    def opener_for(self, results):
        sequence = iter(results)

        def opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(body["jsonrpc"], "2.0")
            return FakeResponse(next(sequence))

        return opener

    def test_verifies_chain_code_and_pair_token_addresses(self):
        results = [
            "0x440",       # chain ID 1088
            "0x6000",      # pool bytecode
            abi_address(TOKEN_A),
            abi_address(TOKEN_B),
            "0x6000",      # token0 bytecode
            "0x6000",      # token1 bytecode
        ]
        result = verify_v2_pool_onchain(pool(), opener=self.opener_for(results))
        self.assertTrue(result.verified)
        self.assertEqual(result.chain_id, CHAIN)
        self.assertTrue(result.pool_has_code)
        self.assertIn("pool_token_addresses_match_discovered_pair", result.checks)

    def test_rejects_wrong_chain_before_querying_pool(self):
        result = verify_v2_pool_onchain(pool(), opener=self.opener_for(["0x1"]))
        self.assertFalse(result.verified)
        self.assertIn("chain_id_mismatch:rpc=1,expected=1088,pool=1088", result.errors)

    def test_marks_mismatched_pair_tokens_unverified(self):
        other = "0x1111111111111111111111111111111111111111"
        results = [
            "0x440", "0x6000", abi_address(TOKEN_A), abi_address(other),
            "0x6000", "0x6000",
        ]
        result = verify_v2_pool_onchain(pool(), opener=self.opener_for(results))
        self.assertFalse(result.verified)
        self.assertIn("pool_token_addresses_do_not_match_discovered_pair", result.errors)

    def test_rejects_rpc_error(self):
        def opener(request, timeout):
            return FakeResponse(error={"code": -32000, "message": "offline"})
        with self.assertRaises(OnChainVerificationError):
            verify_v2_pool_onchain(pool(), opener=opener)

    def test_requires_https_rpc(self):
        with self.assertRaises(ValueError):
            verify_v2_pool_onchain(pool(), rpc_url="http://localhost:8545")


if __name__ == "__main__":
    unittest.main()
