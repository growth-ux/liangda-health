export type AgentSession = {
  session_id: string;
  title: string;
  preview: string;
  updated_at: string;
};

export type AgentMessage = {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  status: 'done' | 'failed' | 'sending';
  created_at: string;
  attachments?: Attachment[];
};

export type Attachment = {
  name: string;
  url: string;
  type: 'image' | 'pdf';
};

export type QuickAction = {
  label: string;
  action: 'open_reports' | 'open_upload' | string;
};

export type StreamCallbacks = {
  onUserMessage?: (message: Pick<AgentMessage, 'message_id' | 'session_id' | 'role' | 'content' | 'attachments'>) => void;
  onAssistantStart?: (message: Pick<AgentMessage, 'message_id' | 'role'>) => void;
  onDelta?: (content: string) => void;
  onAssistantDone?: (message: Pick<AgentMessage, 'message_id' | 'session_id' | 'role' | 'content'>) => void;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export async function listAgentSessions(): Promise<AgentSession[]> {
  const response = await fetch(`${API_BASE}/agent/sessions`, { cache: 'no-store' });
  if (!response.ok) throw new Error('获取会话列表失败');
  return response.json();
}

export async function createAgentSession(title = '新对话'): Promise<AgentSession> {
  const response = await fetch(`${API_BASE}/agent/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  if (!response.ok) throw new Error('创建会话失败');
  const data = await response.json();
  return { ...data, preview: '', updated_at: data.created_at };
}

export async function listAgentMessages(sessionId: string): Promise<AgentMessage[]> {
  const response = await fetch(`${API_BASE}/agent/sessions/${sessionId}/messages`, { cache: 'no-store' });
  if (!response.ok) throw new Error('获取消息列表失败');
  const data = await response.json();
  return data.items;
}

export async function listQuickActions(): Promise<QuickAction[]> {
  const response = await fetch(`${API_BASE}/agent/quick-actions`, { cache: 'no-store' });
  if (!response.ok) throw new Error('获取快捷指令失败');
  return response.json();
}

export async function sendAgentMessageStream(
  sessionId: string,
  content: string,
  attachments: Attachment[] = [],
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${API_BASE}/agent/sessions/${sessionId}/messages:stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, attachments })
  });
  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? '发送失败');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const eventText of events) {
      handleSseEvent(eventText, callbacks);
    }
  }
  if (buffer.trim()) {
    handleSseEvent(buffer, callbacks);
  }
}

function handleSseEvent(eventText: string, callbacks: StreamCallbacks) {
  const lines = eventText.split('\n');
  const event = lines.find((line) => line.startsWith('event: '))?.slice(7);
  const dataLine = lines.find((line) => line.startsWith('data: '));
  const data = dataLine ? JSON.parse(dataLine.slice(6)) : {};

  if (event === 'user_message') callbacks.onUserMessage?.(data);
  if (event === 'assistant_start') callbacks.onAssistantStart?.(data);
  if (event === 'delta') callbacks.onDelta?.(data.content ?? '');
  if (event === 'assistant_done') callbacks.onAssistantDone?.(data);
  if (event === 'error') throw new Error(data.message ?? '模型调用失败');
}
