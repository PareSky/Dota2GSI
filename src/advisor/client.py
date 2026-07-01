"""OpenAI-compatible HTTP API client via requests."""

import json
import re
import sys
from typing import Any, Dict, Optional

import requests


class AdvisorClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int,
        temperature: float,
        extra_body: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._extra_body = extra_body or {}
        self._timeout_seconds = timeout_seconds
        self._warned_no_key = False

    def _chat_completions_url(self) -> str:
        base_url = self._base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if re.search(r"/v\d+$", base_url):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    def _build_payload(
        self,
        system_prompt: str,
        user_message: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        payload.update(self._extra_body)
        return payload

    def _parse_response_text(self, response_data: Dict[str, Any]) -> str:
        choices = response_data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or ""
        if reasoning and not content:
            print(
                f"  [AI Advisor] 模型只输出了推理过程，无最终建议: {reasoning}",
                file=sys.stderr,
            )
        return content

    def complete(
        self,
        system_prompt: str,
        user_message: str,
    ) -> Optional[tuple[str, str, str, str, str]]:
        if not self._api_key:
            if not self._warned_no_key:
                print(
                    "[AI Advisor] 未配置 api_key，跳过 AI 教练功能",
                    file=sys.stderr,
                )
                self._warned_no_key = True
            return None

        try:
            response = requests.post(
                self._chat_completions_url(),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=self._build_payload(system_prompt, user_message),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            response_data = response.json()
            text = self._parse_response_text(response_data)
            if not text:
                print(
                    f"  [AI Advisor] API 返回为空，完整响应: {response.text}",
                    file=sys.stderr,
                )
                return None

            result = text.strip()
            try:
                parsed = json.loads(result)
                analysis = parsed.get("analysis", "")
                command = parsed.get("command", "")
                fight = parsed.get("fight", "")
                item = parsed.get("item", "")
                speech_level = parsed.get("speech_level", "brief")

                analysis = analysis if isinstance(analysis, str) else ""
                command = command if isinstance(command, str) else ""
                fight = fight if isinstance(fight, str) else ""
                item = item if isinstance(item, str) else ""
                if speech_level not in {"brief", "full"}:
                    speech_level = "brief"
                if not command:
                    command = analysis
                    analysis = ""
                    speech_level = "brief"
                print(f"  🤖 AI 战略分析: {analysis}")
                print(f"  🤖 AI 战术指令: {command}")
                print(f"  🤖 AI 团战思路: {fight}")
                print(f"  🤖 AI 出装建议: {item}")
                print(f"  🤖 AI 播报级别: {speech_level}")
                return analysis, command, fight, item, speech_level
            except json.JSONDecodeError:
                print(
                    "  [AI Advisor] JSON解析失败，将全文作为指令",
                    file=sys.stderr,
                )
                print(f"  🤖 AI 回复: {result}")
                return "", result, "", "", "brief"
        except Exception as exc:
            print(f"  [AI Advisor] API 调用失败: {exc}", file=sys.stderr)
            return None

    def reset_session(self) -> None:
        self._warned_no_key = False
