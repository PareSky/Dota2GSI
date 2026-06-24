import json
import sys
from pathlib import Path
from typing import Iterable, Optional


class OntologyRepository:
    """Load and safely query the ontology data used by the AI advisor."""

    _FILENAMES = (
        "hero_profiles.json",
        "item_profiles.json",
        "relation_edges.json",
        "indexes.json",
    )

    def __init__(self, root: Path):
        self.root = Path(root)
        self.available = False
        self._heroes = []
        self._items = []
        self._edges = []
        self._indexes = {}
        self._item_names_by_internal_name = {}

        try:
            loaded = {
                filename: self._load_json(self.root / filename)
                for filename in self._FILENAMES
            }
            heroes = loaded["hero_profiles.json"]
            items = loaded["item_profiles.json"]
            edges = loaded["relation_edges.json"]
            indexes = loaded["indexes.json"]

            if not isinstance(heroes, list):
                raise ValueError("hero_profiles.json 顶层必须是 list")
            if not isinstance(items, list):
                raise ValueError("item_profiles.json 顶层必须是 list")
            if not isinstance(edges, list):
                raise ValueError("relation_edges.json 顶层必须是 list")
            if not isinstance(indexes, dict):
                raise ValueError("indexes.json 顶层必须是 dict")

            self._heroes = heroes
            self._items = items
            self._edges = edges
            self._indexes = indexes
            self._item_names_by_internal_name = self._build_item_name_map(items)
            self.available = True
        except Exception as exc:
            print(f"[AI Advisor] 本体加载失败: {exc}", file=sys.stderr)

    @staticmethod
    def _load_json(path: Path):
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _build_item_name_map(items):
        names = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            internal_name = item.get("内部名称")
            display_name = item.get("物品名")
            if isinstance(internal_name, str) and isinstance(display_name, str):
                names[internal_name] = display_name
        return names

    @staticmethod
    def _safe_index(records, index):
        if isinstance(index, bool) or not isinstance(index, int):
            return None
        if index < 0 or index >= len(records):
            return None
        record = records[index]
        return record if isinstance(record, dict) else None

    def get_hero_profile(self, hero_name: str) -> Optional[dict]:
        if not self.available:
            return None
        profile_indexes = self._indexes.get("hero_profile_by_name")
        if not isinstance(profile_indexes, dict):
            return None
        return self._safe_index(self._heroes, profile_indexes.get(hero_name))

    def get_counter_edges(self, hero_name: str) -> list[dict]:
        if not self.available:
            return []
        edges_by_target = self._indexes.get("edges_by_target")
        if not isinstance(edges_by_target, dict):
            return []
        edge_indexes = edges_by_target.get(hero_name)
        if not isinstance(edge_indexes, list):
            return []

        matches = []
        for index in edge_indexes:
            edge = self._safe_index(self._edges, index)
            if (
                edge is not None
                and edge.get("relation") == "counter"
                and edge.get("target_entity_type") == "hero"
                and edge.get("target_name") == hero_name
            ):
                matches.append(edge)
        return matches

    def translate_item_ids(self, item_ids: Iterable[str]) -> set[str]:
        if not self.available:
            return set()

        translated = set()
        for item_id in item_ids:
            if not isinstance(item_id, str):
                continue
            internal_name = item_id.removeprefix("item_")
            display_name = self._item_names_by_internal_name.get(internal_name)
            if display_name is not None:
                translated.add(display_name)
        return translated
