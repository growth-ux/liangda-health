# 商城功能设计文档

日期：2026-06-13

## 1. 背景与目标

当前项目已经有：

- `prd/prototype/mall.html`：商城首页原型
- `prd/prototype/product-detail.html`：商品详情原型
- 家人档案能力：家人基础资料、健康标签、过敏信息、口味偏好
- 报告知识库和 Agent 能力：PDF 上传、解析、报告详情、健康问答

商城原型强调“根据家庭健康档案智能推荐”，但当前项目还没有真实商品、推荐和购物车能力。

本次目标是补齐商城最小真实闭环：

1. 支持商城首页展示家庭推荐、健康专区、今日推荐和分类
2. 支持商品详情展示推荐理由、营养信息、推荐搭配和健康提示
3. 支持加入购物车、修改数量、删除商品和购物车确认
4. 推荐逻辑基于现有家人档案的健康标签、BMI、过敏和口味偏好

## 2. 本次范围

### 2.1 包含

- 商城首页 `/mall`
- 商品详情页 `/mall/products/:productId`
- 购物车确认页 `/mall/cart`
- 后端新增 `mall` 领域
- 商品、专区、购物车和推荐搭配的数据库模型
- 初始化一批种子商品数据
- 简单规则推荐
- 商品列表、商品详情、购物车 API

### 2.2 不包含

- 真实支付
- 订单系统
- 收货地址
- 库存扣减
- 优惠券、满减、营销活动
- 售后、退款、退货
- 商品后台管理
- SKU 多规格
- 商品图片上传
- 软删除、上下架审核、复杂状态流转
- 接入大模型生成推荐理由

## 3. 关键决策

### 3.1 功能范围

采用“商品浏览 + 健康推荐 + 商品详情 + 购物车确认”的最简闭环。

原因：

- 完整覆盖当前商城和商品详情原型
- 能形成真实可用流程
- 不引入支付、订单、库存等超出当前阶段的复杂能力
- 符合项目“不要过分设计，只需要最简流程”的要求

### 3.2 商品数据来源

第一版商品数据使用数据库 seed 初始化。

不做商品管理后台，原因是当前目标是用户侧商城闭环。商品后台会引入表单、权限、上下架、图片上传等额外工作，不属于本次范围。

### 3.3 推荐方式

第一版采用代码规则推荐，不接大模型。

原因：

- 当前推荐规则和原型文案都比较明确
- 规则可测试、可解释
- 能直接复用家人档案字段
- 避免推荐结果不稳定

### 3.4 购物车归属

第一版购物车使用固定 `cart_owner_id = "default_family"`。

原因：

- 当前项目还没有登录用户体系
- 商城原型是家庭健康商城，不需要先引入账号和多租户
- 后续接登录时可以把 `cart_owner_id` 替换为用户或家庭 ID

## 4. 后端设计

### 4.1 模块结构

新增以下文件：

- `backend/app/models/mall.py`
- `backend/app/schemas/mall.py`
- `backend/app/repositories/mall_repository.py`
- `backend/app/services/mall_recommendation.py`
- `backend/app/api/mall.py`

现有文件需要改造：

- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/tests/test_api_mall.py`

### 4.2 数据表设计

#### mall_products

商品主表。

```text
id                    int primary key auto increment
product_id            varchar(64) unique not null
name                  varchar(120) not null
brand                 varchar(80) null
category_code         varchar(50) not null
category_name         varchar(50) not null
price_cents           int not null
original_price_cents  int null
spec                  varchar(80) null
sales_text            varchar(40) null
image_emoji           varchar(20) null
description           text null
ingredients           text null
shelf_life            varchar(80) null
nutrition             text null
health_tags           text null
recommend_tags        text null
warning_tags          text null
created_at            datetime not null
updated_at            datetime not null
```

说明：

- `product_id` 采用 `prod_<uuid>` 或固定可读 ID，例如 `prod_low_sodium_soy`
- `nutrition` 存 JSON 字符串数组，例如 `[{"label":"钠含量","value":"≤ 4500 mg / 100ml"}]`
- `health_tags` 存展示标签，例如 `["低钠","非转基因"]`
- `recommend_tags` 存规则标签，例如 `["low_sodium","hypertension"]`
- `warning_tags` 存过敏或禁忌标签，例如 `["soy","wheat"]`

#### mall_zones

专区和分类展示配置。

```text
id          int primary key auto increment
zone_code   varchar(50) unique not null
name        varchar(80) not null
zone_type   varchar(20) not null
icon        varchar(20) null
match_tag   varchar(50) null
sort_order  int not null
```

说明：

- `zone_type = "health"` 表示健康专区，例如低钠、控糖、高钙、低脂
- `zone_type = "category"` 表示分类，例如米面、油品、调味
- `match_tag` 用于筛选商品，例如 `low_sodium`

#### mall_cart_items

购物车表。

```text
id             int primary key auto increment
cart_owner_id  varchar(64) not null
product_id     varchar(64) not null
quantity       int not null
created_at     datetime not null
updated_at     datetime not null
```

说明：

- 第一版 `cart_owner_id` 固定为 `default_family`
- 同一 `cart_owner_id + product_id` 只保留一条记录
- 重复加购时数量累加

#### mall_product_relations

推荐搭配表。

```text
id                  int primary key auto increment
product_id           varchar(64) not null
related_product_id   varchar(64) not null
sort_order           int not null
```

### 4.3 Schema 设计

新增 `mall.py` schema：

```text
MallProductSummary
MallProductDetail
MallZone
MallFamilyRecommendation
MallHomeResponse
MallProductListResponse
MallProductDetailResponse
MallCartItem
MallCartResponse
MallCartItemCreateRequest
MallCartItemUpdateRequest
NutritionRow
```

价格字段后端统一返回：

- `price_cents`
- `original_price_cents`
- `price_text`
- `original_price_text`

说明：

- 金额计算使用分，避免浮点误差
- `price_text` 只用于前端直接展示，例如 `¥19.9`

### 4.4 API 设计

新增商城接口：

```text
GET    /mall/home
GET    /mall/products
GET    /mall/products/{product_id}
GET    /mall/cart
POST   /mall/cart/items
PUT    /mall/cart/items/{product_id}
DELETE /mall/cart/items/{product_id}
```

#### GET /mall/home

返回商城首页所需数据。

响应结构：

```json
{
  "family_recommendations": [
    {
      "member_id": "mem_xxx",
      "member_name": "张桂兰",
      "relation": "妈妈",
      "zone_name": "为妈妈推荐",
      "summary": "低钠 · 高钙",
      "products": []
    }
  ],
  "health_zones": [],
  "daily_products": [],
  "categories": []
}
```

处理逻辑：

1. 查询全部商品
2. 查询全部家人
3. 查询健康专区和分类配置
4. 根据家人档案生成家庭推荐
5. 根据商品标签生成今日推荐
6. 返回首页聚合结果

无家人时不报错，返回全家通用推荐、健康专区、今日推荐和分类。

#### GET /mall/products

返回商品列表。

查询参数：

```text
zone_code      string optional
category_code  string optional
member_id      string optional
limit          int optional
```

规则：

- `zone_code` 用于健康专区筛选
- `category_code` 用于分类筛选
- `member_id` 用于按某个家人进行推荐排序
- 多个参数同时存在时，先筛选再排序

#### GET /mall/products/{product_id}

返回商品详情。

响应结构：

```json
{
  "product": {},
  "recommend_reason": "张桂兰（妈妈）血压偏高，建议替代普通生抽",
  "nutrition_rows": [],
  "related_products": [],
  "health_notice": "本推荐不构成医疗建议"
}
```

规则：

- 商品不存在返回 404 `商品不存在`
- `recommend_reason` 取当前家庭中对该商品评分最高的家人生成
- 无匹配家人时返回通用推荐理由

#### GET /mall/cart

返回购物车。

响应结构：

```json
{
  "items": [
    {
      "product_id": "prod_low_sodium_soy",
      "name": "薄盐生抽 500ml",
      "spec": "500ml",
      "image_emoji": "🧴",
      "price_cents": 1990,
      "price_text": "¥19.9",
      "quantity": 2,
      "subtotal_cents": 3980,
      "subtotal_text": "¥39.8"
    }
  ],
  "total_quantity": 2,
  "total_cents": 3980,
  "total_text": "¥39.8"
}
```

#### POST /mall/cart/items

加入购物车。

请求：

```json
{
  "product_id": "prod_low_sodium_soy",
  "quantity": 2
}
```

规则：

- 商品不存在返回 404 `商品不存在`
- `quantity <= 0` 返回 400 `商品数量必须大于 0`
- 同商品已在购物车时累加数量
- 成功后返回最新购物车

#### PUT /mall/cart/items/{product_id}

修改购物车数量。

请求：

```json
{
  "quantity": 3
}
```

规则：

- 商品不在购物车返回 404 `购物车商品不存在`
- `quantity <= 0` 返回 400 `商品数量必须大于 0`
- 成功后返回最新购物车

#### DELETE /mall/cart/items/{product_id}

删除购物车商品。

规则：

- 商品不在购物车返回 404 `购物车商品不存在`
- 成功后返回 204

### 4.5 Repository 设计

新增 `SqlAlchemyMallRepository`，提供：

- `list_products`
- `get_product`
- `list_zones`
- `list_related_products`
- `list_cart_items`
- `add_cart_item`
- `update_cart_item`
- `delete_cart_item`
- `seed_default_data`

`seed_default_data` 只在表为空时初始化默认商品、专区和推荐搭配。

### 4.6 推荐服务设计

新增 `mall_recommendation.py`，提供：

- `build_member_recommendations(members, products)`
- `score_product_for_member(member, product)`
- `build_recommend_reason(member, product)`
- `filter_allergy_products(member, products)`

评分规则：

```text
高血压/血压偏高 + low_sodium       +50
糖尿病/血糖偏高/控糖 + sugar_control/low_gi/no_sugar  +50
BMI >= 24 + low_fat/high_protein    +30
年龄 < 18 + high_calcium            +30
过敏字段命中 warning_tags            排除
口味偏好命中分类或标签               +10
```

推荐理由示例：

- `张桂兰（妈妈）血压偏高，建议优先选择低钠调味品。`
- `爸爸有控糖需求，低 GI 主食更适合作为白米替代。`
- `该商品适合全家日常健康饮食，本推荐不构成医疗建议。`

### 4.7 错误处理

- 商品不存在：404 `商品不存在`
- 家人不存在：404 `家人不存在`
- 购物车商品不存在：404 `购物车商品不存在`
- 加购数量非法：400 `商品数量必须大于 0`
- 首页无商品：返回空数组，不报错
- 首页无成员：返回全家通用推荐，不报错

## 5. 前端设计

### 5.1 API 文件

新增：

- `frontend/src/api/mall.ts`

导出类型和请求函数：

- `getMallHome`
- `listMallProducts`
- `getMallProduct`
- `getMallCart`
- `addMallCartItem`
- `updateMallCartItem`
- `deleteMallCartItem`

React Query key：

- `['mall', 'home']`
- `['mall', 'products', params]`
- `['mall', 'product', productId]`
- `['mall', 'cart']`

### 5.2 页面

#### MallPage

新增：

- `frontend/src/pages/MallPage.tsx`

路由：

```text
/mall
```

页面结构对应 `prd/prototype/mall.html`：

1. 顶部提示条
2. Banner
3. 为你家庭推荐
4. 健康专区
5. 今日猜你想买
6. 分类
7. 购物车入口

交互：

- 点击商品卡片进入 `/mall/products/:productId`
- 点击健康专区筛选商品
- 点击分类筛选商品
- 点击“换一批”本地轮换 `daily_products`

#### MallProductDetailPage

新增：

- `frontend/src/pages/MallProductDetailPage.tsx`

路由：

```text
/mall/products/:productId
```

页面结构对应 `prd/prototype/product-detail.html`：

1. 返回商城
2. 商品图、名称、品牌、规格、销量
3. 价格和原价
4. 健康标签
5. 推荐理由
6. 营养和配料表格
7. 数量选择器
8. 加入购物车
9. 立即购买
10. 推荐搭配
11. 健康提示

交互：

- 加入购物车成功后提示 `已加入购物车`
- 立即购买先加入购物车，再跳转 `/mall/cart`
- 推荐搭配商品点击后进入对应详情页

#### MallCartPage

新增：

- `frontend/src/pages/MallCartPage.tsx`

路由：

```text
/mall/cart
```

页面结构：

1. 购物车商品列表
2. 数量加减
3. 删除商品
4. 合计金额
5. 确认购买

交互：

- 数量加减成功后刷新购物车
- 删除成功后刷新购物车
- 购物车为空时显示空状态和“去商城看看”
- 点击确认购买显示提示：`当前版本已生成购买清单，请联系门店确认配送`

### 5.3 组件

新增目录：

- `frontend/src/components/mall/`

新增组件：

- `MallBanner.tsx`
- `ZoneGrid.tsx`
- `ProductCard.tsx`
- `RecommendationReason.tsx`
- `QuantityStepper.tsx`
- `CartSummary.tsx`

组件职责：

- `MallBanner`：商城顶部宣传区
- `ZoneGrid`：家庭推荐、健康专区、分类卡片通用网格
- `ProductCard`：首页推荐和推荐搭配商品卡片
- `RecommendationReason`：商品详情推荐理由
- `QuantityStepper`：数量加减
- `CartSummary`：购物车总价和确认按钮

### 5.4 路由和导航

修改 `frontend/src/main.tsx`：

```tsx
<Route path="/mall" element={<MallPage />} />
<Route path="/mall/products/:productId" element={<MallProductDetailPage />} />
<Route path="/mall/cart" element={<MallCartPage />} />
```

修改 `frontend/src/components/AppShell.tsx`：

```ts
{ id: 'mall', icon: ShoppingBag, label: '商城', href: '/mall' }
```

### 5.5 样式

继续使用：

- `frontend/src/styles.css`

要求：

- 视觉对齐 `prd/prototype/mall.html` 和 `prd/prototype/product-detail.html`
- 不引入新的 UI 库
- 商品图第一版使用 emoji 或现有 CSS 图形
- 桌面端商品卡片 4 到 5 列
- 移动端商品卡片 2 列
- 页面卡片、按钮、标签延续现有项目风格

## 6. 数据流

### 6.1 商城首页

```text
MallPage
  -> getMallHome()
  -> 后端查询商品、家人、专区
  -> 推荐服务计算家庭推荐和今日推荐
  -> 前端渲染专区和商品卡片
