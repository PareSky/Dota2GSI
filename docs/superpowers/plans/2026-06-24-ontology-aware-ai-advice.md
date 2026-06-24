# Ontology-Aware AI Advice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich each AI coach request with compact enemy traits and countermeasures ranked for the player's current hero, role, inventory, and game phase.

**Architecture:** Add an `OntologyRepository` that loads and indexes the bundled JSON data and an `EnemyKnowledgeBuilder` that performs deterministic scoring and text compression. Keep lineup and inventory extraction in `StateExtractor`, inject the builder into `PromptBuilder`, and rebuild the ontology section for every request so phase and owned-item filtering never become stale.

**Tech Stack:** Python 3.10+, standard-library `json`, `pathlib`, `dataclasses`, existing `unittest` suite, YAML configuration, PyInstaller.

---

## File Map

- Create `src/advisor/ontology.py`: ontology loading, validation, item-name translation, candidate scoring, deduplication, and context rendering.
- Create `tests/test_ontology_advisor.py`: isolated fixtures and unit tests for repository/builder behavior.
- Modify `src/advisor/extractor.py`: expose enemy lineup and owned item IDs without duplicating GSI parsing.
- Modify `src/advisor/prompt.py`: inject dynamic enemy mechanism context into each user message.
- Modify `src/ai_advisor.py`: construct ontology components from `ai_advisor.ontology` configuration and preserve graceful fallback.
- Modify `tests/test_advisor_refactor.py`: replace brittle prompt hashes with structural assertions and cover prompt integration.
- Modify `config.yaml`: document ontology defaults.
- Modify `README.md`: document ontology behavior and configuration.
- Modify `Dota2GSI.spec`: bundle the ontology directory.
- Modify `build.bat`: bundle the ontology directory in the direct PyInstaller command.
- Modify `tests/test_resource_paths.py`: verify both build paths include ontology data.
- Modify `docs/superpowers/specs/2026-06-24-ontology-aware-ai-advice-design.md`: correct the data dependency to include `item_profiles.json`, which is required to map GSI item IDs to Chinese ontology names.

Implementation must preserve the user's existing staged edits in `tests/test_advisor_refactor.py`; edit the current working-tree version and never reset it.

### Task 1: Add repository loading and item-name translation

**Files:**
- Create: `src/advisor/ontology.py`
- Create: `tests/test_ontology_advisor.py`
- Modify: `docs/superpowers/specs/2026-06-24-ontology-aware-ai-advice-design.md`

- [ ] **Step 1: Correct the design document's data dependency**

Replace the sentence that limits the first version to three files with:

```markdown
第一版依赖 `hero_profiles.json`、`item_profiles.json`、`relation_edges.json` 和 `indexes.json`。`item_profiles.json` 用于把 GSI 的 `item_*` 内部名称映射为本体中的中文物品名，从而排除玩家已经拥有的装备。其余文件保留为后续精细化能力，不在第一版扩大范围。
```

Add this repository behavior bullet:

```markdown
- 根据 `item_profiles.json` 建立物品内部名到中文名的映射。
```

- [ ] **Step 2: Write repository fixture helpers and failing tests**

Create `tests/test_ontology_advisor.py` with a minimal reusable fixture:

```python
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))


def write_json(root: Path, name: str, value) -> None:
    (root / name).write_text(
        json.dumps(value, ensure_ascii=False),
        encoding="utf-8",
    )


def create_ontology(root: Path) -> None:
    heroes = [
        {
            "英雄名": "莉娜",
            "内部名称": "npc_dota_hero_lina",
            "英雄派生特征": [{"trait": "高爆发型", "score": 80}],
            "物品需求": ["进攻装", "魔免装"],
            "被什么物品克制": [],
        },
        {
            "英雄名": "幻影刺客",
            "内部名称": "npc_dota_hero_phantom_assassin",
            "英雄派生特征": [
                {"trait": "高爆发型", "score": 90},
                {"trait": "被动依赖型", "score": 85},
                {"trait": "隐身型", "score": 70},
            ],
            "物品需求": ["进攻装"],
            "被什么物品克制": ["破坏装", "反隐装"],
        },
    ]
    items = [
        {
            "物品名": "白银之锋",
            "内部名称": "silver_edge",
            "物品派生特征": [{"trait": "破坏装", "score": 80}],
        },
        {
            "物品名": "显影之尘",
            "内部名称": "dust",
            "物品派生特征": [{"trait": "反隐装", "score": 90}],
        },
    ]
    edges = [
        {
            "edge_id": "EDGE_1",
            "source_entity_type": "item",
            "source_name": "白银之锋",
            "source_trait": "破坏装",
            "target_entity_type": "hero",
            "target_name": "幻影刺客",
            "target_trait": "被动依赖型",
            "relation": "counter",
            "strength": 80,
            "phase": ["midgame", "teamfight"],
            "source_evidence": ["白银之锋=破坏"],
            "target_evidence": ["恩赐解脱=被动+暴击"],
        },
        {
            "edge_id": "EDGE_2",
            "source_entity_type": "item",
            "source_name": "显影之尘",
            "source_trait": "反隐装",
            "target_entity_type": "hero",
            "target_name": "幻影刺客",
            "target_trait": "隐身型",
            "relation": "counter",
            "strength": 85,
            "phase": ["all"],
            "source_evidence": ["显影之尘=反隐"],
            "target_evidence": ["魅影无形=隐身"],
        },
    ]
    indexes = {
        "hero_profile_by_name": {"莉娜": 0, "幻影刺客": 1},
        "item_profile_by_name": {"白银之锋": 0, "显影之尘": 1},
        "edges_by_target": {"幻影刺客": [0, 1]},
    }
    write_json(root, "hero_profiles.json", heroes)
    write_json(root, "item_profiles.json", items)
    write_json(root, "relation_edges.json", edges)
    write_json(root, "indexes.json", indexes)
```

