# liangda-health Backend

## 运行

```bash
uv sync
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

默认使用 MySQL 和内存向量库。连接 MySQL/Milvus 时通过环境变量配置：

```bash
export HEALTH_AGENT_DATABASE_URL='mysql+pymysql://root:123@127.0.0.1:3306/liangda_health'
export HEALTH_AGENT_TEST_DATABASE_URL='mysql+pymysql://root:123@127.0.0.1:3306/liangda_health_test'
export HEALTH_AGENT_MILVUS_ENABLED=true
export HEALTH_AGENT_MILVUS_URI='http://localhost:19530'
export HEALTH_AGENT_EMBEDDING_MODEL='text-embedding-v3'
export HEALTH_AGENT_CLOUD_OCR_ENDPOINT='https://example.com/ocr/pdf'
export HEALTH_AGENT_LLM_API_KEY
```

Embedding 默认使用阿里云 DashScope `text-embedding-v3`，默认复用 `HEALTH_AGENT_LLM_API_KEY`。如需单独配置 embedding key，可设置 `HEALTH_AGENT_EMBEDDING_API_KEY`。

Agent 聊天默认使用阿里云百炼 OpenAI 兼容接口：

```bash
export HEALTH_AGENT_LLM_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'
export HEALTH_AGENT_LLM_MODEL='qwen-plus'
export HEALTH_AGENT_LLM_API_KEY
```

`HEALTH_AGENT_LLM_API_KEY` 不配置时，聊天发送接口会返回“未配置模型 API Key”。

当前机器如果已经有 MySQL/Milvus 容器，可直接使用：

```bash
docker exec mysql mysql -uroot -p123 -e "CREATE DATABASE IF NOT EXISTS liangda_health CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

export HEALTH_AGENT_DATABASE_URL='mysql+pymysql://root:123@localhost:3306/liangda_health'
export HEALTH_AGENT_MILVUS_ENABLED=true
export HEALTH_AGENT_MILVUS_URI='http://localhost:19530'
PYTHONPATH=. python scripts/verify_real_services.py
```

验证 Agent 聊天真实模型链路时，先在当前 shell 配置 `HEALTH_AGENT_LLM_API_KEY`，再执行：

```bash
PYTHONPATH=. python scripts/verify_agent_chat.py
PYTHONPATH=. python scripts/verify_agent_chat_stream.py
PYTHONPATH=. python scripts/verify_agent_chat_with_report.py
```

## 本地 MySQL/Milvus

项目根目录提供了最小 `docker-compose.yml`：

```bash
docker compose up -d mysql etcd minio milvus
cp .env.example .env
cd backend
../.venv/bin/uvicorn app.main:app --reload --port 8000
```

如果不设置 `HEALTH_AGENT_MILVUS_ENABLED=true`，后端默认使用内存向量库，方便本地开发页面和 API。数据库默认使用本机 3306 端口的 MySQL：

```bash
docker compose up -d mysql
```

## 接口

- `POST /api/kb/upload`
- `GET /api/kb/documents`
- `GET /api/kb/documents/{document_id}`
- `GET /api/kb/documents/{document_id}/chunks`
- `DELETE /api/kb/documents/{document_id}`
- `POST /api/kb/search`
- `GET /api/agent/sessions`
- `POST /api/agent/sessions`
- `GET /api/agent/sessions/{session_id}/messages`
- `POST /api/agent/sessions/{session_id}/messages:send`
- `POST /api/agent/sessions/{session_id}/messages:stream`
- `GET /api/agent/quick-actions`
