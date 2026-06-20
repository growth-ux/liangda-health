import type { AgentMessage } from '../../api/agent';
import { MarkdownContent } from './markdown';
import { ProductRecommendationCards } from './ProductRecommendationCards';
import { StructuredCard } from './StructuredCard';
import { EvidenceActions, type EvidenceModalState } from './evidence/EvidenceActions';
import { EvidenceSection } from './evidence/EvidenceSection';

type Props = {
  message: AgentMessage;
  modalState: EvidenceModalState;
  onModalChange: (next: EvidenceModalState) => void;
  mobileEvidenceMode?: boolean;
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

export function MessageBubble({
  message,
  modalState,
  onModalChange,
  mobileEvidenceMode = false,
}: Props) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const time = new Date(message.created_at).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  });
  const isPlaceholder = !isUser && !message.content && message.status === 'sending';
  const productItems = message.product_recommendations ?? [];
  const isInlineEvidenceOpen =
    mobileEvidenceMode &&
    modalState.open &&
    modalState.messageId === message.message_id &&
    !!message.card?.evidence;

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
          {!isUser && message.card && (
            <StructuredCard card={message.card} />
          )}
        </div>
        {isAssistant && (
          <EvidenceActions
            message={message}
            modalState={modalState}
            onChange={onModalChange}
            mobile={mobileEvidenceMode}
          />
        )}
        {isInlineEvidenceOpen && (
          <div className="msg-inline-evidence">
            {modalState.group === 'content' && (
              <EvidenceSection title="本次生成依据" items={message.card?.evidence?.content_items ?? []} />
            )}
            {modalState.group === 'product' && (
              <EvidenceSection title="本次推荐依据" items={message.card?.evidence?.product_items ?? []} />
            )}
          </div>
        )}
        <div className="msg-time">{message.status === 'failed' ? '发送失败' : time}</div>
      </div>
    </div>
  );
}
