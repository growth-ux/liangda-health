import { useState } from 'react';
import { X } from 'lucide-react';

type Props = {
  open: boolean;
  uploading: boolean;
  error: string | null;
  onClose: () => void;
  onUpload: (file: File) => void;
};

export function UploadReportDialog({ open, uploading, error, onClose, onUpload }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  if (!open) return null;

  const submit = () => {
    if (!file) {
      setLocalError('请选择 PDF 文件');
      return;
    }
    if (!file.name.toLowerCase().endsWith('.pdf') || file.type !== 'application/pdf') {
      setLocalError('只支持 PDF 文件');
      return;
    }
    setLocalError(null);
    onUpload(file);
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

        {(localError || error) && <div className="error-box">{localError || error}</div>}

        <div className="dialog-footer">
          <button className="btn-secondary" onClick={onClose} disabled={uploading}>
            取消
          </button>
          <button className="btn-primary" onClick={submit} disabled={uploading || !file}>
            {uploading ? '处理中...' : '上传并入库'}
          </button>
        </div>
      </div>
    </div>
  );
}
