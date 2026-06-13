import type { AgentMessage } from '../../api/agent';
import { MessageBubble } from './MessageBubble';

type Props = {
  messages: AgentMessage[];
  loading: boolean;
};

export function MessageList({ messages, loading }: Props) {
  return (
    <div className="chat-messages">
      {loading && <div className="empty-state">正在加载消息...</div>}
      {!loading && messages.length === 0 && (
        <div className="message-row">
          <div className="msg-avatar agent">家</div>
          <div className="msg-wrap">
            <div className="msg-bubble">
              <div className="msg-text">
                早上好，雨微，今天可以继续问我健康报告相关问题。
              </div>
            </div>
            <div className="msg-time">现在</div>
          </div>
        </div>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.message_id} message={message} />
      ))}
    </div>
  );
}
