import type { AgentMessage } from '../../api/agent';

type Props = {
  message: AgentMessage;
};

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const time = new Date(message.created_at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`msg-avatar ${isUser ? 'user' : 'agent'}`}>{isUser ? '张' : '家'}</div>
      <div className="msg-wrap">
        <div className="msg-bubble">
          <div className="msg-text">
            {message.content || (message.status === 'sending' ? '正在生成...' : '')}
          </div>
        </div>
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
    </div>
  );
}
