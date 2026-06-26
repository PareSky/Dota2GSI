"""
Dota 2 GSI HTTP 服务器
- 监听 Dota 2 客户端 POST 的游戏状态数据
- 路由到 GSIHandler 进行处理
"""

import sys
import os
import logging
import multiprocessing

# 关闭 Flask/Werkzeug 访问日志 (127.0.0.1 - - POST / HTTP/1.1 200 -)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# 修复 Windows GBK 终端下 emoji 输出乱码
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保 src 目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from flask import Flask, request, jsonify

from gsi_handler import GSIHandler
from resource_utils import editable_resource_path
from dota2_setup import setup_gsi_config

app = Flask(__name__)
handler: GSIHandler = None  # 由 main() 初始化


@app.route("/", methods=["POST"])
def gsi_endpoint():
    """Dota 2 GSI 数据入口"""
    if not request.data:
        return jsonify({"status": "ok"}), 200

    try:
        handler.handle(request.data)
    except Exception as e:
        print(f"[ERROR] 数据处理失败: {e}", file=sys.stderr)
        # 即使处理失败也返回 200，避免 Dota 2 重试/阻塞
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "running"}), 200


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件"""
    if not os.path.exists(config_path):
        print(f"[WARN] 配置文件不存在: {config_path}，使用默认配置")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    global handler

    # 配置文件路径：优先命令行参数，其次 exe 同目录（用户可编辑），最后 bundled/源码
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = editable_resource_path("config.yaml")
    config_path = os.path.abspath(config_path)

    config = load_config(config_path)

    setup_result = setup_gsi_config()
    prefix = "[OK]" if setup_result.ok else "[WARN]"
    path_suffix = f": {setup_result.path}" if setup_result.path else ""
    print(f"{prefix} {setup_result.message}{path_suffix}")

    handler = GSIHandler(config)

    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 3000)

    print(f"""
╔══════════════════════════════════════════════╗
║        Dota 2 GSI Listener 已启动           ║
╠══════════════════════════════════════════════╣
║  监听地址 : {host:<30} ║
║  监听端口 : {port:<30} ║
║  日志目录 : {handler.log_dir:<30} ║
║  健康检查 : http://{host}:{port}/health{'':<16} ║
╚══════════════════════════════════════════════╝

📋 GSI 配置已在上方自动检测/安装。如安装成功，重启 Dota 2 即可生效。

🔑 AI 教练配置（可选）:
   方式一: 设置环境变量 DeepSeekApiKey=sk-你的key
   方式二: 在 config.yaml 的 ai_advisor.api_key 填入 key

⏳ 等待 Dota 2 连接...
""")

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