Add initial tests:

```python
class OntologyRepositoryTests(unittest.TestCase):
    def test_loads_profiles_edges_and_item_name_mapping(self):
        from advisor.ontology import OntologyRepository

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_ontology(root)
            repository = OntologyRepository(root)

        self.assertTrue(repository.available)
        self.assertEqual(
            repository.get_hero_profile("幻影刺客")["英雄名"],
            "幻影刺客",
        )
        self.assertEqual(
            [edge["edge_id"] for edge in repository.get_counter_edges("幻影刺客")],
            ["EDGE_1", "EDGE_2"],
        )
        self.assertEqual(
            repository.translate_item_ids({"item_silver_edge", "dust"}),
            {"白银之锋", "显影之尘"},
        )

    def test_missing_or_invalid_data_disables_repository_once(self):
        from advisor.ontology import OntologyRepository

        with tempfile.TemporaryDirectory() as directory:
            errors = io.StringIO()
            with redirect_stderr(errors):
                repository = OntologyRepository(Path(directory))
                first = repository.get_hero_profile("幻影刺客")
                second = repository.get_counter_edges("幻影刺客")

        self.assertFalse(repository.available)
        self.assertIsNone(first)
        self.assertEqual(second, [])
        self.assertEqual(errors.getvalue().count("[AI Advisor] 本体加载失败"), 1)
```

- [ ] **Step 3: Run the repository tests and verify failure**

Run:

```powershell
python -m unittest tests.test_ontology_advisor.OntologyRepositoryTests -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'advisor.ontology'`.

- [ ] **Step 4: Implement the minimal repository**

Create `src/advisor/ontology.py`:

```python
"""Dota 2 mechanism ontology loading and personalized context building."""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set


class OntologyRepository:
    REQUIRED_FILES = (
        "hero_profiles.json",
        "item_profiles.json",
        "relation_edges.json",
        "indexes.json",
    )

    def __init__(self, root: Path):
        self._root = Path(root)
        self.available = False
        self._heroes: List[Dict[str, Any]] = []
        self._items: List[Dict[str, Any]] = []
        self._edges: List[Dict[str, Any]] = []
        self._hero_indexes: Dict[str, int] = {}
        self._edges_by_target: Dict[str, List[int]] = {}
        self._item_name_by_internal: Dict[str, str] = {}
        self._load()

    @staticmethod
    def _read_json(path: Path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load(self) -> None:
        try:
            heroes = self._read_json(self._root / "hero_profiles.json")
            items = self._read_json(self._root / "item_profiles.json")
            edges = self._read_json(self._root / "relation_edges.json")
            indexes = self._read_json(self._root / "indexes.json")
            if not isinstance(heroes, list):
                raise ValueError("hero_profiles.json must contain a list")
            if not isinstance(items, list):
                raise ValueError("item_profiles.json must contain a list")
            if not isinstance(edges, list):
                raise ValueError("relation_edges.json must contain a list")
            if not isinstance(indexes, dict):
                raise ValueError("indexes.json must contain an object")

            self._heroes = heroes
            self._items = items
            self._edges = edges
            self._hero_indexes = indexes.get("hero_profile_by_name", {})
            self._edges_by_target = indexes.get("edges_by_target", {})
            self._item_name_by_internal = {
                str(item.get("内部名称", "")).removeprefix("item_"): item["物品名"]
                for item in items
                if item.get("内部名称") and item.get("物品名")
            }
            self.available = True
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"[AI Advisor] 本体加载失败: {exc}", file=sys.stderr)

    def get_hero_profile(self, hero_name: str) -> Optional[Dict[str, Any]]:
        if not self.available:
            return None
        index = self._hero_indexes.get(hero_name)
        if not isinstance(index, int) or not 0 <= index < len(self._heroes):
            return None
        profile = self._heroes[index]
        return profile if isinstance(profile, dict) else None

    def get_counter_edges(self, hero_name: str) -> List[Dict[str, Any]]:
        if not self.available:
            return []
        result = []
        for index in self._edges_by_target.get(hero_name, []):
            if not isinstance(index, int) or not 0 <= index < len(self._edges):
                continue
            edge = self._edges[index]
            if (
                isinstance(edge, dict)
                and edge.get("relation") == "counter"
                and edge.get("target_entity_type") == "hero"
                and edge.get("target_name") == hero_name
            ):
                result.append(edge)
        return result

    def translate_item_ids(self, item_ids: Iterable[str]) -> Set[str]:
        result = set()
        for item_id in item_ids:
            normalized = str(item_id).removeprefix("item_")
            chinese_name = self._item_name_by_internal.get(normalized)
            if chinese_name:
                result.add(chinese_name)
        return result
```

