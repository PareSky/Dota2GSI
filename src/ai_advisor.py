"""AI 游戏教练门面。

外部继续通过 AiAdvisor.update/reset/set_role 使用功能，内部职责由
advisor 包中的触发器、提取器、提示词、API 客户端和日志器承担。
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from advisor.client import AdvisorClient
from advisor.extractor import StateExtractor
from advisor.logging import AdvisorLogger
from advisor.ontology import EnemyKnowledgeBuilder, OntologyRepository
from advisor.prompt import PromptBuilder
from advisor.trigger import TriggerController
from resource_utils import editable_resource_path


@dataclass
class AdvisorEvent:
    advice_text: str
    analysis_text: str
    fight_text: str
    item_text: str
    game_time: float
    timestamp: str
    speech_level: str = "brief"

    def __str__(self) -> str:
        return (
            f"AI教练[分析]: {self.analysis_text}\n"
            f"AI教练[指令]: {self.advice_text}\n"
            f"AI教练[团战]: {self.fight_text}\n"
            f"AI教练[出装]: {self.item_text}"
        )


class AiAdvisor:
    """定期向 AI 发送游戏状态并返回教练建议。"""

    def __init__(self, config: Dict[str, Any]):
        self._enabled = config.get("enabled", False)
        interval_minutes = config.get("interval_minutes", 5)
        log_dir = config.get("prompt_log_dir", "./logs")

        self._extractor = StateExtractor()
        ontology_config = config.get("ontology", {})
        knowledge_builder = None
        if ontology_config.get("enabled", True):
            ontology_path = ontology_config.get(
                "path",
                "./Dota2MechanismOntology",
            )
            if not os.path.isabs(ontology_path):
                ontology_path = editable_resource_path(ontology_path)
            repository = OntologyRepository(ontology_path)
            knowledge_builder = EnemyKnowledgeBuilder(
                repository=repository,
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
        self._prompt = PromptBuilder(
            config,
            self._extractor,
            knowledge_builder,
        )
        self._trigger = TriggerController(interval_minutes, self._extractor)
        self._client = AdvisorClient(
            api_key=config.get("api_key", "")
            or os.environ.get("DeepSeekApiKey", ""),
            base_url=config.get("base_url", "https://api.deepseek.com"),
            model=config.get("model", "deepseek-v4-pro"),
            max_tokens=config.get("max_tokens", 60),
            temperature=config.get("temperature", 0.7),
            extra_body=config.get("extra_body", {}),
            timeout_seconds=config.get("timeout_seconds", 30),
        )
        self._logger = AdvisorLogger(log_dir)

        # 保留原字段，兼容已有调试代码。
        self._interval_minutes = interval_minutes
        self._system_prompt = self._prompt.system_prompt

    def update(self, data: Dict[str, Any]) -> List[AdvisorEvent]:
        if not self._enabled:
            return []

        clock_time = data.get("map", {}).get("clock_time", -1)
        if clock_time < 0:
            return []

        self._extractor.accumulate_lineups(data)
        self._extractor.update_hero_visibility(data)
        decision = self._trigger.evaluate(data)
        if not decision.should_query:
            return []

        user_message = self._prompt.build_user_message(
            data,
            decision.recently_killed or None,
        )
        self._log_prompt(user_message)
        result = self._call_api(user_message)
        self._trigger.complete(data, succeeded=result is not None)
        if result is None:
            return []

        analysis, command, fight, item, speech_level = result
        self._prompt.record_advice(clock_time, command, analysis)
        self._log_advice(command, clock_time, analysis)
        return [
            AdvisorEvent(
                advice_text=command,
                analysis_text=analysis,
                fight_text=fight,
                item_text=item,
                game_time=clock_time,
                timestamp=datetime.now().isoformat(timespec="seconds"),
                speech_level=speech_level,
            )
        ]

    def set_role(self, role: str) -> None:
        self._prompt.set_role(role)

    def reset(self) -> None:
        self._trigger.reset()
        self._extractor.reset()
        self._prompt.reset()
        self._client.reset_session()
        self._logger.reset()

    # 以下委托方法保留现有内部调试/测试入口，不承载业务实现。

    @property
    def _last_bucket(self) -> int:
        return self._trigger.last_bucket

    @_last_bucket.setter
    def _last_bucket(self, value: int) -> None:
        self._trigger.last_bucket = value

    def _accumulate_lineups(self, data: Dict[str, Any]) -> None:
        self._extractor.accumulate_lineups(data)

    def _build_user_message(self, data: Dict[str, Any]) -> str:
        return self._prompt.build_user_message(data)

    def _build_history_section(self) -> str:
        return self._prompt.build_history_section()

    def _log_prompt(self, user_message: str) -> None:
        self._logger.log_prompt(
            user_message=user_message,
            system_prompt=self._prompt.system_prompt,
            game_time_minutes=int(
                self._trigger.last_bucket * self._interval_minutes
            ),
            history_section=self._prompt.build_history_section(),
        )

    def _log_advice(
        self,
        advice: str,
        game_time: float,
        analysis: str = "",
    ) -> None:
        self._logger.log_advice(advice, game_time, analysis)

    def _call_api(
        self,
        user_message: str,
    ) -> Optional[tuple[str, str, str, str, str]]:
        return self._client.complete(
            self._prompt.system_prompt,
            user_message,
        )
