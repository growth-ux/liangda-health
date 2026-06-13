import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { listMembers } from '../api/members';
import { deleteDocument, listDocuments, uploadPdf } from '../api/kb';
import { AppShell } from '../components/AppShell';
import { ReportGrid } from '../components/ReportGrid';
import { ReportToolbar } from '../components/ReportToolbar';
import { UploadReportDialog } from '../components/UploadReportDialog';

type FamilyFilter = string;
type SortMode = 'uploaded' | 'exam' | 'family';

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [family, setFamily] = useState<FamilyFilter>('all');
  const [sortMode, setSortMode] = useState<SortMode>('uploaded');
  const [dialogOpen, setDialogOpen] = useState(searchParams.get('upload') === '1');
  const [uploadError, setUploadError] = useState<string | null>(null);
  const documentsQuery = useQuery({ queryKey: ['documents'], queryFn: listDocuments });
  const membersQuery = useQuery({ queryKey: ['members'], queryFn: listMembers });
  const uploadMutation = useMutation({
    mutationFn: uploadPdf,
    onSuccess: async () => {
      setDialogOpen(false);
      setUploadError(null);
      setSearchParams({});
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      await queryClient.invalidateQueries({ queryKey: ['members'] });
    },
    onError: (error: Error) => setUploadError(error.message)
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
      await queryClient.invalidateQueries({ queryKey: ['members'] });
    }
  });

  const filters = useMemo(() => {
    const items = documentsQuery.data ?? [];
    return [
      { value: 'all', label: '全部', count: items.length },
      ...(membersQuery.data ?? []).map((member) => ({
        value: member.member_id,
        label: member.name,
        count: items.filter((item) => item.member_id === member.member_id).length
      }))
    ];
  }, [documentsQuery.data, membersQuery.data]);

  const documents = useMemo(() => {
    const items = [...(documentsQuery.data ?? [])];
    const filtered = family === 'all' ? items : items.filter((item) => item.member_id === family);

    return filtered.sort((a, b) => {
      if (sortMode === 'exam') {
        return (b.exam_date ?? '').localeCompare(a.exam_date ?? '');
      }
      if (sortMode === 'family') {
        return `${a.member_name ?? ''}${a.member_relation ?? ''}`.localeCompare(
          `${b.member_name ?? ''}${b.member_relation ?? ''}`
        );
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [documentsQuery.data, family, sortMode]);

  return (
    <AppShell title="上传报告" activeId="reports">
      <ReportToolbar
        activeFamily={family}
        filters={filters}
        sortMode={sortMode}
        onFamilyChange={setFamily}
        onSortModeChange={setSortMode}
        onUploadClick={() => setDialogOpen(true)}
      />

      {documentsQuery.isLoading && <div className="empty-state">正在加载报告...</div>}
      {documentsQuery.isError && <div className="error-box">报告列表加载失败</div>}
      {!documentsQuery.isLoading && (
        <ReportGrid
          documents={documents}
          deletingDocumentId={deleteMutation.variables ?? null}
          onDelete={(documentId) => deleteMutation.mutate(documentId)}
          onUploadClick={() => setDialogOpen(true)}
        />
      )}
      {deleteMutation.isError && <div className="error-box">报告删除失败</div>}

      <div className="alert-info">
        <div className="alert-icon">i</div>
        <div>
          <strong>说明：</strong>报告上传后会自动解析、OCR 识别并进入知识库。点击报告卡片可查看详情和识别结果。
        </div>
      </div>

      <UploadReportDialog
        defaultMemberId={searchParams.get('memberId')}
        open={dialogOpen}
        uploading={uploadMutation.isPending}
        error={uploadError}
        onClose={() => {
          setDialogOpen(false);
          setSearchParams({});
        }}
        onUpload={(payload) => uploadMutation.mutate(payload)}
      />
    </AppShell>
  );
}
