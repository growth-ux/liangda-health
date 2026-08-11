import { FileText, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Member } from '../../api/members';
import { getMemberInitial, getMemberTone } from './memberUtils';

type Props = {
  member: Member;
  onDelete?: (member: Member) => void;
};

function formatMeta(member: Member) {
  const parts = [member.gender, `${member.age}岁`];
  if (member.height_cm) parts.push(`${member.height_cm}cm`);
  if (member.weight_kg) parts.push(`${member.weight_kg}kg`);
  return parts.join(' · ');
}

export function MemberCard({ member, onDelete }: Props) {
  const tone = getMemberTone(member.relation);

  const handleDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`确定要删除「${member.name}」的档案吗？`)) {
      onDelete?.(member);
    }
  };

  return (
    <Link className="member-rich-card" to={`/members/${member.member_id}`}>
      {onDelete && (
        <button className="member-delete-btn" onClick={handleDelete} title="删除家人">
          <X size={16} />
        </button>
      )}
      <div className="member-rich-header">
        <div className="member-rich-avatar" style={tone}>
          {getMemberInitial(member.name)}
        </div>
        <div className="member-rich-info">
          <div className="member-rich-name">
            <span className="member-rich-name-text">{member.name}</span>
            <span className="member-rich-relation">{member.relation}</span>
          </div>
          <div className="member-rich-meta">{formatMeta(member)}</div>
        </div>
      </div>

      <div className="member-rich-tags">
        {member.health_tags.length ? (
          member.health_tags.map((tag) => (
            <span key={tag} className="tag tag-warning">
              {tag}
            </span>
          ))
        ) : (
          <span className="tag tag-success">健康档案已创建</span>
        )}
      </div>

      <div className="member-reports-section">
        <FileText size={14} />
        体检报告 <span className="member-reports-count">({member.report_count ?? 0})</span>
      </div>

      {member.recent_documents?.length ? (
        member.recent_documents.map((document) => (
          <div className="member-report-item" key={document.document_id}>
            <span className="member-report-name">{document.file_name}</span>
            <span className="member-report-date">{document.exam_date?.slice(0, 10) ?? '-'}</span>
            <span className={`tag ${document.status === 'ready' ? 'tag-success' : 'tag-warning'}`}>
              {document.status === 'ready' ? '已识别' : '处理中'}
            </span>
          </div>
        ))
      ) : (
        <div className="member-empty">暂无报告</div>
      )}
    </Link>
  );
}
