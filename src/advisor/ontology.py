import json
import sys
from pathlib import Path
from typing import Iterable, Optional


class OntologyRepository:
    _FILES = (
        "hero_profiles.json",
        "item_profiles.json",
        "relation_edges.json",
        "indexes.json",
    )

    def __init__(self, root: Path):
        self.available = False
        self._heroes = []
        self._edges = []
        self._indexes = {}
        self._item_names = {}

        try:
            data = {
                filename: json.loads(
                    (Path(root) / filename).read_text(encoding="utf-8")
                )
                for filename in self._FILES
            }
            heroes = data["hero_profiles.json"]
            items = data["item_profiles.json"]
            edges = data["relation_edges.json"]
            indexes = data["indexes.json"]
            if not isinstance(heroes, list):
                raise ValueError("hero_profiles.json 顶层必须是 list")
            if not isinstance(items, list):
                raise ValueError("item_profiles.json 顶层必须是 list")
            if not isinstance(edges, list):
                raise ValueError("relation_edges.json 顶层必须是 list")
            if not isinstance(indexes, dict):
                raise ValueError("indexes.json 顶层必须是 dict")

            self._heroes = heroes
            self._edges = edges
            self._indexes = indexes
            self._item_names = {
                item["内部名称"]: item["物品名"]
                for item in items
                if isinstance(item, dict)
                and isinstance(item.get("内部名称"), str)
                and isinstance(item.get("物品名"), str)
            }
            self.available = True
        except Exception as exc:
            print(f"[AI Advisor] 本体加载失败: {exc}", file=sys.stderr)

    @staticmethod
    def _record_at(records, index):
        if isinstance(index, bool) or not isinstance(index, int):
            return None
        if index < 0 or index >= len(records):
            return None
        record = records[index]
        return record if isinstance(record, dict) else None

    def get_hero_profile(self, hero_name: str) -> Optional[dict]:
        if not self.available:
            return None
        by_name = self._indexes.get("hero_profile_by_name")
        if not isinstance(by_name, dict):
            return None
        return self._record_at(self._heroes, by_name.get(hero_name))

    def get_counter_edges(self, hero_name: str) -> list[dict]:
        if not self.available:
            return []
        by_target = self._indexes.get("edges_by_target")
        if not isinstance(by_target, dict):
            return []
        edge_indexes = by_target.get(hero_name)
        if not isinstance(edge_indexes, list):
            return []

        result = []
        for index in edge_indexes:
            edge = self._record_at(self._edges, index)
            if (
                edge is not None
                and edge.get("relation") == "counter"
                and edge.get("target_entity_type") == "hero"
                and edge.get("target_name") == hero_name
            ):
                result.append(edge)
        return result

    def translate_item_ids(self, item_ids: Iterable[str]) -> set[str]:
        if not self.available:
            return set()
        result = set()
        for item_id in item_ids:
            if not isinstance(item_id, str):
                continue
            name = self._item_names.get(item_id.removeprefix("item_"))
            if name is not None:
                result.add(name)
        return result
