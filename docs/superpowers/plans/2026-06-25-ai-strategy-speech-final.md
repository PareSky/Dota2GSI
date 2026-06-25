# AI Strategy Speech Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let AI choose `brief` or `full` local speech, add strategic analysis to `full`, and keep full announcements near 25 seconds at configurable Windows SAPI rate 4 without trimming commands or item advice.

**Architecture:** Extend the AI JSON and `AdvisorEvent` contracts with `speech_level`. Put pure duration and composition rules in a new `speech_policy.py`; keep `tts.py` focused on tagged queueing and PowerShell execution. `GSIHandler` configures speech, composes advisor messages, and removes only pending advisor messages when a new game starts.

**Tech Stack:** Python 3.10, standard-library `dataclasses`, `queue`, `threading`, `subprocess`, `unittest`, PowerShell `System.Speech`.

---

## File map

- Create `src/speech_policy.py` for validated settings, duration estimation, natural-boundary trimming, and advisor speech composition.
- Create `tests/test_speech_policy.py` for pure policy tests.
- Modify `src/advisor/client.py`, `src/advisor/prompt.py`, `src/ai_advisor.py`, and `AIPromt.md` for the four-field AI contract.
- Modify `tests/test_advisor_refactor.py` for the new contract and to replace stale prompt hashes with structural assertions.
- Modify `src/tts.py` and `src/speak.ps1` for tagged requests, configurable rate, dynamic timeout, and selective queue clearing.
- Create `tests/test_tts.py` for queue and subprocess behavior.
- Modify `src/gsi_handler.py` and `tests/test_gsi_handler_async.py` for integration.
- Modify `config.yaml`, `README.md`, and `tests/test_logging_config.py` for user-facing configuration.

## Baseline

The current full suite has 21 tests with 3 failures and 1 error, all in `tests/test_advisor_refactor.py`. They are stale expectations: two-value client tuples, a two-value mocked API result, and outdated exact prompt lengths/hashes. Task 1 updates these contract tests before adding the new field.

---

### Task 1: Add the four-field AI protocol

**Files:**
- Modify: `src/advisor/client.py:25-101`
- Modify: `src/advisor/prompt.py:161-174`
- Modify: `src/ai_advisor.py:21-34,110-130,178-185`
- Modify: `AIPromt.md`
- Test: `tests/test_advisor_refactor.py`

- [ ] **Step 1: Write failing client parsing tests**

Use fake responses containing valid `full`, invalid `loud`, missing level, empty command, and plain text:

```python
completions = Completions(
    [
        '{"analysis":"局势","command":"推进","item":"黑皇杖","speech_level":"full"}',
        '{"analysis":"稳住","command":"带线","item":"","speech_level":"loud"}',
        '{"analysis":"默认","command":"控盾","item":""}',
        '{"analysis":"只分析","command":"","speech_level":"full"}',
        "plain text",
    ]
)
```

Assert:

```python
self.assertEqual(
    client.complete("SYS", "USER"),
    ("局势", "推进", "黑皇杖", "full"),
)
self.assertEqual(
    client.complete("SYS", "USER"),
    ("稳住", "带线", "", "brief"),
)
self.assertEqual(
    client.complete("SYS", "USER"),
    ("默认", "控盾", "", "brief"),
)
self.assertEqual(
    client.complete("SYS", "USER"),
    ("", "只分析", "", "brief"),
)
self.assertEqual(
    client.complete("SYS", "USER"),
    ("", "plain text", "", "brief"),
)
```

- [ ] **Step 2: Run the focused test and verify failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_advisor_refactor.AdvisorComponentTests.test_client_preserves_json_and_fallback_parsing -v
```

Expected: `FAIL` because the client returns only three values.

- [ ] **Step 3: Implement parsing and downgrade rules**

Change the signature:

```python
def complete(
    self,
    system_prompt: str,
    user_message: str,
) -> Optional[tuple[str, str, str, str]]:
```

Normalize the parsed fields:

```python
analysis = parsed.get("analysis", "")
command = parsed.get("command", "")
item = parsed.get("item", "")
speech_level = parsed.get("speech_level", "brief")

analysis = analysis if isinstance(analysis, str) else ""
command = command if isinstance(command, str) else ""
item = item if isinstance(item, str) else ""
if speech_level not in {"brief", "full"}:
    speech_level = "brief"
if not command:
    command = analysis
    analysis = ""
    speech_level = "brief"
