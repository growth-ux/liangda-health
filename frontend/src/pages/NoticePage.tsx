import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Clock, FileText, ShoppingBag, TriangleAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  doneNotice,
  listNotices,
  readAllNotices,
  readNotice,
  snoozeNotice,
  type NoticeCategoryFilter,
  type NoticeItem,
  type NoticeLevel
} from '../api/notices';
import { AppShell } from '../components/AppShell';

const filters: { value: NoticeCategoryFilter; label: string; countKey: NoticeCategoryFilter }[] = [
  { value: 'all', label: '全部', countKey: 'all' },
  { value: 'health_alert', label: '健康预警', countKey: 'health_alert' },
  { value: 'system', label: '系统', countKey: 'system' },
  { value: 'recommendation', label: '推荐', countKey: 'recommendation' }
];

function NoticeIcon({ level, category }: { level: NoticeLevel; category: NoticeItem['category'] }) {
  if (level === 'danger') {
    return (
      <div className="notice-icon danger">
        <TriangleAlert size={18} />
      </div>
    );
  }
  if (level === 'warning') {
    return (
      <div className="notice-icon warning">
        <Clock size={18} />
      </div>
    );
  }
  if (level === 'success') {
    return (
      <div className="notice-icon success">
        <Check size={18} />
      </div>
    );
  }
  return (
    <div className="notice-icon info">
      {category === 'recommendation' ? <ShoppingBag size={18} /> : <FileText size={18} />}
    </div>
  );
}

export function NoticePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<NoticeCategoryFilter>('all');
  const noticesQuery = useQuery({
    queryKey: ['notices', category],
    queryFn: () => listNotices(category)
  });

  const refreshNotices = () => {
    queryClient.invalidateQueries({ queryKey: ['notices'] });
    queryClient.invalidateQueries({ queryKey: ['notice-summary'] });
  };

  const readMutation = useMutation({
    mutationFn: readNotice,
    onSuccess: refreshNotices
  });
  const snoozeMutation = useMutation({
    mutationFn: snoozeNotice,
    onSuccess: refreshNotices
  });
  const doneMutation = useMutation({
    mutationFn: doneNotice,
    onSuccess: refreshNotices
  });
  const readAllMutation = useMutation({
    mutationFn: readAllNotices,
    onSuccess: refreshNotices
  });

  const handlePrimaryAction = async (notice: NoticeItem) => {
    if (notice.action_text === '收到') {
      doneMutation.mutate(notice.notice_id);
      return;
    }
    await readMutation.mutateAsync(notice.notice_id);
    if (notice.target_url) {
      navigate(notice.target_url);
    }
  };

  const counts = noticesQuery.data?.counts;

  return (
    <AppShell title="通知中心" activeId="notice">
      <div className="notice-toolbar">
        <div className="notice-filters">
          {filters.map((filter) => (
            <button
              className={`btn ${category === filter.value ? 'btn-primary' : ''}`}
              key={filter.value}
              onClick={() => setCategory(filter.value)}
              type="button"
            >
              {filter.label} ({counts?.[filter.countKey] ?? 0})
            </button>
          ))}
        </div>
        <button
          className="btn"
          disabled={readAllMutation.isPending || !counts?.unread}
          onClick={() => readAllMutation.mutate()}
          type="button"
        >
          全部已读
        </button>
      </div>

      {noticesQuery.isLoading && <div className="empty-state">正在加载通知...</div>}
      {noticesQuery.isError && <div className="error-box">通知加载失败</div>}

      {!noticesQuery.isLoading && !noticesQuery.isError && !noticesQuery.data?.groups.length && (
        <div className="empty-state">暂无通知</div>
      )}

      {noticesQuery.data?.groups.map((group) => (
        <section className="card" key={group.label}>
          <div className="notice-group-title">{group.label}</div>
          <div className="notice-list">
            {group.items.map((notice) => (
              <article
                className={`notice-item ${notice.status !== 'unread' ? 'is-read' : ''}`}
                key={notice.notice_id}
              >
                <NoticeIcon level={notice.level} category={notice.category} />
                <div className="notice-body">
                  <div className="notice-title">{notice.title}</div>
                  <div className="notice-desc">{notice.description}</div>
                  <div className="notice-meta">{notice.meta_text}</div>
                </div>
                <div className="notice-actions">
                  {notice.secondary_action === '稍后' && (
                    <button
                      className="btn"
                      disabled={snoozeMutation.isPending}
                      onClick={() => snoozeMutation.mutate(notice.notice_id)}
                      type="button"
                    >
                      稍后
                    </button>
                  )}
                  {notice.action_text && (
                    <button
                      className={notice.action_text === '查看' ? 'btn-primary' : 'btn'}
                      disabled={readMutation.isPending || doneMutation.isPending}
                      onClick={() => handlePrimaryAction(notice)}
                      type="button"
                    >
                      {notice.action_text}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </AppShell>
  );
}
