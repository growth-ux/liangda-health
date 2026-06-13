import { FileText } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { KbDocument } from '../../api/kb';

type Props = {
  documents: KbDocument[];
};

function formatDate(value: string | null | undefined) {
  if (!value) return '未识别日期';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

export function MemberReportList({ documents }: Props) {
  if (!documents.length) {
    return <div className="empty-state">暂无报告，先上传一份体检报告。</div>;
  }

  return (
    <div className="member-document-list">
      {documents.map((document) => (
        <Link className="member-document-row" key={document.document_id} to={`/reports/${document.document_id}`}>
          <div className="member-document-icon">
            <FileText size={18} />
          </div>
          <div className="member-document-main">
            <div className="member-document-title">{document.file_name}</div>
            <div className="member-document-meta">
              {formatDate(document.exam_date)} · {document.page_count} 页
            </div>
          </div>
          <span className={`tag ${document.status === 'ready' ? 'tag-success' : 'tag-warning'}`}>
            {document.status === 'ready' ? '已识别' : '处理中'}
          </span>
        </Link>
      ))}
    </div>
  );
}
