import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PencilLine, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { deleteMember, getMember, listMemberDocuments } from '../api/members';
import { uploadPdf, type KbDocument } from '../api/kb';
import { AppShell } from '../components/AppShell';
import { MemberReportList } from '../components/members/MemberReportList';
import { getMemberInitial, getMemberTone } from '../components/members/memberUtils';
import { UploadReportDialog } from '../components/UploadReportDialog';

export function MemberDetailPage() {
  const { memberId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const memberQuery = useQuery({
    queryKey: ['member', memberId],
    queryFn: () => getMember(memberId!),
    enabled: Boolean(memberId)
  });
  const documentsQuery = useQuery({
    queryKey: ['member-documents', memberId],
    queryFn: () => listMemberDocuments(memberId!),
    enabled: Boolean(memberId)
  });
  const deleteMutation = useMutation({
    mutationFn: deleteMember,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['members'] });
      navigate('/members');
    }
  });
  const uploadMutation = useMutation({
    mutationFn: uploadPdf,
    onSuccess: async () => {
      setDialogOpen(false);
      setUploadError(null);
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      await queryClient.invalidateQueries({ queryKey: ['members'] });
      await queryClient.invalidateQueries({ queryKey: ['member-documents', memberId] });
    },
    onError: (error: Error) => setUploadError(error.message)
  });

  const documents = useMemo(
    () => (documentsQuery.data ?? []) as KbDocument[],
    [documentsQuery.data]
  );

  if (memberQuery.isLoading) {
    return (
      <AppShell title="家人详情" activeId="members">
        <div className="empty-state">正在加载家人资料...</div>
      </AppShell>
    );
  }

  if (memberQuery.isError || !memberQuery.data) {
    return (
      <AppShell title="家人详情" activeId="members">
        <div className="error-box">家人详情加载失败</div>
      </AppShell>
    );
  }

  const member = memberQuery.data;
  const tone = getMemberTone(member.relation);

  return (
    <AppShell title={`家人详情 · ${member.name}`} activeId="members">
      <Link className="back-link" to="/members">
        <ArrowLeft size={16} />
        返回家人列表
      </Link>

      <section className="member-detail-hero">
        <div className="member-detail-avatar" style={tone}>
          {getMemberInitial(member.name)}
        </div>
        <div className="member-detail-main">
          <div className="member-detail-title">
            {member.name}
            <span>{member.relation} · {member.age}岁</span>
          </div>
          <div className="member-detail-meta">
            {member.gender}
            {member.height_cm ? ` · 身高 ${member.height_cm}cm` : ''}
            {member.weight_kg ? ` · 体重 ${member.weight_kg}kg` : ''}
            {member.bmi ? ` · BMI ${member.bmi}` : ''}
          </div>
          <div className="member-detail-tags">
            {member.health_tags.map((tag) => (
              <span className="tag tag-warning" key={tag}>
                {tag}
              </span>
            ))}
            {member.allergies && <span className="tag tag-info">{member.allergies}</span>}
            {member.taste_preferences && <span className="tag tag-success">{member.taste_preferences}</span>}
          </div>
        </div>
        <div className="member-detail-actions">
          <button className="btn-secondary" onClick={() => setDialogOpen(true)} type="button">
            <Upload size={16} />
            上传报告
          </button>
          <button className="btn-secondary" onClick={() => navigate(`/members/${member.member_id}/edit`)} type="button">
            <PencilLine size={16} />
            编辑
          </button>
          <button className="btn-secondary" onClick={() => deleteMutation.mutate(member.member_id)} type="button">
            删除
          </button>
        </div>
      </section>

      <section className="detail-card member-summary-card">
        <div className="section-title">基础信息</div>
        <div className="detail-grid">
          <Info label="手机号" value={member.phone || '-'} />
          <Info label="过敏 / 忌口" value={member.allergies || '-'} />
          <Info label="口味偏好" value={member.taste_preferences || '-'} />
          <Info label="出生年" value={String(member.birth_year)} />
        </div>
        {deleteMutation.isError && <div className="error-box">{(deleteMutation.error as Error).message}</div>}
      </section>

      <section className="detail-card member-reports-card">
        <div className="section-title">体检报告</div>
        {documentsQuery.isLoading && <div className="empty-state">正在加载报告...</div>}
        {documentsQuery.isError && <div className="error-box">报告列表加载失败</div>}
        {!documentsQuery.isLoading && !documentsQuery.isError && <MemberReportList documents={documents} />}
      </section>

      <UploadReportDialog
        defaultMemberId={member.member_id}
        error={uploadError}
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setUploadError(null);
        }}
        onUpload={(payload) => uploadMutation.mutate(payload)}
        uploading={uploadMutation.isPending}
      />
    </AppShell>
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
