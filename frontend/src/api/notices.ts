const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type NoticeCategory = 'health_alert' | 'system' | 'recommendation' | 'reminder';
export type NoticeCategoryFilter = 'all' | 'health_alert' | 'system' | 'recommendation';
export type NoticeLevel = 'danger' | 'warning' | 'info' | 'success';
export type NoticeStatus = 'unread' | 'read' | 'snoozed' | 'done';

export type NoticeItem = {
  notice_id: string;
  category: NoticeCategory;
  level: NoticeLevel;
  title: string;
  description: string;
  source: string;
  source_text: string;
  status: NoticeStatus;
  created_at: string;
  meta_text: string;
  target_url: string | null;
  action_text: string | null;
  secondary_action: string | null;
};

export type NoticeListResponse = {
  counts: {
    all: number;
    health_alert: number;
    system: number;
    recommendation: number;
    unread: number;
  };
  groups: {
    label: string;
    items: NoticeItem[];
  }[];
};

export type NoticeSummaryResponse = {
  unread: number;
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

export async function listNotices(category: NoticeCategoryFilter): Promise<NoticeListResponse> {
  const params = new URLSearchParams({ category });
  const response = await fetch(`${API_BASE}/api/notices?${params.toString()}`);
  return readJson<NoticeListResponse>(response, '获取通知列表失败');
}

export async function getNoticeSummary(): Promise<NoticeSummaryResponse> {
  const response = await fetch(`${API_BASE}/api/notices/summary`);
  return readJson<NoticeSummaryResponse>(response, '获取通知未读数失败');
}

export async function readNotice(noticeId: string): Promise<NoticeItem> {
  const response = await fetch(`${API_BASE}/api/notices/${noticeId}/read`, { method: 'POST' });
  return readJson<NoticeItem>(response, '标记通知已读失败');
}

export async function readAllNotices(): Promise<{ updated: number }> {
  const response = await fetch(`${API_BASE}/api/notices/read-all`, { method: 'POST' });
  return readJson<{ updated: number }>(response, '全部已读失败');
}

export async function snoozeNotice(noticeId: string): Promise<NoticeItem> {
  const response = await fetch(`${API_BASE}/api/notices/${noticeId}/snooze`, { method: 'POST' });
  return readJson<NoticeItem>(response, '通知稍后处理失败');
}

export async function doneNotice(noticeId: string): Promise<NoticeItem> {
  const response = await fetch(`${API_BASE}/api/notices/${noticeId}/done`, { method: 'POST' });
  return readJson<NoticeItem>(response, '确认通知失败');
}
