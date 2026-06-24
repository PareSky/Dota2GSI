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


class EnemyKnowledgeBuilder:
    _ROLE_PREFERENCES = {
        "1": ("进攻装", "魔免装", "留人装", "破坏装"),
        "2": ("进攻装", "魔免装", "留人装", "破坏装"),
        "3": ("保命装", "团队装", "位移装", "留人装"),
        "4": ("保命装", "反隐装", "视野装", "团队装", "驱散装"),
        "5": ("保命装", "反隐装", "视野装", "团队装", "驱散装"),
    }
    _TEAM_OBLIGATIONS = {"反隐装", "视野装", "禁疗装"}
    _TRAIT_TACTICS = {
        "高爆发型": "保持距离，预留保命技能",
        "高机动型": "保留硬控，不要单独追击",
        "幻象核心型": "保留范围技能清幻象并识别真身",
        "隐身型": "提前铺反隐，避免无视野单走",
        "被动依赖型": "优先考虑破坏效果",
        "回复型": "尽早准备禁疗",
        "团战先手型": "分散站位，避免多人被先手",
    }

    def __init__(
        self,
        repository: OntologyRepository,
        min_counter_strength: int = 70,
        max_traits_per_hero: int = 3,
        max_counters_per_hero: int = 2,
        max_context_chars: int = 1800,
    ):
        self._repository = repository
        self._min_strength = min_counter_strength
        self._max_traits = max_traits_per_hero
        self._max_counters = max_counters_per_hero
        self._max_chars = max_context_chars

    @staticmethod
    def _phase(game_time: float) -> str:
        if game_time < 15 * 60:
            return "early"
        if game_time < 30 * 60:
            return "midgame"
        return "lategame"

    def _score_counter(
        self,
        edge: dict,
        phase: str,
        role_preferences: tuple[str, ...],
        player_item_needs: set[str],
    ) -> int:
        trait = edge.get("source_trait", "")
        score = int(edge.get("strength", 0))
        phases = set(edge.get("phase", []))
        phase_matches = (
            "all" in phases
            or phase in phases
            or (phase == "midgame" and "teamfight" in phases)
            or (
                phase == "lategame"
                and bool(phases & {"midgame", "teamfight"})
            )
        )
        if phase_matches:
            score += 10
        if trait in player_item_needs:
            score += 12
        if trait in self._TEAM_OBLIGATIONS:
            score += 25
        elif role_preferences:
            score += 12 if trait in role_preferences else -8
        return score

    def build(
        self,
        enemy_heroes,
        player_hero,
        role,
        owned_item_ids,
        game_time,
    ) -> str:
        if not self._repository.available:
            return ""

        owned_items = self._repository.translate_item_ids(owned_item_ids)
        player_profile = self._repository.get_hero_profile(player_hero) or {}
        player_item_needs = {
            item
            for item in player_profile.get("物品需求", [])
            if isinstance(item, str)
        }
        role_preferences = self._ROLE_PREFERENCES.get(str(role), ())
        phase = self._phase(game_time)
        used_items = set(owned_items)
        lines = []
        threats = {"隐身型": [], "回复型": [], "幻象核心型": []}

        for enemy in enemy_heroes:
            profile = self._repository.get_hero_profile(enemy)
            if profile is None:
                continue

            raw_traits = profile.get("英雄派生特征", [])
            traits = [
                trait
                for trait in raw_traits
                if isinstance(trait, dict)
                and isinstance(trait.get("trait"), str)
            ]
            traits.sort(
                key=lambda item: (
                    item.get("score", 0)
                    if isinstance(item.get("score", 0), (int, float))
                    else 0
                ),
                reverse=True,
            )
            trait_names = [
                item["trait"] for item in traits[:self._max_traits]
            ]
            all_trait_names = {item["trait"] for item in traits}
            for threat in threats:
                if threat in all_trait_names:
                    threats[threat].append(enemy)

            counters = []
            for edge in self._repository.get_counter_edges(enemy):
                item_name = edge.get("source_name")
                strength = edge.get("strength", 0)
                if (
                    edge.get("source_entity_type") != "item"
                    or not isinstance(item_name, str)
                    or not isinstance(strength, (int, float))
                    or strength < self._min_strength
                    or item_name in used_items
                ):
                    continue
                counters.append(
                    (
                        self._score_counter(
                            edge,
                            phase,
                            role_preferences,
                            player_item_needs,
                        ),
                        item_name,
                        edge.get("source_trait", "反制装"),
                    )
                )
            counters.sort(key=lambda item: item[0], reverse=True)

            selected = []
            for _score, item_name, item_trait in counters:
                if item_name in used_items:
                    continue
                used_items.add(item_name)
                selected.append(f"{item_name}（{item_trait}）")
                if len(selected) >= self._max_counters:
                    break

            parts = []
            if trait_names:
                parts.append(f"特性：{'、'.join(trait_names)}")
                tactic = next(
                    (
                        self._TRAIT_TACTICS[trait]
                        for trait in trait_names
                        if trait in self._TRAIT_TACTICS
                    ),
                    "",
                )
                if tactic:
                    parts.append(f"打法：{tactic}")
            if selected:
                parts.append(f"反制候选：{'、'.join(selected)}")
            if parts:
                lines.append(f"- {enemy}：{'；'.join(parts)}")

        team_tips = []
        if threats["隐身型"]:
            team_tips.append(
                f"{'、'.join(threats['隐身型'])}有隐身，团队补反隐与视野"
            )
        if threats["回复型"]:
            team_tips.append(
                f"{'、'.join(threats['回复型'])}回复强，团队补禁疗"
            )
        if threats["幻象核心型"]:
            team_tips.append(
                f"{'、'.join(threats['幻象核心型'])}依赖幻象，准备范围清幻象"
            )
        if team_tips:
            lines.append(f"- 团队提示：{'；'.join(team_tips)}")

        if not lines:
            return ""
        result = "【敌方机制参考】"
        included = []
        for line in lines:
            candidate = result + "\n" + "\n".join(included + [line])
            if len(candidate) <= self._max_chars:
                included.append(line)
        if not included:
            return ""
        return result + "\n" + "\n".join(included)
