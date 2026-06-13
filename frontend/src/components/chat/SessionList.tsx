import { useState, useRef, useEffect } from 'react';
import { MoreVertical } from 'lucide-react';
import type { AgentSession } from '../../api/agent';

type Props = {
  sessions: AgentSession[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: () => void;
  onDelete: (sessionId: string) => void;
  deleting: boolean;
};

export function SessionList({ sessions, activeSessionId, onSelect, onCreate, onDelete, deleting }: Props) {
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <aside className="chat-sessions">
      <div className="chat-sessions-header">
        <span>对话历史</span>
        <button className="btn-ghost-small" type="button" onClick={onCreate} aria-label="新建对话">
          +
        </button>
      </div>
      <div className="session-list" ref={menuRef}>
        {sessions.map((session) => (
          <div
            key={session.session_id}
            className={`session-item-wrapper ${session.session_id === activeSessionId ? 'active' : ''}`}
          >
            <button
              className={`session-item ${session.session_id === activeSessionId ? 'active' : ''}`}
              type="button"
              onClick={() => onSelect(session.session_id)}
            >
              <div className="session-title">{session.title}</div>
              <div className="session-preview">{session.preview || '暂无消息'}</div>
            </button>
            <button
              className="session-more-btn"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setOpenMenuId(openMenuId === session.session_id ? null : session.session_id);
              }}
              disabled={deleting}
              aria-label="更多操作"
            >
              <MoreVertical size={14} strokeWidth={2} />
            </button>
            {openMenuId === session.session_id && (
              <div className="session-menu">
                <button
                  className="session-menu-item danger"
                  type="button"
                  onClick={() => {
                    onDelete(session.session_id);
                    setOpenMenuId(null);
                  }}
                >
                  删除
                </button>
              </div>
            )}
          </div>
        ))}
        {sessions.length === 0 && <div className="session-empty">暂无对话</div>}
      </div>
    </aside>
  );
}