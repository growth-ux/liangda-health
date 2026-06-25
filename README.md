# 粮达健康

粮达健康当前定位为：**基于健康报告理解、家庭健康画像、手环近期状态、Agent 记忆和商品推荐转化的家庭健康智能营销系统**。

当前代码主体是最小可用闭环的可行性验证，长期方向是面向中粮集团的 B2B2C 家庭健康运营平台：以家庭健康饮食决策为入口，连接家庭用户、中粮品牌方和集团运营体系，形成从健康理解到商品转化、再到用户反馈回流的闭环。 

## 长期 B2B2C 架构方向

长期规划参考 [liangda-health-market-roadmap.md](docs/liangda-health-market-roadmap.md)


平台服务三类对象：

- 家庭用户：家庭主账号、父母、配偶、孩子、老人。
- 中粮品牌方：食品、茶饮、肉蛋白、乳品早餐、健康营养品等品牌运营主体。
- 集团管理方：集团数字化、品牌运营、品类运营、用户运营、数据治理。

长期能力分层：

- 业务触点层：家庭健康入口、品牌运营入口、集团管理入口。
- 核心业务能力层：家庭用户中心、健康数据中心、家庭健康图谱中心、商品与内容中心、智能决策与推荐中心、Agent 交互中心、品牌运营中心、数据治理与平台支撑中心。
- 平台中台能力层：统一家庭健康标签、统一商品健康标签、统一推荐引擎、统一证据链、人群分层、活动编排、品牌接入标准和数据资产沉淀。
- 闭环价值层：家庭健康资产沉淀、品牌精准运营增长、多品牌协同转化、集团统一经营能力平台。

长期主链路：

```text
家庭健康数据 -> 家庭健康图谱 -> 饮食决策 -> 商品/内容匹配 -> 品牌运营转化 -> 用户反馈回流
```

当前代码优先支撑家庭用户侧和智能推荐闭环；品牌运营入口、集团管理入口、统一经营看板、活动编排和多品牌治理属于后续平台化建设范围。

## 当前可行性验证闭环

```text
创建家庭成员
-> 上传健康报告
-> PDF/OCR 文本提取、切片、向量化和 RAG 证据追溯
-> 抽取健康事实并沉淀到健康事实库
-> 汇总家庭成员画像和手环近期状态
-> Agent 编排健康画像、记忆、报告检索、餐单和商城推荐
-> 输出饮食建议、商品推荐和推荐依据
-> 购物车/反馈承接后续营销转化
```

当前阶段不要把项目理解为单纯的报告问答工具，也不要理解为普通商城。报告 RAG 主要负责查证据和追溯原文；健康事实、家庭画像、记忆、餐单和商品推荐共同承担智能营销决策。

## 已落地能力

- 家庭成员管理：成员档案、角色关系、健康标签、报告绑定。
- 健康报告知识库：PDF 上传、文本提取、OCR 入口、chunk 切分、embedding、Milvus 检索、成员隔离、报告详情和原文片段追溯。
- 健康事实库：从报告中抽取风险、指标、建议等结构化事实，并保留文档、页码、chunk 和证据文本。
- 健康画像聚合：结合成员档案、健康事实和设备近期状态，生成成员/家庭健康分析视图。
- 设备数据：按成员维护最近 7 天手环/设备状态，并支持本地模拟同步。
- Agent 对话：会话管理、流式回复、工具编排、结构化卡片、推荐商品卡片、推荐依据展示。
- 记忆系统：基于 mem0 方向沉淀偏好、排斥、阶段目标和营销反馈，用于跨会话个性化。
- 商城转化：商品列表、商品详情、健康推荐理由、购物车增删改查。
- 通知中心：健康提醒、已读、稍后提醒、完成状态。


## 技术栈

- 前端：React 19、React Router 7、TanStack Query、Vite 6、TypeScript、Tailwind CSS、lucide-react。
- 后端：FastAPI、SQLAlchemy、Pydantic Settings、LangChain、mem0ai、PyMuPDF、DashScope、pymilvus。
- 存储：MySQL 8.4、Milvus 2.5、MinIO、etcd。
- 模型服务：默认使用阿里云百炼 OpenAI 兼容接口，聊天模型默认 `qwen-plus`，embedding 默认 `text-embedding-v3`。

## 目录结构

```text
.
├── backend/                 # FastAPI 后端
│   ├── app/api/             # API 路由：agent、kb、members、mall、device、notice 等
│   ├── app/models/          # SQLAlchemy 数据模型
│   ├── app/repositories/    # 数据访问层
│   ├── app/schemas/         # Pydantic 请求/响应模型
│   ├── app/services/        # 核心业务服务、Agent 工具、RAG、画像、记忆、推荐
│   ├── app/scripts/         # 数据迁移和向量库重建脚本
│   ├── scripts/             # 本地验证脚本
│   └── tests/               # 后端测试
├── frontend/                # React 前端
│   ├── src/api/             # 前端 API 封装
│   ├── src/components/      # 通用组件、聊天组件、商城组件、成员组件
│   ├── src/pages/           # 页面路由
│   └── public/mall-products # 商城商品静态图片资源
├── docs/                    # 产品规划、架构文档、迭代设计
├── prd/                     # 原型和 PRD 资料
├── docker-compose.yml       # MySQL、Milvus、MinIO、etcd 本地依赖
└── .env.example             # 后端环境变量示例
```

