const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type DashboardOverview = {
  member_count: number;
  report_count: number;
  health_fact_count: number;
  session_count: number;
  message_count: number;
  recommendation_count: number;
  cart_item_count: number;
  cart_amount_yuan: number;
};

export type DashboardAiUsage = {
  model_name: string | null;
  token_prompt_total: number;
  token_completion_total: number;
  estimated_cost_yuan: number;
};

export type FunnelStep = {
  name: string;
  value: number;
};

export type BrandRankItem = {
  brand: string;
  category_name: string | null;
  recommend_count: number;
  cart_count: number;
  amount_yuan: number;
};

export type CategoryPenetrationItem = {
  category_name: string;
  recommend_count: number;
};

export type DashboardDailyPoint = {
  date: string;
  message_count: number;
  recommendation_count: number;
};

export type DashboardFactStatus = {
  normal: number;
  warning: number;
  danger: number;
};

export type DashboardNoticeDoneRate = {
  total: number;
  done: number;
  rate: number;
};

export type NameCountItem = {
  name: string;
  count: number;
};

export type MemberProfile = {
  gender_distribution: NameCountItem[];
  relation_distribution: NameCountItem[];
  age_bands: NameCountItem[];
  health_tag_cloud: NameCountItem[];
};

export type FactRiskItem = {
  name: string;
  warning_count: number;
  danger_count: number;
};

export type RiskMemberItem = {
  member_id: string;
  member_name: string;
  relation: string | null;
  danger_count: number;
  warning_count: number;
};

export type HeatmapPoint = {
  weekday: number;
  hour: number;
  count: number;
};

export type CardUsageItem = {
  kind: string;
  count: number;
};

export type SessionDepth = {
  session_count: number;
  avg_user_turns: number;
  max_user_turns: number;
};

export type HotProductItem = {
  product_id: string;
  name: string;
  brand: string | null;
  category_name: string | null;
  image_emoji: string | null;
  price_yuan: number;
  recommend_count: number;
  cart_count: number;
  amount_yuan: number;
};

export type LiveEventType = 'report_upload' | 'fact_extract' | 'ai_recommend' | 'ai_card' | 'cart_add';

export type LiveEvent = {
  event_type: LiveEventType;
  text: string;
  occurred_at: string;
};

export type DashboardResponse = {
  overview: DashboardOverview;
  ai_usage: DashboardAiUsage;
  funnel: FunnelStep[];
  brand_ranks: BrandRankItem[];
  category_penetration: CategoryPenetrationItem[];
  daily_trend: DashboardDailyPoint[];
  fact_status: DashboardFactStatus;
  notice_done: DashboardNoticeDoneRate;
  member_profile: MemberProfile;
  fact_risk_top: FactRiskItem[];
  risk_members: RiskMemberItem[];
  interaction_heatmap: HeatmapPoint[];
  card_usage: CardUsageItem[];
  session_depth: SessionDepth;
  hot_products: HotProductItem[];
  live_events: LiveEvent[];
};

export async function getDashboard(): Promise<DashboardResponse> {
  const response = await fetch(`${API_BASE}/api/admin/dashboard`);
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json') || !response.ok) {
    throw new Error('获取经营看板数据失败');
  }
  return response.json();
}
