from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechSettings:
    rate: int = 4
    full_max_seconds: float = 25
    estimated_chars_per_second: float = 7
    timeout_buffer_seconds: float = 8

    @classmethod
    def from_config(cls, config):
        def positive(value, default):
            try:
                value = float(value)
                return value if value > 0 else default
            except (TypeError, ValueError):
                return default

        try:
            rate = max(-10, min(10, int(config.get("rate", 4))))
        except (TypeError, ValueError):
            rate = 4
        try:
            buffer_seconds = float(
                config.get("timeout_buffer_seconds", 8)
            )
            if buffer_seconds < 0:
                buffer_seconds = 8
        except (TypeError, ValueError):
            buffer_seconds = 8
        return cls(
            rate=rate,
            full_max_seconds=positive(
                config.get("full_max_seconds", 25), 25
            ),
            estimated_chars_per_second=positive(
                config.get("estimated_chars_per_second", 7), 7
            ),
            timeout_buffer_seconds=buffer_seconds,
        )

    def estimate_seconds(self, text):
        return len(text) / self.estimated_chars_per_second

    def subprocess_timeout(self, text):
        return max(
            5.0,
            self.estimate_seconds(text) + self.timeout_buffer_seconds,
        )


_BOUNDARIES = "。！？；，、"


def _trim_at_boundary(text, limit):
    candidate = text[:max(0, limit)].rstrip()
    for index in range(len(candidate) - 1, -1, -1):
        if candidate[index] in _BOUNDARIES:
            return candidate[: index + 1].rstrip()
    return candidate.rstrip(_BOUNDARIES + " ")


def compose_advisor_speech(
    analysis,
    command,
    fight,
    item,
    speech_level,
    settings,
):
    fight_part = f"团战思路：{fight}" if fight else ""
    item_part = f"出装建议：{item}" if item else ""
    brief_text = "。".join(
        part for part in (command, fight_part, item_part) if part
    )
    if speech_level != "full" or not analysis:
        return brief_text

    command_part = f"战术指令：{command}" if command else ""
    full_action_text = "。".join(
        part for part in (command_part, fight_part, item_part) if part
    )
    analysis_prefix = "战略分析："
    separator = "。" if full_action_text else ""
    max_chars = int(
        settings.full_max_seconds
        * settings.estimated_chars_per_second
    )
    analysis_budget = max_chars - len(
        full_action_text + separator + analysis_prefix
    )
    trimmed = _trim_at_boundary(analysis, analysis_budget)
    if not trimmed:
        return brief_text
    trimmed = trimmed.rstrip(_BOUNDARIES)
    return f"{full_action_text}{separator}{analysis_prefix}{trimmed}"
