const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type NutritionRow = {
  label: string;
  value: string;
};

export type MallProduct = {
  product_id: string;
  name: string;
  brand: string | null;
  category_code: string;
  category_name: string;
  price_cents: number;
  price_text: string;
  original_price_cents: number | null;
  original_price_text: string | null;
  spec: string | null;
  sales_text: string | null;
  image_emoji: string | null;
  image_url: string | null;
  health_tags: string[];
  recommend_reason: string | null;
};

export type MallProductDetail = MallProduct & {
  description: string | null;
  ingredients: string | null;
  shelf_life: string | null;
  nutrition_rows: NutritionRow[];
  warning_tags: string[];
};

export type MallZone = {
  zone_code: string;
  name: string;
  zone_type: string;
  icon: string | null;
  match_tag: string | null;
  sort_order: number;
};

export type MallFamilyRecommendation = {
  member_id: string;
  member_name: string;
  relation: string;
  zone_name: string;
  summary: string;
  products: MallProduct[];
};

export type MallHomeResponse = {
  family_recommendations: MallFamilyRecommendation[];
  health_zones: MallZone[];
  daily_products: MallProduct[];
  categories: MallZone[];
};

export type MallProductListResponse = {
  products: MallProduct[];
  zone: MallZone | null;
};

export type MallProductDetailResponse = {
  product: MallProductDetail;
  recommend_reason: string | null;
  nutrition_rows: NutritionRow[];
  related_products: MallProduct[];
  health_notice: string;
};

export type MallCartItem = {
  product_id: string;
  name: string;
  spec: string | null;
  image_emoji: string | null;
  image_url: string | null;
  price_cents: number;
  price_text: string;
  quantity: number;
  subtotal_cents: number;
  subtotal_text: string;
};

export type MallCartResponse = {
  items: MallCartItem[];
  total_quantity: number;
  total_cents: number;
  total_text: string;
};

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    throw new Error(fallback);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? fallback);
  }
  return response.json();
}

export async function getMallHome(): Promise<MallHomeResponse> {
  const response = await fetch(`${API_BASE}/mall/home`);
  return readJson<MallHomeResponse>(response, '获取商城首页失败');
}

export async function listMallProducts(params?: {
  zone_code?: string;
  category_code?: string;
  member_id?: string;
  limit?: number;
}): Promise<MallProductListResponse> {
  const search = new URLSearchParams();
  if (params?.zone_code) search.set('zone_code', params.zone_code);
  if (params?.category_code) search.set('category_code', params.category_code);
  if (params?.member_id) search.set('member_id', params.member_id);
  if (params?.limit) search.set('limit', String(params.limit));
  const query = search.toString();
  const url = `${API_BASE}/mall/products${query ? `?${query}` : ''}`;
  const response = await fetch(url);
  return readJson<MallProductListResponse>(response, '获取商品列表失败');
}

export async function getMallProduct(productId: string): Promise<MallProductDetailResponse> {
  const response = await fetch(`${API_BASE}/mall/products/${productId}`);
  return readJson<MallProductDetailResponse>(response, '获取商品详情失败');
}

export async function getMallCart(): Promise<MallCartResponse> {
  const response = await fetch(`${API_BASE}/mall/cart`);
  return readJson<MallCartResponse>(response, '获取购物车失败');
}

export async function addMallCartItem(productId: string, quantity: number): Promise<MallCartResponse> {
  const response = await fetch(`${API_BASE}/mall/cart/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, quantity })
  });
  return readJson<MallCartResponse>(response, '加入购物车失败');
}

export async function updateMallCartItem(productId: string, quantity: number): Promise<MallCartResponse> {
  const response = await fetch(`${API_BASE}/mall/cart/items/${productId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity })
  });
  return readJson<MallCartResponse>(response, '修改购物车失败');
}

export async function deleteMallCartItem(productId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/mall/cart/items/${productId}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? '删除购物车商品失败');
  }
}
