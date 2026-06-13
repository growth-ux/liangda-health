import type { AgentSession } from '../../api/agent';

type Props = {
  sessions: AgentSession[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
};

export function SessionList({ sessions, activeSessionId, onSelect, onCreate }: Props) {
  return (
    <aside className="chat-sessions">
      <div className="chat-sessions-header">
        <span>对话历史</span>
        <button className="btn-ghost-small" type="button" onClick={onCreate} aria-label="新建对话">
          +
        </button>
      </div>
      <div className="session-list">
        {sessions.map((session) => (
          <button
            key={session.session_id}
            className={`session-item ${session.session_id === activeSessionId ? 'active' : ''}`}
            type="button"
            onClick={() => onSelect(session.session_id)}
          >
            <div className="session-title">{session.title}</div>
            <div className="session-preview">{session.preview || '暂无消息'}</div>
          </button>
        ))}
        {sessions.length === 0 && <div className="session-empty">暂无对话</div>}
      </div>
    </aside>
  );
}
