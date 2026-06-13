import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteDocument, listDocuments, uploadPdf } from '../api/kb';
import { AppShell } from '../components/AppShell';
import { ReportGrid } from '../components/ReportGrid';
import { ReportToolbar } from '../components/ReportToolbar';
import { UploadReportDialog } from '../components/UploadReportDialog';
import type { KbDocument } from '../api/kb';

type FamilyFilter = 'all' | 'mom' | 'dad' | 'me' | 'kid';
type SortMode = 'uploaded' | 'exam' | 'family';

function getFamily(document: KbDocument): FamilyFilter {
  const patient = document.patient_name ?? document.title ?? document.file_name;
  if (/妈|母|王秀英/.test(patient)) return 'mom';
  if (/爸|父|张建国/.test(patient)) return 'dad';
  if (/女儿|小溪|孩子|儿童/.test(patient)) return 'kid';
  return 'me';
}

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [family, setFamily] = useState<FamilyFilter>('all');
  const [sortMode, setSortMode] = useState<SortMode>('uploaded');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const documentsQuery = useQuery({ queryKey: ['documents'], queryFn: listDocuments });
  const uploadMutation = useMutation({
    mutationFn: uploadPdf,
    onSuccess: async () => {
      setDialogOpen(false);
      setUploadError(null);
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (error: Error) => setUploadError(error.message)
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
    }
  });

  const filterCounts = useMemo(() => {
    const items = documentsQuery.data ?? [];
    return {
      all: items.length,
      mom: items.filter((item) => getFamily(item) === 'mom').length,
      dad: items.filter((item) => getFamily(item) === 'dad').length,
      me: items.filter((item) => getFamily(item) === 'me').length,
      kid: items.filter((item) => getFamily(item) === 'kid').length
    };
  }, [documentsQuery.data]);

  const documents = useMemo(() => {
    const items = [...(documentsQuery.data ?? [])];
    const filtered = family === 'all' ? items : items.filter((item) => getFamily(item) === family);

    return filtered.sort((a, b) => {
      if (sortMode === 'exam') {
        return (b.exam_date ?? '').localeCompare(a.exam_date ?? '');
      }
      if (sortMode === 'family') {
        return getFamily(a).localeCompare(getFamily(b));
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [documentsQuery.data, family, sortMode]);

  return (
    <AppShell title="上传报告" activeId="reports">
      <ReportToolbar
        activeFamily={family}
        counts={filterCounts}
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
        open={dialogOpen}
        uploading={uploadMutation.isPending}
        error={uploadError}
        onClose={() => setDialogOpen(false)}
        onUpload={(file) => uploadMutation.mutate(file)}
      />
    </AppShell>
  );
}
