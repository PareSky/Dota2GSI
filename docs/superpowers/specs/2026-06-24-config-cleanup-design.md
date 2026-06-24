# 配置清理设计

## 目标

删除无效或重复的配置项，让 `config.yaml`、运行时行为和 README 保持一致。

## 配置变更

- 删除 `logging.console_pretty_print` 与 `logging.console_max_depth`，控制台保持安静。
- 删除 `logging.json_lines`，避免与 `logging.session_file` 重复。
- 保留并接通 `logging.session_file`：
  - `true`：新局开始时创建会话 JSONL，并按现有一分钟间隔写入。
  - `false`：不创建、不写入会话 JSONL。
- 删除 `vision.event_log_file`。
- 视野事件固定写入 `<logging.log_dir>/vision_events.jsonl`。

## 代码清理

- `GSIHandler` 不再保存已删除配置对应的字段。
- 删除未调用的控制台摘要、建筑摘要和深度截断方法。
- `_start_new_session()` 仅在 `session_file` 开启时生成会话文件路径。
- `_write_to_file()` 仅根据会话文件路径判断是否写入。

## 文档更新

README 更新为当前实际功能：

- 完整列出视野追踪、资源计时、TTS 和 AI 教练。
- 更新当前模块结构。
- 配置表只列真实生效的配置。
- 说明会话日志每分钟最多记录一次。
- 补充 EXE 构建命令和输出位置。

## 验证

- 测试 `session_file: true` 会创建并写入会话日志。
- 测试 `session_file: false` 不创建会话日志。
- 测试视野事件日志固定写入 `log_dir/vision_events.jsonl`。
- 运行全部单元测试、Python 语法检查和 `git diff --check`。
