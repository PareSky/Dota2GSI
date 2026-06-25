"""
Windows TTS 语音模块
- 使用 Windows SAPI 朗读文本（通过 PowerShell）
- 队列播放，避免多条语音重叠
- 英雄名中文映射，兜底英文
"""

import subprocess
import sys
import queue
import threading

from resource_utils import resource_path


# ==========================================================================
# 英雄名映射: Dota 2 内部名 → 中文名
# ==========================================================================
HERO_MAP: dict[str, str] = {
    # ── 力量 ──
    "abaddon": "亚巴顿",
    "alchemist": "炼金术士",
    "axe": "斧王",
    "beastmaster": "兽王",
    "brewmaster": "酒仙",
    "bristleback": "钢背兽",
    "centaur": "半人马战行者",
    "chaos_knight": "混沌骑士",
    "clockwerk": "发条技师",
    "dawnbreaker": "破晓辰星",
    "doom_bringer": "末日使者",
    "dragon_knight": "龙骑士",
    "earth_spirit": "大地之灵",
    "earthshaker": "撼地者",
    "elder_titan": "上古巨神",
    "huskar": "哈斯卡",
    "io": "艾欧",
    "kunkka": "昆卡",
    "legion_commander": "军团指挥官",
    "life_stealer": "噬魂鬼",
    "lone_druid": "德鲁伊",
    "lycan": "狼人",
    "magnataur": "马格纳斯",
    "marci": "玛西",
    "mars": "玛尔斯",
    "night_stalker": "暗夜魔王",
    "omniknight": "全能骑士",
    "phoenix": "凤凰",
    "primal_beast": "兽",
    "pudge": "帕吉",
    "sand_king": "沙王",
    "skeleton_king": "冥魂大帝",
    "slardar": "斯拉达",
    "spirit_breaker": "裂魂人",
    "sven": "斯温",
    "tidehunter": "潮汐猎人",
    "timbersaw": "伐木机",
    "tiny": "小小",
    "treant": "树精卫士",
    "troll_warlord": "巨魔战将",
    "tusk": "巨牙海民",
    "underlord": "孽主",
    "undying": "不朽尸王",
    "wraith_king": "冥魂大帝",

    # ── 敏捷 ──
    "antimage": "敌法师",
    "arc_warden": "天穹守望者",
    "bloodseeker": "嗜血狂魔",
    "bounty_hunter": "赏金猎人",
    "broodmother": "育母蜘蛛",
    "clinkz": "克林克兹",
    "drow_ranger": "卓尔游侠",
    "ember_spirit": "灰烬之灵",
    "faceless_void": "虚空假面",
    "furion": "先知",
    "gyrocopter": "矮人直升机",
    "hoodwink": "森海飞霞",
    "juggernaut": "主宰",
    "kez": "凯",
    "luna": "露娜",
    "medusa": "美杜莎",
    "meepo": "米波",
    "mirana": "米拉娜",
    "monkey_king": "齐天大圣",
    "morphling": "变体精灵",
    "naga_siren": "娜迦海妖",
    "nyx_assassin": "司夜刺客",
    "pangolier": "石鳞剑士",
    "phantom_assassin": "幻影刺客",
    "phantom_lancer": "幻影长矛手",
    "razor": "雷泽",
    "riki": "力丸",
    "shadow_fiend": "影魔",
    "slark": "斯拉克",
    "sniper": "狙击手",
    "spectre": "幽鬼",
    "templar_assassin": "圣堂刺客",
    "terrorblade": "恐怖利刃",
    "ursa": "熊战士",
    "vengefulspirit": "复仇之魂",
    "venomancer": "剧毒术士",
    "viper": "冥界亚龙",
    "weaver": "编织者",
    "windrunner": "风行者",

    # ── 智力 ──
    "ancient_apparition": "远古冰魄",
    "bane": "祸乱之源",
    "batrider": "蝙蝠骑士",
    "chen": "陈",
    "crystal_maiden": "水晶室女",
    "dark_seer": "黑暗贤者",
    "dark_willow": "邪影芳灵",
    "dazzle": "戴泽",
    "death_prophet": "死亡先知",
    "disruptor": "干扰者",
    "enchantress": "魅惑魔女",
    "enigma": "谜团",
    "grimstroke": "天涯墨客",
    "invoker": "祈求者",
    "keeper_of_the_light": "光之守卫",
    "leshrac": "拉席克",
    "lich": "巫妖",
    "lina": "莉娜",
    "lion": "莱恩",
    "muerta": "琼英碧灵",
    "necrolyte": "瘟疫法师",
    "obsidian_destroyer": "殁境神蚀者",
    "ogre_magi": "食人魔魔法师",
    "oracle": "神谕者",
    "puck": "帕克",
    "pugna": "帕格纳",
    "queenofpain": "痛苦女王",
    "ringmaster": "百戏大王",
    "rubick": "拉比克",
    "shadow_demon": "暗影恶魔",
    "shadow_shaman": "暗影萨满",
    "silencer": "沉默术士",
    "skywrath_mage": "天怒法师",
    "snapfire": "电炎绝手",
    "storm_spirit": "风暴之灵",
    "techies": "工程师",
    "tinker": "修补匠",
    "visage": "维萨吉",
    "void_spirit": "虚无之灵",
    "warlock": "术士",
    "winter_wyvern": "寒冬飞龙",
    "witch_doctor": "巫医",
    "zuus": "宙斯",

    # ── 别名 ──
    "nevermore": "影魔",       # shadow_fiend 别名
    "magnus": "马格纳斯",      # magnataur 别名
    "furion": "先知",          # natures_prophet 别名
    "rattletrap": "发条技师",  # clockwerk 别名

    "abyssal_underlord" : "孽主",
    "largo" : "朗戈",
    "marci" : "马西",
    "jakiro": "杰奇若",
}


