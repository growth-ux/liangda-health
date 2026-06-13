import { ArrowLeft, ChevronDown, ChevronUp, FileText } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getDocument, listDocumentChunks } from '../api/kb';

export function DocumentDetailPage() {
  const { documentId } = useParams();
  const [openChunkId, setOpenChunkId] = useState<string | null>(null);
  const documentQuery = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => getDocument(documentId!),
    enabled: Boolean(documentId)
  });
  const chunksQuery = useQuery({
    queryKey: ['document-chunks', documentId],
    queryFn: () => listDocumentChunks(documentId!),
    enabled: Boolean(documentId)
  });

  return (
    <main className="page-shell">
      <Link className="back-link" to="/reports">
        <ArrowLeft size={16} />
        返回报告列表
      </Link>

      {documentQuery.isLoading && <div className="empty-state">正在加载文档...</div>}
      {documentQuery.isError && <div className="error-box">文档详情加载失败</div>}

      {documentQuery.data && (
        <>
          <section className="detail-card">
            <div className="detail-icon">
              <FileText size={48} />
            </div>
            <div className="detail-content">
              <div className="eyebrow">PDF 报告</div>
              <h1>{documentQuery.data.title || documentQuery.data.file_name}</h1>
              <div className="detail-grid">
                <Info label="文件名" value={documentQuery.data.file_name} />
                <Info label="检查日期" value={documentQuery.data.exam_date || '-'} />
                <Info label="机构" value={documentQuery.data.institution || '-'} />
                <Info label="页数" value={`${documentQuery.data.page_count} 页`} />
                <Info label="状态" value={documentQuery.data.status} />
                <Info label="文件大小" value={formatSize(documentQuery.data.file_size ?? 0)} />
                <Info label="文件路径" value={documentQuery.data.file_path || '-'} />
              </div>
            </div>
          </section>

          <section className="chunks-panel">
            <div className="chunks-title">报告分块</div>
            {chunksQuery.isLoading && <div className="empty-state">正在加载分块...</div>}
            {chunksQuery.isError && <div className="error-box">分块列表加载失败</div>}
            {chunksQuery.data?.length === 0 && <div className="empty-state">暂无分块</div>}
            {!!chunksQuery.data?.length && (
              <div className="chunk-table">
                <div className="chunk-row chunk-head">
                  <div>数据名称</div>
                  <div>数据大小</div>
                  <div>状态</div>
                  <div>所属页码</div>
                  <div>索引顺序</div>
                  <div>操作</div>
                </div>
                {chunksQuery.data.map((chunk, index) => {
                  const isOpen = openChunkId === chunk.chunk_id;
                  return (
                    <div className="chunk-record" key={chunk.chunk_id}>
                      <div className="chunk-row">
                        <div>
                          <div className="chunk-name">切片 {index + 1}</div>
                          <div className="chunk-sub">Chunk ID：{chunk.chunk_id}</div>
                        </div>
                        <div>{formatTextSize(chunk.content)}</div>
                        <div>
                          <span className="chunk-status">解析完成</span>
                        </div>
                        <div>第 {chunk.page_no} 页</div>
                        <div>{index + 1}</div>
                        <div>
                          <button
                            className="chunk-action"
                            onClick={() => setOpenChunkId(isOpen ? null : chunk.chunk_id)}
                            type="button"
                          >
                            查看切片
                            {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                        </div>
                      </div>
                      {isOpen && <pre className="chunk-content">{chunk.content}</pre>}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatSize(size: number) {
  if (!size) return '-';
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

function formatTextSize(text: string) {
  const bytes = new Blob([text]).size;
  if (bytes < 1024) return `${bytes}B`;
  return `${(bytes / 1024).toFixed(2)}KB`;
}
