"""从 Dota 2 GSI 数据提取 AI 教练所需状态。"""

from typing import Any, Dict, List, Optional

from tts import hero_cn_name


class StateExtractor:
    ITEM_SLOTS = [
        "slot0", "slot1", "slot2", "slot3", "slot4", "slot5",
        "neutral0", "teleport0",
    ]
    ABILITY_SLOTS = ["ability0", "ability1", "ability2", "ability3"]
    TOWER_NAME_MAP = {
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
    TOWER_ORDER = [
        "上一塔", "上二塔", "上三塔",
        "中一塔", "中二塔", "中三塔",
        "下一塔", "下二塔", "下三塔",
        "基地塔",
    ]
    LANDMARKS = [
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
        ("夜魇神秘商店", 4886, -1207, "dire"),
        ("天辉神秘商店", -5080, 1947, "radiant"),
        ("上路传送门", -6457, 7599, None),
        ("下路传送门", 6425, -7313, None),
        ("肉山巢穴(左上)", -3190, 2112, None),
        ("肉山巢穴(右下)", 2496, -2926, None),
    ]

    def __init__(self):
        self.team_lineups: Dict[str, List[str]] = {
            "radiant": [],
            "dire": [],
        }
        self._lineups_seen: set = set()

    def reset(self) -> None:
        self.team_lineups = {"radiant": [], "dire": []}
        self._lineups_seen = set()

    def accumulate_lineups(self, data: Dict[str, Any]) -> None:
        if sum(map(len, self.team_lineups.values())) >= 10:
            return
        for obj in data.get("minimap", {}).values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue
            team = obj.get("team")
            hero_name = obj.get("name") or obj.get("unitname", "")
            if (
                team is None
                or not hero_name
                or not hero_name.startswith("npc_dota_hero_")
            ):
                continue
            key = (team, hero_name)
            if key in self._lineups_seen:
                continue
            self._lineups_seen.add(key)
            cn = hero_cn_name(hero_name)
            if team == 2:
                self.team_lineups["radiant"].append(cn)
            elif team == 3:
                self.team_lineups["dire"].append(cn)
        if sum(map(len, self.team_lineups.values())) >= 10:
            print(
                "  [AI Advisor] 阵容收集完成: "
                f"天辉={self.team_lineups['radiant']}, "
                f"夜魇={self.team_lineups['dire']}"
            )

    @classmethod
    def nearest_landmark(cls, xpos: float, ypos: float) -> str:
        best = None
        best_dist = float("inf")
        for name, lx, ly, _team in cls.LANDMARKS:
            dist = (xpos - lx) ** 2 + (ypos - ly) ** 2
            if dist < best_dist:
                best_dist = dist
                best = name
        return best or "未知位置"

    @staticmethod
    def extract_hero_names(data: Dict[str, Any]) -> Dict[int, set]:
        result = {2: set(), 3: set()}
        for obj in data.get("minimap", {}).values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue
            team = obj.get("team")
            name = obj.get("name") or obj.get("unitname", "")
            if team in (2, 3) and name.startswith("npc_dota_hero_"):
                result[team].add(name)
        return result

    def extract_hero_positions(
        self,
        data: Dict[str, Any],
        recently_killed: Optional[Dict[int, List[str]]] = None,
    ) -> str:
        player_is_radiant = (
            data.get("player", {}).get("team_name", "") == "radiant"
        )
        player_hero_name = data.get("hero", {}).get("name", "")
        radiant_heroes: List[str] = []
        dire_heroes: List[str] = []
        seen = set()
        for obj in data.get("minimap", {}).values():
            image = obj.get("image", "")
            if "herocircle" not in image and image != "minimap_enemyicon":
                continue
            team = obj.get("team")
            hero_name = obj.get("name") or obj.get("unitname", "")
            if (
                team is None
                or not hero_name.startswith("npc_dota_hero_")
                or hero_name in seen
            ):
                continue
            seen.add(hero_name)
            xpos = obj.get("xpos", 0)
            ypos = obj.get("ypos", 0)
            marker = "【我】" if hero_name == player_hero_name else ""
            line = (
                f"{marker}{hero_cn_name(hero_name)}({xpos},{ypos})"
                f"→{self.nearest_landmark(xpos, ypos)}"
            )
            if team == 2:
                radiant_heroes.append(line)
            elif team == 3:
                dire_heroes.append(line)
        notes: List[str] = []
        if recently_killed:
            if recently_killed.get(2):
                notes.append(
                    f"刚死亡(天辉): {', '.join(recently_killed[2])}"
                )
            if recently_killed.get(3):
                notes.append(
                    f"刚死亡(夜魇): {', '.join(recently_killed[3])}"
                )
        else:
            notes.append("(未列出的英雄可能不在视野内，不一定已死亡)")
        radiant = (
            f"天辉({len(radiant_heroes)}人): "
            f"{', '.join(radiant_heroes) if radiant_heroes else '未知'}"
        )
        dire = (
            f"夜魇({len(dire_heroes)}人): "
            f"{', '.join(dire_heroes) if dire_heroes else '未知'}"
        )
        return "\n".join(
            ([radiant, dire] if player_is_radiant else [dire, radiant])
            + notes
        )

    def extract_ward_info(self, data: Dict[str, Any]) -> str:
        wards = {2: {"obs": [], "sen": []}, 3: {"obs": [], "sen": []}}
        for obj in data.get("minimap", {}).values():
            unitname = obj.get("unitname", "")
            team = obj.get("team")
            if team not in wards:
                continue
            ward_type = None
            if unitname == "npc_dota_observer_wards":
                ward_type = "obs"
            elif unitname == "npc_dota_sentry_wards":
                ward_type = "sen"
            if ward_type:
                xpos = obj.get("xpos", 0)
                ypos = obj.get("ypos", 0)
                wards[team][ward_type].append(
                    f"({xpos},{ypos})→{self.nearest_landmark(xpos, ypos)}"
                )

        def describe(team: int, name: str) -> str:
            obs = wards[team]["obs"]
            sen = wards[team]["sen"]
            if not obs and not sen:
                return f"{name}视野: 未发现"
            obs_str = (
                f"假眼({len(obs)}): {', '.join(obs)}" if obs else "假眼: 无"
            )
            sen_str = (
                f"真眼({len(sen)}): {', '.join(sen)}" if sen else "真眼: 无"
            )
            return f"{name}视野: {obs_str}; {sen_str}"

        return "\n".join(
            [describe(2, "天辉"), describe(3, "夜魇"), "(仅统计视野内可见的守卫)"]
        )

    def build_player_state(self, data: Dict[str, Any]) -> str:
        hero = data.get("hero", {})
        player = data.get("player", {})
        item_names = []
        for slot_key in self.ITEM_SLOTS:
            slot = data.get("items", {}).get(slot_key, {})
            name = slot.get("name", "")
            if name and name != "empty":
                short_name = name.replace("item_", "")
                cd = slot.get("cooldown", 0) or 0
                if cd > 0:
                    short_name += f"(cd:{cd:.0f}s)"
                item_names.append(short_name)
        skill_levels = []
        for ab_key in self.ABILITY_SLOTS:
            ability = data.get("abilities", {}).get(ab_key, {})
            level = ability.get("level", 0)
            name = ability.get("name", "")
            cd = ability.get("cooldown", 0) or 0
            cd_str = f"(cd:{cd:.0f}s)" if cd > 0 else ""
            if name:
                short = name.split(".")[-1] if "." in name else name
                parts = short.split("_", 1)
                short = parts[1] if len(parts) > 1 else short
                skill_levels.append(f"{short}:lv{level}{cd_str}")
            else:
                skill_levels.append(f"技能{ab_key[-1]}:lv{level}{cd_str}")
        radiant_alive: List[str] = []
        dire_alive: List[str] = []
        for obj in data.get("minimap", {}).values():
            if "tower" not in obj.get("image", ""):
                continue
            team = obj.get("team")
            unitname = obj.get("unitname", "") or obj.get("name", "")
            lookup = unitname[4:] if unitname.startswith("npc_") else unitname
            cn_name = self.TOWER_NAME_MAP.get(lookup)
            if team == 2 and cn_name and cn_name not in radiant_alive:
                radiant_alive.append(cn_name)
            elif team == 3 and cn_name and cn_name not in dire_alive:
                dire_alive.append(cn_name)
        sort_key = lambda name: (
            self.TOWER_ORDER.index(name) if name in self.TOWER_ORDER else 99
        )
        radiant_alive.sort(key=sort_key)
        dire_alive.sort(key=sort_key)
        radiant_towers = (
            f"天辉存活塔({len(radiant_alive)}): "
            + ", ".join(f"天辉{name}" for name in radiant_alive)
            if radiant_alive else "天辉塔: 无视野"
        )
        dire_towers = (
            f"夜魇存活塔({len(dire_alive)}): "
            + ", ".join(f"夜魇{name}" for name in dire_alive)
            if dire_alive else "夜魇塔: 无视野"
        )
        return "\n".join(
            [
                f"等级: Lv{hero.get('level', 0)}",
                f"血量: {hero.get('health_percent', 0)}%  "
                f"蓝量: {hero.get('mana_percent', 0)}%",
                f"KDA: {player.get('kills', 0)}/"
                f"{player.get('deaths', 0)}/{player.get('assists', 0)}",
                f"补刀: {player.get('last_hits', 0)}/{player.get('denies', 0)}",
                f"GPM/XPM: {player.get('gpm', 0)}/{player.get('xpm', 0)}",
                f"金钱: {player.get('gold', 0)}",
                f"装备: {', '.join(item_names) if item_names else '无'}",
                f"技能: {' '.join(skill_levels)}",
                radiant_towers,
                dire_towers,
            ]
        )
