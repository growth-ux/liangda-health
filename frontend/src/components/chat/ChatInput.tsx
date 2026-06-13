import { Paperclip, Send, Smile, X, Image, FileText } from 'lucide-react';
import type { Attachment, QuickAction } from '../../api/agent';

type Props = {
  value: string;
  attachments: Attachment[];
  quickActions: QuickAction[];
  sending: boolean;
  uploading: boolean;
  error: string | null;
  onChange: (value: string) => void;
  onSend: () => void;
  onUpload: (file: File) => void;
  onRemoveAttachment?: (index: number) => void;
  onQuickAction?: (action: QuickAction) => void;
};

export function ChatInput({
  value,
  attachments,
  quickActions,
  sending,
  uploading,
  error,
  onChange,
  onSend,
  onUpload,
  onRemoveAttachment,
  onQuickAction
}: Props) {
  const isDisabled = sending || uploading;

  return (
    <div className="chat-input-area">
      {error && (
        <div className="chat-error">
          <span>{error}</span>
          <button type="button" onClick={onSend} disabled={isDisabled || (!value.trim() && attachments.length === 0)}>
            重试
          </button>
        </div>
      )}
      {quickActions.length > 0 && (
        <div className="quick-actions">
          {quickActions.map((action) => (
            <button
              key={action.action}
              className="quick-action"
              type="button"
              onClick={() => onQuickAction?.(action)}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
      <div className="chat-input">
        <div className="chat-input-box">
          {attachments.length > 0 && (
            <div className="attachment-preview-list">
              {attachments.map((attachment, index) => (
                <div key={index} className="attachment-preview-item">
                  <span className="attachment-icon">
                    {attachment.type === 'image' ? <Image size={14} /> : <FileText size={14} />}
                  </span>
                  <span className="attachment-name">{attachment.name}</span>
                  <button
                    type="button"
                    className="attachment-remove"
                    onClick={() => onRemoveAttachment?.(index)}
                    title="移除"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="chat-input-main">
            <input
              type="text"
              placeholder="问问管家..."
              value={value}
              disabled={isDisabled}
              onChange={(event) => onChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  onSend();
                }
              }}
            />
            <div className="chat-input-actions">
              <label className={`chat-file-action ${isDisabled ? 'disabled' : ''}`} title="上传 PDF 报告">
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  disabled={isDisabled}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = '';
                    if (file) onUpload(file);
                  }}
                />
                <Paperclip size={16} strokeWidth={1.8} />
              </label>
              <Smile size={16} strokeWidth={1.8} />
            </div>
          </div>
        </div>
        <button className="chat-send-btn" type="button" disabled={isDisabled || (!value.trim() && attachments.length === 0)} onClick={onSend}>
          <Send size={17} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}