- [ ] **Step 5: Run repository tests**

Run:

```powershell
python -m unittest tests.test_ontology_advisor.OntologyRepositoryTests -v
```

Expected: both tests `ok`.

- [ ] **Step 6: Commit repository loading**

```powershell
git add src/advisor/ontology.py tests/test_ontology_advisor.py docs/superpowers/specs/2026-06-24-ontology-aware-ai-advice-design.md
git commit -m "feat: load Dota mechanism ontology"
```

### Task 2: Expose enemy lineup and owned item IDs

**Files:**
- Modify: `src/advisor/extractor.py`
- Modify: `tests/test_advisor_refactor.py`

- [ ] **Step 1: Write failing extractor tests**

Extend `AdvisorComponentTests`:

```python
def test_extractor_returns_enemy_lineup_for_both_teams(self):
    from advisor.extractor import StateExtractor

    extractor = StateExtractor()
    extractor.team_lineups = {
        "radiant": ["莉娜", "斧王"],
        "dire": ["幻影刺客", "力丸"],
    }

    self.assertEqual(
        extractor.get_enemy_lineup("radiant"),
        ["幻影刺客", "力丸"],
    )
    self.assertEqual(
        extractor.get_enemy_lineup("dire"),
        ["莉娜", "斧王"],
    )
    self.assertEqual(extractor.get_enemy_lineup(""), [])


def test_extractor_returns_normalized_owned_item_ids(self):
    from advisor.extractor import StateExtractor

    data = sample_data()
    data["items"]["slot1"] = {"name": "item_silver_edge"}
    data["items"]["slot2"] = {"name": "empty"}

    self.assertEqual(
        StateExtractor.extract_owned_item_ids(data),
        {"blink", "silver_edge"},
    )
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
python -m unittest tests.test_advisor_refactor.AdvisorComponentTests.test_extractor_returns_enemy_lineup_for_both_teams tests.test_advisor_refactor.AdvisorComponentTests.test_extractor_returns_normalized_owned_item_ids -v
```

Expected: `ERROR` because both methods are missing.

- [ ] **Step 3: Implement the extractor methods**

Add to `StateExtractor` after `reset()`:

```python
def get_enemy_lineup(self, player_team_name: str) -> List[str]:
    if player_team_name == "radiant":
        return list(self.team_lineups.get("dire", []))
    if player_team_name == "dire":
        return list(self.team_lineups.get("radiant", []))
    return []

@classmethod
def extract_owned_item_ids(cls, data: Dict[str, Any]) -> set:
    owned = set()
    items = data.get("items", {})
    for slot_key in cls.ITEM_SLOTS:
        name = items.get(slot_key, {}).get("name", "")
        if name and name != "empty":
            owned.add(name.removeprefix("item_"))
    return owned
```

- [ ] **Step 4: Run extractor tests**

Run:

```powershell
python -m unittest tests.test_advisor_refactor.AdvisorComponentTests.test_extractor_returns_enemy_lineup_for_both_teams tests.test_advisor_refactor.AdvisorComponentTests.test_extractor_returns_normalized_owned_item_ids -v
```

Expected: both tests `ok`.

- [ ] **Step 5: Commit extractor context**

```powershell
git add src/advisor/extractor.py tests/test_advisor_refactor.py
git commit -m "feat: extract ontology player context"
```

### Task 3: Implement role-, hero-, inventory-, and phase-aware scoring

**Files:**
- Modify: `src/advisor/ontology.py`
- Modify: `tests/test_ontology_advisor.py`

- [ ] **Step 1: Write failing scoring tests**

Append:

```python
class EnemyKnowledgeBuilderTests(unittest.TestCase):
    def build_repository(self, root: Path):
        from advisor.ontology import OntologyRepository

        create_ontology(root)
        return OntologyRepository(root)

    def test_role_changes_counter_scores_without_hiding_team_duties(self):
        from advisor.ontology import EnemyKnowledgeBuilder

        with tempfile.TemporaryDirectory() as directory:
            repository = self.build_repository(Path(directory))
            builder = EnemyKnowledgeBuilder(repository)
            carry = builder._score_candidates(
                enemy="幻影刺客",
                player_needs={"进攻装", "魔免装"},
                role="1",
                owned_items=set(),
                game_time=1200,
            )
            support = builder._score_candidates(
                enemy="幻影刺客",
                player_needs={"进攻装", "魔免装"},
                role="5",
                owned_items=set(),
                game_time=1200,
            )

        carry_scores = {candidate.item: candidate.score for candidate in carry}
        support_scores = {
            candidate.item: candidate.score for candidate in support
        }
        self.assertGreater(
            carry_scores["白银之锋"],
            support_scores["白银之锋"],
        )
        self.assertGreater(
            support_scores["显影之尘"],
            support_scores["白银之锋"],
        )
        self.assertTrue(
            next(
                candidate
                for candidate in support
                if candidate.item == "显影之尘"
            ).team_duty
        )

    def test_owned_item_is_removed_and_phase_changes_score(self):
        from advisor.ontology import EnemyKnowledgeBuilder

        with tempfile.TemporaryDirectory() as directory:
            repository = self.build_repository(Path(directory))
            builder = EnemyKnowledgeBuilder(repository)
            early = builder.build(
                ["幻影刺客"], "莉娜", "1", set(), 300
            )
            mid = builder.build(
                ["幻影刺客"], "莉娜", "1", {"silver_edge"}, 1200
            )

        self.assertIn("白银之锋", early)
        self.assertNotIn("白银之锋", mid)
        self.assertIn("显影之尘", mid)
```

