import type { AgentMessage } from '../../api/agent';
import { MarkdownContent } from './markdown';
import { ProductRecommendationCards } from './ProductRecommendationCards';

type Props = {
  message: AgentMessage;
};

function PlaceholderDots() {
  return (
    <span className="msg-placeholder-dots" aria-label="正在生成">
      <span className="msg-placeholder-dot" />
      <span className="msg-placeholder-dot" />
      <span className="msg-placeholder-dot" />
    </span>
  );
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const time = new Date(message.created_at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
  const isPlaceholder = !isUser && !message.content && message.status === 'sending';
  const productItems = message.product_recommendations ?? [];

  return (
    <div className={`message-row ${isUser ? 'user' : ''}`}>
      <div className={`msg-avatar ${isUser ? 'user' : 'agent'}`}>{isUser ? '张' : '家'}</div>
      <div className="msg-wrap">
        <div className="msg-bubble">
          <div className="msg-text">
            {isPlaceholder ? <PlaceholderDots /> : isUser ? message.content : <MarkdownContent text={message.content} />}
          </div>
          {!isUser && productItems.length > 0 && (
            <ProductRecommendationCards items={productItems} />
          )}
        </div>
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
    </div>
  );
}