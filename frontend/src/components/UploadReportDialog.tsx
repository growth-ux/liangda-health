import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { listMembers } from '../api/members';

type Props = {
  open: boolean;
  uploading: boolean;
  error: string | null;
  defaultMemberId?: string | null;
  onClose: () => void;
  onUpload: (payload: { file: File; memberId: string }) => void;
};

export function UploadReportDialog({
  open,
  uploading,
  error,
  defaultMemberId = null,
  onClose,
  onUpload
}: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [memberId, setMemberId] = useState(defaultMemberId ?? '');
  const [localError, setLocalError] = useState<string | null>(null);
  const membersQuery = useQuery({
    queryKey: ['members'],
    queryFn: listMembers,
    enabled: open
  });

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setLocalError(null);
    setMemberId(defaultMemberId ?? '');
  }, [defaultMemberId, open]);

  if (!open) return null;

  const submit = () => {
    if (!memberId) {
      setLocalError('请选择家人');
      return;
    }
    if (!file) {
      setLocalError('请选择 PDF 文件');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.pdf') || file.type !== 'application/pdf') {
      setLocalError('只支持 PDF 文件');
      return;
    }
    setLocalError(null);
    onUpload({ file, memberId });
  };

  return (
    <div className="dialog-backdrop">
      <div className="dialog">
        <div className="dialog-header">
          <div>
            <div className="dialog-title">上传 PDF 报告</div>
            <div className="dialog-subtitle">同步解析并建立知识库，请勿关闭页面。</div>
          </div>
          <button className="icon-btn" onClick={onClose} disabled={uploading}>
            <X size={18} />
          </button>
        </div>

        <div className="field-block compact">
          <span>归属家人</span>
          <select
            className="member-select"
            disabled={uploading || membersQuery.isLoading || !membersQuery.data?.length}
            onChange={(event) => setMemberId(event.target.value)}
            value={memberId}
          >
            <option value="">请选择家人</option>
            {membersQuery.data?.map((member) => (
              <option key={member.member_id} value={member.member_id}>
                {member.name} · {member.relation}
              </option>
            ))}
          </select>
        </div>

        <label className="upload-zone">
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            disabled={uploading}
          />
          <span className="upload-icon">PDF</span>
          <span className="upload-text">{file ? file.name : '点击选择 PDF 文件'}</span>
          <span className="upload-sub">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : ''}</span>
        </label>

        {!membersQuery.isLoading && !membersQuery.data?.length && (
          <div className="empty-state">请先添加家人，再上传报告。</div>
        )}
        {(localError || error) && <div className="error-box">{localError || error}</div>}

        <div className="dialog-footer">
          <button className="btn-secondary" onClick={onClose} disabled={uploading}>
            取消
          </button>
          <button
            className="btn-primary"
            onClick={submit}
            disabled={uploading || !file || !memberId || !membersQuery.data?.length}
          >
            {uploading ? '处理中...' : '上传并入库'}
          </button>
        </div>
      </div>
    </div>
  );
}
