# Dota 2 GSI Listener

一个 Windows 上运行的 Dota 2 实时游戏助手。它通过 Flask 接收 Dota 2 GSI 数据，记录游戏状态、追踪敌方视野、提醒资源刷新，并可调用 DeepSeek 提供语音战术建议。

## 功能

- 接收 Dota 2 推送的 GSI JSON 数据。
- 每局生成会话 JSONL 日志，可通过配置关闭。
- 追踪敌方英雄进入、离开视野及多人消失事件。
- 提前 15 秒提醒神符、莲花、经验符、魔方和魔晶刷新。
- 使用 Windows SAPI 播放中文 TTS。
- 异步调用 DeepSeek AI 教练，不阻塞 GSI HTTP 请求。
- 新局开始时弹出分路选择窗口。

## 安装与运行

建议使用 Python 3.10 或更高版本：

```powershell
pip install -r requirements.txt
python src/server.py
```

使用自定义配置文件：

```powershell
python src/server.py path\to\config.yaml
```

健康检查地址：

```text
http://127.0.0.1:3000/health
```

## 配置 Dota 2

将 [gamestate_integration_gsi_config.cfg](gamestate_integration_gsi_config.cfg) 复制到：

```text
C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\dota\cfg\gamestate_integration\
```

如果目录不存在，请手动创建。复制后重启 Dota 2。

## 配置说明

配置文件为 [config.yaml](config.yaml)。

| 配置项 | 说明 | 默认值 |
|---|---|---|
| `server.host` | HTTP 监听地址 | `127.0.0.1` |
| `server.port` | HTTP 监听端口 | `3000` |
| `logging.log_dir` | 所有日志的输出目录 | `./logs` |
| `logging.session_file` | 是否创建每局 GSI JSONL 日志 | `true` |
| `vision.enabled` | 是否启用敌方视野追踪 | `true` |
| `ai_advisor.enabled` | 是否启用 AI 教练 | `true` |
| `ai_advisor.api_key` | DeepSeek API Key，也可使用 `DeepSeekApiKey` 环境变量 | 空 |
| `ai_advisor.base_url` | OpenAI 兼容 API 地址 | `https://api.deepseek.com` |
| `ai_advisor.model` | 请求的模型名称 | `deepseek-v4-pro` |
| `ai_advisor.interval_minutes` | 定时分析间隔，单位为游戏内分钟 | `1` |
| `ai_advisor.max_tokens` | AI 最大输出 token 数 | `500` |
| `ai_advisor.temperature` | AI 温度参数 | `0.2` |
| `ai_advisor.system_prompt_file` | 系统提示词文件 | `./AIPromt.md` |
| `ai_advisor.system_prompt` | 提示词文件不可用时的后备提示词 | 见配置文件 |
| `ai_advisor.prompt_log_dir` | AI 提示词及建议日志目录 | `./logs` |

`logging.session_file: true` 时，每局创建一个 `gsi_session_<时间>.jsonl`，游戏时间每经过至少 60 秒写入一次。

视野事件固定写入：

```text
<logging.log_dir>/vision_events.jsonl
```

AI Key 推荐通过当前用户环境变量配置：

```powershell
[Environment]::SetEnvironmentVariable(
    "DeepSeekApiKey",
    "sk-你的Key",
    "User"
)
```

重新打开终端后生效。

## 项目结构

```text
Dota2GSI/
├── src/
│   ├── server.py          # Flask HTTP 入口
│   ├── gsi_handler.py     # GSI 编排与日志管理
│   ├── vision_tracker.py  # 敌方视野状态机
│   ├── game_timer.py      # 资源刷新计时器
│   ├── ai_advisor.py      # AI 教练兼容门面与流程编排
│   ├── ai_worker.py       # AI 后台线程
│   ├── advisor/
│   │   ├── trigger.py     # 定时、比分变化与冷却状态机
│   │   ├── extractor.py   # GSI 状态与地图信息提取
│   │   ├── prompt.py      # 系统提示词和用户消息构建
│   │   ├── client.py      # DeepSeek/OpenAI 兼容 API
│   │   └── logging.py     # 提示词与建议 JSONL 日志
│   ├── role_selector.py   # 独立进程分路窗口
│   ├── tts.py             # TTS 队列与英雄名映射
│   ├── speak.ps1          # Windows SAPI 脚本
│   └── resource_utils.py  # 源码与 PyInstaller 资源路径
├── config.yaml
├── AIPromt.md
├── Dota2GSI.spec
└── gamestate_integration_gsi_config.cfg
```

## 构建 Windows EXE

```powershell
.\build.bat
```

输出：

```text
dist\Dota2GSI.exe
```

EXE 会打包 `config.yaml`、`AIPromt.md` 和 `src/speak.ps1`。
