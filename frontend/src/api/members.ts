const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export type MemberDocument = {
  document_id: string;
  file_name: string;
  exam_date: string | null;
  status: 'processing' | 'ready' | 'failed';
  page_count?: number;
  created_at?: string;
  title?: string | null;
  patient_name?: string | null;
  institution?: string | null;
  thumbnail_url?: string;
  member_id?: string | null;
  member_name?: string | null;
  member_relation?: string | null;
};

export type Member = {
  member_id: string;
  name: string;
  relation: string;
  gender: string;
  birth_year: number;
  age: number;
  height_cm: number | null;
  weight_kg: number | null;
  health_tags: string[];
  allergies: string | null;
  taste_preferences: string | null;
  phone?: string | null;
  bmi?: number | null;
  report_count?: number;
  recent_documents?: MemberDocument[];
  created_at: string;
  updated_at: string;
};

export type MemberPayload = {
  name: string;
  relation: string;
  gender: string;
  birth_year: number;
  phone?: string | null;
  height_cm?: number | null;
  weight_kg?: number | null;
  health_tags: string[];
  allergies?: string | null;
  taste_preferences?: string | null;
};

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    throw new Error(fallback);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? fallback);
  }
  return response.json();
}

export async function listMembers(): Promise<Member[]> {
  const response = await fetch(`${API_BASE}/api/members`);
  return readJson<Member[]>(response, '获取家人列表失败');
}

export async function createMember(payload: MemberPayload): Promise<Member> {
  const response = await fetch(`${API_BASE}/api/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return readJson<Member>(response, '创建家人失败');
}

export async function getMember(memberId: string): Promise<Member> {
  const response = await fetch(`${API_BASE}/api/members/${memberId}`);
  return readJson<Member>(response, '获取家人详情失败');
}

export async function updateMember(memberId: string, payload: MemberPayload): Promise<Member> {
  const response = await fetch(`${API_BASE}/api/members/${memberId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  return readJson<Member>(response, '更新家人失败');
}

export async function deleteMember(memberId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/members/${memberId}`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? '删除家人失败');
  }
}

export async function listMemberDocuments(memberId: string): Promise<MemberDocument[]> {
  const response = await fetch(`${API_BASE}/api/members/${memberId}/documents`);
  return readJson<MemberDocument[]>(response, '获取家人报告失败');
}
