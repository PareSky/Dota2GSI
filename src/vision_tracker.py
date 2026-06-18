"""
敌方视野追踪模块
- 逐帧对比 minimap 数据中的英雄对象
- 检测敌方英雄：进入视野 (ENTERED) / 离开视野 (LEFT)
- 离开视野有 5 秒延迟确认，避免草丛/树林短暂丢失视野导致频繁误报
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class MinimapHero:
    """minimap 中的英雄对象"""
    object_key: str       # e.g., "o84"
    hero_name: str        # e.g., "npc_dota_hero_skeleton_king"
    xpos: float
    ypos: float
    team: int             # 2=radiant, 3=dire
    is_self: bool = False


@dataclass
class VisionEvent:
    """视野变化事件"""
    event_type: str       # "ENTERED" | "LEFT"
    hero_name: str
    xpos: float
    ypos: float
    game_time: float      # 游戏内时间（秒）
    timestamp: str        # 现实时间 ISO 格式

    def __str__(self) -> str:
        if self.event_type == "MASS_LEFT":
            return f"⚠ 多人消失: {self.hero_name}"
        icon = "👁" if self.event_type == "ENTERED" else "🚫"
        label = "进入视野" if self.event_type == "ENTERED" else "离开视野"
        return f"{icon} {self.hero_name} {label} (x:{self.xpos:.0f}, y:{self.ypos:.0f})"


class VisionTracker:
    """逐帧追踪 minimap 中敌方英雄的可见性"""

    # team 常量
    TEAM_RADIANT = 2
    TEAM_DIRE = 3

    # 消失延迟：英雄从 minimap 消失后等 N 秒才确认离开视野
    LEAVE_DELAY = 10.0
    # 多人消失报告间隔（秒）
    MASS_LEAVE_COOLDOWN = 60.0

    def __init__(self):
        # 当前帧可见的敌方英雄: hero_name -> MinimapHero
        self._visible_enemies: Dict[str, MinimapHero] = {}
        # 当前帧可见的友方英雄
        self._visible_allies: Dict[str, MinimapHero] = {}
        # 我的队伍
        self._my_team: Optional[int] = None
        # 待确认离开: hero_name -> (消失时的 game_time, 消失前的英雄信息)
        self._pending_leave: Dict[str, Tuple[float, MinimapHero]] = {}
        # 上次多人消失报告的时间
        self._last_mass_leave_time: float = -999.0
        # 上一帧比分（用于判断死亡 vs 消失）
        self._last_radiant_score: int = 0
        self._last_dire_score: int = 0

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def update(
        self,
        minimap_data: Dict[str, Any],
        player_team: str,
        game_time: float,
        radiant_score: int = 0,
        dire_score: int = 0,
    ) -> List[VisionEvent]:
        """
        处理一帧 minimap 数据，返回视野变化事件列表。

        Args:
            minimap_data: data["minimap"] 字典
            player_team: data["player"]["team_name"] ("radiant" / "dire")
            game_time: 游戏内时间（秒）
            radiant_score: 当前天辉比分
            dire_score: 当前夜魇比分
        """
        if not minimap_data:
            return []

        # 1. 确定己方队伍
        self._ensure_team(player_team, minimap_data)

        if self._my_team is None:
            return []  # 无法确定队伍，跳过

        enemy_team = self.TEAM_DIRE if self._my_team == self.TEAM_RADIANT else self.TEAM_RADIANT

        # 2. 解析当前帧的英雄
        current_enemies: Dict[str, MinimapHero] = {}
        current_allies: Dict[str, MinimapHero] = {}

        for key, obj in minimap_data.items():
            hero = self._parse_hero(key, obj)
            if hero is None:
                continue
            if hero.team == enemy_team:
                current_enemies[hero.hero_name] = hero
            elif hero.team == self._my_team:
                current_allies[hero.hero_name] = hero

        # 3. 对比上一帧，生成事件
        events: List[VisionEvent] = []
        now_ts = datetime.now().isoformat(timespec="seconds")

        prev_enemy_names = set(self._visible_enemies.keys())
        curr_enemy_names = set(current_enemies.keys())

        # 进入视野: 当前有, 上一帧没有 (包括从 pending 中恢复的)
        entered = curr_enemy_names - prev_enemy_names
        for name in entered:
            h = current_enemies[name]
            events.append(VisionEvent(
                event_type="ENTERED",
                hero_name=h.hero_name,
                xpos=h.xpos,
                ypos=h.ypos,
                game_time=game_time,
                timestamp=now_ts,
            ))
            # 如果在 pending 中，取消 pending（又回来了）
            self._pending_leave.pop(name, None)

        # 从视野消失: 上一帧有, 当前没有 → 判断是死亡还是离开视野
        left = prev_enemy_names - curr_enemy_names

        # 己方比分在这一帧增加了 → 有敌人死了（死亡 ≠ 离开视野）
        my_score = radiant_score if self._my_team == self.TEAM_RADIANT else dire_score
        my_score_prev = self._last_radiant_score if self._my_team == self.TEAM_RADIANT else self._last_dire_score
        enemy_died_this_frame = (my_score > my_score_prev)

        for name in left:
            if enemy_died_this_frame:
                continue  # 同帧击杀，跳过
            self._pending_leave[name] = (game_time, self._visible_enemies[name])

        # 比分增加时清除最近 2 秒的 pending（跨帧击杀容错）
        if enemy_died_this_frame:
            to_remove = [
                name for name, (vt, _) in self._pending_leave.items()
                if game_time - vt <= 2.0
            ]
            for name in to_remove:
                del self._pending_leave[name]

        # 检查 pending 中超时的，确认离开
        confirmed_left = [
            name for name, (vanish_time, _) in self._pending_leave.items()
            if game_time - vanish_time >= self.LEAVE_DELAY
        ]
        for name in confirmed_left:
            _, h = self._pending_leave.pop(name)
            events.append(VisionEvent(
                event_type="LEFT",
                hero_name=h.hero_name,
                xpos=h.xpos,
                ypos=h.ypos,
                game_time=game_time,
                timestamp=now_ts,
            ))

        # 4人以上同时消失 → 多人消失警报（间隔 60 秒）
        if len(confirmed_left) >= 4 and game_time - self._last_mass_leave_time >= self.MASS_LEAVE_COOLDOWN:
            self._last_mass_leave_time = game_time
            events.append(VisionEvent(
                event_type="MASS_LEFT",
                hero_name=f"{len(confirmed_left)}人",
                xpos=0.0, ypos=0.0,
                game_time=game_time,
                timestamp=now_ts,
            ))

        # 4. 更新状态
        self._visible_enemies = current_enemies
        self._visible_allies = current_allies
        self._last_radiant_score = radiant_score
        self._last_dire_score = dire_score

        return events

    def reset(self) -> None:
        """重置追踪器（新游戏开始时调用）"""
        self._visible_enemies.clear()
        self._visible_allies.clear()
        self._pending_leave.clear()
        self._my_team = None

    def get_visible_enemies(self) -> List[MinimapHero]:
        """返回当前可见的敌方英雄列表"""
        return list(self._visible_enemies.values())

    def get_visible_allies(self) -> List[MinimapHero]:
        """返回当前可见的友方英雄列表"""
        return list(self._visible_allies.values())

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _ensure_team(self, player_team: str, minimap_data: Dict[str, Any]) -> None:
        """确认己方队伍编号"""
        if self._my_team is not None:
            return
        # 优先从 player.team_name 推断
        if player_team == "radiant":
            self._my_team = self.TEAM_RADIANT
        elif player_team == "dire":
            self._my_team = self.TEAM_DIRE
        else:
            # 兜底：从 minimap 中的 self 标记推断
            for obj in minimap_data.values():
                if obj.get("image") == "minimap_herocircle_self":
                    self._my_team = obj.get("team")
                    break

    @staticmethod
    def _parse_hero(key: str, obj: Dict[str, Any]) -> Optional[MinimapHero]:
        """从 minimap 条目中解析英雄对象，不是英雄则返回 None"""
        image = obj.get("image", "")
        # 英雄有三种图标: herocircle(友方), herocircle_self(自己), enemyicon(敌方)
        if "herocircle" not in image and image != "minimap_enemyicon":
            return None

        team = obj.get("team")
        if team is None:
            return None

        # 优先用 name 字段（普通英雄），其次 unitname（self 可能没有 name）
        hero_name = obj.get("name") or obj.get("unitname", "")
        if not hero_name or not hero_name.startswith("npc_dota_hero_"):
            return None

        return MinimapHero(
            object_key=key,
            hero_name=hero_name,
            xpos=obj.get("xpos", 0.0),
            ypos=obj.get("ypos", 0.0),
            team=team,
            is_self=(image == "minimap_herocircle_self"),
        )
