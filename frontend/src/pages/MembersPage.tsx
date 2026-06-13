import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { listMembers } from '../api/members';
import { AppShell } from '../components/AppShell';
import { MemberCard } from '../components/members/MemberCard';

export function MembersPage() {
  const membersQuery = useQuery({ queryKey: ['members'], queryFn: listMembers });

  return (
    <AppShell title="家庭成员" activeId="members">
      <div className="page-header">
        <div>
          <h1>家庭成员</h1>
        </div>
        <Link className="btn-primary" to="/members/new">
          + 添加家人
        </Link>
      </div>

      {membersQuery.isLoading && <div className="empty-state">正在加载家人列表...</div>}
      {membersQuery.isError && <div className="error-box">家人列表加载失败</div>}

      {!!membersQuery.data?.length && (
        <div className="members-grid">
          {membersQuery.data.map((member) => (
            <MemberCard key={member.member_id} member={member} />
          ))}
        </div>
      )}

      {!membersQuery.isLoading && !membersQuery.data?.length && (
        <div className="empty-state">还没有家人档案，先添加第一位家人。</div>
      )}
    </AppShell>
  );
}