- [ ] **Step 2: Run scoring tests and verify failure**

Run:

```powershell
python -m unittest tests.test_ontology_advisor.EnemyKnowledgeBuilderTests -v
```

Expected: `ImportError` for `EnemyKnowledgeBuilder`.

- [ ] **Step 3: Add candidate type and deterministic scoring**

Append to `src/advisor/ontology.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CounterCandidate:
    enemy: str
    item: str
    item_trait: str
    target_trait: str
    score: int
    team_duty: bool
    order: int


class EnemyKnowledgeBuilder:
    ROLE_TRAITS = {
        "1": {"进攻装", "魔免装", "留人装", "破坏装", "续航装"},
        "2": {"进攻装", "位移装", "留人装", "魔免装", "技能强化装"},
        "3": {"保命装", "团队装", "位移装", "留人装", "反制装"},
        "4": {"位移装", "保命装", "反隐装", "视野装", "留人装", "团队装"},
        "5": {"保命装", "反隐装", "视野装", "团队装", "驱散装"},
    }
    TEAM_DUTY_TRAITS = {"反隐装", "视野装", "禁疗装"}
    PHASES = (
        (8 * 60, "laning"),
        (15 * 60, "early"),
        (30 * 60, "midgame"),
    )

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

    @classmethod
    def _phase(cls, game_time: float) -> str:
        for boundary, phase in cls.PHASES:
            if game_time < boundary:
                return phase
        return "lategame"

    @staticmethod
    def _phase_matches(current: str, edge_phases: Iterable[str]) -> bool:
        phases = set(edge_phases)
        if "all" in phases:
            return True
        if current == "midgame":
            return bool(phases & {"midgame", "teamfight"})
        if current == "lategame":
            return bool(phases & {"midgame", "lategame", "teamfight"})
        return False

    def _score_candidates(
        self,
        enemy: str,
        player_needs: Set[str],
        role: str,
        owned_items: Set[str],
        game_time: float,
    ) -> List[CounterCandidate]:
        current_phase = self._phase(game_time)
        role_traits = self.ROLE_TRAITS.get(role, set())
        candidates = []
        for order, edge in enumerate(self._repository.get_counter_edges(enemy)):
            strength = edge.get("strength")
            item = edge.get("source_name")
            item_trait = edge.get("source_trait", "")
            if (
                not isinstance(strength, (int, float))
                or strength < self._min_strength
                or not item
                or item in owned_items
            ):
                continue
            team_duty = item_trait in self.TEAM_DUTY_TRAITS
            score = int(strength)
            phases = edge.get("phase", [])
            if "all" in phases:
                score += 5
            if self._phase_matches(current_phase, phases):
                score += 10
            if item_trait in role_traits:
                score += 15
            elif not team_duty:
                score -= 20
            if item_trait in player_needs:
                score += 10
            if team_duty:
                score += 20
            candidates.append(
                CounterCandidate(
                    enemy=enemy,
                    item=item,
                    item_trait=item_trait,
                    target_trait=edge.get("target_trait", ""),
                    score=score,
                    team_duty=team_duty,
                    order=order,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                not candidate.team_duty,
                -candidate.score,
                candidate.order,
                candidate.item,
            ),
        )

    def build(
        self,
        enemy_heroes: List[str],
        player_hero: str,
        role: str,
        owned_item_ids: Set[str],
        game_time: float,
    ) -> str:
        if not self._repository.available or not enemy_heroes:
            return ""
        player_profile = self._repository.get_hero_profile(player_hero) or {}
        player_needs = set(player_profile.get("物品需求", []))
        owned_items = self._repository.translate_item_ids(owned_item_ids)
        lines = ["【敌方机制参考】"]
        for enemy in enemy_heroes:
            profile = self._repository.get_hero_profile(enemy)
            if not profile:
                continue
            traits = sorted(
                profile.get("英雄派生特征", []),
                key=lambda value: -int(value.get("score", 0)),
            )
            trait_names = [
                value.get("trait", "")
                for value in traits
                if value.get("trait")
            ][:self._max_traits]
            candidates = self._score_candidates(
                enemy,
                player_needs,
                role,
                owned_items,
                game_time,
            )[:self._max_counters]
            counter_text = "；".join(
                f"{candidate.item_trait}可考虑{candidate.item}"
                for candidate in candidates
            )
            detail = f"特性：{'、'.join(trait_names)}"
            if counter_text:
                detail += f"。针对：{counter_text}"
            lines.append(f"- {enemy}：{detail}。")
        return "\n".join(lines) if len(lines) > 1 else ""
```

