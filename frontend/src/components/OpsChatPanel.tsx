import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Send, Sparkles, X } from 'lucide-react';
import { MarkdownContent } from './chat/markdown';
import {
  createOpsSession,
  sendOpsStream
} from '../api/opsAgent';

type ChatMsg = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
};

const QUICK_PROMPTS = [
  { icon: '📊', label: '最近经营情况怎么样？' },
  { icon: '🏆', label: '哪些品牌转化最好？' },
  { icon: '💡', label: '有什么运营建议？' },
  { icon: '⚠️', label: '高风险成员有哪些？' }
];

export function OpsChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  useEffect(() => {
    if (open && !sessionId) {
      createOpsSession().then((s) => setSessionId(s.session_id)).catch(console.error);
    }
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [open, sessionId]);

  const handleSend = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || !sessionId || sending) return;

    setInput('');
    setSending(true);

    const userMsg: ChatMsg = { id: `u_${Date.now()}`, role: 'user', content };
    const assistantId = `a_${Date.now()}`;
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: 'assistant', content: '', streaming: true }]);

    try {
      await sendOpsStream(sessionId, content, {
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + delta } : m))
          );
        },
        onAssistantDone: (msg) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: msg.content || m.content, streaming: false } : m))
          );
        },
        onError: (err) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, content: `❌ ${err}`, streaming: false } : m))
          );
        }
      });
    } catch {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, content: '❌ 网络请求失败', streaming: false } : m))
      );
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!open) {
    return (
      <button className="ops-fab" onClick={() => setOpen(true)} title="AI 运营助手">
        <Sparkles size={20} />
        <span className="ops-fab-label">AI 运营助手</span>
      </button>
    );
  }

  return (
    <div className="ops-chat-panel">
      <div className="ops-chat-header">
        <div className="ops-chat-header-left">
          <Bot size={20} />
          <div>
            <div className="ops-chat-header-title">AI 运营助手</div>
            <div className="ops-chat-header-sub">集团经营数据 · 智能洞察</div>
          </div>
        </div>
        <button className="ops-chat-close" onClick={() => setOpen(false)}>
          <X size={16} />
        </button>
      </div>

      <div className="ops-chat-body">
        {messages.length === 0 && (
          <div className="ops-chat-welcome">
            <Sparkles size={24} className="ops-chat-welcome-icon" />
            <div className="ops-chat-welcome-title">集团运营 AI 助手</div>
            <div className="ops-chat-welcome-sub">
              查询经营数据、分析品牌转化、发现运营洞察，一句话搞定
            </div>
            <div className="ops-quick-prompts">
              {QUICK_PROMPTS.map(({ icon, label }) => (
                <button key={label} className="ops-quick-btn" onClick={() => handleSend(label)}>
                  {icon} {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`ops-msg ops-msg-${msg.role}`}>
            <div className="ops-msg-avatar">
              {msg.role === 'user' ? '👤' : <Bot size={16} />}
            </div>
            <div className="ops-msg-bubble">
              {msg.role === 'user' ? (
                <div className="ops-msg-text">{msg.content}</div>
              ) : msg.streaming && !msg.content ? (
                <div className="ops-msg-thinking">
                  <div className="ops-thinking-dots">
                    <span /><span /><span />
                  </div>
                  正在分析数据…
                </div>
              ) : (
                <MarkdownContent text={msg.content} />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="ops-chat-input-bar">
        <input
          ref={inputRef}
          className="ops-chat-input"
          placeholder="输入问题，如「最近转化率怎么样」"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          className="ops-chat-send"
          onClick={() => handleSend()}
          disabled={!input.trim() || sending}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
