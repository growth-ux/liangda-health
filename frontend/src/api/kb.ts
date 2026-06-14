export type KbDocument = {
  document_id: string;
  file_name: string;
  title: string | null;
  patient_name: string | null;
  exam_date: string | null;
  institution: string | null;
  member_id?: string | null;
  member_name?: string | null;
  member_relation?: string | null;
  status: 'processing' | 'ready' | 'failed';
  page_count: number;
  created_at: string;
  thumbnail_url: string;
  file_path?: string;
  file_size?: number;
  error_message?: string | null;
};

export type UploadResponse = {
  document_id: string;
  status: string;
  page_count: number;
  chunk_count: number;
  error_message?: string | null;
};

export type SearchResult = {
  document_id: string;
  chunk_id: string;
  page_no: number;
  content: string;
  score: number;
};

export type DocumentChunk = {
  chunk_id: string;
  page_no: number;
  content: string;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export async function listDocuments(): Promise<KbDocument[]> {
  const response = await fetch(`${API_BASE}/api/kb/documents`);
  if (!response.ok) throw new Error('获取报告列表失败');
  return response.json();
}

export async function getDocument(documentId: string): Promise<KbDocument> {
  const response = await fetch(`${API_BASE}/api/kb/documents/${documentId}`);
  if (!response.ok) throw new Error('获取文档详情失败');
  return response.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/kb/documents/${documentId}`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error('删除报告失败');
}

export async function listDocumentChunks(documentId: string): Promise<DocumentChunk[]> {
  const response = await fetch(`${API_BASE}/api/kb/documents/${documentId}/chunks`);
  if (!response.ok) throw new Error('获取分块列表失败');
  const data = await response.json();
  return data.items;
}

export async function uploadPdf({
  file,
  memberId
}: {
  file: File;
  memberId: string;
}): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('member_id', memberId);
  const response = await fetch(`${API_BASE}/api/kb/upload`, {
    method: 'POST',
    body: form
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? 'PDF 上传失败');
  }
  return response.json();
}

export async function searchKb(query: string, topK: number): Promise<SearchResult[]> {
  const response = await fetch(`${API_BASE}/api/kb/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK })
  });
  if (!response.ok) throw new Error('搜索失败');
  const data = await response.json();
  return data.items;
}
