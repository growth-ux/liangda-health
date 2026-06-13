# PDF 报告知识库设计

## 背景

粮达健康需要先实现“上传报告”相关能力。当前范围只包含 PDF 报告知识库，不提前实现健康分析、聊天 Agent、商品推荐、通知等模块。

知识库模块的目标是把用户上传的 PDF 健康报告转换成可存储、可检索、可追溯到页码的知识内容。

## 范围

本阶段实现：

- PDF 文件上传
- PDF 文本提取
- 云 OCR 识别扫描版 PDF
- 页级文本保存
- 简单元数据抽取
- 文本切片
- embedding 生成
- MySQL 保存文档、页文本、chunk
- Milvus 保存 chunk 向量
- 基础知识库搜索

本阶段不实现：

- 异步任务队列
- 人工修正
- 复杂状态机
- 逻辑删除/归档
- 重新索引
- 多租户复杂权限
- 健康指标结构化
- 健康分析
- 聊天 Agent
- 商品推荐

## 技术选型

- 前端：React + TypeScript + Vite
- UI 样式：Tailwind CSS + 少量业务 CSS
- 前端请求：TanStack Query
- 前端路由：React Router
- 前端图标：lucide-react
- 后端：后续实现时可使用 FastAPI 或项目确定的 Web 框架
- 关系数据库：MySQL
- 向量库：Milvus
- 文件类型：仅支持 PDF
- OCR：云 OCR 服务
- PDF 文本提取：PyMuPDF 或同类 PDF 解析库

前端推荐 `React + TypeScript + Vite`，原因是当前项目还没有正式前端工程，Vite 启动成本低，React 组件化适合后续把报告卡片、上传区、搜索结果拆成独立模块。样式参考现有原型 `prd/prototype/reports.html` 和 `prd/prototype/css/style.css`，保持克制、留白、健康绿、卡片式报告宫格的视觉方向。

## 主流程

```text
上传 PDF
→ 提取文本
→ 必要时调用云 OCR
→ 保存页文本
→ 切片
→ 生成 embedding
→ 写入 MySQL
→ 写入 Milvus
→ 支持搜索
```

`POST /kb/upload` 使用同步处理。接口返回成功时，文档已经完成切片和向量入库；接口返回失败时，文档状态为 `failed` 并记录错误信息。

## 数据模型

### kb_documents

保存 PDF 文档信息和基础元数据。

```sql
CREATE TABLE kb_documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id VARCHAR(64) NOT NULL UNIQUE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL,
    page_count INT DEFAULT 0,

    title VARCHAR(255) NULL,
    patient_name VARCHAR(100) NULL,
    exam_date DATE NULL,
    institution VARCHAR(255) NULL,

    status VARCHAR(32) NOT NULL DEFAULT 'processing',
    error_message TEXT NULL,

    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);
```

`status` 只保留最少状态：

- `processing`
- `ready`
- `failed`

### kb_pages

保存每页 PDF 提取出的文本。

```sql
CREATE TABLE kb_pages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    document_id VARCHAR(64) NOT NULL,
    page_no INT NOT NULL,
    text_content LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL,

    INDEX idx_document_page (document_id, page_no)
);
```

### kb_chunks

保存切片文本和页码来源。

```sql
CREATE TABLE kb_chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    chunk_id VARCHAR(64) NOT NULL UNIQUE,
    document_id VARCHAR(64) NOT NULL,
    page_no INT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NOT NULL,

    INDEX idx_document_id (document_id)
);
```

## Milvus Collection

Collection 名称：

```text
kb_chunks_vector
```

字段：

```text
chunk_id      VarChar，主键
document_id   VarChar
embedding     FloatVector
```

Milvus 只负责向量检索。检索命中后，通过 `chunk_id` 回 MySQL 查询完整 chunk 内容、页码和文档信息。

## API 设计

### 上传 PDF

```text
POST /kb/upload
```

请求：

```text
multipart/form-data
file: PDF 文件
```

成功响应：

```json
{
  "document_id": "doc_xxx",
  "status": "ready",
  "page_count": 6,
  "chunk_count": 18
}
```

失败响应：

```json
{
  "document_id": "doc_xxx",
  "status": "failed",
  "error_message": "PDF 解析失败"
}
```

处理步骤：

```text
1. 校验是否 PDF
2. 保存 PDF 到本地目录
3. 创建 kb_documents，状态 processing
4. 用 PDF 工具提取每页文本
5. 如果整份 PDF 没有可用文本，调用云 OCR
6. 保存 kb_pages
7. 简单抽取 title、patient_name、exam_date、institution
8. 按页切片，保存 kb_chunks
9. 调 embedding 模型生成向量
10. 写入 Milvus
11. 更新 kb_documents.status = ready
12. 返回 document_id
```

### 文档列表

```text
GET /kb/documents
```

返回文档列表，包含：

- `document_id`
- `file_name`
- `title`
- `patient_name`
- `exam_date`
- `institution`
- `status`
- `page_count`
- `created_at`

### 文档详情

```text
GET /kb/documents/{document_id}
```

返回文档详情，包含：

- 文档基础信息
- PDF 文件路径
- 页数
- 基础元数据
- 当前状态

### 搜索

```text
POST /kb/search
```

请求：

```json
{
  "query": "骨密度异常",
  "top_k": 5
}
```

处理步骤：

```text
1. 对 query 生成 embedding
2. 在 Milvus 中搜索相似 chunk
3. 使用 chunk_id 回 MySQL 查询 chunk 内容
4. 返回 chunk 内容、document_id、page_no 和 score
```

响应：

