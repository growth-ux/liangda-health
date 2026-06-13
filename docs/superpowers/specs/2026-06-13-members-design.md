# 家人功能设计文档

日期：2026-06-13

## 1. 背景与目标

当前项目已经有：

- `prd/prototype/members.html`：家人列表原型
- `prd/prototype/add-member.html`：添加家人原型
- `prd/prototype/member-detail.html`：家人详情原型
- 报告知识库能力：PDF 上传、解析、OCR、向量入库、报告列表和详情

当前项目还没有真实的家人数据模型。前端报告页使用姓名正则临时判断“妈妈/爸爸/我/女儿”，这无法支撑真实的家人档案和报告归属。

本次目标是补齐“家人”功能的最小真实闭环，并严格控制范围，不做额外扩展：

1. 支持新增、编辑、查看家人
2. 支持报告上传时明确归属到某个家人
3. 家人列表和详情展示该家人的真实关联报告
4. 报告页基于真实 `member_id` 进行筛选，不再使用姓名猜测

## 2. 本次范围

### 2.1 包含

- 家人列表页
- 添加家人页
- 编辑家人页
- 家人详情页
- 报告上传弹窗增加“归属家人”必选项
- 后端新增 `members` 领域
- 报告表增加 `member_id`
- 报告列表返回成员信息

### 2.2 不包含

- 家人头像上传
- 自动按 OCR 姓名匹配家人
- 报告上传后再二次归档
- 关键健康指标结构化入库
- 血压趋势图真实数据
- Agent 长期建议真实生成
- 软删除、回收站、解绑历史
- 一份报告关联多个家人

## 3. 关键决策

### 3.1 报告归属方式

采用“上传时手动选择家人”的方式。

原因：

- 与当前确认范围一致
- 交互简单，落地最直接
- 避免 OCR 识别姓名不准带来的错误归属
- 符合当前项目“最简实现”的要求

### 3.2 家人详情页内容

本次家人详情页只展示真实已有数据：

- 成员基础资料
- 健康标签
- 忌口和口味偏好
- 关联报告列表

不做原型里的关键健康指标、趋势图和长期建议真实能力，也不放静态 mock 数据。

### 3.3 数据建模方案

采用“`members` 表 + `kb_documents.member_id` 直接关联”的方案。

不采用单独的关系表，原因是当前没有“一份报告归属多人”的需求，独立映射表会引入多余复杂度。

## 4. 后端设计

### 4.1 模块结构

新增以下文件：

- `backend/app/models/member.py`
- `backend/app/schemas/member.py`
- `backend/app/repositories/member_repository.py`
- `backend/app/api/members.py`

现有文件需要改造：

- `backend/app/models/kb.py`
- `backend/app/schemas/kb.py`
- `backend/app/repositories/kb_repository.py`
- `backend/app/services/kb_service.py`
- `backend/app/api/kb.py`
- `backend/app/main.py`
- `backend/app/db/session.py` 或单独的数据库初始化函数

### 4.2 数据表设计

#### members

字段如下：

```text
id                 int primary key auto increment
member_id          varchar(64) unique not null
name               varchar(100) not null
relation           varchar(50) not null
gender             varchar(10) not null
birth_year         int not null
phone              varchar(30) null
height_cm          int null
weight_kg          int null
health_tags        text null
allergies          varchar(255) null
taste_preferences  varchar(255) null
created_at         datetime not null
updated_at         datetime not null
```

说明：

- `member_id` 采用和现有 `document_id`、`session_id` 一致的字符串主业务键，例如 `mem_<uuid>`
- `health_tags` 使用 JSON 字符串数组存储，例如 `["高血压","高血脂"]`
- 不引入独立标签表，避免超出当前范围

#### kb_documents

新增字段：

```text
member_id varchar(64) null index
```

说明：

- 新字段允许为 `null`，仅用于兼容历史数据
- 本次新增上传流程中，`member_id` 为必填
- 不在数据库层加外键约束，保持当前项目风格简单一致

### 4.3 Schema 设计

新增 `member.py` schema：

```text
MemberCreateRequest
MemberUpdateRequest
MemberListItem
MemberDetail
MemberDocumentItem
```

核心字段：

- `name`
- `relation`
- `gender`
- `birth_year`
- `phone`
- `height_cm`
- `weight_kg`
- `health_tags`
- `allergies`
- `taste_preferences`

`MemberListItem` 额外返回：

- `age`
- `report_count`
- `recent_documents`

`MemberDetail` 额外返回：

- `age`
- `bmi`

年龄和 BMI 在 schema 层计算即可，和当前 `kb.py` 中 `thumbnail_url` 的做法一致。

### 4.4 API 设计

新增成员接口：

```text
GET    /members
POST   /members
GET    /members/{member_id}
PUT    /members/{member_id}
DELETE /members/{member_id}
GET    /members/{member_id}/documents
```

接口职责：

- `GET /members`
  - 返回家人列表
  - 每个成员附带 `report_count`
  - 每个成员附带最近 3 份报告概要
- `POST /members`
  - 创建家人
- `GET /members/{member_id}`
  - 返回家人基础资料
