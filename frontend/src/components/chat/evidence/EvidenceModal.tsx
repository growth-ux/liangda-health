import type { AgentMessage } from '../../../api/agent';
import { EvidenceEmpty } from './EvidenceEmpty';
import { EvidenceSection } from './EvidenceSection';
import type { EvidenceModalState } from './EvidenceActions';

type Props = {
  message: AgentMessage | null;
  modalState: EvidenceModalState;
  onClose: () => void;
  onChange: (next: EvidenceModalState) => void;
};

export function EvidenceModal({ message, modalState, onClose, onChange }: Props) {
  if (!modalState.open) {
    return null;
  }

  const evidence = message?.card?.evidence;
  const contentItems = evidence?.content_items ?? [];
  const productItems = evidence?.product_items ?? [];
  const items = modalState.group === 'content' ? contentItems : productItems;
  const sectionTitle = modalState.group === 'content' ? '本次生成依据' : '本次推荐依据';
  const chainLabel = modalState.group === 'content' ? '生成链' : '推荐链';
  const canShowContent = contentItems.length > 0;
  const canShowProduct = productItems.length > 0;

  return (
    <div className="chat-evidence-modal-backdrop" onClick={onClose}>
      <div className="chat-evidence-modal" onClick={(event) => event.stopPropagation()}>
        <div className="chat-evidence-modal-head">
          <div>
            <div className="chat-evidence-modal-title">证据链</div>
            <div className="chat-evidence-modal-subtitle">来自当前这条回复的真实依据</div>
          </div>
          <button type="button" className="chat-evidence-modal-close" onClick={onClose} aria-label="关闭证据链">
            ×
          </button>
        </div>
        <div className="chat-evidence-modal-body">
          <div className="chat-evidence-modal-toolbar">
            <div className="chat-evidence-modal-tabs">
              {canShowContent && (
                <button
                  type="button"
                  className={modalState.group === 'content' ? 'active' : ''}
                  onClick={() => onChange({ open: true, messageId: modalState.messageId, group: 'content' })}
                >
                  生成链
                </button>
              )}
              {canShowProduct && (
                <button
                  type="button"
                  className={modalState.group === 'product' ? 'active' : ''}
                  onClick={() => onChange({ open: true, messageId: modalState.messageId, group: 'product' })}
                >
                  推荐链
                </button>
              )}
            </div>
            <div className="chat-evidence-modal-count">{chainLabel} {items.length} 条</div>
          </div>
          {items.length === 0 ? (
            <EvidenceEmpty />
          ) : (
            <EvidenceSection title={sectionTitle} items={items} />
          )}
        </div>
      </div>
    </div>
  );
}
