import json
import tempfile
import unittest
from pathlib import Path

from agent_system.dex_research.dex_registry import load_dex_registry


class DexRegistryTests(unittest.TestCase):
    def test_loads_netswap_and_tethys_and_keeps_unknown_tethys_router_null(self):
        entries = load_dex_registry()
        by_id = {entry.dex_id: entry for entry in entries}
        self.assertEqual(set(by_id), {"netswap", "tethys"})
        self.assertIsNotNone(by_id["netswap"].router_address)
        self.assertIsNone(by_id["tethys"].router_address)
        self.assertTrue(by_id["tethys"].factory_source_url.endswith(".pdf"))

    def test_rejects_unknown_router_with_fabricated_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps({
                "chain_id": 1088,
                "dexes": [{
                    "dex_id": "example", "name": "Example",
                    "factory_address": "0x1111111111111111111111111111111111111111",
                    "factory_source_url": "https://example.org/factory",
                    "explorer_factory_url": "https://example.org/explorer",
                    "router_address": None,
                    "router_source_url": "https://example.org/router",
                    "explorer_router_url": None,
                    "confidence": "test"
                }]
            }), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dex_registry(path)


if __name__ == "__main__":
    unittest.main()
