import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, ExternalLink } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getHealthAnalysisOverview,
  type HealthAnalysisOverview,
  type HealthAnalysisRange
} from '../api/healthAnalysis';
import { AppShell } from '../components/AppShell';

const rangeOptions: { value: HealthAnalysisRange; label: string }[] = [
  { value: 'this_month', label: '本月' },
  { value: 'last_3_months', label: '近 3 月' },
  { value: 'last_6_months', label: '近 6 月' },
  { value: 'last_12_months', label: '近 1 年' }
];

function metricTrend(delta: number): string {
  if (delta > 0) return `↑ ${delta} 较上月`;
  if (delta < 0) return `↓ ${Math.abs(delta)} 较上月`;
  return '较上月持平';
}

function statusClass(status: 'success' | 'warning' | 'danger'): string {
  if (status === 'danger') return 'tag tag-danger';
  if (status === 'warning') return 'tag tag-warning';
  return 'tag tag-success';
}

function summaryClass(level: HealthAnalysisOverview['summary'][number]['level']): string {
  return `health-summary-${level}`;
}

export function HealthAnalysisPage() {
  const navigate = useNavigate();
  const [range, setRange] = useState<HealthAnalysisRange>('this_month');
  const overviewQuery = useQuery({
    queryKey: ['health-analysis', range],
    queryFn: () => getHealthAnalysisOverview(range)
  });

  const overview = overviewQuery.data;
  const hasMembers = (overview?.member_cards.length ?? 0) > 0;
  const rows = useMemo(() => overview?.abnormal_items ?? [], [overview]);

  return (
    <AppShell title="家庭健康分析" activeId="report">
      <div className="health-analysis-head">
        <div>
          <div className="health-analysis-family">{overview?.family.name ?? '张雨微的家庭'}</div>
          <div className="health-analysis-title">
            健康分析
            <span>· {overview?.family.period_label ?? '-'}</span>
          </div>
        </div>
        <div className="health-analysis-actions">
          <select
            className="form-select health-analysis-range"
            value={range}
            onChange={(event) => setRange(event.target.value as HealthAnalysisRange)}
          >
            {rangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button className="btn-secondary" type="button">
            <Download size={16} />
            导出
          </button>
        </div>
      </div>

      {overviewQuery.isLoading && <div className="empty-state">正在加载健康分析...</div>}
      {overviewQuery.isError && <div className="error-box">健康分析加载失败</div>}

      {!overviewQuery.isLoading && !overviewQuery.isError && overview && !hasMembers && (
        <div className="empty-state">
          暂无家人档案，请先到<Link to="/members">家人页面</Link>创建档案。
        </div>
      )}

      {!overviewQuery.isLoading && !overviewQuery.isError && overview && hasMembers && (
        <>
          <div className="health-metric-grid">
            <div className="health-metric">
              <div className="health-metric-label">家庭综合分</div>
              <div className="health-metric-value">{overview.metrics.family_score}</div>
              <div className="health-metric-trend">{metricTrend(overview.metrics.family_score_delta)}</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">待关注指标</div>
              <div className="health-metric-value danger">{overview.metrics.attention_count}</div>
              <div className="health-metric-trend">项需干预</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">已存报告</div>
              <div className="health-metric-value">{overview.metrics.report_count}</div>
              <div className="health-metric-trend">份</div>
            </div>
            <div className="health-metric">
              <div className="health-metric-label">已绑设备</div>
              <div className="health-metric-value primary">{overview.metrics.device_count}</div>
              <div className="health-metric-trend">只手环</div>
            </div>
          </div>

          <section className="health-summary-card">
            <div className="card-title">本周家庭健康摘要（Agent 生成）</div>
            <ul>
              {overview.summary.map((item) => (
                <li key={item.text} className={summaryClass(item.level)}>
                  {item.text}
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <div className="card-title">异常指标 Top 5</div>
            <table className="table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>家人</th>
                  <th>当前值</th>
                  <th>状态</th>
                  <th>趋势</th>
                  <th>建议</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((item) => (
                  <tr key={`${item.member_id}-${item.metric}-${item.current_value}`}>
                    <td>{item.metric}</td>
                    <td>
                      {item.member_name}（{item.member_relation}）
                    </td>
                    <td>{item.current_value}</td>
                    <td>
                      <span className={statusClass(item.status)}>{item.status_text}</span>
                    </td>
                    <td>{item.trend_text}</td>
                    <td>
                      <button
                        className="health-link-button"
                        onClick={() =>
                          navigate(
                            `/chat?prompt=${encodeURIComponent(
                              `请根据${item.member_name}的${item.metric}问题给出家庭健康建议：${item.suggestion}`
                            )}`
                          )
                        }
                        type="button"
                      >
                        看建议
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="card-title">各成员健康卡</div>
            <div className="health-member-grid">
              {overview.member_cards.map((member) => (
                <button
                  className="health-member-card"
                  key={member.member_id}
                  onClick={() => navigate(`/members/${member.member_id}`)}
                  type="button"
                >
                  <div className="health-member-avatar">{member.avatar_text}</div>
                  <div className="health-member-info">
                    <div className="health-member-name">
                      <span>{member.relation} ·</span>
                      {member.name}
                      <span className={statusClass(member.status)}>{member.status_text}</span>
                    </div>
                    <div className="health-member-meta">
                      {member.age}岁 · 健康分 {member.health_score}
                    </div>
                  </div>
                  <ExternalLink size={16} />
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </AppShell>
  );
}