## 本地启动

### 1. 启动基础服务

```bash
docker compose up -d mysql etcd minio milvus
```

Milvus 是报告向量检索和记忆向量能力的依赖，需要和 MySQL 一起启动。

### 2. 配置环境变量

```bash
cp .env.example .env
```

常用配置：

```bash
HEALTH_AGENT_DATABASE_URL=mysql+pymysql://root:123@127.0.0.1:3306/liangda_health
HEALTH_AGENT_TEST_DATABASE_URL=mysql+pymysql://root:123@127.0.0.1:3306/liangda_health_test
HEALTH_AGENT_MILVUS_URI=http://localhost:19530
HEALTH_AGENT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
HEALTH_AGENT_LLM_MODEL=qwen-plus
HEALTH_AGENT_LLM_API_KEY=
HEALTH_AGENT_EMBEDDING_MODEL=text-embedding-v3
HEALTH_AGENT_EMBEDDING_API_KEY=
```

`HEALTH_AGENT_LLM_API_KEY` 未配置时，Agent 聊天接口会返回未配置模型 API Key。embedding key 未单独配置时，后端会尝试复用 LLM API Key。

### 3. 启动后端

```bash
uv sync
.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

健康检查：

```bash
curl http://localhost:8000/api/health
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`。Vite 会代理：

- `/api` -> `http://localhost:8000`
- `/uploads` -> `http://localhost:8000`
- `/mall-products` -> `http://localhost:8000`

## 前端页面

- `/`、`/chat`：家庭健康 Agent 对话。
- `/reports`：健康报告列表和上传。
- `/reports/:documentId`：报告详情、chunk 和健康事实。
- `/report`：健康分析总览。
- `/members`：家庭成员列表。
- `/members/new`、`/members/:memberId`、`/members/:memberId/edit`：成员新增、详情、编辑。
- `/mall`、`/mall/products`、`/mall/products/:productId`、`/mall/cart`：商城首页、商品列表、详情、购物车。
- `/devices`：设备近期状态。
- `/notice`：通知中心。

## 后端 API 概览

- `GET /api/health`：健康检查。
- `/api/members`：成员增删改查和成员报告列表。
- `/api/kb`：报告上传、文档列表、详情、chunk、健康事实、搜索、删除。
- `/api/health-analysis`：家庭健康分析和成员健康分析。
- `/api/devices`：成员设备概览和模拟同步。
- `/api/agent`：会话、消息、流式发送、快捷操作。
- `/api/mall`：商城首页、商品、购物车。
- `/api/notices`：通知列表、摘要、已读、稍后提醒、完成。

## 常用验证

```bash
# 后端测试
PYTHONPATH=backend uv run pytest backend/tests

# 前端构建
cd frontend
npm run build
```

真实服务链路验证：

```bash
PYTHONPATH=backend python backend/scripts/verify_real_services.py
PYTHONPATH=backend python backend/scripts/verify_agent_chat.py
PYTHONPATH=backend python backend/scripts/verify_agent_chat_stream.py
PYTHONPATH=backend python backend/scripts/verify_agent_chat_with_report.py
```

## Milvus 向量库重建

`kb_chunks` 是 SQL 侧 source of truth。需要重建向量库时使用后端脚本。

注意：该操作会 drop 现有 Milvus collection，再按当前 schema 重建。

```bash
cd backend
python -m app.scripts.migrate_kb_member_binding
python -m app.scripts.rebuild_milvus_vectors --dry-run
python -m app.scripts.rebuild_milvus_vectors --limit 50
python -m app.scripts.rebuild_milvus_vectors
```

## 已经迭代规划

项目已经迭代的规划参考 [docs/liangda-health-iteration-roadmap.md](docs/iteration-roadmap_already_completed.md)。

规划优先级：

- P0：统一产品定位和页面文案。
- P1：健康事实库。
- P2：健康画像接入健康事实。
- P3：记忆系统。
- P4：Agent 意图识别和工具路由。
- P5：餐单接商品推荐。
- P6：推荐证据链展示。
- P7：AI 技术增强。

后续新功能需要优先对照 roadmap 和 B2B2C 架构文档；如果实现方向与长期规划冲突，应先暂停确认。

## 开发约定

- 不自动提交代码。
- 开发新页面时，前端界面需要和 `prd/` 目录对应原型保持一致，除非是明确的后续细节调整。
- 新功能框架选型需要优先考虑项目现有技术栈。
- 不擅自改动用户已有改动，包括调试日志、临时验证代码和未提交文件。
- 项目要求、沟通和文档优先使用中文。