return analysis, command, item, speech_level
```

Return `("", result, "", "brief")` for non-JSON text.

- [ ] **Step 4: Run the focused test and verify success**

Run the command from Step 2. Expected: `OK`.

- [ ] **Step 5: Write failing event and prompt tests**

Make the advisor mock return:

```python
(
    "analysis",
    "command",
    "item",
    "full",
)
```

Assert the produced event contains all four values:

```python
self.assertEqual(timer_event[0].analysis_text, "analysis")
self.assertEqual(timer_event[0].advice_text, "command")
self.assertEqual(timer_event[0].item_text, "item")
self.assertEqual(timer_event[0].speech_level, "full")
```

Replace both brittle prompt length/hash assertions with:

```python
self.assertIn('"analysis"', message)
self.assertIn('"command"', message)
self.assertIn('"item"', message)
self.assertIn('"speech_level"', message)
self.assertIn('"brief"', message)
self.assertIn('"full"', message)
self.assertIn("当前时间: 1分5秒", message)
```

- [ ] **Step 6: Run the advisor module and verify failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_advisor_refactor -v
```

Expected: failures for missing `speech_level` propagation and three-value unpacking.

- [ ] **Step 7: Propagate the field**

Add a backward-compatible final dataclass field:

```python
@dataclass
class AdvisorEvent:
    advice_text: str
    analysis_text: str
    item_text: str
    game_time: float
    timestamp: str
    speech_level: str = "brief"
```

Unpack and pass it:

```python
analysis, command, item, speech_level = result
```

```python
AdvisorEvent(
    advice_text=command,
    analysis_text=analysis,
    item_text=item,
    game_time=clock_time,
    timestamp=datetime.now().isoformat(timespec="seconds"),
    speech_level=speech_level,
)
```

Update `_call_api()` to return `Optional[tuple[str, str, str, str]]`.

- [ ] **Step 8: Update both prompt sources**

In `PromptBuilder`, require:

```text
4. "speech_level": 只能是 "brief" 或 "full"。局势方向明显变化、关键克制首次出现、阶段转换或重大团战结果改变策略时用 "full"，其余情况用 "brief"。
```

Update `AIPromt.md` to the same four-field JSON contract. Its format, examples, field rules, and mandatory rules must all mention `analysis`, `command`, `item`, and `speech_level`; remove the obsolete “两个字段” text.

- [ ] **Step 9: Run advisor tests**

Run the command from Step 6. Expected: all tests pass.

- [ ] **Step 10: Commit**

```powershell
git add src/advisor/client.py src/advisor/prompt.py src/ai_advisor.py AIPromt.md tests/test_advisor_refactor.py
git commit -m "feat: add AI speech level protocol"
```

---

### Task 2: Implement the local speech policy

**Files:**
- Create: `src/speech_policy.py`
- Create: `tests/test_speech_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create tests for invalid settings, `brief`, `full`, invalid levels, natural trimming, and preservation of command/item:

```python
class SpeechSettingsTests(unittest.TestCase):
    def test_invalid_values_fall_back_and_rate_is_clamped(self):
        settings = SpeechSettings.from_config(
            {
                "rate": 99,
                "full_max_seconds": 0,
                "estimated_chars_per_second": -1,
                "timeout_buffer_seconds": -3,
            }
        )
        self.assertEqual(settings.rate, 10)
        self.assertEqual(settings.full_max_seconds, 25)
        self.assertEqual(settings.estimated_chars_per_second, 7)
        self.assertEqual(settings.timeout_buffer_seconds, 8)
```

```python
def test_brief_omits_analysis(self):
    text = compose_advisor_speech(
        "战略分析", "立刻推塔", "黑皇杖", "brief", SpeechSettings()
    )
    self.assertEqual(text, "立刻推塔。出装建议：黑皇杖")

def test_full_includes_all_sections(self):
    text = compose_advisor_speech(
        "我方团战更强。",
        "控盾逼团",
        "黑皇杖",
        "full",
        SpeechSettings(),
    )
    self.assertEqual(
        text,
        "战略分析：我方团战更强。战术指令：控盾逼团。出装建议：黑皇杖",
    )

def test_invalid_level_downgrades_to_brief(self):
    text = compose_advisor_speech(
        "分析", "撤退", "", "unexpected", SpeechSettings()
    )
    self.assertEqual(text, "撤退")
```

For trimming, use a six-second budget and assert the first natural sentence remains while the complete command and item remain. Also use a one-second budget and assert long command/item strings are still unchanged.

- [ ] **Step 2: Run tests and verify import failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_speech_policy -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement settings**

```python
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
```

- [ ] **Step 4: Implement complete composition logic**

```python
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
    item,
    speech_level,
    settings,
):
    item_part = f"出装建议：{item}" if item else ""
    brief_text = "。".join(
        part for part in (command, item_part) if part
    )
    if speech_level != "full" or not analysis:
        return brief_text

    command_part = f"战术指令：{command}" if command else ""
    full_action_text = "。".join(
        part for part in (command_part, item_part) if part
    )
    prefix = "战略分析："
    separator = "。" if full_action_text else ""
    max_chars = int(
        settings.full_max_seconds
        * settings.estimated_chars_per_second
    )
    analysis_budget = max_chars - len(
        prefix + separator + full_action_text
    )
    trimmed = _trim_at_boundary(analysis, analysis_budget)
    if not trimmed:
        return brief_text
    return f"{prefix}{trimmed}{separator}{full_action_text}"