- [ ] **Step 4: Run scoring tests**

Run:

```powershell
python -m unittest tests.test_ontology_advisor.EnemyKnowledgeBuilderTests -v
```

Expected: all scoring tests `ok`.

- [ ] **Step 5: Commit scoring**

```powershell
git add src/advisor/ontology.py tests/test_ontology_advisor.py
git commit -m "feat: rank personalized enemy counters"
```

### Task 4: Add team-duty merging, tactics, stable deduplication, and size limits

**Files:**
- Modify: `src/advisor/ontology.py`
- Modify: `tests/test_ontology_advisor.py`

- [ ] **Step 1: Expand fixture data and write failing compression tests**

Add this hero to the `heroes` fixture:

```python
{
    "英雄名": "力丸",
    "内部名称": "npc_dota_hero_riki",
    "英雄派生特征": [
        {"trait": "隐身型", "score": 90},
        {"trait": "高爆发型", "score": 75},
    ],
    "物品需求": ["进攻装"],
    "被什么物品克制": ["反隐装", "视野装"],
},
```

Add this edge to `edges`:

```python
{
    "edge_id": "EDGE_3",
    "source_entity_type": "item",
    "source_name": "显影之尘",
    "source_trait": "反隐装",
    "target_entity_type": "hero",
    "target_name": "力丸",
    "target_trait": "隐身型",
    "relation": "counter",
    "strength": 85,
    "phase": ["all"],
    "source_evidence": ["显影之尘=反隐"],
    "target_evidence": ["永久隐身=隐身"],
},
```

Update `hero_profile_by_name` with `"力丸": 2` and update
`edges_by_target` with `"力丸": [2]`. Then add:

```python
def test_team_duties_are_merged_and_unknown_heroes_are_skipped(self):
    from advisor.ontology import EnemyKnowledgeBuilder

    with tempfile.TemporaryDirectory() as directory:
        repository = self.build_repository(Path(directory))
        builder = EnemyKnowledgeBuilder(repository)
        text = builder.build(
            ["幻影刺客", "力丸", "不存在"],
            "莉娜",
            "5",
            set(),
            1200,
        )

    self.assertEqual(text.count("显影之尘"), 1)
    self.assertIn("团队重点：敌方存在隐身威胁", text)
    self.assertNotIn("不存在", text)


def test_output_keeps_complete_lines_within_character_limit(self):
    from advisor.ontology import EnemyKnowledgeBuilder

    with tempfile.TemporaryDirectory() as directory:
        repository = self.build_repository(Path(directory))
        builder = EnemyKnowledgeBuilder(
            repository,
            max_context_chars=90,
        )
        text = builder.build(
            ["幻影刺客", "力丸"],
            "莉娜",
            "5",
            set(),
            1200,
        )

    self.assertLessEqual(len(text), 90)
    self.assertFalse(text.endswith("："))
    self.assertTrue(all(line.endswith(("】", "。")) for line in text.splitlines()))
```

- [ ] **Step 2: Run compression tests and verify failure**

Run:

```powershell
python -m unittest tests.test_ontology_advisor.EnemyKnowledgeBuilderTests.test_team_duties_are_merged_and_unknown_heroes_are_skipped tests.test_ontology_advisor.EnemyKnowledgeBuilderTests.test_output_keeps_complete_lines_within_character_limit -v
```

Expected: failures because duplicate/team summaries and bounded whole-line rendering are not implemented.

- [ ] **Step 3: Implement tactic summaries and bounded rendering**

Add constants:

```python
TRAIT_TACTICS = {
    "高爆发型": "保持安全距离并预留保命技能",
    "高机动型": "保留硬控，避免单独追击",
    "幻象核心型": "准备范围清理，优先识别真身",
    "隐身型": "提前铺反隐，避免无视野单走",
    "被动依赖型": "优先考虑破坏效果",
    "回复型": "尽早准备禁疗",
}
```

Replace `build()` with this deterministic implementation:

