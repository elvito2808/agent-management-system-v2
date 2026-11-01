import json
import unittest
from decimal import Decimal

from agent_system.dex_research.dex_registry import DexDeployment
from agent_system.dex_research.models import PoolCandidate, TokenIdentity
from agent_system.dex_research.report import render_json_report, render_markdown_report
from agent_system.dex_research.service import VerifiedPoolResult


class ReportTests(unittest.TestCase):
    def setUp(self):
        pool = PoolCandidate(
            chain_id=1088, dex_id="tethys",
            pool_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            token0=TokenIdentity(1088, "0x1111111111111111111111111111111111111111", "TOKEN"),
            token1=TokenIdentity(1088, "0x2222222222222222222222222222222222222222", "m.USDC"),
            liquidity_usd=Decimal("1234.50"), volume_24h_usd=None,
            source_url="https://dexscreener.com/metis/example",
            fetched_at_utc="2026-11-01T00:00:00Z",
        )
        self.result = VerifiedPoolResult(pool=pool, verification=None, error="RPC unavailable")
        self.deployments = [DexDeployment(
            chain_id=1088, dex_id="tethys", name="Tethys",
            factory_address="0x3333333333333333333333333333333333333333",
            factory_source_url="https://example.org/audit.pdf",
            router_address=None, router_source_url=None,
            explorer_factory_url="https://example.org/factory",
            explorer_router_url=None, confidence="router unknown",
        )]

    def test_json_keeps_unknown_values_and_router_status_explicit(self):
        report = json.loads(render_json_report([self.result], self.deployments,
                                                generated_at_utc="2026-11-01T01:00:00Z"))
        item = report["results"][0]
        self.assertIsNone(item["volume_24h_usd_reported"])
        self.assertIsNone(item["router_address"])
        self.assertEqual(item["router_status"], "unknown")
        self.assertFalse(item["pool_onchain_verified"])
        self.assertEqual(item["verification_error"], "RPC unavailable")

    def test_markdown_marks_unknown_metrics_and_router(self):
        report = render_markdown_report([self.result], self.deployments)
        self.assertIn("| unknown | unknown | not verified | unknown |", report)
        self.assertIn("Missing metrics are shown as unknown, not zero.", report)


if __name__ == "__main__":
    unittest.main()