def hero_cn_name(raw_name: str) -> str:
    """
    英雄名转中文，无映射则返回简化英文。

    >>> hero_cn_name("npc_dota_hero_zuus")
    '宙斯'
    >>> hero_cn_name("npc_dota_hero_witch_doctor")
    '巫医'
    >>> hero_cn_name("npc_dota_hero_unknown_hero")
    'unknown hero'
    """
    # 去掉 npc_dota_hero_ 前缀
    key = raw_name
    if key.startswith("npc_dota_hero_"):
        key = key[len("npc_dota_hero_"):]

    # 查映射
    if key in HERO_MAP:
        return HERO_MAP[key]

    # 兜底：下划线转空格
    return key.replace("_", " ")


# ==========================================================================
# 语音请求数据类
# ==========================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    category: str = "alert"


# ==========================================================================
# 语音队列
# ==========================================================================

class SpeechQueue:
    """串行播放队列：逐条朗读，不会重叠"""

    def __init__(self, settings):
        self._settings = settings
        self._queue: queue.Queue = queue.Queue()
        self._queue_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False

    def configure(self, settings) -> None:
        """更新语音设置"""
        self._settings = settings

    def start(self) -> None:
        """启动后台播放线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止播放线程"""
        self._running = False
        self._queue.put(None)

    def say(self, text, category="alert"):
        """将文本加入播放队列（立即返回，不阻塞）"""
        with self._queue_lock:
            self._queue.put(SpeechRequest(text, category))

    def clear_pending(self, category=None):
        """清除待播放队列中匹配类别的请求"""
        kept = []
        with self._queue_lock:
            while True:
                try:
                    request = self._queue.get_nowait()
                except queue.Empty:
                    break
                if request is None:
                    kept.append(request)
                elif category is not None and request.category != category:
                    kept.append(request)
            for request in kept:
                self._queue.put(request)

    def clear(self) -> None:
        """清空待播放队列"""
        self.clear_pending()

    def pending_requests(self):
        """返回待播放请求列表（用于测试）"""
        with self._queue_lock:
            return list(self._queue.queue)

    def _worker(self) -> None:
        """后台线程：逐条取出并同步朗读"""
        while self._running:
            request = self._queue.get()
            if request is None:
                break
            try:
                self._run_request(request.text)
            except Exception:
                pass

    def _run_request(self, text):
        """执行 PowerShell TTS 子进程"""
        ps1_path = resource_path("src", "speak.ps1")
        subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ps1_path,
                "-text",
                text,
                "-rate",
                str(self._settings.rate),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=self._settings.subprocess_timeout(text),
        )


_speech_settings = None
_speech_queue: SpeechQueue | None = None


def configure_speech(config):
    """全局语音配置入口"""
    global _speech_settings, _speech_queue
    from speech_policy import SpeechSettings
    _speech_settings = SpeechSettings.from_config(config)
    if _speech_queue is not None:
        _speech_queue.configure(_speech_settings)


def clear_pending_speech(category=None):
    """清除待播放队列中匹配类别的请求"""
    if _speech_queue is not None:
        _speech_queue.clear_pending(category)


def speak(text, category="alert"):
    """全局入口：加入语音队列"""
    global _speech_settings, _speech_queue
    if sys.platform != "win32":
        return
    if _speech_settings is None:
        from speech_policy import SpeechSettings
        _speech_settings = SpeechSettings()
    if _speech_queue is None:
        _speech_queue = SpeechQueue(_speech_settings)
        _speech_queue.start()
    _speech_queue.say(text, category)
