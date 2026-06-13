import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { createMember, getMember, updateMember, type MemberPayload } from '../api/members';
import { AppShell } from '../components/AppShell';
import { MemberForm } from '../components/members/MemberForm';

export function MemberFormPage() {
  const { memberId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = Boolean(memberId);
  const detailQuery = useQuery({
    queryKey: ['member', memberId],
    queryFn: () => getMember(memberId!),
    enabled: isEdit
  });

  const createMutation = useMutation({
    mutationFn: createMember
  });

  const updateMutation = useMutation({
    mutationFn: ({ targetId, payload }: { targetId: string; payload: MemberPayload }) =>
      updateMember(targetId, payload),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['members'] });
      await queryClient.invalidateQueries({ queryKey: ['member', variables.targetId] });
      navigate(`/members/${variables.targetId}`);
    }
  });

  const saving = createMutation.isPending || updateMutation.isPending;
  const error = (createMutation.error as Error | null)?.message ?? (updateMutation.error as Error | null)?.message ?? null;

  if (isEdit && detailQuery.isLoading) {
    return (
      <AppShell title="编辑家人" activeId="members">
        <div className="empty-state">正在加载家人资料...</div>
      </AppShell>
    );
  }

  if (isEdit && detailQuery.isError) {
    return (
      <AppShell title="编辑家人" activeId="members">
        <div className="error-box">家人资料加载失败</div>
      </AppShell>
    );
  }

  return (
    <AppShell title={isEdit ? '编辑家人' : '添加家人'} activeId="members">
      <MemberForm
        error={error}
        initialValue={detailQuery.data}
        mode={isEdit ? 'edit' : 'create'}
        onCancel={() => navigate(isEdit && memberId ? `/members/${memberId}` : '/members')}
        onSubmit={(payload, action) => {
          if (isEdit && memberId) {
            updateMutation.mutate({ targetId: memberId, payload });
            return;
          }
          createMutation.mutate(payload, {
            onSuccess: async (member) => {
              createMutation.reset();
              await queryClient.invalidateQueries({ queryKey: ['members'] });
              if (action === 'save-and-upload') {
                navigate(`/reports?upload=1&memberId=${member.member_id}`);
                return;
              }
              navigate('/members');
            }
          });
        }}
        saving={saving}
      />
    </AppShell>
  );
}