```

- [ ] **Step 5: Run policy tests**

Run the command from Step 2. Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add src/speech_policy.py tests/test_speech_policy.py
git commit -m "feat: add advisor speech composition policy"
```

---

### Task 3: Upgrade the TTS queue and SAPI execution

**Files:**
- Modify: `src/tts.py:189-257`
- Modify: `src/speak.ps1`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write failing queue tests**

Instantiate `SpeechQueue` without starting its worker:

```python
speech = SpeechQueue(SpeechSettings())
speech.say("资源提醒", category="alert")
speech.say("旧局分析", category="advisor")
speech.say("夜晚降临", category="alert")
speech.clear_pending("advisor")
self.assertEqual(
    [(r.text, r.category) for r in speech.pending_requests()],
    [("资源提醒", "alert"), ("夜晚降临", "alert")],
)
```

Patch process execution:

```python
settings = SpeechSettings(
    rate=4,
    estimated_chars_per_second=5,
    timeout_buffer_seconds=8,
)
speech = SpeechQueue(settings)
with (
    patch("tts.resource_path", return_value="speak.ps1"),
    patch("tts.subprocess.run") as run,
):
    speech._run_request("一" * 100)
args, kwargs = run.call_args
self.assertEqual(args[0][-2:], ["-rate", "4"])
self.assertEqual(kwargs["timeout"], 28)
```

Read `speak.ps1` and assert it contains `[int]$rate` and `$voice.Rate = $rate`.

- [ ] **Step 2: Run tests and verify failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_tts -v
```

Expected: constructor/API assertion failures.

- [ ] **Step 3: Implement tagged requests and selective clearing**

```python
from dataclasses import dataclass
from speech_policy import SpeechSettings


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    category: str = "alert"
```

`SpeechQueue.__init__` receives `settings`, stores `_queue_lock`, and keeps the existing daemon worker. `say()` always enqueues a `SpeechRequest`; platform filtering stays in the module-level `speak()` so the queue remains independently testable:

```python
def say(self, text, category="alert"):
    with self._queue_lock:
        self._queue.put(SpeechRequest(text, category))
```

Implement:

```python
def clear_pending(self, category=None):
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

def pending_requests(self):
    with self._queue_lock:
        return list(self._queue.queue)
```

The worker treats `None` as stop, otherwise calls `_run_request(request.text)`.

- [ ] **Step 4: Implement dynamic process execution**

```python
def _run_request(self, text):
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
```

Catch `subprocess.TimeoutExpired` and other exceptions in the worker, print a concise stderr diagnostic, and continue.

- [ ] **Step 5: Add global configuration API**

```python
_speech_settings = SpeechSettings()
_speech_queue = None


def configure_speech(config):
    global _speech_settings
    _speech_settings = SpeechSettings.from_config(config)
    if _speech_queue is not None:
        _speech_queue.configure(_speech_settings)


def clear_pending_speech(category=None):
    if _speech_queue is not None:
        _speech_queue.clear_pending(category)


def speak(text, category="alert"):
    global _speech_queue
    if sys.platform != "win32":
        return
    if _speech_queue is None:
        _speech_queue = SpeechQueue(_speech_settings)
        _speech_queue.start()
    _speech_queue.say(text, category)
```

`SpeechQueue.configure()` replaces its settings reference.

- [ ] **Step 6: Make PowerShell rate configurable**

```powershell
param(
    [string]$text,
    [int]$rate = 4
)
$rate = [Math]::Max(-10, [Math]::Min(10, $rate))
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.Rate = $rate
```

Keep Chinese voice selection and `$voice.Speak($text)`.

- [ ] **Step 7: Run TTS tests**

Run the command from Step 2. Expected: all pass.

- [ ] **Step 8: Commit**

```powershell
git add src/tts.py src/speak.ps1 tests/test_tts.py
git commit -m "feat: add configurable non-truncating TTS queue"
```

---

### Task 4: Connect advisor events to local speech

**Files:**
- Modify: `src/gsi_handler.py:12-18,27-54,119-151,208-217`
- Modify: `tests/test_gsi_handler_async.py`

- [ ] **Step 1: Write failing brief/full integration tests**

Create events with identical text and different levels:

```python
def make_event(level):
    return AdvisorEvent(
        advice_text="控盾逼团",
        analysis_text="我方团战更强，应主动控制肉山区域。",
        item_text="黑皇杖",
        game_time=900,
        timestamp="2026-06-25T00:00:00",
        speech_level=level,
    )
