"""Tests for BrandRegistry — JSON-backed brand registry (CRUD).

Seam under test: the public interface of BrandRegistry, exercised through a
tempfile JSON file (same pattern as test_team_filtering.py). No internals.

Issue: #136 — BrandRegistry + Brand entity
ADR: docs/adr/0005-brand-entity.md
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

from backend.agents.brand_registry import BrandRegistry


class TestBrandRegistryCreate(unittest.TestCase):
    """create_brand persists a brand with id, name, brand_context, timestamps."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "brand_registry.json")
        with open(self.path, "w") as f:
            json.dump([], f)
        self.registry = BrandRegistry(filepath=self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_brand_returns_brand_with_id_and_name(self):
        brand = self.registry.create_brand("Acme")
        self.assertEqual(brand["name"], "Acme")
        self.assertTrue(brand["id"])

    def test_create_brand_persists_to_json(self):
        self.registry.create_brand("Acme")
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Acme")

    def test_create_brand_has_timestamps(self):
        brand = self.registry.create_brand("Acme")
        self.assertTrue(brand["created_at"])
        self.assertTrue(brand["updated_at"])

    def test_create_brand_default_brand_context_has_expected_fields(self):
        brand = self.registry.create_brand("Acme")
        ctx = brand["brand_context"]
        for key in ("tone", "target_audience", "guidelines", "forbidden_words"):
            self.assertIn(key, ctx)

    def test_create_brand_accepts_custom_brand_context(self):
        ctx = {
            "tone": "friendly",
            "target_audience": "teens",
            "guidelines": "be concise",
            "forbidden_words": ["spam"],
        }
        brand = self.registry.create_brand("Acme", brand_context=ctx)
        self.assertEqual(brand["brand_context"]["tone"], "friendly")
        self.assertEqual(brand["brand_context"]["forbidden_words"], ["spam"])


class TestBrandRegistryGet(unittest.TestCase):
    """get_brand returns the brand by id, or None."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "brand_registry.json")
        with open(self.path, "w") as f:
            json.dump([], f)
        self.registry = BrandRegistry(filepath=self.path)
        self.brand = self.registry.create_brand("Acme")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_brand_returns_brand_by_id(self):
        found = self.registry.get_brand(self.brand["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "Acme")

    def test_get_brand_returns_none_for_unknown_id(self):
        self.assertIsNone(self.registry.get_brand("nope"))


class TestBrandRegistryList(unittest.TestCase):
    """list_brands returns all brands, newest first."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "brand_registry.json")
        with open(self.path, "w") as f:
            json.dump([], f)
        self.registry = BrandRegistry(filepath=self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_brands_empty(self):
        self.assertEqual(self.registry.list_brands(), [])

    def test_list_brands_returns_all_newest_first(self):
        self.registry.create_brand("First")
        self.registry.create_brand("Second")
        brands = self.registry.list_brands()
        self.assertEqual(len(brands), 2)
        # newest first: "Second" created after "First"
        self.assertEqual(brands[0]["name"], "Second")


class TestBrandRegistryUpdate(unittest.TestCase):
    """update_brand updates allowed fields + bumps updated_at."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "brand_registry.json")
        with open(self.path, "w") as f:
            json.dump([], f)
        self.registry = BrandRegistry(filepath=self.path)
        self.brand = self.registry.create_brand("Acme")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_brand_name(self):
        ok = self.registry.update_brand(self.brand["id"], {"name": "Acme Co"})
        self.assertTrue(ok)
        self.assertEqual(self.registry.get_brand(self.brand["id"])["name"], "Acme Co")

    def test_update_brand_context(self):
        ok = self.registry.update_brand(self.brand["id"], {
            "brand_context": {"tone": "bold", "target_audience": "",
                              "guidelines": "", "forbidden_words": []}
        })
        self.assertTrue(ok)
        self.assertEqual(self.registry.get_brand(self.brand["id"])["brand_context"]["tone"], "bold")

    def test_update_brand_bumps_updated_at(self):
        old = self.brand["updated_at"]
        self.registry.update_brand(self.brand["id"], {"name": "New"})
        self.assertNotEqual(self.registry.get_brand(self.brand["id"])["updated_at"], old)

    def test_update_brand_unknown_id_returns_false(self):
        self.assertFalse(self.registry.update_brand("nope", {"name": "X"}))


class TestBrandRegistryDelete(unittest.TestCase):
    """delete_brand removes a brand; unknown id returns False."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "brand_registry.json")
        with open(self.path, "w") as f:
            json.dump([], f)
        self.registry = BrandRegistry(filepath=self.path)
        self.brand = self.registry.create_brand("Acme")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_delete_brand_removes_it(self):
        self.assertTrue(self.registry.delete_brand(self.brand["id"]))
        self.assertIsNone(self.registry.get_brand(self.brand["id"]))

    def test_delete_brand_unknown_id_returns_false(self):
        self.assertFalse(self.registry.delete_brand("nope"))


class TestBrandRegistryPerUserIsolation(unittest.TestCase):
    """user_id routes to a per-user path, isolating data between users."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_user_id_uses_per_user_path(self):
        os.environ["AGENT_APP_DATA_DIR"] = self.tmpdir
        try:
            reg_a = BrandRegistry(user_id="user_a")
            reg_a.create_brand("Brand A")
            reg_b = BrandRegistry(user_id="user_b")
            # user_b should not see user_a's brand
            self.assertEqual(reg_b.list_brands(), [])
            # user_a sees its own brand
            self.assertEqual(len(reg_a.list_brands()), 1)
        finally:
            del os.environ["AGENT_APP_DATA_DIR"]


if __name__ == "__main__":
    unittest.main()
