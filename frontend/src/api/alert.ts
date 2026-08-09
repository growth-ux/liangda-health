const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type MetricType =
  | 'systolic_bp' | 'diastolic_bp' | 'heart_rate' | 'steps' | 'sleep_hours' | 'blood_oxygen'
  | 'health_fact' | 'health_trend' | 'recheck';
export type Operator = '>' | '<' | '>=' | '<=';
export type Channel = 'in_app' | 'sms' | 'both';

export type AlertRuleItem = {
  rule_id: string;
  member_id: string;
  member_name: string | null;
  member_relation: string | null;
  metric_type: MetricType;
  metric_type_text: string;
  operator: Operator;
  threshold: number;
  channel: Channel;
  enabled: boolean;
  created_at: string;
};

export type AlertRuleCreatePayload = {
  member_id: string;
  metric_type: MetricType;
  operator: Operator;
  threshold: number;
  channel: Channel;
};

export type AlertRuleUpdatePayload = {
  metric_type?: MetricType;
  operator?: Operator;
  threshold?: number;
  channel?: Channel;
  enabled?: boolean;
};

export type AlertRuleListResponse = {
  rules: AlertRuleItem[];
  member_coverage: Record<string, boolean>;
};

export type SmsConfig = {
  id: number;
  provider: string;
  api_key: string;
  api_secret: string;
  signature: string;
  template_id: string;
  enabled: boolean;
  created_at: string;
};

export type SmsConfigSavePayload = {
  provider: string;
  api_key: string;
  api_secret: string;
  signature: string;
  template_id: string;
  enabled: boolean;
};

export type SmsConfigResponse = {
  config: SmsConfig | null;
};

export type SmsTestResponse = {
  status: string;
  message: string;
};

export type SmsLogItem = {
  id: number;
  rule_id: string;
  member_id: string;
  phone: string;
  content: string;
  status: string;
  created_at: string;
};

export type SmsLogListResponse = {
  logs: SmsLogItem[];
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

// ── 预警规则 ──────────────────────────────────────────────────────────────

export async function listAlertRules(): Promise<AlertRuleListResponse> {
  const response = await fetch(`${API_BASE}/api/settings/alert-rules`);
  return readJson<AlertRuleListResponse>(response, '获取预警规则列表失败');
}

export async function createAlertRule(payload: AlertRuleCreatePayload): Promise<AlertRuleItem> {
  const response = await fetch(`${API_BASE}/api/settings/alert-rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return readJson<AlertRuleItem>(response, '创建预警规则失败');
}

export async function updateAlertRule(ruleId: string, payload: AlertRuleUpdatePayload): Promise<AlertRuleItem> {
  const response = await fetch(`${API_BASE}/api/settings/alert-rules/${ruleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return readJson<AlertRuleItem>(response, '更新预警规则失败');
}

export async function deleteAlertRule(ruleId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/settings/alert-rules/${ruleId}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? '删除预警规则失败');
  }
}

// ── 短信配置 ──────────────────────────────────────────────────────────────

export async function getSmsConfig(): Promise<SmsConfigResponse> {
  const response = await fetch(`${API_BASE}/api/settings/sms-config`);
  return readJson<SmsConfigResponse>(response, '获取短信配置失败');
}

export async function saveSmsConfig(payload: SmsConfigSavePayload): Promise<SmsConfigResponse> {
  const response = await fetch(`${API_BASE}/api/settings/sms-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return readJson<SmsConfigResponse>(response, '保存短信配置失败');
}

export async function testSmsConfig(phone: string): Promise<SmsTestResponse> {
  const response = await fetch(`${API_BASE}/api/settings/sms-config/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone })
  });
  return readJson<SmsTestResponse>(response, '测试短信发送失败');
}

export async function listSmsLogs(): Promise<SmsLogListResponse> {
  const response = await fetch(`${API_BASE}/api/settings/sms-logs`);
  return readJson<SmsLogListResponse>(response, '获取短信发送记录失败');
}
