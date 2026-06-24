import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from advisor.ontology import OntologyRepository


def write_fixture(root, *, heroes=None, items=None, edges=None, indexes=None):
    payloads = {
        "hero_profiles.json": heroes if heroes is not None else [],
        "item_profiles.json": items if items is not None else [],
        "relation_edges.json": edges if edges is not None else [],
        "indexes.json": indexes if indexes is not None else {},
    }
    for filename, payload in payloads.items():
        (root / filename).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


class OntologyRepositoryTests(unittest.TestCase):
    def test_loads_profile_counter_edges_and_translates_both_item_id_forms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            hero = {"英雄名": "力丸", "英雄派生特征": ["隐身"]}
            counter_edge = {
                "relation": "counter",
                "target_entity_type": "hero",
                "target_name": "力丸",
                "source_name": "显影之尘",
            }
            write_fixture(
                root,
                heroes=[hero],
                items=[{"物品名": "白银之锋", "内部名称": "silver_edge"}],
                edges=[counter_edge],
                indexes={
                    "hero_profile_by_name": {"力丸": 0},
                    "edges_by_target": {"力丸": [0]},
                },
            )

            repository = OntologyRepository(root)

            self.assertTrue(repository.available)
            self.assertEqual(repository.get_hero_profile("力丸"), hero)
            self.assertEqual(repository.get_counter_edges("力丸"), [counter_edge])
            self.assertEqual(
                repository.translate_item_ids(
                    ["item_silver_edge", "silver_edge", "item_unknown"]
                ),
                {"白银之锋"},
            )

    def test_missing_file_disables_repository_and_warns_only_at_construction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                repository = OntologyRepository(Path(temp_dir))
                self.assertIsNone(repository.get_hero_profile("力丸"))
                self.assertEqual(repository.get_counter_edges("力丸"), [])
                self.assertEqual(repository.translate_item_ids(["item_blink"]), set())

            self.assertFalse(repository.available)
            self.assertEqual(stderr.getvalue().count("[AI Advisor] 本体加载失败:"), 1)

    def test_invalid_indexes_and_non_matching_edges_are_skipped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            valid_edge = {
                "relation": "counter",
                "target_entity_type": "hero",
                "target_name": "力丸",
            }
            write_fixture(
                root,
                heroes=[{"英雄名": "力丸"}],
                edges=[
                    valid_edge,
                    {
                        "relation": "depend",
                        "target_entity_type": "hero",
                        "target_name": "力丸",
                    },
                    {
                        "relation": "counter",
                        "target_entity_type": "item",
                        "target_name": "力丸",
                    },
                    {
                        "relation": "counter",
                        "target_entity_type": "hero",
                        "target_name": "斧王",
                    },
                    "bad record",
                ],
                indexes={
                    "hero_profile_by_name": {
                        "力丸": True,
                        "斧王": "bad",
                        "莉娜": 99,
                    },
                    "edges_by_target": {
                        "力丸": [0, 1, 2, 3, 4, True, "bad", 99],
                        "斧王": "bad",
                    },
                },
            )

            repository = OntologyRepository(root)

            self.assertIsNone(repository.get_hero_profile("力丸"))
            self.assertIsNone(repository.get_hero_profile("斧王"))
            self.assertIsNone(repository.get_hero_profile("莉娜"))
            self.assertEqual(repository.get_counter_edges("力丸"), [valid_edge])
            self.assertEqual(repository.get_counter_edges("斧王"), [])


if __name__ == "__main__":
    unittest.main()