```

### 6.2 商品详情

```text
MallProductDetailPage
  -> getMallProduct(productId)
  -> 后端查询商品、家人、推荐搭配
  -> 推荐服务生成推荐理由
  -> 前端渲染详情和加购按钮
```

### 6.3 加入购物车

```text
详情页点击加入购物车
  -> addMallCartItem({ product_id, quantity })
  -> 后端校验商品和数量
  -> 新增或累加购物车记录
  -> 返回最新购物车
  -> 前端提示成功并刷新 cart query
```

### 6.4 购物车确认

```text
MallCartPage
  -> getMallCart()
  -> 后端查询购物车和商品
  -> 计算小计、总数量、总价
  -> 前端展示购买清单
```

## 7. 测试设计

### 7.1 后端测试

新增：

- `backend/tests/test_api_mall.py`

覆盖：

1. `GET /mall/home` 能返回健康专区、分类和今日推荐
2. 高血压成员优先推荐低钠商品
3. 糖尿病成员优先推荐控糖商品
4. 过敏命中商品不出现在该成员推荐里
5. `GET /mall/products/{product_id}` 返回商品详情和推荐搭配
6. 商品不存在返回 404
7. 加购同商品会累加数量
8. 修改购物车数量成功
9. 修改数量为 0 返回 400
10. 删除购物车商品成功

### 7.2 前端验证

执行：

```bash
cd frontend
npm run build
```

浏览器验证：

- `/mall` 能正常展示商城首页
- 商城导航入口可点击
- 商品卡片进入详情页
- 详情页加入购物车成功
- 立即购买跳转购物车
- 购物车数量修改、删除和空状态正常

## 8. 实施顺序

1. 新增后端 mall 模型、schema、repository 和 API
2. 增加默认商品、专区和推荐搭配 seed
3. 增加规则推荐服务
4. 增加后端 API 测试
5. 新增前端 mall API 文件
6. 新增商城首页
7. 新增商品详情页
8. 新增购物车确认页
9. 接入路由和侧边栏导航
10. 构建并浏览器验证

## 9. 风险与约束

- 当前无登录体系，购物车只能使用固定家庭 ID
- 当前商品图片用 emoji 或 CSS 图形，无法表达真实商品包装
- 推荐规则依赖家人健康标签质量，标签过少时推荐会偏通用
- 当前不做订单和支付，因此“确认购买”只生成提示，不形成交易记录

## 10. 验收标准

1. 用户能从侧边栏进入商城
2. 商城首页内容来自后端接口，不是纯前端静态数据
3. 家庭推荐能基于至少一个家人的健康标签产生差异化推荐
4. 商品详情展示推荐理由、营养信息、推荐搭配和健康提示
5. 用户能加入购物车、修改数量、删除商品
6. 用户能进入购物车确认页并看到总价
7. 不出现支付、订单、地址、库存等超出本次范围的功能