```

Patch `gsi_handler.configure_speech` and `gsi_handler.speak`. Assert `brief` excludes analysis, `full` includes all three sections, and both calls use `category="advisor"`.

- [ ] **Step 2: Write failing configuration and reset tests**

Construct with:

```python
"tts": {
    "rate": 4,
    "full_max_seconds": 25,
    "estimated_chars_per_second": 7,
    "timeout_buffer_seconds": 8,
}
```

Assert `configure_speech` receives that mapping. Patch `clear_pending_speech` in the existing new-session test and assert:

```python
clear_pending_speech.assert_called_once_with("advisor")
```

- [ ] **Step 3: Run handler tests and verify failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_gsi_handler_async -v
```

Expected: failures because the integration APIs are not used.

- [ ] **Step 4: Implement integration**

Import:

```python
from speech_policy import SpeechSettings, compose_advisor_speech
from tts import (
    clear_pending_speech,
    configure_speech,
    hero_cn_name,
    speak,
)
```

In `__init__`:

```python
tts_cfg = config.get("tts", {})
configure_speech(tts_cfg)
self._speech_settings = SpeechSettings.from_config(tts_cfg)
```

At the start of `_start_new_session()`:

```python
clear_pending_speech("advisor")
```

Replace `_on_advisor_event()` composition:

```python
text = compose_advisor_speech(
    analysis=event.analysis_text,
    command=event.advice_text,
    item=event.item_text,
    speech_level=event.speech_level,
    settings=self._speech_settings,
)
if text:
    speak(text, category="advisor")
```

- [ ] **Step 5: Run handler tests**

Run the command from Step 3. Expected: all pass.

- [ ] **Step 6: Run related regressions**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_logging_config tests.test_state_machines tests.test_async_services -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/gsi_handler.py tests/test_gsi_handler_async.py
git commit -m "feat: route AI speech levels to local TTS"
```

---

### Task 5: Add configuration and documentation

**Files:**
- Modify: `config.yaml`
- Modify: `README.md`
- Modify: `tests/test_logging_config.py`

- [ ] **Step 1: Write failing config test**

Import `yaml`, load repository `config.yaml`, and assert:

```python
self.assertEqual(
    config["tts"],
    {
        "rate": 4,
        "full_max_seconds": 25,
        "estimated_chars_per_second": 7,
        "timeout_buffer_seconds": 8,
    },
)
```

- [ ] **Step 2: Run and verify failure**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest tests.test_logging_config -v
```

Expected: missing `tts` configuration failure.

- [ ] **Step 3: Add defaults**

```yaml
tts:
  # Windows SAPI 语速，范围 -10 到 10
  rate: 4
  # full 战略播报的目标最长时长
  full_max_seconds: 25
  # 本地时长预算和动态超时估算
  estimated_chars_per_second: 7
  # PowerShell 进程启动与收尾缓冲
  timeout_buffer_seconds: 8
```

- [ ] **Step 4: Document behavior**

Add all four `tts.*` settings to the README table. Explain that `brief` plays command and item, `full` adds analysis, invalid levels become `brief`, and over-budget speech shortens only analysis.

- [ ] **Step 5: Run config tests**

Run the command from Step 2. Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add config.yaml README.md tests/test_logging_config.py
git commit -m "docs: configure AI strategy speech"
```

---

### Task 6: Verify the complete feature

**Files:**
- Verify all modified files

- [ ] **Step 1: Run full unit suite**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m unittest discover -s tests -v
```

Expected: all tests pass with zero failures and errors.

- [ ] **Step 2: Compile sources**

```powershell
& 'C:\Users\meiyo\AppData\Local\Programs\Python\Python310\python.exe' -m compileall -q src tests
```

Expected: exit code `0`, no output.

- [ ] **Step 3: Check repository diff**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors and only intentional changes.

- [ ] **Step 4: Perform Windows SAPI smoke test**

```powershell
powershell -ExecutionPolicy Bypass -File src\speak.ps1 -text "战略分析语音测试。立刻控盾。出装建议，黑皇杖。" -rate 4
```

Expected: one complete Chinese announcement at the faster rate, without truncation.

- [ ] **Step 5: Report evidence**

Record the passing test count, compile result, and whether the audible SAPI smoke test completed. Do not claim completion if any verification step fails.