- `PUT /members/{member_id}`
  - 更新家人资料
- `DELETE /members/{member_id}`
  - 仅允许删除没有任何报告的家人
- `GET /members/{member_id}/documents`
  - 返回该家人的全部报告列表

改造报告接口：

#### POST /kb/upload

由当前仅接收 `file` 改为接收：

```text
file: PDF
member_id: string
```

处理逻辑：

1. 校验文件为 PDF
2. 校验 `member_id` 已传且成员存在
3. 创建 `kb_documents` 记录时写入 `member_id`
4. 执行原有 PDF 解析、OCR、分块、向量入库
5. 返回原有上传结果

#### GET /kb/documents

返回字段增加：

- `member_id`
- `member_name`
- `member_relation`

#### GET /kb/documents/{document_id}

返回字段增加：

- `member_id`
- `member_name`
- `member_relation`

### 4.5 Repository 设计

新增 `SqlAlchemyMemberRepository`，提供：

- `create_member`
- `list_members`
- `get_member`
- `update_member`
- `delete_member`
- `list_documents`
- `exists_by_member_id`
- `count_documents`

`GET /members` 的聚合方式采用最简单策略：

1. 先查全部 members
2. 再批量查这些 member_id 对应的 documents
3. 在 Python 内存中完成：
   - 每个成员的 `report_count`
   - 最近 3 份报告的筛选和排序

原因：

- 当前数据量小
- 可读性强
- 避免复杂 SQL 聚合
- 更符合现有仓储层风格

### 4.6 数据初始化与表结构更新

当前项目使用 `Base.metadata.create_all()`，没有 Alembic。

这会带来一个明确限制：

- 新增 `members` 表可以自动创建
- 现有 `kb_documents` 新增列不会被 `create_all()` 自动补齐

因此本次需要补一个最小数据库初始化动作，为 `kb_documents` 增加 `member_id` 列。

推荐落地方式：

- 在应用启动阶段执行一次轻量 SQL 检查
- 若 `kb_documents.member_id` 不存在，则执行：

```sql
ALTER TABLE kb_documents ADD COLUMN member_id VARCHAR(64) NULL;
CREATE INDEX ix_kb_documents_member_id ON kb_documents (member_id);
```

目的只是让当前项目在没有迁移框架的前提下可运行，不引入完整迁移体系。

## 5. 前端设计

### 5.1 路由

新增：

```text
/members
/members/new
/members/:memberId
/members/:memberId/edit
```

并将侧边栏中的“家人”导航改成真实链接：

```text
to="/members"
```

### 5.2 前端 API

新增文件：

- `frontend/src/api/members.ts`

包含：

- `listMembers`
- `createMember`
- `getMember`
- `updateMember`
- `deleteMember`
- `listMemberDocuments`

改造：

- `frontend/src/api/kb.ts`

`uploadPdf` 入参从：

```ts
uploadPdf(file: File)
```

改为：

```ts
uploadPdf({ file, memberId }: { file: File; memberId: string })
```

`KbDocument` 类型增加：

- `member_id?: string | null`
- `member_name?: string | null`
- `member_relation?: string | null`

### 5.3 页面与组件

新增页面：

- `frontend/src/pages/MembersPage.tsx`
- `frontend/src/pages/MemberFormPage.tsx`
- `frontend/src/pages/MemberDetailPage.tsx`

新增组件：

- `frontend/src/components/members/MemberCard.tsx`
- `frontend/src/components/members/MemberForm.tsx`
- `frontend/src/components/members/MemberReportList.tsx`
- `frontend/src/components/members/HealthTagPicker.tsx`

### 5.4 家人列表页

页面对齐 `prd/prototype/members.html`：

- 顶部标题“家庭成员”
- 右上角“添加家人”按钮
- 两列卡片网格

卡片展示：

- 头像块
- 姓名
- 关系
- 性别 / 年龄 / 身高 / 体重
- 健康标签
- 报告区块
- 最近 3 份报告

无报告时显示：

- `暂无报告`

点击整张卡片进入详情页。

### 5.5 头像规则

本次不做头像上传，按关系映射颜色与显示文字：

- 父亲/爸爸：蓝色
- 母亲/妈妈：粉色
- 本人：橙色
- 儿子/女儿：绿色
- 其他：紫色

头像内容优先显示姓名首字或姓氏。

### 5.6 添加/编辑家人页

页面对齐 `prd/prototype/add-member.html`，字段包括：

- 姓名，必填
- 关系，必填
- 性别，必填
- 出生年，必填
- 手机号，可选
- 身高，可选
- 体重，可选
- 已知慢病/健康标签，可选
- 过敏 / 忌口，可选
- 口味偏好，可选

健康标签采用预设可点击选项，不做自由输入。预设值直接取原型中的标签：

- 高血压
- 糖尿病
- 高血脂
- 骨质疏松
- 痛风
- 心血管疾病
- 胃肠疾病

新增页操作：

- 取消
- 保存
- 保存并上传报告

编辑页操作：

- 取消
- 保存

“保存并上传报告”的行为：