```python
def build(
    self,
    enemy_heroes: List[str],
    player_hero: str,
    role: str,
    owned_item_ids: Set[str],
    game_time: float,
) -> str:
    if not self._repository.available or not enemy_heroes:
        return ""
    player_profile = self._repository.get_hero_profile(player_hero) or {}
    player_needs = set(player_profile.get("物品需求", []))
    owned_items = self._repository.translate_item_ids(owned_item_ids)
    hero_entries = []
    best_candidates = {}
    invisible_enemies = []
    healing_enemies = []
    illusion_enemies = []

    for enemy in enemy_heroes:
        profile = self._repository.get_hero_profile(enemy)
        if not profile:
            continue
        traits = sorted(
            profile.get("英雄派生特征", []),
            key=lambda value: -int(value.get("score", 0)),
        )
        trait_names = [
            value.get("trait", "")
            for value in traits
            if value.get("trait")
        ][:self._max_traits]
        if "隐身型" in trait_names:
            invisible_enemies.append(enemy)
        if "回复型" in trait_names:
            healing_enemies.append(enemy)
        if "幻象核心型" in trait_names:
            illusion_enemies.append(enemy)
        candidates = self._score_candidates(
            enemy,
            player_needs,
            role,
            owned_items,
            game_time,
        )
        for candidate in candidates:
            key = (candidate.item, candidate.item_trait)
            current = best_candidates.get(key)
            if current is None or candidate.score > current.score:
                best_candidates[key] = candidate
        tactic = next(
            (
                self.TRAIT_TACTICS[trait]
                for trait in trait_names
                if trait in self.TRAIT_TACTICS
            ),
            "",
        )
        hero_entries.append((enemy, trait_names, tactic, candidates))

    lines = ["【敌方机制参考】"]
    if invisible_enemies:
        lines.append("团队重点：敌方存在隐身威胁，持续携带粉和真眼。")
    if healing_enemies:
        lines.append("团队重点：敌方回复能力强，尽早补充禁疗。")
    if illusion_enemies:
        lines.append(
            "团队重点：敌方依赖幻象，保留范围技能清理并识别真身。"
        )

    allowed_keys = set(best_candidates)
    rendered_items = set()
    for enemy, trait_names, tactic, candidates in hero_entries:
        counter_parts = []
        for candidate in candidates:
            key = (candidate.item, candidate.item_trait)
            if (
                key not in allowed_keys
                or candidate.item in rendered_items
                or len(counter_parts) >= self._max_counters
            ):
                continue
            rendered_items.add(candidate.item)
            counter_parts.append(
                f"{candidate.item_trait}可考虑{candidate.item}"
            )
        detail = f"特性：{'、'.join(trait_names)}"
        if tactic:
            detail += f"。打法：{tactic}"
        if counter_parts:
            detail += f"。针对：{'；'.join(counter_parts)}"
        lines.append(f"- {enemy}：{detail}。")
    return self._bounded_join(lines)
```

Use this helper for bounded output:

```python
def _bounded_join(self, lines: List[str]) -> str:
    accepted = []
    for line in lines:
        candidate = "\n".join(accepted + [line])
        if len(candidate) > self._max_chars:
            break
        accepted.append(line)
    return "\n".join(accepted) if len(accepted) > 1 else ""
```

- [ ] **Step 4: Run all ontology tests**

Run:

```powershell
python -m unittest tests.test_ontology_advisor -v
```

Expected: all tests `ok`.

- [ ] **Step 5: Commit context compression**

```powershell
git add src/advisor/ontology.py tests/test_ontology_advisor.py
git commit -m "feat: compress enemy mechanism context"
```

### Task 5: Integrate dynamic ontology context into prompts

**Files:**
- Modify: `src/advisor/prompt.py`
- Modify: `src/ai_advisor.py`
- Modify: `tests/test_advisor_refactor.py`

- [ ] **Step 1: Write failing prompt integration tests**

Add a stub and tests:

```python
class StubKnowledgeBuilder:
    def __init__(self):
        self.calls = []

    def build(
        self,
        enemy_heroes,
        player_hero,
        role,
        owned_item_ids,
        game_time,
    ):
        self.calls.append(
            (
                enemy_heroes,
                player_hero,
                role,
                owned_item_ids,
                game_time,
            )
        )
        return "【敌方机制参考】\n- 斧王：不要站桩硬拼。"


def test_prompt_injects_dynamic_enemy_knowledge_after_lineups(self):
    from advisor.extractor import StateExtractor
    from advisor.prompt import PromptBuilder

    extractor = StateExtractor()
    data = sample_data(clock_time=1200)
    extractor.accumulate_lineups(data)
    knowledge = StubKnowledgeBuilder()
    prompt = PromptBuilder(
        {"system_prompt": "SYS", "system_prompt_file": ""},
        extractor,
        knowledge_builder=knowledge,
    )
    prompt.set_role("2")

    message = prompt.build_user_message(data)

    self.assertLess(message.index("夜魇阵容"), message.index("【敌方机制参考】"))
    self.assertLess(message.index("【敌方机制参考】"), message.index("当前时间"))
    self.assertEqual(
        knowledge.calls[0],
        (["斧王"], "莉娜", "2", {"blink"}, 1200),
    )


def test_prompt_rebuilds_knowledge_when_inventory_changes(self):
    from advisor.extractor import StateExtractor
    from advisor.prompt import PromptBuilder

    extractor = StateExtractor()
    data = sample_data(clock_time=1200)
    extractor.accumulate_lineups(data)
    knowledge = StubKnowledgeBuilder()
    prompt = PromptBuilder(
        {"system_prompt": "SYS", "system_prompt_file": ""},
        extractor,
        knowledge_builder=knowledge,
    )
    prompt.build_user_message(data)
    data["items"]["slot1"] = {"name": "item_silver_edge"}
    prompt.build_user_message(data)

    self.assertEqual(len(knowledge.calls), 2)
    self.assertEqual(knowledge.calls[1][3], {"blink", "silver_edge"})
```

- [ ] **Step 2: Run prompt tests and verify failure**

Run:

```powershell
python -m unittest tests.test_advisor_refactor.AdvisorComponentTests.test_prompt_injects_dynamic_enemy_knowledge_after_lineups tests.test_advisor_refactor.AdvisorComponentTests.test_prompt_rebuilds_knowledge_when_inventory_changes -v
```

