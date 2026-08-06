const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type OpsMessage = {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};

export type OpsSession = {
  session_id: string;
  title: string;
  preview: string;
  updated_at: string;
};

export type OpsStreamCallbacks = {
  onUserMessage?: (msg: Pick<OpsMessage, 'message_id' | 'session_id' | 'role' | 'content'>) => void;
  onAssistantStart?: (msg: Pick<OpsMessage, 'message_id' | 'role'>) => void;
  onDelta?: (text: string) => void;
  onAssistantDone?: (msg: Pick<OpsMessage, 'message_id' | 'session_id' | 'role' | 'content'>) => void;
  onError?: (message: string) => void;
};

export async function createOpsSession(title = '运营分析'): Promise<OpsSession> {
  const res = await fetch(`${API_BASE}/api/ops-agent/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  if (!res.ok) throw new Error('创建运营会话失败');
  const data = await res.json();
  return { ...data, preview: '', updated_at: data.created_at };
}

export async function listOpsSessions(): Promise<OpsSession[]> {
  const res = await fetch(`${API_BASE}/api/ops-agent/sessions`, { cache: 'no-store' });
  if (!res.ok) throw new Error('获取运营会话列表失败');
  return res.json();
}

export async function listOpsMessages(sessionId: string): Promise<OpsMessage[]> {
  const res = await fetch(`${API_BASE}/api/ops-agent/sessions/${sessionId}/messages`, { cache: 'no-store' });
  if (!res.ok) throw new Error('获取运营消息失败');
  const data = await res.json();
  return data.items;
}

export async function sendOpsStream(
  sessionId: string,
  content: string,
  callbacks: OpsStreamCallbacks
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/ops-agent/sessions/${sessionId}/messages:stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content })
  });
  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? '发送失败');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const evt of events) parseOpsEvent(evt, callbacks);
  }
  if (buffer.trim()) parseOpsEvent(buffer, callbacks);
}

function parseOpsEvent(text: string, cb: OpsStreamCallbacks) {
  const lines = text.split('\n');
  const event = lines.find((l) => l.startsWith('event: '))?.slice(7);
  const dataLine = lines.find((l) => l.startsWith('data: '));
  const data = dataLine ? JSON.parse(dataLine.slice(6)) : {};

  if (event === 'user_message') cb.onUserMessage?.(data);
  if (event === 'assistant_start') cb.onAssistantStart?.(data);
  if (event === 'delta') cb.onDelta?.(data.content ?? '');
  if (event === 'assistant_done') cb.onAssistantDone?.(data);
  if (event === 'error') cb.onError?.(data.message ?? '模型调用失败');
}
