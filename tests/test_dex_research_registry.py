import json
import tempfile
import unittest
from pathlib import Path

from agent_system.dex_research.registry import load_stablecoin_registry


class StablecoinRegistryTests(unittest.TestCase):
    def test_loads_repository_metis_registry(self):
        entries = load_stablecoin_registry()
        self.assertEqual([entry.symbol for entry in entries], ["m.USDC", "m.USDT"])
        self.assertTrue(all(entry.chain_id == 1088 for entry in entries))
        self.assertTrue(all(entry.source_url.startswith("https://") for entry in entries))

    def test_rejects_registry_without_chain_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps({"tokens": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_stablecoin_registry(path)

    def test_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_stablecoin_registry(path)


if __name__ == "__main__":
    unittest.main()
