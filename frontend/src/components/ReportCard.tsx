import { FileText, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { KbDocument } from '../api/kb';

type Props = {
  document?: KbDocument;
  deleting?: boolean;
  isNew?: boolean;
  onDelete?: (documentId: string) => void;
  onUploadClick?: () => void;
};

const statusLabel: Record<KbDocument['status'], string> = {
  processing: '处理中',
  ready: '可搜索',
  failed: '失败'
};

function formatDate(value: string | null, emptyText = '未识别日期'): string {
  if (!value) return emptyText;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function getMeta(document: KbDocument): string {
  const uploadedAt = formatDate(document.created_at, '未知上传时间');
  if (document.status === 'failed') return `${uploadedAt} · 解析失败`;
  if (document.status === 'processing') return `${uploadedAt} · 解析中`;
  return `${uploadedAt} · ${document.page_count} 页已入库`;
}

export function ReportCard({ document, deleting = false, isNew, onDelete, onUploadClick }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);

  if (isNew) {
    return (
      <button className="report-tile report-tile-new" onClick={onUploadClick}>
        <span className="new-icon-circle">
          <Plus size={22} />
        </span>
        <span className="new-text">上传新报告</span>
      </button>
    );
  }

  if (!document) return null;

  return (
    <Link className="report-tile" to={`/reports/${document.document_id}`}>
      <div className="tile-header thumbnail">
        <img
          className="tile-thumbnail"
          src={document.thumbnail_url}
          alt={`${document.file_name} 首页缩略图`}
          loading="lazy"
          onError={(event) => {
            event.currentTarget.style.display = 'none';
          }}
        />
        <span className="tile-thumbnail-fallback">
          <FileText size={42} strokeWidth={1.6} />
        </span>
        <button
          className={`tile-more ${document.status}`}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            setMenuOpen((open) => !open);
          }}
          type="button"
        >
          {document.status === 'ready' ? '⋯' : statusLabel[document.status]}
        </button>
        {menuOpen && (
          <div className="tile-menu" onClick={(event) => event.stopPropagation()}>
            <button
              className="tile-menu-item danger"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onDelete?.(document.document_id);
                setMenuOpen(false);
              }}
              type="button"
            >
              <Trash2 size={16} />
              {deleting ? '删除中' : '删除'}
            </button>
          </div>
        )}
      </div>
      <div className="tile-title">{document.file_name}</div>
      <div className="tile-meta">{getMeta(document)}</div>
    </Link>
  );
}
