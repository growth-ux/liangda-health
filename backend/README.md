# liangda-health Backend

## 运行

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

默认使用 `sqlite:///./backend/dev.db` 和内存向量库，便于本地启动。连接 MySQL/Milvus 时通过环境变量配置：

```bash
export MEAL_AGENT_DATABASE_URL='mysql+pymysql://user:password@localhost:3306/liangda_health'
export MEAL_AGENT_MILVUS_ENABLED=true
export MEAL_AGENT_MILVUS_URI='http://localhost:19530'
export MEAL_AGENT_EMBEDDING_ENDPOINT='https://example.com/embedding'
export MEAL_AGENT_CLOUD_OCR_ENDPOINT='https://example.com/ocr/pdf'
```

`MEAL_AGENT_EMBEDDING_ENDPOINT` 接收 JSON `{"texts": ["..."]}`，返回 JSON `{"embeddings": [[...]]}`。不配置时使用确定性本地向量，方便本地测试；真实环境应配置 embedding 服务。

当前机器如果已经有 MySQL/Milvus 容器，可直接使用：

```bash
docker exec mysql mysql -uroot -p123 -e "CREATE DATABASE IF NOT EXISTS liangda_health CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

export MEAL_AGENT_DATABASE_URL='mysql+pymysql://root:123@localhost:3306/liangda_health'
export MEAL_AGENT_MILVUS_ENABLED=true
export MEAL_AGENT_MILVUS_URI='http://localhost:19530'
PYTHONPATH=. python scripts/verify_real_services.py
```

## 本地 MySQL/Milvus

项目根目录提供了最小 `docker-compose.yml`：

```bash
docker compose up -d mysql etcd minio milvus
cp .env.example .env
cd backend
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

如果不设置 `MEAL_AGENT_MILVUS_ENABLED=true`，后端默认使用内存向量库，方便本地开发页面和 API。

## 接口

- `POST /kb/upload`
- `GET /kb/documents`
- `GET /kb/documents/{document_id}`
- `GET /kb/documents/{document_id}/chunks`
- `DELETE /kb/documents/{document_id}`
- `POST /kb/search`
