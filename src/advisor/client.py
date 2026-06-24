"""DeepSeek/OpenAI 兼容 API 客户端。"""

import json
import sys
from typing import Optional


class AdvisorClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = None
        self._warned_no_key = False

    def complete(
        self,
        system_prompt: str,
        user_message: str,
    ) -> Optional[tuple[str, str]]:
        if not self._api_key:
            if not self._warned_no_key:
                print(
                    "[AI Advisor] 未配置 api_key，跳过 AI 教练功能",
                    file=sys.stderr,
                )
                self._warned_no_key = True
            return None

        try:
            import openai
        except ImportError:
            print(
                "[AI Advisor] openai 库未安装，请运行: pip install openai",
                file=sys.stderr,
            )
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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                extra_body={"thinking": {"type": "disabled"}},
            )
            msg = response.choices[0].message
            text = msg.content
            reasoning = getattr(msg, "reasoning_content", None) or ""
            if reasoning and not text:
                print(
                    f"  [AI Advisor] 模型只输出了推理过程，无最终建议: {reasoning}",
                    file=sys.stderr,
                )
                return None

            if text:
                result = text.strip()
                try:
                    parsed = json.loads(result)
                    analysis = parsed.get("analysis", "")
                    command = parsed.get("command", "")
                    if not command:
                        command = analysis
                        analysis = ""
                    print(f"  🤖 AI 战略分析: {analysis}")
                    print(f"  🤖 AI 战术指令: {command}")
                    return analysis, command
                except json.JSONDecodeError:
                    print(
                        "  [AI Advisor] JSON解析失败，将全文作为指令",
                        file=sys.stderr,
                    )
                    print(f"  🤖 AI 回复: {result}")
                    return "", result

            print(
                f"  [AI Advisor] API 返回为空，完整响应: {msg}",
                file=sys.stderr,
            )
            return None
        except Exception as exc:
            print(f"  [AI Advisor] API 调用失败: {exc}", file=sys.stderr)
            return None

    def reset_session(self) -> None:
        self._warned_no_key = False
