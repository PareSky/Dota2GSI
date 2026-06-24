"""AI 教练提示词状态与文本构建。"""

import os
import sys
from typing import Any, Dict, List, Optional

from advisor.extractor import StateExtractor
from advisor.ontology import EnemyKnowledgeBuilder
from resource_utils import resource_path
from tts import hero_cn_name


class PromptBuilder:
    def __init__(
        self,
        config: Dict[str, Any],
        extractor: StateExtractor,
        knowledge_builder: Optional[EnemyKnowledgeBuilder] = None,
    ):
        self._extractor = extractor
        self._knowledge_builder = knowledge_builder
        self.system_prompt = self._load_system_prompt(config)
        self._fixed_prefix: Optional[str] = None
        self._advice_history: List[tuple] = []
        self.last_analysis: Optional[str] = None
        self._role = ""

    @staticmethod
    def _load_system_prompt(config: Dict[str, Any]) -> str:
        system_prompt_file = config.get("system_prompt_file", "")
        if system_prompt_file:
            if not os.path.isabs(system_prompt_file):
                system_prompt_file = resource_path(system_prompt_file)
            if os.path.exists(system_prompt_file):
                with open(system_prompt_file, "r", encoding="utf-8") as file:
                    return file.read()
            print(
                f"[AI Advisor] 提示词文件不存在: {system_prompt_file}，"
                "使用内置提示词",
                file=sys.stderr,
            )
        return config.get(
            "system_prompt",
            "你是一个专业的 Dota 2 教练。直接给出建议，不要解释。",
        )

    @property
    def advice_history(self) -> List[tuple]:
        return self._advice_history

    def set_role(self, role: str) -> None:
        self._role = role
        print(f"  [AI Advisor] 玩家分路已设置: {role}")

    def reset(self) -> None:
        self._fixed_prefix = None
        self._advice_history = []
        self.last_analysis = None
        self._role = ""

    def record_advice(
        self,
        game_time: float,
        advice: str,
        analysis: str,
    ) -> None:
        self._advice_history.append((game_time, advice))
        self.last_analysis = analysis

    def get_fixed_prefix(self, data: Dict[str, Any]) -> str:
        lineups = self._extractor.team_lineups
        lineups_complete = sum(map(len, lineups.values())) >= 10
        if self._fixed_prefix is not None and lineups_complete:
            return self._fixed_prefix

        hero = data.get("hero", {})
        player = data.get("player", {})
        hero_name = hero_cn_name(
            hero.get("name", player.get("hero_name", ""))
        )
        team_cn = (
            "天辉" if player.get("team_name", "") == "radiant" else "夜魇"
        )
        radiant = lineups.get("radiant", []) or ["未知"]
        dire = lineups.get("dire", []) or ["未知"]
        role_map = {
            "1": "1号位(大哥)",
            "2": "2号位(中单)",
            "3": "3号位(劣势路)",
            "4": "4号位(劣势路辅助)",
            "5": "5号位(优势路辅助)",
        }
        role_str = role_map.get(self._role, "")
        prefix = (
            f"我玩的是{hero_name}，我在{team_cn}，我的分路是{role_str}。\n"
            f"天辉阵容: {', '.join(radiant)}\n"
            f"夜魇阵容: {', '.join(dire)}"
        )
        if lineups_complete:
            self._fixed_prefix = prefix
        return prefix

    def build_variable_part(
        self,
        data: Dict[str, Any],
        recently_killed: Optional[Dict[int, List[str]]] = None,
    ) -> str:
        map_info = data.get("map", {})
        clock_time = map_info.get("clock_time", 0)
        mins = int(clock_time // 60)
        secs = int(clock_time % 60)
        player_state = self._extractor.build_player_state(data)
        hero_positions = self._extractor.extract_hero_positions(
            data,
            recently_killed,
        )
        ward_info = self._extractor.extract_ward_info(data)
        last_analysis_part = ""
        if self.last_analysis:
            last_analysis_part = (
                f"\n上一次战略分析: {self.last_analysis}"
            )
        return (
            f"\n"
            f"当前时间: {mins}分{secs}秒\n"
            f"比分: 天辉 {map_info.get('radiant_score', 0)} - "
            f"{map_info.get('dire_score', 0)} 夜魇\n"
            f"\n"
            f"英雄位置:\n"
            f"{hero_positions}\n"
            f"\n"
            f"视野守卫:\n"
            f"{ward_info}\n"
            f"\n"
            f"我的英雄状态:\n"
            f"{player_state}"
            f"{last_analysis_part}"
        )

    def build_user_message(
        self,
        data: Dict[str, Any],
        recently_killed: Optional[Dict[int, List[str]]] = None,
    ) -> str:
        knowledge = ""
        if self._knowledge_builder is not None:
            player = data.get("player", {})
            hero = data.get("hero", {})
            knowledge = self._knowledge_builder.build(
                enemy_heroes=self._extractor.get_enemy_lineup(
                    player.get("team_name", "")
                ),
                player_hero=hero_cn_name(
                    hero.get("name", player.get("hero_name", ""))
                ),
                role=self._role,
                owned_item_ids=self._extractor.extract_owned_item_ids(data),
                game_time=data.get("map", {}).get("clock_time", 0),
            )
            if knowledge:
                knowledge = f"\n{knowledge}\n"
        instruction = (
            "\n\n请根据以上所有信息，输出一个JSON对象，包含三个字段：\n"
            '1. "analysis": 80-150字的战略局势分析（阵容优劣势/克制关系/当前阶段/应该采取的策略方向）\n'
            '2. "command": 1条15-30字的极简战术指令，不要与上一条战术指令重复\n'
            '3. "item": 5-10字的出装建议（针对对方关键英雄的克制装备或补全阵容短板）\n'
            "机制参考仅是候选，需结合局势、英雄、分路和已有装备，"
            "不要重复推荐已购装备。\n"
            "只输出JSON本身，不要添加```json标记或任何其他文字。\n"
            "确保JSON合法可解析，analysis、command和item内的文本不要包含未转义的双引号。"
        )
        return (
            self.get_fixed_prefix(data)
            + knowledge
            + self.build_history_section()
            + self.build_variable_part(data, recently_killed)
            + instruction
        )

    def build_history_section(self) -> str:
        if not self._advice_history:
            return ""
        lines = ["\n之前的建议:"]
        for game_time, advice in self._advice_history:
            mins = int(game_time // 60)
            secs = int(game_time % 60)
            lines.append(f"- ({mins}分{secs}秒) {advice}")
        return "\n".join(lines) + "\n"
