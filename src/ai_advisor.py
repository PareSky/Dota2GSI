"""
AI 游戏教练模块
- 每 N 分钟（默认 1 分钟）收集游戏状态数据
- 发送到 DeepSeek API 获取教练建议
- 控制台打印 + TTS 语音播报

缓存优化：
- System prompt 从 AIPromt.md 加载，每次调用完全相同 → API 缓存命中
- User message 分两部分：固定前缀（英雄/阵容，一局不变）+ 可变数据（时间/装备/状态，放末尾）
- 固定前缀计算一次后缓存，后续调用复用
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from resource_utils import resource_path
from tts import hero_cn_name


@dataclass
class AdvisorEvent:
    """AI 教练建议事件"""
    advice_text: str       # 战术指令（用于 TTS 语音朗读）
    analysis_text: str     # 战略分析（仅控制台打印）
    game_time: float
    timestamp: str

    def __str__(self) -> str:
        return f"AI教练[分析]: {self.analysis_text}\nAI教练[指令]: {self.advice_text}"


class AiAdvisor:
    """定期向 AI 发送游戏状态，获取教练建议"""

    # 需要提取的物品槽位
    ITEM_SLOTS = ["slot0", "slot1", "slot2", "slot3", "slot4", "slot5",
                   "neutral0", "teleport0"]

    # 需要提取的技能槽位
    ABILITY_SLOTS = ["ability0", "ability1", "ability2", "ability3"]

    # 塔名映射：GSI buildings 内部名 → 中文简称
    TOWER_NAME_MAP: Dict[str, str] = {
        # 天辉（Radiant / goodguys）
        "dota_goodguys_tower1_top": "上一塔",
        "dota_goodguys_tower2_top": "上二塔",
        "dota_goodguys_tower3_top": "上三塔",
        "dota_goodguys_tower1_mid": "中一塔",
        "dota_goodguys_tower2_mid": "中二塔",
        "dota_goodguys_tower3_mid": "中三塔",
        "dota_goodguys_tower1_bot": "下一塔",
        "dota_goodguys_tower2_bot": "下二塔",
        "dota_goodguys_tower3_bot": "下三塔",
        "dota_goodguys_tower4": "基地塔",
        # 夜魇（Dire / badguys）
        "dota_badguys_tower1_top": "上一塔",
        "dota_badguys_tower2_top": "上二塔",
        "dota_badguys_tower3_top": "上三塔",
        "dota_badguys_tower1_mid": "中一塔",
        "dota_badguys_tower2_mid": "中二塔",
        "dota_badguys_tower3_mid": "中三塔",
        "dota_badguys_tower1_bot": "下一塔",
        "dota_badguys_tower2_bot": "下二塔",
        "dota_badguys_tower3_bot": "下三塔",
        "dota_badguys_tower4": "基地塔",
    }

    # 塔排序键（按路、层级排列，与 TOWER_NAME_MAP 的值对应）
    _TOWER_ORDER = [
        "上一塔", "上二塔", "上三塔",
        "中一塔", "中二塔", "中三塔",
        "下一塔", "下二塔", "下三塔",
        "基地塔",
    ]

    # 地标坐标（来自 LANDMARKS.md，地图中心为 0,0）
    # 格式: (名称, x, y, 阵营)
    LANDMARKS: List[tuple] = [
        # === 夜魇（Dire，右上）===
        ("夜魇上路一塔", -5274, 6036, "dire"),
        ("夜魇上路二塔", -128, 6016, "dire"),
        ("夜魇上路三塔", 3552, 5776, "dire"),
        ("夜魇上路高地塔", 4944, 4776, "dire"),
        ("夜魇中路一塔", 524, 652, "dire"),
        ("夜魇中路二塔", 2496, 2112, "dire"),
        ("夜魇中路三塔", 4272, 3759, "dire"),
        ("夜魇中路高地塔", 5280, 4432, "dire"),
        ("夜魇下路一塔", 6269, -2240, "dire"),
        ("夜魇下路二塔", 6400, 384, "dire"),
        ("夜魇下路三塔", 6336, 3032, "dire"),
        ("夜魇下路高地塔", 6326, 3798, "dire"),
        ("夜魇远古遗迹", 5528, 5000, "dire"),
        # === 天辉（Radiant，左下）===
        ("天辉上路一塔", -6336, 1856, "radiant"),
        ("天辉上路二塔", -6501, -872, "radiant"),
        ("天辉上路三塔", -6592, -3408, "radiant"),
        ("天辉上路高地塔", -5712, -4864, "radiant"),
        ("天辉中路一塔", -1544, -1408, "radiant"),
        ("天辉中路二塔", -3190, -2926, "radiant"),
        ("天辉中路三塔", -4640, -4144, "radiant"),
        ("天辉中路高地塔", -5392, -5192, "radiant"),
        ("天辉下路一塔", 4859, -6379, "radiant"),
        ("天辉下路二塔", -360, -6256, "radiant"),
        ("天辉下路三塔", -3952, -6112, "radiant"),
        ("天辉下路高地塔", -4279, -5853, "radiant"),
        ("天辉远古遗迹", -5920, -5352, "radiant"),
        # === 野外 ===
        ("夜魇神秘商店", 4886, -1207, "dire"),
        ("天辉神秘商店", -5080, 1947, "radiant"),
        # ("夜魇莲花池", 7503, -4404, "dire"),
        # ("天辉莲花池", -7548, 4209, "radiant"),
        ("上路传送门", -6457, 7599, None),
        ("下路传送门", 6425, -7313, None),
        # === 肉山 ===
        ("肉山巢穴(左上)", -3190, 2112, None),
        ("肉山巢穴(右下)", 2496, -2926, None),
    ]

    def __init__(self, config: Dict[str, Any]):
        self._enabled: bool = config.get("enabled", False)
        self._api_key: str = config.get("api_key", "") or os.environ.get("DeepSeekApiKey", "")
        self._base_url: str = config.get("base_url", "https://api.deepseek.com")
        self._model: str = config.get("model", "deepseek-chat")
        self._interval_minutes: int = config.get("interval_minutes", 5)
        self._max_tokens: int = config.get("max_tokens", 60)
        self._temperature: float = config.get("temperature", 0.7)
        self._prompt_log_dir: str = config.get("prompt_log_dir", "./logs")

        # System prompt：优先从文件加载，否则用 config 中的 inline 文本
        system_prompt_file = config.get("system_prompt_file", "")
        if system_prompt_file:
            # 相对路径统一相对于源码项目根目录或 PyInstaller 解压目录
            if not os.path.isabs(system_prompt_file):
                system_prompt_file = resource_path(system_prompt_file)
            if os.path.exists(system_prompt_file):
                with open(system_prompt_file, "r", encoding="utf-8") as f:
                    self._system_prompt: str = f.read()
            else:
                print(f"[AI Advisor] 提示词文件不存在: {system_prompt_file}，使用内置提示词",
                      file=sys.stderr)
                self._system_prompt: str = config.get(
                    "system_prompt",
                    "你是一个专业的 Dota 2 教练。直接给出建议，不要解释。",
                )
        else:
            self._system_prompt: str = config.get(
                "system_prompt",
                "你是一个专业的 Dota 2 教练。直接给出建议，不要解释。",
            )

        # 内部状态
        self._client = None          # openai 客户端（延迟初始化）
        self._last_bucket: int = -1  # 上次触发的时间桶
        self._team_lineups: Dict[str, List[str]] = {"radiant": [], "dire": []}  # 双方阵容（跨帧累积）
        self._lineups_seen: set = set()  # 已见过的英雄 internal name（去重）
        self._warned_no_key: bool = False  # 只警告一次 API Key 缺失
        self._prompt_log_path: Optional[str] = None  # 提示词日志文件路径
        self._advice_log_path: Optional[str] = None   # AI 建议日志文件路径（只保留最新一条）
        self._fixed_prefix: Optional[str] = None  # 用户消息固定前缀（一局缓存）
        self._advice_history: List[tuple] = []  # 本局 AI 建议历史 [(game_time, text), ...]
        self._last_analysis: Optional[str] = None  # 上一次的战略分析（供 AI 参考，避免重复）
        self._role: str = ""  # 玩家分路（1-5号位），新游戏开始时由弹窗设置
        self._last_scores: tuple = (-1, -1)  # 上一帧 (radiant_score, dire_score)
        self._score_change_time: float = -1  # 最近比分变化时的游戏时间，-1=无待处理
        self._last_query_time: float = -1    # 上次 AI 查询的游戏时间，用于 20s 全局冷却
        self._last_frame_heroes: Dict[int, set] = {}  # 上帧 minimap 可见英雄（team→name集合）
        self._recently_killed: Dict[int, List[str]] = {}  # 比分变化时刚死的英雄（team→中文名列表）

        os.makedirs(self._prompt_log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def update(self, data: Dict[str, Any]) -> List[AdvisorEvent]:
        """
        根据当前游戏状态，决定是否查询 AI 教练。
        触发条件：定时（每 N 分钟）或比分变化（延迟 5 秒）。
        所有触发共享 20 秒全局冷却。
        返回 AdvisorEvent 列表（0 或 1 个）。
        """
        if not self._enabled:
            return []

        clock_time = data.get("map", {}).get("clock_time", -1)
        if clock_time < 0:
            return []

        # 跳过游戏刚开始的 60 秒（阵容和状态都还不完整）
        if clock_time < 60:
            return []

        map_info = data.get("map", {})
        radiant_score = map_info.get("radiant_score", 0)
        dire_score = map_info.get("dire_score", 0)
        current_scores = (radiant_score, dire_score)

        # --- 检测比分变化 ---
        if self._last_scores != (-1, -1) and current_scores != self._last_scores:
            # 比分变化瞬间：对比上帧英雄 vs 当前英雄，消失的视为刚死
            current_heroes = self._extract_hero_names(data)
            for team in (2, 3):
                disappeared = self._last_frame_heroes.get(team, set()) - current_heroes.get(team, set())
                for hname in disappeared:
                    cn = hero_cn_name(hname)
                    if cn not in self._recently_killed.get(team, []):
                        self._recently_killed.setdefault(team, []).append(cn)
            if self._score_change_time > 0:
                print(f"  [AI Advisor] 比分再次变化 {self._last_scores} → {current_scores}，"
                      f"重新计时 5 秒")
            else:
                killed_list = []
                for names in self._recently_killed.values():
                    killed_list.extend(names)
                print(f"  [AI Advisor] 比分变化 {self._last_scores} → {current_scores}，"
                      f"检测到死亡: {killed_list if killed_list else '未能识别'}，5 秒后查询 AI")
            self._score_change_time = clock_time
        self._last_scores = current_scores

        # --- 判断触发条件 ---
        COOLDOWN = 20  # 全局冷却（秒）

        # 定时触发：时间桶变化
        interval_seconds = self._interval_minutes * 60
        adjusted_time = clock_time - 5
        current_bucket = int(adjusted_time / interval_seconds) if adjusted_time >= 0 else -1
        timer_trigger = (current_bucket >= 1 and current_bucket > self._last_bucket)

        # 比分触发：比分变化后已过 5 秒
        score_trigger = (
            self._score_change_time > 0
            and (clock_time - self._score_change_time) >= 5
        )

        # 均不触发 → 返回（打印首次提示）
        if not timer_trigger and not score_trigger:
            if self._last_bucket == -1 and current_bucket == 1 and clock_time > interval_seconds - 60:
                print(f"  [AI Advisor] 将在 {interval_seconds//60} 分钟后首次查询 AI...")
            self._last_frame_heroes = self._extract_hero_names(data)
            return []

        # --- 全局冷却检查 ---
        if self._last_query_time > 0 and (clock_time - self._last_query_time) < COOLDOWN:
            remaining = COOLDOWN - (clock_time - self._last_query_time)
            if score_trigger:
                self._score_change_time = -1  # 清除待处理，避免下一帧重复提示
                self._recently_killed = {}     # 同时清除死亡记录
                print(f"  [AI Advisor] 比分触发但冷却中（剩余 {remaining:.0f}s），跳过")
            if timer_trigger:
                self._last_bucket = current_bucket  # 推进桶，避免每帧重试
            self._last_frame_heroes = self._extract_hero_names(data)
            return []

        # --- 执行查询 ---
        if timer_trigger:
            self._last_bucket = current_bucket
        # 比分触发不清除 _last_bucket，不影响定时节奏

        # 清除比分变化状态
        self._score_change_time = -1

        # 跨帧累积双方阵容（直到凑齐 10 个英雄）
        self._accumulate_lineups(data)

        # 构建用户消息（固定前缀 + 可变数据）
        user_message = self._build_user_message(data)

        # 死亡记录已消费，清除
        self._recently_killed = {}

        # 打印提示词到控制台 + 写入日志
        self._log_prompt(user_message)

        # 调用 API
        result = self._call_api(user_message)
        if result is None:
            self._last_frame_heroes = self._extract_hero_names(data)
            return []

        analysis, command = result

        # 记录状态
        self._last_query_time = clock_time
        self._advice_history.append((clock_time, command))
        self._last_analysis = analysis

        # 写入建议日志（记录完整信息）
        self._log_advice(command, clock_time, analysis)

        now_ts = datetime.now().isoformat(timespec="seconds")
        self._last_frame_heroes = self._extract_hero_names(data)
        return [AdvisorEvent(
            advice_text=command,
            analysis_text=analysis,
            game_time=clock_time,
            timestamp=now_ts,
        )]

    def set_role(self, role: str) -> None:
        """设置玩家分路（由外部在新游戏开始时调用）"""
        self._role = role
        print(f"  [AI Advisor] 玩家分路已设置: {role}")

    def reset(self) -> None:
        """新游戏开始时重置状态"""
        self._last_bucket = -1
        self._team_lineups = {"radiant": [], "dire": []}
        self._lineups_seen = set()
        self._warned_no_key = False
        self._prompt_log_path = None
        self._advice_log_path = None
        self._fixed_prefix = None
        self._advice_history = []
        self._last_analysis = None
        self._role = ""
        self._last_scores = (-1, -1)
        self._score_change_time = -1
        self._last_query_time = -1
        self._last_frame_heroes = {}
        self._recently_killed = {}

    # ------------------------------------------------------------------
    # 阵容提取（跨帧累积）
    # ------------------------------------------------------------------

    def _accumulate_lineups(self, data: Dict[str, Any]) -> None:
        """
        跨帧累积双方英雄阵容。
        每帧从 minimap 中提取英雄，去重后加入对应阵营。
        直到凑齐 10 个英雄为止。
        """
        # 已经凑齐 10 个，不再累积
        if len(self._team_lineups["radiant"]) + len(self._team_lineups["dire"]) >= 10:
            return

        minimap_data = data.get("minimap", {})
        if not minimap_data:
            return

        for obj in minimap_data.values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue

            team = obj.get("team")
            if team is None:
                continue

            hero_name = obj.get("name") or obj.get("unitname", "")
            if not hero_name or not hero_name.startswith("npc_dota_hero_"):
                continue

            # 用 (team, hero_name) 作为去重 key
            key = (team, hero_name)
            if key in self._lineups_seen:
                continue
            self._lineups_seen.add(key)

            cn = hero_cn_name(hero_name)
            if team == 2:
                self._team_lineups["radiant"].append(cn)
            elif team == 3:
                self._team_lineups["dire"].append(cn)

        total = len(self._team_lineups["radiant"]) + len(self._team_lineups["dire"])
        if total >= 10:
            print(f"  [AI Advisor] 阵容收集完成: "
                  f"天辉={self._team_lineups['radiant']}, "
                  f"夜魇={self._team_lineups['dire']}")

    # ------------------------------------------------------------------
    # 英雄位置分析
    # ------------------------------------------------------------------

    @classmethod
    def _nearest_landmark(cls, xpos: float, ypos: float) -> str:
        """找到距离 (xpos, ypos) 最近的地标，返回地标名称"""
        best = None
        best_dist = float("inf")
        for name, lx, ly, _team in cls.LANDMARKS:
            dx = xpos - lx
            dy = ypos - ly
            dist = dx * dx + dy * dy  # 平方距离，避免 sqrt
            if dist < best_dist:
                best_dist = dist
                best = name
        return best or "未知位置"

    @staticmethod
    def _extract_hero_names(data: Dict[str, Any]) -> Dict[int, set]:
        """从 minimap 提取可见英雄名，按队伍分组（team 2=天辉, 3=夜魇）。
        每帧调用，轻量级，不含地标匹配。"""
        result: Dict[int, set] = {2: set(), 3: set()}
        minimap = data.get("minimap", {})
        for obj in minimap.values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue
            team = obj.get("team")
            if team not in (2, 3):
                continue
            name = obj.get("name") or obj.get("unitname", "")
            if name and name.startswith("npc_dota_hero_"):
                result[team].add(name)
        return result

    def _extract_hero_positions(self, data: Dict[str, Any],
                                 recently_killed: Optional[Dict[int, List[str]]] = None) -> str:
        """从 minimap 提取所有英雄当前位置，返回描述文本。

        recently_killed: 比分变化瞬间识别出的死亡英雄 {team: [中文名, ...]}
        在比分变化时已计算好，不依赖 5 秒后的 minimap 状态。"""
        minimap_data = data.get("minimap", {})
        player_team_name = data.get("player", {}).get("team_name", "")
        player_is_radiant = player_team_name == "radiant"
        hero = data.get("hero", {})
        player_hero_name = hero.get("name", "")

        radiant_heroes: List[str] = []
        dire_heroes: List[str] = []
        seen: set = set()

        for obj in minimap_data.values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue

            team = obj.get("team")
            if team is None:
                continue

            hero_name = obj.get("name") or obj.get("unitname", "")
            if not hero_name or not hero_name.startswith("npc_dota_hero_"):
                continue

            if hero_name in seen:
                continue
            seen.add(hero_name)

            xpos = obj.get("xpos", 0)
            ypos = obj.get("ypos", 0)
            cn = hero_cn_name(hero_name)
            landmark = AiAdvisor._nearest_landmark(xpos, ypos)

            # 标记自己
            is_self = (hero_name == player_hero_name)
            marker = "【我】" if is_self else ""

            line = f"{marker}{cn}({xpos},{ypos})→{landmark}"
            if team == 2:
                radiant_heroes.append(line)
            elif team == 3:
                dire_heroes.append(line)

        # 构建注释行（recently_killed 在比分变化瞬间已计算好，直接使用）
        notes: List[str] = []
        if recently_killed:
            dead_radiant = recently_killed.get(2, [])
            dead_dire = recently_killed.get(3, [])
            if dead_radiant:
                notes.append(f"刚死亡(天辉): {', '.join(dead_radiant)}")
            if dead_dire:
                notes.append(f"刚死亡(夜魇): {', '.join(dead_dire)}")
        else:
            notes.append("(未列出的英雄可能不在视野内，不一定已死亡)")

        if player_is_radiant:
            parts = [
                f"天辉({len(radiant_heroes)}人): {', '.join(radiant_heroes) if radiant_heroes else '未知'}",
                f"夜魇({len(dire_heroes)}人): {', '.join(dire_heroes) if dire_heroes else '未知'}",
            ] + notes
        else:
            parts = [
                f"夜魇({len(dire_heroes)}人): {', '.join(dire_heroes) if dire_heroes else '未知'}",
                f"天辉({len(radiant_heroes)}人): {', '.join(radiant_heroes) if radiant_heroes else '未知'}",
            ] + notes

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 视野守卫提取
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_ward_info(data: Dict[str, Any]) -> str:
        """从 minimap 提取双方视野守卫（假眼=obs, 真眼=invis），返回描述文本"""
        minimap_data = data.get("minimap", {})
        radiant_obs: List[str] = []
        radiant_sen: List[str] = []
        dire_obs: List[str] = []
        dire_sen: List[str] = []

        for obj in minimap_data.values():
            unitname = obj.get("unitname", "")
            team = obj.get("team")
            xpos = obj.get("xpos", 0)
            ypos = obj.get("ypos", 0)
            landmark = AiAdvisor._nearest_landmark(xpos, ypos)

            if unitname == "npc_dota_observer_wards":
                entry = f"({xpos},{ypos})→{landmark}"
                if team == 2:
                    radiant_obs.append(entry)
                elif team == 3:
                    dire_obs.append(entry)
            elif unitname == "npc_dota_sentry_wards":
                entry = f"({xpos},{ypos})→{landmark}"
                if team == 2:
                    radiant_sen.append(entry)
                elif team == 3:
                    dire_sen.append(entry)

        parts: List[str] = []
        if radiant_obs or radiant_sen:
            obs_str = f"假眼({len(radiant_obs)}): {', '.join(radiant_obs)}" if radiant_obs else "假眼: 无"
            sen_str = f"真眼({len(radiant_sen)}): {', '.join(radiant_sen)}" if radiant_sen else "真眼: 无"
            parts.append(f"天辉视野: {obs_str}; {sen_str}")
        else:
            parts.append("天辉视野: 未发现")

        if dire_obs or dire_sen:
            obs_str = f"假眼({len(dire_obs)}): {', '.join(dire_obs)}" if dire_obs else "假眼: 无"
            sen_str = f"真眼({len(dire_sen)}): {', '.join(dire_sen)}" if dire_sen else "真眼: 无"
            parts.append(f"夜魇视野: {obs_str}; {sen_str}")
        else:
            parts.append("夜魇视野: 未发现")

        parts.append("(仅统计视野内可见的守卫)")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 玩家状态提取
    # ------------------------------------------------------------------

    @staticmethod
    def _build_player_state(data: Dict[str, Any]) -> str:
        """从 GSI 数据中提取玩家英雄的详细状态（可变部分）"""
        hero = data.get("hero", {})
        player = data.get("player", {})

        level = hero.get("level", 0)
        health_pct = hero.get("health_percent", 0)
        mana_pct = hero.get("mana_percent", 0)
        kills = player.get("kills", 0)
        deaths = player.get("deaths", 0)
        assists = player.get("assists", 0)
        last_hits = player.get("last_hits", 0)
        denies = player.get("denies", 0)
        gpm = player.get("gpm", 0)
        xpm = player.get("xpm", 0)
        gold = player.get("gold", 0)

        # 装备 + 冷却时间
        items_data = data.get("items", {})
        item_names: List[str] = []
        for slot_key in AiAdvisor.ITEM_SLOTS:
            slot = items_data.get(slot_key, {})
            name = slot.get("name", "")
            if name and name != "empty":
                short_name = name.replace("item_", "")
                cd = slot.get("cooldown", 0) or 0
                if cd > 0:
                    short_name += f"(cd:{cd:.0f}s)"
                item_names.append(short_name)

        # 技能等级 + 冷却时间
        abilities_data = data.get("abilities", {})
        skill_levels: List[str] = []
        for ab_key in AiAdvisor.ABILITY_SLOTS:
            ab = abilities_data.get(ab_key, {})
            lv = ab.get("level", 0)
            name = ab.get("name", "")
            cd = ab.get("cooldown", 0) or 0
            if name:
                short = name.split(".")[-1] if "." in name else name
                parts = short.split("_", 1)
                short = parts[1] if len(parts) > 1 else short
                cd_str = f"(cd:{cd:.0f}s)" if cd > 0 else ""
                skill_levels.append(f"{short}:lv{lv}{cd_str}")
            else:
                cd_str = f"(cd:{cd:.0f}s)" if cd > 0 else ""
                skill_levels.append(f"技能{ab_key[-1]}:lv{lv}{cd_str}")

        # 建筑状态（从 minimap 识别具体存活塔，unitname 如 npc_dota_badguys_tower2_mid）
        minimap = data.get("minimap", {})
        radiant_alive: List[str] = []
        dire_alive: List[str] = []

        for obj in minimap.values():
            if "tower" not in obj.get("image", ""):
                continue
            team = obj.get("team")
            unitname = obj.get("unitname", "") or obj.get("name", "")
            if not unitname:
                continue

            # 去掉 npc_ 前缀以匹配 TOWER_NAME_MAP
            # 例如 npc_dota_goodguys_tower2_mid → dota_goodguys_tower2_mid
            lookup_key = unitname
            if unitname.startswith("npc_"):
                lookup_key = unitname[len("npc_"):]

            cn_name = AiAdvisor.TOWER_NAME_MAP.get(lookup_key)
            if not cn_name:
                continue

            if team == 2 and cn_name not in radiant_alive:
                radiant_alive.append(cn_name)
            elif team == 3 and cn_name not in dire_alive:
                dire_alive.append(cn_name)

        # 按路/层级排序
        def _tower_sort(name: str) -> int:
            try:
                return AiAdvisor._TOWER_ORDER.index(name)
            except ValueError:
                return 99

        radiant_alive.sort(key=_tower_sort)
        dire_alive.sort(key=_tower_sort)

        radiant_tower_str = (
            f"天辉存活塔({len(radiant_alive)}): "
            + ", ".join(f"天辉{n}" for n in radiant_alive)
            if radiant_alive else "天辉塔: 无视野"
        )
        dire_tower_str = (
            f"夜魇存活塔({len(dire_alive)}): "
            + ", ".join(f"夜魇{n}" for n in dire_alive)
            if dire_alive else "夜魇塔: 无视野"
        )

        lines = [
            f"等级: Lv{level}",
            f"血量: {health_pct}%  蓝量: {mana_pct}%",
            f"KDA: {kills}/{deaths}/{assists}",
            f"补刀: {last_hits}/{denies}",
            f"GPM/XPM: {gpm}/{xpm}",
            f"金钱: {gold}",
            f"装备: {', '.join(item_names) if item_names else '无'}",
            f"技能: {' '.join(skill_levels)}",
            f"{radiant_tower_str}",
            f"{dire_tower_str}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 用户消息构建（缓存优化）
    # ------------------------------------------------------------------

    def _get_fixed_prefix(self, data: Dict[str, Any]) -> str:
        """构建并缓存用户消息的固定前缀（同一局游戏不变，API 可缓存）

        注意：只有当阵容凑齐 10 个英雄后才缓存前缀。
        在此之前每次都重新构建，确保阵容数据逐步完善。
        """
        lineups_complete = (
            len(self._team_lineups["radiant"]) + len(self._team_lineups["dire"]) >= 10
        )
        if self._fixed_prefix is not None and lineups_complete:
            return self._fixed_prefix

        hero = data.get("hero", {})
        player = data.get("player", {})
        hero_name = hero_cn_name(hero.get("name", player.get("hero_name", "")))
        player_team = player.get("team_name", "")
        team_cn = "天辉" if player_team == "radiant" else "夜魇"
        radiant = self._team_lineups.get("radiant", []) or ["未知"]
        dire = self._team_lineups.get("dire", []) or ["未知"]

        # 分路中文名映射
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

        # 阵容完整后才缓存，后续查询复用（API 前缀缓存命中）
        if lineups_complete:
            self._fixed_prefix = prefix

        return prefix

    def _build_variable_part(self, data: Dict[str, Any]) -> str:
        """构建用户消息的可变部分（每帧不同，放末尾以最大化前缀缓存命中）"""
        map_info = data.get("map", {})
        clock_time = map_info.get("clock_time", 0)
        mins = int(clock_time // 60)
        secs = int(clock_time % 60)
        radiant_score = map_info.get("radiant_score", 0)
        dire_score = map_info.get("dire_score", 0)

        player_state = self._build_player_state(data)
        hero_positions = self._extract_hero_positions(
            data, self._recently_killed if self._recently_killed else None
        )
        ward_info = self._extract_ward_info(data)

        # 附加上一次的战略分析，供 AI 参考（避免重复分析）
        last_analysis_part = ""
        if self._last_analysis:
            last_analysis_part = f"\n上一次战略分析: {self._last_analysis}"

        return (
            f"\n"
            f"当前时间: {mins}分{secs}秒\n"
            f"比分: 天辉 {radiant_score} - {dire_score} 夜魇\n"
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

    def _build_user_message(self, data: Dict[str, Any]) -> str:
        """
        构建完整的用户消息。
        固定前缀在前（可缓存），历史建议在中，实时数据在后。
        """
        fixed = self._get_fixed_prefix(data)
        history = self._build_history_section()
        variable = self._build_variable_part(data)
        instruction = (
            "\n\n请根据以上所有信息，输出一个JSON对象，包含两个字段：\n"
            '1. "analysis": 80-150字的战略局势分析（阵容优劣势/克制关系/当前阶段/应该采取的策略方向）\n'
            '2. "command": 1条15-30字的极简战术指令，不要与上一条重复\n'
            "只输出JSON本身，不要添加```json标记或任何其他文字。\n"
            "确保JSON合法可解析，analysis和command内的文本不要包含未转义的双引号。"
        )
        return fixed + history + variable + instruction

    def _build_history_section(self) -> str:
        """构建本局历史建议部分（供 AI 参考，避免重复建议）"""
        if not self._advice_history:
            return ""
        lines = ["\n之前的建议:"]
        for game_time, advice in self._advice_history:
            mins = int(game_time // 60)
            secs = int(game_time % 60)
            lines.append(f"- ({mins}分{secs}秒) {advice}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # 提示词日志
    # ------------------------------------------------------------------

    def _log_prompt(self, user_message: str) -> None:
        """打印提示词到控制台，并写入日志文件"""
        mins = int(self._last_bucket * self._interval_minutes)
        separator = "=" * 60

        # 控制台打印
        print(f"\n{separator}")
        print(f"🤖 发送给 AI 的提示词 (游戏时间 {mins}:00):")
        print(f"   System: ({len(self._system_prompt)} 字符, 来自 AIPromt.md)")
        print(f"   User:")
        for line in user_message.split("\n"):
            print(f"     {line}")
        print(f"{separator}\n")

        # 写入日志文件（去掉历史建议部分，ai_advices 已单独记录）
        log_message = user_message
        if self._advice_history:
            history_section = self._build_history_section()
            if history_section:
                log_message = user_message.replace(history_section, "\n")
        if self._prompt_log_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._prompt_log_path = os.path.join(
                self._prompt_log_dir, f"ai_prompts_{ts}.jsonl"
            )

        log_entry = {
            "game_time_minutes": mins,
            "system_prompt_length": len(self._system_prompt),
            "user_message": log_message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._prompt_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    def _log_advice(self, advice: str, game_time: float, analysis: str = "") -> None:
        """逐条追加 AI 建议到日志文件"""
        if self._advice_log_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._advice_log_path = os.path.join(
                self._prompt_log_dir, f"ai_advices_{ts}.jsonl"
            )

        mins = int(game_time // 60)
        secs = int(game_time % 60)
        entry = {
            "game_time": f"{mins}:{secs:02d}",
            "analysis": analysis,
            "command": advice,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self._advice_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # API 调用
    # ------------------------------------------------------------------

    def _call_api(self, user_message: str) -> Optional[tuple]:
        """调用 DeepSeek API，返回 (analysis, command) 或 None（失败时）"""
        if not self._api_key:
            if not self._warned_no_key:
                print("[AI Advisor] 未配置 api_key，跳过 AI 教练功能", file=sys.stderr)
                self._warned_no_key = True
            return None

        try:
            import openai
        except ImportError:
            print("[AI Advisor] openai 库未安装，请运行: pip install openai", file=sys.stderr)
            return None

        if self._client is None:
            self._client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                extra_body={
                    "thinking": {"type": "disabled"},
                },
            )
            msg = response.choices[0].message
            text = msg.content

            # 注意：reasoning_content 是模型的思维链/分析过程，不是最终建议
            # 绝不将其作为建议返回
            reasoning = getattr(msg, "reasoning_content", None) or ""
            if reasoning and not text:
                print(f"  [AI Advisor] 模型只输出了推理过程，无最终建议: {reasoning}", file=sys.stderr)
                return None

            if text:
                result = text.strip()
                # 尝试解析 JSON 结构化输出: {"analysis": "...", "command": "..."}
                try:
                    parsed = json.loads(result)
                    analysis = parsed.get("analysis", "")
                    command = parsed.get("command", "")
                    if not command:
                        # command 为空时，用 analysis 作为 fallback
                        command = analysis
                        analysis = ""
                    print(f"  🤖 AI 战略分析: {analysis}")
                    print(f"  🤖 AI 战术指令: {command}")
                    return (analysis, command)
                except json.JSONDecodeError:
                    # Fallback: JSON 解析失败，全文当 command
                    print(f"  [AI Advisor] JSON解析失败，将全文作为指令", file=sys.stderr)
                    print(f"  🤖 AI 回复: {result}")
                    return ("", result)

            # 调试：打印完整 message 对象
            print(f"  [AI Advisor] API 返回为空，完整响应: {msg}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"  [AI Advisor] API 调用失败: {e}", file=sys.stderr)
            return None
