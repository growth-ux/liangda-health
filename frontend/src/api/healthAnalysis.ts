const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type HealthAnalysisRange = 'this_month' | 'last_3_months' | 'last_6_months' | 'last_12_months';

export type HealthAnalysisOverview = {
  family: {
    name: string;
    period_label: string;
  };
  metrics: {
    family_score: number;
    family_score_delta: number;
    attention_count: number;
    report_count: number;
    device_count: number;
  };
  summary: {
    level: 'danger' | 'warning' | 'success' | 'info';
    text: string;
  }[];
  abnormal_items: {
    metric: string;
    member_id: string;
    member_name: string;
    member_relation: string;
    current_value: string;
    status: 'danger' | 'warning';
    status_text: string;
    trend_text: string;
    suggestion: string;
  }[];
  member_cards: {
    member_id: string;
    name: string;
    relation: string;
    age: number;
    health_score: number;
    status: 'success' | 'warning' | 'danger';
    status_text: string;
    avatar_text: string;
  }[];
};

export type HealthAnalysisMember = {
  member_card: HealthAnalysisOverview['member_cards'][number];
  indicators: {
    key: string;
    label: string;
    value: string;
    unit: string | null;
    status: 'danger' | 'warning' | 'success' | 'info';
    status_text: string;
  }[];
  blood_pressure_7d: {
    date: string;
    systolic: number;
    diastolic: number;
  }[];
  abnormalities: HealthAnalysisOverview['abnormal_items'];
  advice: {
    title: string;
    lines: string[];
    prompt: string;
  };
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

export async function getHealthAnalysisOverview(range: HealthAnalysisRange): Promise<HealthAnalysisOverview> {
  const params = new URLSearchParams({ range });
  const response = await fetch(`${API_BASE}/api/health-analysis/overview?${params.toString()}`);
  return readJson<HealthAnalysisOverview>(response, '获取健康分析失败');
}

export async function getMemberHealthAnalysis(memberId: string): Promise<HealthAnalysisMember> {
  const response = await fetch(`${API_BASE}/api/health-analysis/members/${memberId}`);
  return readJson<HealthAnalysisMember>(response, '获取成员健康分析失败');
}
