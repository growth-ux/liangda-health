import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, FileText, PencilLine, Watch } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { deleteMember, getMember, listMemberDocuments } from '../api/members';
import { getMemberHealthAnalysis } from '../api/healthAnalysis';
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
  const healthAnalysisQuery = useQuery({
    queryKey: ['member-health-analysis', memberId],
    queryFn: () => getMemberHealthAnalysis(memberId!),
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
  const healthIndicators = useMemo(() => healthAnalysisQuery.data?.indicators ?? [], [healthAnalysisQuery.data]);
  const bpTrend = useMemo(() => healthAnalysisQuery.data?.blood_pressure_7d ?? [], [healthAnalysisQuery.data]);
  const timelineItems = useMemo(
    () =>
      documents.map((document, index) => ({
        key: document.document_id,
        date: formatDocumentDate(document.exam_date),
        title: document.title || document.file_name,
        desc: buildDocumentDesc(document, healthAnalysisQuery.data?.abnormalities ?? [], index)
      })),
    [documents, healthAnalysisQuery.data]
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

      <section className="member-hero">
        <div className="member-avatar member-hero-avatar" style={tone}>
          {getMemberInitial(member.name)}
        </div>
        <div className="member-hero-info">
          <div className="member-hero-name">
            {member.name}
            <span className="member-hero-name-meta">· {member.relation} · {member.age}岁</span>
          </div>
          <div className="member-hero-meta">
            {member.height_cm ? `身高 ${member.height_cm}cm` : '身高未填写'}
            {member.weight_kg ? ` · 体重 ${member.weight_kg}kg` : ''}
            {member.bmi ? ` · BMI ${member.bmi}` : ''}
          </div>
          <div className="member-hero-tags">
            {member.health_tags.map((tag) => (
              <span className="tag tag-warning" key={tag}>
                {tag}
              </span>
            ))}
            {member.allergies && <span className="tag tag-info">{member.allergies}</span>}
            {healthAnalysisQuery.data && <span className="tag tag-success">{healthAnalysisQuery.data.member_card.status_text}</span>}
          </div>
        </div>
        <div className="member-hero-actions">
          <button className="btn" onClick={() => setDialogOpen(true)} type="button">
            <FileText size={16} />
            上传报告
          </button>
          <button className="btn" onClick={() => navigate('/devices')} type="button">
            <Watch size={16} color="#111827" />
            设备
          </button>
          <button className="btn" onClick={() => navigate(`/members/${member.member_id}/edit`)} type="button">
            <PencilLine size={16} />
          </button>
        </div>
      </section>

      <section className="card">
        <div className="card-title">
          关键健康指标
          <span className="mt-1.49 ml-1.5 text-xs font-normal text-gray-400">· 近 7 天均值</span>
          {healthAnalysisQuery.data && (
            <span className="card-title-actions">
              健康分 {healthAnalysisQuery.data.member_card.health_score}
            </span>
          )}
        </div>
        {healthAnalysisQuery.isLoading && <div className="empty-state">正在加载健康指标...</div>}
        {healthAnalysisQuery.isError && <div className="error-box">健康指标加载失败</div>}
        {!healthAnalysisQuery.isLoading && !healthAnalysisQuery.isError && healthAnalysisQuery.data && (
          <div className="health-indicators">
            {healthIndicators.map((indicator) => (
              <div className="health-indicator" key={indicator.key}>
                <div className="health-indicator-label">{indicator.label}</div>
                <div className="health-indicator-value">
                  {indicator.value}
                  {indicator.unit ? <span>{indicator.unit}</span> : null}
                </div>
                <div className={`health-indicator-status tag-${indicator.status === 'info' ? 'info' : indicator.status}`}>
                  {indicator.status === 'danger' ? '↑ ' : indicator.status === 'warning' ? '↓ ' : '✓ '}
                  {indicator.status_text}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <div className="card-title">近 7 天血压趋势（来自手环）</div>
        {healthAnalysisQuery.isLoading && <div className="empty-state">正在加载血压趋势...</div>}
        {healthAnalysisQuery.isError && <div className="error-box">血压趋势加载失败</div>}
        {!healthAnalysisQuery.isLoading && !healthAnalysisQuery.isError && healthAnalysisQuery.data && (
          <>
            <div className="chart-box">
              <div className="chart-placeholder">
                {bpTrend.map((point) => {
                  const level =
                    point.systolic >= 140 || point.diastolic >= 90
                      ? 'danger'
                      : point.systolic >= 130 || point.diastolic >= 85
                        ? 'warning'
                        : 'success';
                  const ratio = Math.min(100, Math.max(40, Math.round((point.systolic / 170) * 100)));
                  return <div className={`chart-bar ${level}`} key={point.date} style={{ height: `${ratio}%` }} />;
                })}
              </div>
            </div>
            <div className="chart-labels">
              {bpTrend.map((point) => (
                <span key={`${point.date}-label`}>{point.date.slice(5)}</span>
              ))}
            </div>
            <div className="member-bp-values">
              {bpTrend.map((point) => {
                const level = point.systolic >= 140 || point.diastolic >= 90 ? 'danger' : point.systolic >= 130 || point.diastolic >= 85 ? 'warning' : 'success';
                return (
                  <span className={`tag tag-${level}`} key={`${point.date}-value`}>
                    {point.date.slice(5)} · {point.systolic}/{point.diastolic}
                  </span>
                );
              })}
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="card-title">
          体检报告
          <button className="card-title-actions button-reset" onClick={() => setDialogOpen(true)} type="button">
            + 上传新报告
          </button>
        </div>
        {documentsQuery.isLoading && <div className="empty-state">正在加载报告...</div>}
        {documentsQuery.isError && <div className="error-box">报告列表加载失败</div>}
        {!documentsQuery.isLoading && !documentsQuery.isError && (
          <>
            {timelineItems.length > 0 ? (
              <div className="timeline">
                {timelineItems.map((item) => (
                  <div className="timeline-item" key={item.key}>
                    <div className="timeline-date">{item.date}</div>
                    <div className="timeline-title">{item.title}</div>
                    <div className="timeline-desc">{item.desc}</div>
                  </div>
                ))}
              </div>
            ) : (
              <MemberReportList documents={documents} />
            )}
          </>
        )}
        {deleteMutation.isError && <div className="error-box">{(deleteMutation.error as Error).message}</div>}
      </section>

      <section className="card member-advice-prototype-card">
        <div className="card-title">管家长期建议</div>
        {healthAnalysisQuery.isLoading && <div className="empty-state">正在生成建议...</div>}
        {healthAnalysisQuery.isError && <div className="error-box">建议加载失败</div>}
        {!healthAnalysisQuery.isLoading && !healthAnalysisQuery.isError && healthAnalysisQuery.data && (
          <>
            <div className="member-advice-body">
              <div className="member-advice-badge">粮</div>
              <div className="member-advice-content">
                {healthAnalysisQuery.data.advice.lines.map((line) => (
                  <div key={line}>{line}</div>
                ))}
              </div>
            </div>
            <div className="member-advice-actions">
              <button
                className="btn btn-primary"
                onClick={() => navigate(`/chat?prompt=${encodeURIComponent(healthAnalysisQuery.data.advice.prompt)}`)}
                type="button"
              >
                跟管家细聊
              </button>
            </div>
          </>
        )}
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

function formatDocumentDate(value: string | null | undefined) {
  if (!value) return '未识别日期';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function buildDocumentDesc(
  document: KbDocument,
  abnormalities: { metric: string; current_value: string; status_text: string }[],
  index: number
) {
  const abnormalText =
    abnormalities
      .slice(index * 2, index * 2 + 2)
      .map((item) => `${item.metric} ${item.current_value}${item.status_text ? `（${item.status_text}）` : ''}`)
      .join('；') || '已自动归档';
  return `${document.file_name}。${abnormalText}。`;
}
