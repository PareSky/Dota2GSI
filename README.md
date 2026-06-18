# Dota 2 GSI Listener

实时监听 Dota 2 游戏状态数据，控制台美化输出 + 结构化 JSON 日志。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务器
python src/server.py
```

## 配置 Dota 2

将 `gsi_config.cfg` 复制到 Dota 2 的 GSI 配置目录：

```
C:\Program Files (x86)\Steam\steamapps\common\dota 2 beta\game\dota\cfg\gamestate_integration\
```

> 如果 `gamestate_integration` 目录不存在，手动创建即可。

复制后**重启 Dota 2**，进入游戏后数据会自动推送。

## 项目结构

```
Dota2GSI/
├── src/
│   ├── server.py        # Flask HTTP 服务器入口
│   └── gsi_handler.py   # GSI 数据处理 & 日志
├── config.yaml           # 服务器配置
├── gsi_config.cfg        # Dota 2 GSI 配置模板
├── requirements.txt
└── logs/                 # 日志输出目录
```

## 配置说明 (config.yaml)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `server.host` | 监听地址 | `127.0.0.1` |
| `server.port` | 监听端口 | `3000` |
| `logging.log_dir` | 日志输出目录 | `./logs` |
| `logging.console_pretty_print` | 控制台美化打印 | `true` |
| `logging.console_max_depth` | 控制台 JSON 最大深度 | `3` |
| `logging.session_file` | 每局游戏一个日志文件 | `true` |

## 控制台输出示例

```
[21:05:32] ⏱ 02:15 | 🦸 npx_dota_hero_axe | ⚔ 3/0/1 | ⬆ Lv.7 | 💰 2840
--------------------------------------------------
{
  "map": {
    "clock_time": 135,
    ...
  },
  "player": {
    "kills": 3,
    ...
  }
}
```

## 后续计划

- [ ] 游戏事件检测（击杀、死亡、买活、肉山等）
- [ ] 数据统计 & 分析
- [ ] Web Dashboard / Overlay
- [ ] 多玩家支持