```json
{
  "items": [
    {
      "document_id": "doc_xxx",
      "chunk_id": "chunk_xxx",
      "page_no": 3,
      "content": "骨密度 T 值 -2.1，提示骨量减少...",
      "score": 0.86
    }
  ]
}
```

## 前端设计

前端只实现知识库模块自身页面，不提前接入健康分析、聊天或推荐。

页面形态参考 `prd/prototype/reports.html`：

- 顶部工具栏：左侧筛选，右侧排序和上传按钮
- 主体区域：报告卡片宫格
- 第一张卡片：上传新报告入口
- 普通卡片：展示报告标题、检查日期、页数、状态
- 卡片点击：进入文档详情

原型中的家庭成员筛选可以先简化为知识库字段筛选，例如状态、姓名、报告类型。当前数据库只设计了姓名、标题、检查日期、机构，因此第一版前端筛选也只围绕这些字段展开。

### 页面范围

本阶段前端包含 3 个页面或视图：

- 报告列表页
- 上传报告页
- 文档详情页
- 知识库搜索页

也可以先合并成一个页面，通过区域切换完成：

```text
顶部：工具栏和上传入口
中部：报告卡片宫格
右侧或下方：搜索结果
```

推荐先按单页实现，后续再拆路由：

```text
/reports
报告列表 + 上传入口 + 搜索

/reports/:document_id
文档详情
```

### 前端组件划分

最简组件：

```text
ReportToolbar
报告筛选、排序、上传按钮。

ReportGrid
报告卡片宫格，参考 reports.html。

ReportCard
单个报告卡片。

UploadReportDialog
PDF 上传弹窗或上传区域。

DocumentDetail
文档详情。

KbSearchPanel
知识库搜索输入和结果列表。
```

### 报告列表页

用途：

- 展示已经入库的 PDF 报告
- 进入上传流程
- 查看文档基础信息

列表字段：

- 文件名
- 标题
- 姓名
- 检查日期
- 机构
- 页数
- 状态
- 上传时间

视觉表现参考 `reports.html` 的卡片宫格：

```text
上传新报告卡片
→ 虚线边框、居中加号、绿色 hover

报告卡片
→ 白底、浅边框、8px 圆角
→ 顶部浅色预览区
→ 下方标题和元信息
```

状态展示：

- `processing`：处理中
- `ready`：可搜索
- `failed`：处理失败

最简操作：

- 上传新报告
- 查看详情

### 上传报告页

上传页只支持 PDF。

页面元素：

- PDF 拖拽/点击上传区域
- 文件名、文件大小展示
- 上传按钮
- 处理中 loading
- 成功结果
- 失败提示

前端校验：

- 文件扩展名必须是 `.pdf`
- 文件类型应为 `application/pdf`
- 文件大小按后端限制提示

交互流程：

```text
选择 PDF
→ 前端校验
→ 调用 POST /kb/upload
→ 按钮进入处理中
→ 接口成功后展示 document_id、page_count、chunk_count
→ 刷新文档列表
→ 接口失败后展示 error_message
```

因为上传接口是同步处理，前端需要明确提示：

```text
正在解析 PDF 并建立知识库，请勿关闭页面
```

按钮状态：

- 未选择文件：禁用
- 上传处理中：禁用，展示 loading
- 成功/失败后：恢复可操作

### 文档详情页

文档详情页可以先做简单版本。

展示内容：

- 文件名
- 文件路径或下载/预览入口
- 页数
- 标题
- 姓名
- 检查日期
- 机构
- 状态

本阶段不要求做 PDF 在线预览，也不要求展示所有页文本。后续需要核对 OCR 文本时再增加。

### 知识库搜索页

用途：

- 输入问题或关键词
- 搜索 Milvus 中的相关 chunk
- 展示原文片段和页码

页面元素：

- 搜索输入框
- `top_k` 选择，默认 5
- 搜索按钮
- 搜索结果列表

搜索结果字段：

- 原文片段 `content`
- 页码 `page_no`
- 文档 ID `document_id`
- 相似度 `score`

结果展示样式：

```text
第 3 页 · score 0.86
骨密度 T 值 -2.1，提示骨量减少...
```

### 前端错误提示

最简错误提示即可：

- 请选择 PDF 文件
- 文件上传失败
- PDF 解析失败
- 云 OCR 识别失败
- 向量入库失败
- 搜索失败

错误信息优先使用后端返回的 `error_message`。

## 切片规则

先使用最简单规则：

- 按页切片
- 每个 chunk 约 800 中文字符
- 相邻 chunk 重叠 100 字
- 每个 chunk 记录来源 `page_no`

暂时不识别表格、不识别章节。后续如果检索效果不足，再增加表格识别、章节切分或混合检索。

## OCR 规则

优先直接提取 PDF 文本。

如果所有页面提取出的有效文本总长度小于 100 字，则调用云 OCR。

本阶段不做复杂 PDF 类型判断，也不设计多 OCR 兜底。

## 错误处理

上传接口同步执行。任一步失败时：

- `kb_documents.status` 更新为 `failed`
- `error_message` 记录失败原因
- 接口返回失败响应

本阶段不做自动重试。发现需要重试能力后，再增加重新解析或异步任务。

## 成功标准

完成后应满足：

- PDF 可以上传
- 文本可以解析
- 扫描版 PDF 可以通过云 OCR 获取文本
- 页文本可以保存到 MySQL
- 文本可以切片并保存到 MySQL
- chunk 向量可以保存到 Milvus
- 用户可以通过问题搜索知识库
- 搜索结果可以返回原文片段和页码
