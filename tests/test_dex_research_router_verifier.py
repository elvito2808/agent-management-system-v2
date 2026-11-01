import json
import unittest

from agent_system.dex_research.verifier import (
    verify_router_factory_onchain,
)

ROUTER = "0x1E876cCe41B7b844FDe09E38Fa1cf00f213bFf56"
FACTORY = "0x70f51d68D16e8f9e418441280342BD43AC9Dff9f"
OTHER_FACTORY = "0x1111111111111111111111111111111111111111"


class FakeResponse:
    def __init__(self, result):
        self.payload = {"jsonrpc": "2.0", "id": 1, "result": result}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def abi_address(address):
    return "0x" + address[2:].lower().rjust(64, "0")


class RouterFactoryVerificationTests(unittest.TestCase):
    def opener_for(self, results):
        sequence = iter(results)
        def opener(request, timeout):
            return FakeResponse(next(sequence))
        return opener

    def test_router_factory_matches_registry(self):
        result = verify_router_factory_onchain(
            ROUTER, FACTORY,
            opener=self.opener_for(["0x440", "0x6000", abi_address(FACTORY)]),
        )
        self.assertTrue(result.verified)
        self.assertIn("router_factory_matches_registry", result.checks)

    def test_router_factory_mismatch_is_not_verified(self):
        result = verify_router_factory_onchain(
            ROUTER, FACTORY,
            opener=self.opener_for(["0x440", "0x6000", abi_address(OTHER_FACTORY)]),
        )
        self.assertFalse(result.verified)
        self.assertIn("router_factory_does_not_match_registry", result.errors)

    def test_wrong_chain_stops_before_router_query(self):
        result = verify_router_factory_onchain(
            ROUTER, FACTORY, opener=self.opener_for(["0x1"])
        )
        self.assertFalse(result.verified)
        self.assertIn("chain_id_mismatch:rpc=1,expected=1088", result.errors)


if __name__ == "__main__":
    unittest.main()