Expected: `TypeError` because `PromptBuilder` does not accept `knowledge_builder`.

- [ ] **Step 3: Inject the builder into `PromptBuilder`**

Update the constructor:

```python
def __init__(
    self,
    config: Dict[str, Any],
    extractor: StateExtractor,
    knowledge_builder=None,
):
    self._extractor = extractor
    self._knowledge_builder = knowledge_builder
    ...
```

Add:

```python
def build_ontology_section(self, data: Dict[str, Any]) -> str:
    if self._knowledge_builder is None:
        return ""
    player = data.get("player", {})
    player_hero = hero_cn_name(
        data.get("hero", {}).get(
            "name",
            player.get("hero_name", ""),
        )
    )
    text = self._knowledge_builder.build(
        enemy_heroes=self._extractor.get_enemy_lineup(
            player.get("team_name", "")
        ),
        player_hero=player_hero,
        role=self._role,
        owned_item_ids=self._extractor.extract_owned_item_ids(data),
        game_time=data.get("map", {}).get("clock_time", 0),
    )
    return f"\n{text}\n" if text else ""
```

Build the user message in this order:

```python
return (
    self.get_fixed_prefix(data)
    + self.build_ontology_section(data)
    + self.build_history_section()
    + self.build_variable_part(data, recently_killed)
    + instruction
)
```

Extend the instruction with:

```python
"敌方机制参考只作为候选依据，必须结合当前局势、你的英雄、分路和已有装备；"
"不要重复推荐已拥有装备，除非是必须由团队承担的反隐等关键义务。\n"
```

- [ ] **Step 4: Construct ontology services in `AiAdvisor`**

Add imports:

```python
from pathlib import Path
from advisor.ontology import EnemyKnowledgeBuilder, OntologyRepository
from resource_utils import resource_path
```

Before constructing `PromptBuilder`:

```python
ontology_config = config.get("ontology", {})
knowledge_builder = None
if ontology_config.get("enabled", True):
    ontology_path = ontology_config.get(
        "path",
        "./Dota2MechanismOntology",
    )
    root = (
        Path(ontology_path)
        if os.path.isabs(ontology_path)
        else Path(resource_path(ontology_path))
    )
    repository = OntologyRepository(root)
    knowledge_builder = EnemyKnowledgeBuilder(
        repository,
        min_counter_strength=ontology_config.get(
            "min_counter_strength",
            70,
        ),
        max_traits_per_hero=ontology_config.get(
            "max_traits_per_hero",
            3,
        ),
        max_counters_per_hero=ontology_config.get(
            "max_counters_per_hero",
            2,
        ),
        max_context_chars=ontology_config.get(
            "max_context_chars",
            1800,
        ),
    )
```

Pass it into:

```python
self._prompt = PromptBuilder(
    config,
    self._extractor,
    knowledge_builder=knowledge_builder,
)
```

- [ ] **Step 5: Replace brittle prompt hashes**

In the two current golden prompt tests:

- Explicitly set `"ontology": {"enabled": False}` when testing the legacy prompt shape.
- Remove SHA-256 and exact-length assertions.
- Assert stable structural markers instead:

```python
self.assertTrue(message.startswith("我玩的是莉娜"))
self.assertIn("夜魇阵容: 斧王", message)
self.assertIn("当前时间: 1分5秒", message)
self.assertIn('"item": 5-10字的出装建议', message)
```

Remove the now-unused `hashlib` import.

- [ ] **Step 6: Run prompt and advisor tests**

Run:

```powershell
python -m unittest tests.test_advisor_refactor -v
```

Expected: all tests `ok`.

- [ ] **Step 7: Commit prompt integration**

```powershell
git add src/advisor/prompt.py src/ai_advisor.py tests/test_advisor_refactor.py
git commit -m "feat: add ontology context to AI prompts"
```

### Task 6: Add configuration, packaging, and user documentation

**Files:**
- Modify: `config.yaml`
- Modify: `README.md`
- Modify: `Dota2GSI.spec`
- Modify: `build.bat`
- Modify: `tests/test_resource_paths.py`

- [ ] **Step 1: Write the failing packaging test**

Change the resource list:

```python
for resource in (
    "config.yaml",
    "AIPromt.md",
    "src/speak.ps1",
    "Dota2MechanismOntology",
):
    self.assertIn(resource, spec.replace("\\", "/"))
    self.assertIn(resource, build.replace("\\", "/"))
```

- [ ] **Step 2: Run resource tests and verify failure**

Run:

```powershell
python -m unittest tests.test_resource_paths.PyInstallerResourceTests -v
```

Expected: `FAIL` because `Dota2MechanismOntology` is absent from both build definitions.

- [ ] **Step 3: Add configuration defaults**

Under `ai_advisor` in `config.yaml`:

```yaml
  # 敌方英雄机制本体
  ontology:
    enabled: true
    path: "./Dota2MechanismOntology"
    min_counter_strength: 70
    max_traits_per_hero: 3
    max_counters_per_hero: 2
    max_context_chars: 1800
```

- [ ] **Step 4: Bundle the ontology directory**

Add to `Dota2GSI.spec` `datas`:

```python
('Dota2MechanismOntology', 'Dota2MechanismOntology'),
```

