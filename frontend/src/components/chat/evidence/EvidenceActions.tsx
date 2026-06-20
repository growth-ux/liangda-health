import type { AgentMessage } from '../../../api/agent';

export type EvidenceModalState =
  | {
      open: true;
      messageId: string;
      group: 'content' | 'product';
    }
  | {
      open: false;
      messageId: null;
      group: null;
    };

type Props = {
  message: AgentMessage;
  modalState: EvidenceModalState;
  onChange: (next: EvidenceModalState) => void;
  mobile?: boolean;
};

export function EvidenceActions({ message, modalState, onChange, mobile = false }: Props) {
  const evidence = message.card?.evidence;
  const hasContent = (evidence?.content_items?.length ?? 0) > 0;
  const hasProduct = (evidence?.product_items?.length ?? 0) > 0;

  if (!hasContent && !hasProduct) return null;

  return (
    <div className={`evidence-actions-row${mobile ? ' mobile' : ''}`}>
      {hasContent && (
        <button
          type="button"
          className={
            modalState.open && modalState.messageId === message.message_id && modalState.group === 'content'
              ? 'active'
              : ''
          }
          onClick={() =>
            onChange({ open: true, messageId: message.message_id, group: 'content' })
          }
        >
          生成依据
        </button>
      )}
      {hasProduct && (
        <button
          type="button"
          className={
            modalState.open && modalState.messageId === message.message_id && modalState.group === 'product'
              ? 'active'
              : ''
          }
          onClick={() =>
            onChange({ open: true, messageId: message.message_id, group: 'product' })
          }
        >
          推荐依据
        </button>
      )}
    </div>
  );
}
