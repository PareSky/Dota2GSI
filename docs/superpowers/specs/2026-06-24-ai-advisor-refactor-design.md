# AI Advisor 纯重构设计

## 目标

将接近 900 行的 `src/ai_advisor.py` 拆分为职责清晰的内部组件，同时保持所有外部行为不变。

本次仅重构代码结构，不改变：

- `AiAdvisor` 的构造方式与公共方法。
- AI 触发时间、比分延迟和冷却规则。
- 提示词文本、顺序和换行。
- DeepSeek 请求参数及响应降级行为。
- 日志文件名、字段和内容。
- `AdvisorEvent` 的字段及返回方式。

## 文件结构

```text
src/
├── ai_advisor.py              # 兼容门面与流程编排
└── advisor/
    ├── __init__.py
    ├── trigger.py             # 触发条件与冷却状态机
    ├── extractor.py           # GSI 状态提取与阵容累积
    ├── prompt.py              # 系统提示词和用户消息构建
    ├── client.py              # DeepSeek API 调用与响应解析
    └── logging.py             # AI 提示词和建议日志
```

`src/ai_advisor.py` 继续导出 `AiAdvisor` 和 `AdvisorEvent`，因此
`ai_worker.py` 与 `gsi_handler.py` 无需修改导入路径。

## 组件职责

### `ai_advisor.py`

作为稳定门面，负责：

- 读取配置并创建内部组件。
- 保留 `update(data)`、`set_role(role)`、`reset()`。
- 按原顺序编排触发、提取、提示词、日志和 API。
- 将成功结果包装为 `AdvisorEvent`。

门面不再直接解析 minimap、拼接提示词或调用 OpenAI SDK。

### `advisor/trigger.py`

负责所有触发状态：

- 游戏开始 60 秒内跳过。
- 定时触发时间桶。
- 比分变化检测与 5 秒延迟。
- 20 秒全局冷却。
- 上一帧英雄集合及刚死亡英雄识别。
- 上次成功查询时间。

组件返回结构化触发结果，明确表示：

- 是否查询。
- 当前时间桶。
- 本次触发来源。
- 最近死亡英雄。

只有 API 成功后才记录成功查询时间，保持当前行为。

### `advisor/extractor.py`

负责从 GSI 数据提取信息：

- 跨帧累积双方阵容。
- 提取 minimap 英雄集合和位置。
- 匹配最近地图地标。
- 提取真假眼信息。
- 提取血蓝、KDA、补刀、GPM/XPM、金币。
- 提取装备、技能等级和冷却。
- 提取双方存活防御塔。

现有地标、塔名、物品槽位和技能槽位常量一并迁入本模块。

### `advisor/prompt.py`

负责提示词状态和文本：

- 加载系统提示词文件及后备提示词。
- 保存玩家分路。
- 构建并缓存阵容完整后的固定前缀。
- 构建历史建议区。
- 构建实时状态区。
- 附加上一条战略分析。
- 拼接最终 JSON 输出要求。
- 保存本局建议历史及上次分析。

对相同状态输入，重构前后生成的 system prompt 和 user message 必须逐字符一致。

### `advisor/client.py`

负责 API 边界：

- 延迟导入 `openai`。
- 延迟创建 OpenAI 兼容客户端。
- 保持 `model`、`max_tokens`、`temperature` 和 `extra_body` 不变。
- 解析 `analysis` 与 `command`。
- command 为空时沿用 analysis 的降级规则。
- JSON 解析失败时将完整响应作为 command。
- 缺少 API Key 时只警告一次。

返回 `Optional[tuple[str, str]]`，不返回 `AdvisorEvent`。

### `advisor/logging.py`

负责文件日志：

- 首次写入时生成 `ai_prompts_<时间>.jsonl`。
- 首次写入时生成 `ai_advices_<时间>.jsonl`。
- 保持当前 JSON 字段、时间格式和 UTF-8 编码。
- 记录提示词时继续移除历史建议区，避免重复存储。
- 新局重置两个日志文件路径。

控制台输出内容和出现时机保持不变。

## 数据流

```text
AiAdvisor.update(data)
    → TriggerController.evaluate(data)
    → StateExtractor.accumulate_lineups(data)
    → StateExtractor.build_snapshot(data, trigger_result)
    → PromptBuilder.build_user_message(snapshot)
    → AdvisorLogger.log_prompt(...)
    → AdvisorClient.complete(system_prompt, user_message)
    → PromptBuilder.record_advice(...)
    → AdvisorLogger.log_advice(...)
    → AdvisorEvent
```

未触发查询时，只更新触发器所需的上一帧英雄和比分状态，不构建提示词、不写日志、不调用 API。

## 状态归属

为避免拆分后出现重复状态，每项状态只有一个所有者：

| 状态 | 所有者 |
|---|---|
| 时间桶、比分、冷却、上一帧英雄、最近死亡 | `TriggerController` |
| 双方阵容、已见英雄 | `StateExtractor` |
| 分路、固定前缀、建议历史、上次分析 | `PromptBuilder` |
| OpenAI 客户端、缺 Key 警告 | `AdvisorClient` |
| 两个日志文件路径 | `AdvisorLogger` |

`AiAdvisor.reset()` 按固定顺序重置所有组件。

## 迁移策略

采用小步迁移，每步保持测试通过：

1. 先补黄金测试，记录现有提示词、触发和 API 解析行为。
2. 提取 `AdvisorClient` 和 `AdvisorLogger`，接口边界最独立。
3. 提取 `StateExtractor`，移动纯解析函数和常量。
4. 提取 `PromptBuilder`，用黄金测试保证文本不变。
5. 最后提取 `TriggerController`，保持状态机行为不变。
6. 将 `ai_advisor.py` 收敛为门面并运行全量回归。

不在一次改动中重写数据模型，也不引入新的业务规则。

## 测试与验收

新增测试覆盖：

- 固定 GSI 帧产生的 user message 与重构前黄金文本一致。
- 定时触发、比分延迟和冷却序列一致。
- 缺少 API Key、合法 JSON、command 为空及非法 JSON 的解析一致。
- 提示词日志和建议日志的文件名及 JSON 字段一致。
- `reset()` 清空所有局内状态。
- `AiAdvisor` 的公共接口与现有 `AiAdvisorWorker` 集成测试继续通过。

最终运行：

```powershell
python -m unittest discover -s tests -v
python -m py_compile src\ai_advisor.py src\advisor\*.py
git diff --check
```