1. 先创建成员
2. 成功后跳转到报告页并自动打开上传弹窗
3. 弹窗默认选中刚创建的成员

### 5.7 家人详情页

本次详情页只展示真实已有数据，不补假模块。

页面结构：

1. 返回链接
2. 头部资料区
3. 报告列表区

头部资料区展示：

- 头像
- 姓名
- 关系
- 年龄
- 身高
- 体重
- BMI
- 健康标签
- 忌口 / 过敏
- 口味偏好

头部操作按钮：

- 上传报告
- 编辑

报告列表区：

- 展示当前家人的全部报告
- 排序按上传时间倒序
- 复用现有报告卡片样式能力，但不需要再显示“上传新报告”卡片

无报告时显示空状态和上传按钮。

### 5.8 报告上传弹窗改造

改造 `UploadReportDialog`：

- 增加家人选择下拉框
- 必须选中家人后才能提交
- 打开弹窗时加载成员列表

交互规则：

- 如果从报告页进入，默认不选中成员，必须手动选择
- 如果从家人详情页进入，默认选中当前成员
- 如果当前没有任何家人，弹窗内显示“请先添加家人”，并禁用上传提交

不做自动识别家人，不做 OCR 姓名预匹配。

### 5.9 报告页改造

当前 `ReportsPage` 中 `getFamily()` 使用姓名正则归类。

本次改为基于真实 `member_id` 归类。

改造点：

- 家人筛选项来自成员接口，不再写死“妈妈/爸爸/我/女儿”
- “全部”保留
- 每个筛选项显示成员姓名和报告数
- 排序仍保留：
  - 按上传时间
  - 按检查日期
  - 按家人

报告卡片增加成员信息展示：

- `member_name`
- `member_relation`

## 6. 交互流程

### 6.1 新增家人

```text
成员列表页
  -> 点击“添加家人”
  -> 填写表单
  -> 点击“保存”
  -> 返回成员列表并显示新卡片
```

### 6.2 新增家人后直接上传报告

```text
成员列表页
  -> 点击“添加家人”
  -> 填写表单
  -> 点击“保存并上传报告”
  -> 创建成功
  -> 进入报告页
  -> 自动打开上传弹窗
  -> 默认选中刚创建的成员
```

### 6.3 从家人详情上传报告

```text
家人详情页
  -> 点击“上传报告”
  -> 打开上传弹窗
  -> 默认选中当前成员
  -> 上传完成后刷新详情页报告列表
```

### 6.4 从报告页上传报告

```text
报告页
  -> 点击“上传新报告”
  -> 打开上传弹窗
  -> 手动选择家人
  -> 上传完成后刷新报告列表
```

## 7. 错误处理

只保留必要错误提示：

- 成员必填字段缺失：`400`
- 成员不存在：`404`
- 上传时未传 `member_id`：`400`
- 上传时 `member_id` 不存在：`404`
- 非 PDF 文件：沿用现有 `400`
- 删除不存在成员：`404`
- 删除已有报告成员：`400`，提示“该家人已有报告，不能删除”

前端展示保持简单：

- 表单校验错误显示在字段或表单顶部
- 上传错误显示在弹窗错误区域
- 列表加载失败显示统一错误提示框

## 8. 测试设计

### 8.1 后端测试

新增或补充以下测试：

- `test_members_create_and_list`
- `test_members_detail_returns_member`
- `test_members_update`
- `test_members_delete_without_documents`
- `test_members_delete_with_documents_rejected`
- `test_member_documents_endpoint_returns_only_member_documents`
- `test_kb_upload_requires_member_id`
- `test_kb_upload_rejects_unknown_member_id`
- `test_kb_document_list_contains_member_info`
- `test_kb_document_detail_contains_member_info`

测试方式延续现有风格：

- API 层使用 `FastAPI TestClient`
- Repository / 假数据可沿用 `FakeDb`
- 需要时使用现有 `db_session` fixture

### 8.2 前端验证

本次前端不强制补单元测试，优先保证构建和联调可运行。

至少执行：

```bash
cd frontend && npm run build
cd backend && pytest
```

如果实现中新增明显的复杂纯函数，再按需要补局部测试。

## 9. 实施边界

本次完成后，系统能力应达到：

1. 家人信息可新增、编辑、查看
2. 报告上传必须归属一个家人
3. 家人列表显示真实报告数量和最近报告
4. 家人详情显示真实关联报告
5. 报告页基于真实成员关联筛选

本次不会解决：

1. 历史报告自动归属
2. 报告内容结构化成健康指标
3. 家庭全局健康汇总
4. 家人删除后的复杂数据迁移

## 10. 实施建议顺序

建议按以下顺序实现：

1. 新增 `members` model/schema/repository/api
2. 为 `kb_documents` 增加 `member_id`
3. 改造 `POST /kb/upload`
4. 改造 `GET /kb/documents` 和详情返回成员信息
5. 新增前端 members API 和路由
6. 实现家人列表页
7. 实现家人表单页
8. 实现家人详情页
9. 改造上传弹窗
10. 改造报告页筛选逻辑
11. 补测试并验证