Add to the PyInstaller command in `build.bat`:

```bat
--add-data "Dota2MechanismOntology;Dota2MechanismOntology"
```

Keep the command on one line to preserve current script style.

- [ ] **Step 5: Document the feature**

Add to the README feature list:

```markdown
- 根据敌方英雄机制本体，结合玩家英雄、分路、已有装备和游戏阶段生成个性化针对建议。
```

Add these configuration rows:

```markdown
| `ai_advisor.ontology.enabled` | 是否启用敌方机制知识 | `true` |
| `ai_advisor.ontology.path` | 本体数据目录 | `./Dota2MechanismOntology` |
| `ai_advisor.ontology.min_counter_strength` | 最低克制关系强度 | `70` |
| `ai_advisor.ontology.max_traits_per_hero` | 每名敌人最多注入特性数 | `3` |
| `ai_advisor.ontology.max_counters_per_hero` | 每名敌人最多注入反制数 | `2` |
| `ai_advisor.ontology.max_context_chars` | 机制参考最大字符数 | `1800` |
```

Update the build description to state that the executable bundles `Dota2MechanismOntology`.

- [ ] **Step 6: Run resource tests**

Run:

```powershell
python -m unittest tests.test_resource_paths -v
```

Expected: all tests `ok`.

- [ ] **Step 7: Commit configuration and packaging**

```powershell
git add config.yaml README.md Dota2GSI.spec build.bat tests/test_resource_paths.py
git commit -m "build: bundle AI mechanism ontology"
```

### Task 7: Verify degradation paths and the full suite

**Files:**
- Modify: `tests/test_ontology_advisor.py`
- Modify: `tests/test_advisor_refactor.py`

- [ ] **Step 1: Add disabled and unavailable integration tests**

Add:

```python
def test_disabled_ontology_does_not_load_files(self):
    with tempfile.TemporaryDirectory() as log_dir:
        advisor = AiAdvisor(
            {
                "enabled": True,
                "system_prompt": "SYS",
                "prompt_log_dir": log_dir,
                "ontology": {
                    "enabled": False,
                    "path": "missing",
                },
            }
        )
        message = advisor._build_user_message(sample_data())

    self.assertNotIn("【敌方机制参考】", message)


def test_missing_ontology_still_builds_normal_prompt(self):
    with tempfile.TemporaryDirectory() as directory:
        errors = io.StringIO()
        with redirect_stderr(errors):
            advisor = AiAdvisor(
                {
                    "enabled": True,
                    "system_prompt": "SYS",
                    "prompt_log_dir": directory,
                    "ontology": {
                        "enabled": True,
                        "path": str(Path(directory) / "missing"),
                    },
                }
            )
            message = advisor._build_user_message(sample_data())

    self.assertIn("当前时间", message)
    self.assertNotIn("【敌方机制参考】", message)
    self.assertIn("[AI Advisor] 本体加载失败", errors.getvalue())
```

- [ ] **Step 2: Run degradation tests**

Run:

```powershell
python -m unittest tests.test_advisor_refactor.AiAdvisorGoldenTests.test_disabled_ontology_does_not_load_files tests.test_advisor_refactor.AiAdvisorGoldenTests.test_missing_ontology_still_builds_normal_prompt -v
```

Expected: both tests `ok`.

- [ ] **Step 3: Run the complete test suite**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: all tests pass with no failures or errors.

- [ ] **Step 4: Run syntax compilation**

Run:

```powershell
python -m compileall -q src tests
```

Expected: exit code `0` and no output.

- [ ] **Step 5: Inspect a real ontology prompt without calling the API**

Run:

```powershell
python -c "import sys; sys.path.insert(0, 'src'); from ai_advisor import AiAdvisor; d={'map':{'clock_time':1200},'player':{'team_name':'radiant'},'hero':{'name':'npc_dota_hero_lina'},'items':{},'abilities':{},'minimap':{'self':{'image':'minimap_herocircle_self','team':2,'name':'npc_dota_hero_lina'},'enemy':{'image':'minimap_enemyicon','team':3,'name':'npc_dota_hero_phantom_assassin'}}}; a=AiAdvisor({'enabled':False,'system_prompt':'SYS','system_prompt_file':'','ontology':{'enabled':True,'path':'./Dota2MechanismOntology','max_context_chars':1800}}); a.set_role('2'); a._accumulate_lineups(d); m=a._build_user_message(d); s=m.index('【敌方机制参考】'); e=m.index('当前时间'); print(m[s:e].strip())"
```

Expected:

- The section contains the enemy hero.
- It contains no already-owned item.
- Its length is at most `max_context_chars`.
- It contains no raw JSON or Python representation.

- [ ] **Step 6: Review the diff for scope and user changes**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Expected:

- No whitespace errors.
- No unrelated source files changed.
- `Dota2MechanismOntology/` remains user-provided data; do not rewrite its JSON files.
- Previously staged user edits in `tests/test_advisor_refactor.py` remain represented in the final content.

- [ ] **Step 7: Commit final degradation coverage**

```powershell
git add tests/test_ontology_advisor.py tests/test_advisor_refactor.py
git commit -m "test: cover ontology advisor degradation"
```

