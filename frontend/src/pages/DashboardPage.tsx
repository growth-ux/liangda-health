import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Clock3,
  Coins,
  FileText,
  Flame,
  HeartPulse,
  Landmark,
  Layers,
  LayoutGrid,
  MessageCircle,
  Radio,
  ShoppingBag,
  Sparkles,
  TrendingUp,
  Users
} from 'lucide-react';
import {
  getDashboard,
  type DashboardResponse,
  type LiveEvent,
  type LiveEventType
} from '../api/dashboard';

function formatNumber(value: number): string {
  return value.toLocaleString('zh-CN');
}

function formatMoney(value: number): string {
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const LIVE_EVENT_META: Record<LiveEventType, { label: string; className: string }> = {
  report_upload: { label: '报告上传', className: 'upload' },
  fact_extract: { label: '事实提取', className: 'fact' },
  ai_recommend: { label: 'AI 推荐', className: 'recommend' },
  ai_card: { label: 'AI 服务', className: 'card' },
  cart_add: { label: '加购转化', className: 'cart' }
};

const CARD_KIND_LABEL: Record<string, string> = {
  meal_plan: '膳食计划',
  kb_interpretation: '报告解读',
  qa: '健康问答',
  greeting: '问候关怀',
  general_advice: '健康建议'
};

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function useClock(): string {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const pad = (v: number) => String(v).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}

function KpiBand({ data }: { data: DashboardResponse }) {
  const households = Math.max(Math.round(data.overview.member_count / 4), 0);

  return (
    <div className="dash-kpi-band">
      <div className="dash-kpi glow-green">
        <div className="dash-kpi-head"><Users size={14} /> 覆盖家庭成员</div>
        <div className="dash-kpi-value">{formatNumber(data.overview.member_count)}</div>
        <div className="dash-kpi-sub">约 {formatNumber(households)} 个家庭</div>
      </div>
      <div className="dash-kpi glow-cyan">
        <div className="dash-kpi-head"><FileText size={14} /> 健康报告归档</div>
        <div className="dash-kpi-value">{formatNumber(data.overview.report_count)}</div>
        <div className="dash-kpi-sub">PDF / OCR 结构化入库</div>
      </div>
      <div className="dash-kpi glow-cyan">
        <div className="dash-kpi-head"><HeartPulse size={14} /> 健康事实沉淀</div>
        <div className="dash-kpi-value">{formatNumber(data.overview.health_fact_count)}</div>
        <div className="dash-kpi-sub">每条可追溯原文证据</div>
      </div>
      <div className="dash-kpi glow-cyan">
        <div className="dash-kpi-head"><MessageCircle size={14} /> AI 对话轮次</div>
        <div className="dash-kpi-value">{formatNumber(data.overview.message_count)}</div>
        <div className="dash-kpi-sub">{formatNumber(data.overview.session_count)} 个会话</div>
      </div>
      <div className="dash-kpi glow-amber hero">
        <div className="dash-kpi-head"><Coins size={14} /> 预估转化金额</div>
        <div className="dash-kpi-value">
          {formatMoney(data.overview.cart_amount_yuan)}
          <span className="dash-kpi-unit">元</span>
        </div>
        <div className="dash-kpi-sub">按加购商品实时计价</div>
      </div>
      <div className="dash-kpi glow-red">
        <div className="dash-kpi-head"><ShoppingBag size={14} /> 加入购物车</div>
        <div className="dash-kpi-value">{formatNumber(data.overview.cart_item_count)}</div>
        <div className="dash-kpi-sub">健康推荐转化承接</div>
      </div>
    </div>
  );
}

function BrandMatrixPanel({ data }: { data: DashboardResponse }) {
  const maxCount = Math.max(...data.brand_ranks.map((item) => item.recommend_count), 1);

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <LayoutGrid size={15} />
        品牌转化矩阵
        <span className="dash-panel-tag">推荐次数 / 加购 / 转化额</span>
      </div>
      {!data.brand_ranks.length && <div className="dash-empty">暂无推荐数据</div>}
      <div className="dash-brand-list">
        {data.brand_ranks.map((item, index) => (
          <div className="dash-brand-row" key={item.brand}>
            <div className={`dash-brand-rank ${index < 3 ? 'top' : ''}`}>{index + 1}</div>
            <div className="dash-brand-info">
              <div className="dash-brand-name">
                {item.brand}
                {item.category_name && <span className="dash-brand-category">{item.category_name}</span>}
              </div>
              <div className="dash-brand-bar-track">
                <div
                  className="dash-brand-bar"
                  style={{ width: `${Math.max((item.recommend_count / maxCount) * 100, 3)}%` }}
                />
              </div>
            </div>
            <div className="dash-brand-nums">
              <span className="dash-brand-recommend">{formatNumber(item.recommend_count)} 次推荐</span>
              <span className="dash-brand-cart">{formatNumber(item.cart_count)} 加购</span>
            </div>
            <div className="dash-brand-amount">¥{formatNumber(item.amount_yuan)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function FunnelPanel({ data }: { data: DashboardResponse }) {
  const maxValue = Math.max(...data.funnel.map((step) => step.value), 1);
  const first = data.funnel[0]?.value ?? 0;
  const last = data.funnel[data.funnel.length - 1]?.value ?? 0;
  const rate = first > 0 ? Math.round((last / first) * 100) : 0;

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <TrendingUp size={15} />
        推荐转化漏斗
        <span className="dash-panel-tag">AI 驱动全链路</span>
      </div>
      <div className="dash-funnel">
        {data.funnel.map((step) => (
          <div className="dash-funnel-row" key={step.name}>
            <div className="dash-funnel-label">{step.name}</div>
            <div className="dash-funnel-track">
              <div
                className="dash-funnel-bar"
                style={{ width: `${Math.max((step.value / maxValue) * 100, 4)}%` }}
              />
            </div>
            <div className="dash-funnel-value">{formatNumber(step.value)}</div>
          </div>
        ))}
      </div>
      <div className="dash-funnel-rate">
        <div className="dash-funnel-rate-label">推荐消息 → 加购 转化率</div>
        <div className="dash-funnel-rate-value">{rate}%</div>
        <div className="dash-funnel-rate-sub">画像 + 记忆驱动的个性化推荐</div>
      </div>
    </section>
  );
}

function CategoryPanel({ data }: { data: DashboardResponse }) {
  const items = data.category_penetration;
  const maxCount = Math.max(...items.map((item) => item.recommend_count), 1);
  const totalCount = items.reduce((sum, item) => sum + item.recommend_count, 0);
  const top3Rate = totalCount > 0
    ? Math.round((items.slice(0, 3).reduce((sum, item) => sum + item.recommend_count, 0) / totalCount) * 100)
    : 0;

  return (
    <section className="dash-panel dash-panel-fill">
      <div className="dash-panel-title">
        <Layers size={15} />
        品类推荐渗透
        <span className="dash-panel-tag">Top {items.length}</span>
      </div>
      {!items.length && <div className="dash-empty">暂无推荐数据</div>}
      <div className="dash-category-list">
        {items.map((item, index) => (
          <div className="dash-category-row" key={item.category_name}>
            <div className={`dash-category-rank ${index < 3 ? 'top' : ''}`}>{index + 1}</div>
            <div className="dash-category-info">
              <div className="dash-category-head">
                <span className="dash-category-name" title={item.category_name}>{item.category_name}</span>
                <span className="dash-category-value">{formatNumber(item.recommend_count)}</span>
              </div>
              <div className="dash-category-track">
                <div
                  className="dash-category-bar"
                  style={{ width: `${Math.max((item.recommend_count / maxCount) * 100, 3)}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
      {items.length > 0 && (
        <div className="dash-category-foot">
          <div className="dash-category-foot-item">
            <div className="dash-category-foot-value">{formatNumber(totalCount)}</div>
            <div className="dash-category-foot-label">品类推荐总量</div>
          </div>
          <div className="dash-category-foot-item">
            <div className="dash-category-foot-value">{top3Rate}%</div>
            <div className="dash-category-foot-label">TOP3 集中度</div>
          </div>
          <div className="dash-category-foot-item">
            <div className="dash-category-foot-value">{items.length}</div>
            <div className="dash-category-foot-label">覆盖品类</div>
          </div>
        </div>
      )}
    </section>
  );
}

function TrendPanel({ data }: { data: DashboardResponse }) {
  const points = data.daily_trend;
  const maxCount = Math.max(...points.map((point) => point.message_count), 1);
  const halfCount = Math.round(maxCount / 2);
  const totalMessages = points.reduce((sum, point) => sum + point.message_count, 0);

  return (
    <section className="dash-panel dash-panel-fill">
      <div className="dash-panel-title">
        <TrendingUp size={15} />
        AI 互动趋势
        <span className="dash-panel-tag">近 14 天 · 共 {formatNumber(totalMessages)} 轮</span>
      </div>
      <div className="dash-trend-chart">
        <div className="dash-trend-grid">
          <i style={{ bottom: '100%' }}><b>{maxCount}</b></i>
          <i style={{ bottom: '50%' }}><b>{halfCount}</b></i>
          <i style={{ bottom: 0 }}><b>0</b></i>
        </div>
        <div className="dash-trend-bars">
          {points.map((point) => (
            <div className="dash-trend-col" key={point.date}>
              <div className="dash-trend-tip">
                {point.date.slice(5)} · 对话 {point.message_count} · 推荐 {point.recommendation_count}
              </div>
              <div className="dash-trend-stack" style={{ height: `${Math.max((point.message_count / maxCount) * 100, point.message_count > 0 ? 6 : 0)}%` }}>
                <div className="dash-trend-seg recommend" style={{ flex: point.recommendation_count }} />
                <div className="dash-trend-seg normal" style={{ flex: Math.max(point.message_count - point.recommendation_count, 0) }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="dash-trend-ticks">
        {points.map((point, index) => (
          <span key={point.date}>
            {index % 3 === 0 || index === points.length - 1 ? point.date.slice(5) : ''}
          </span>
        ))}
      </div>
      <div className="dash-trend-legend">
        <span><i className="recommend" /> 推荐消息</span>
        <span><i className="normal" /> 普通对话</span>
      </div>
    </section>
  );
}

function FactPanel({ data }: { data: DashboardResponse }) {
  const { normal, warning, danger } = data.fact_status;
  const total = normal + warning + danger;
  const items = [
    { label: '需重点干预', value: danger, className: 'danger' },
    { label: '建议关注', value: warning, className: 'warning' },
    { label: '指标正常', value: normal, className: 'normal' }
  ];
  const doneRate = data.notice_done.total > 0 ? Math.round(data.notice_done.rate * 100) : 0;

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <BadgeCheck size={15} />
        健康干预成效
      </div>
      {!total && <div className="dash-empty">暂无健康事实</div>}
      {total > 0 && (
        <>
          <div className="dash-fact-dist">
            <i className="danger" style={{ width: `${(danger / total) * 100}%` }} />
            <i className="warning" style={{ width: `${(warning / total) * 100}%` }} />
            <i className="normal" style={{ width: `${(normal / total) * 100}%` }} />
          </div>
          <div className="dash-fact-list">
            {items.map((item) => (
              <div className="dash-fact-row" key={item.label}>
                <span className={`dash-fact-dot ${item.className}`} />
                <span className="dash-fact-label">{item.label}</span>
                <span className="dash-fact-value">{formatNumber(item.value)} 条</span>
                <span className="dash-fact-rate">{Math.round((item.value / total) * 100)}%</span>
              </div>
            ))}
          </div>
          <div className="dash-fact-progress">
            <div className="dash-fact-progress-head">
              <span>健康提醒完成率</span>
              <strong>{doneRate}%</strong>
            </div>
            <div className="dash-fact-progress-track">
              <i style={{ width: `${doneRate}%` }} />
            </div>
            <div className="dash-fact-progress-sub">
              已完成 {data.notice_done.done}/{data.notice_done.total} · 每条事实可追溯报告原文与页码证据
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function AiUsagePanel({ data }: { data: DashboardResponse }) {
  const { ai_usage, overview } = data;
  const totalTokens = ai_usage.token_prompt_total + ai_usage.token_completion_total;
  const recommendRate = overview.message_count > 0
    ? Math.round((overview.recommendation_count / overview.message_count) * 100)
    : 0;

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <Sparkles size={15} />
        AI 用量与成本
      </div>
      <div className="dash-usage-grid">
        <div className="dash-usage-item">
          <div className="dash-usage-label">主力模型</div>
          <div className="dash-usage-value">{ai_usage.model_name ?? '未配置'}</div>
          <div className="dash-usage-sub">百炼 · 通义千问</div>
        </div>
        <div className="dash-usage-item">
          <div className="dash-usage-label">累计 Token</div>
          <div className="dash-usage-value">{formatNumber(totalTokens)}</div>
          <div className="dash-usage-sub">入 {formatNumber(ai_usage.token_prompt_total)} / 出 {formatNumber(ai_usage.token_completion_total)}</div>
        </div>
        <div className="dash-usage-item">
          <div className="dash-usage-label">估算成本</div>
          <div className="dash-usage-value">¥{ai_usage.estimated_cost_yuan.toFixed(2)}</div>
          <div className="dash-usage-sub">按公开计费估算</div>
        </div>
        <div className="dash-usage-item">
          <div className="dash-usage-label">推荐消息占比</div>
          <div className="dash-usage-value">{recommendRate}%</div>
          <div className="dash-usage-sub">推荐消息 / 总对话</div>
        </div>
      </div>
    </section>
  );
}

function LiveTicker({ events }: { events: LiveEvent[] }) {
  if (!events.length) return null;
  const duration = Math.max(events.length * 7, 36);
  const items = [...events, ...events];

  return (
    <div className="dash-ticker">
      <div className="dash-ticker-label">
        <Radio size={13} /> 实时动态
      </div>
      <div className="dash-ticker-viewport">
        <div className="dash-ticker-track" style={{ animationDuration: `${duration}s` }}>
          {items.map((event, index) => {
            const meta = LIVE_EVENT_META[event.event_type] ?? { label: '动态', className: 'fact' };
            return (
              <span className="dash-ticker-item" key={`${event.occurred_at}-${index}`}>
                <i className={`dash-ticker-tag ${meta.className}`}>{meta.label}</i>
                {event.text}
                <em>{event.occurred_at.slice(5, 16).replace('T', ' ')}</em>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function MemberProfilePanel({ data }: { data: DashboardResponse }) {
  const { member_profile } = data;
  const maxBand = Math.max(...member_profile.age_bands.map((item) => item.count), 1);
  const hasData = member_profile.age_bands.some((item) => item.count > 0);

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <Users size={15} />
        家庭成员画像
        <span className="dash-panel-tag">年龄 / 角色 / 健康标签</span>
      </div>
      {!hasData && <div className="dash-empty">暂无成员数据</div>}
      {hasData && (
        <>
          <div className="dash-profile-block">
            {member_profile.age_bands.map((band) => (
              <div className="dash-profile-row" key={band.name}>
                <div className="dash-profile-label">{band.name}</div>
                <div className="dash-profile-track">
                  <div
                    className="dash-profile-bar"
                    style={{ width: `${Math.max((band.count / maxBand) * 100, band.count > 0 ? 4 : 0)}%` }}
                  />
                </div>
                <div className="dash-profile-value">{band.count} 人</div>
              </div>
            ))}
          </div>
          <div className="dash-profile-chips">
            {member_profile.gender_distribution.map((item) => (
              <span className="dash-chip" key={`gender-${item.name}`}>
                {item.name} <b>{item.count}</b>
              </span>
            ))}
            {member_profile.relation_distribution.map((item) => (
              <span className="dash-chip" key={`relation-${item.name}`}>
                {item.name} <b>{item.count}</b>
              </span>
            ))}
          </div>
          {member_profile.health_tag_cloud.length > 0 && (
            <div className="dash-tag-cloud">
              {member_profile.health_tag_cloud.map((tag, index) => (
                <span
                  className={`dash-tag-item dash-tag-size-${index < 3 ? 'lg' : index < 7 ? 'md' : 'sm'}`}
                  key={tag.name}
                >
                  {tag.name}×{tag.count}
                </span>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function HealthRiskPanel({ data }: { data: DashboardResponse }) {
  const maxTotal = Math.max(
    ...data.fact_risk_top.map((item) => item.warning_count + item.danger_count),
    1
  );

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <AlertTriangle size={15} />
        健康风险雷达
        <span className="dash-panel-tag">异常指标 / 重点成员</span>
      </div>
      {!data.fact_risk_top.length && <div className="dash-empty">暂无异常健康事实</div>}
      {data.fact_risk_top.length > 0 && (
        <div className="dash-risk-list">
          {data.fact_risk_top.map((item) => {
            const total = item.warning_count + item.danger_count;
            return (
              <div className="dash-risk-row" key={item.name}>
                <div className="dash-risk-name" title={item.name}>{item.name}</div>
                <div className="dash-risk-track">
                  <div className="dash-risk-bar danger" style={{ width: `${(item.danger_count / maxTotal) * 100}%` }} />
                  <div className="dash-risk-bar warning" style={{ width: `${(item.warning_count / maxTotal) * 100}%` }} />
                </div>
                <div className="dash-risk-value">{total} 条</div>
              </div>
            );
          })}
        </div>
      )}
      {data.risk_members.length > 0 && (
        <>
          <div className="dash-risk-subtitle">重点干预成员</div>
          <div className="dash-risk-members">
            {data.risk_members.map((member) => (
              <div className="dash-risk-member" key={member.member_id}>
                <span className="dash-risk-member-name">
                  {member.member_name}
                  {member.relation && <i>{member.relation}</i>}
                </span>
                <span className="dash-risk-member-badges">
                  {member.danger_count > 0 && <b className="danger">干预 {member.danger_count}</b>}
                  {member.warning_count > 0 && <b className="warning">关注 {member.warning_count}</b>}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function HotProductPanel({ data }: { data: DashboardResponse }) {
  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <Flame size={15} />
        AI 爆品榜
        <span className="dash-panel-tag">推荐 / 加购 / 转化额</span>
      </div>
      {!data.hot_products.length && <div className="dash-empty">暂无推荐商品</div>}
      <div className="dash-hot-list">
        {data.hot_products.map((item, index) => (
          <div className="dash-hot-row" key={item.product_id}>
            <div className={`dash-brand-rank ${index < 3 ? 'top' : ''}`}>{index + 1}</div>
            <div className="dash-hot-thumb">{item.image_emoji ?? '📦'}</div>
            <div className="dash-hot-info">
              <div className="dash-hot-name" title={item.name}>{item.name}</div>
              <div className="dash-hot-meta">
                {item.brand}{item.category_name ? ` · ${item.category_name}` : ''} · ¥{formatMoney(item.price_yuan)}
              </div>
            </div>
            <div className="dash-hot-nums">
              <span className="dash-brand-recommend">{formatNumber(item.recommend_count)} 推荐</span>
              <span className="dash-brand-cart">{formatNumber(item.cart_count)} 加购</span>
            </div>
            <div className="dash-brand-amount">¥{formatNumber(item.amount_yuan)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function HeatmapPanel({ data }: { data: DashboardResponse }) {
  const { counts, maxCount } = useMemo(() => {
    const map = new Map<string, number>();
    let max = 0;
    for (const point of data.interaction_heatmap) {
      map.set(`${point.weekday}-${point.hour}`, point.count);
      max = Math.max(max, point.count);
    }
    return { counts: map, maxCount: max };
  }, [data.interaction_heatmap]);

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <Clock3 size={15} />
        AI 对话热力图
        <span className="dash-panel-tag">星期 × 时段 · 用户提问</span>
      </div>
      {maxCount === 0 && <div className="dash-empty">暂无对话数据</div>}
      {maxCount > 0 && (
        <>
          <div className="dash-heatmap">
            {WEEKDAY_LABELS.map((label, weekday) => (
              <div className="dash-heatmap-row" key={label}>
                <span className="dash-heatmap-label">{label}</span>
                {Array.from({ length: 24 }, (_, hour) => {
                  const count = counts.get(`${weekday}-${hour}`) ?? 0;
                  return (
                    <i
                      key={hour}
                      className="dash-heatmap-cell"
                      style={{ opacity: count > 0 ? 0.25 + (0.75 * count) / maxCount : 0.06 }}
                      title={`${label} ${hour}:00 · ${count} 轮提问`}
                    />
                  );
                })}
              </div>
            ))}
            <div className="dash-heatmap-axis">
              <span />
              <em>0时</em>
              <em>6时</em>
              <em>12时</em>
              <em>18时</em>
              <em>23时</em>
            </div>
          </div>
          <div className="dash-heatmap-note">颜色越亮代表该时段家庭与 AI 的互动越密集</div>
        </>
      )}
    </section>
  );
}

function AiServicePanel({ data }: { data: DashboardResponse }) {
  const { card_usage, session_depth } = data;
  const maxCount = Math.max(...card_usage.map((item) => item.count), 1);

  return (
    <section className="dash-panel">
      <div className="dash-panel-title">
        <Layers size={15} />
        AI 服务结构
        <span className="dash-panel-tag">结构化卡片 / 会话深度</span>
      </div>
      {!card_usage.length && <div className="dash-empty">暂无结构化服务</div>}
      {card_usage.length > 0 && (
        <div className="dash-service-list">
          {card_usage.map((item) => (
            <div className="dash-service-row" key={item.kind}>
              <div className="dash-service-name">{CARD_KIND_LABEL[item.kind] ?? item.kind}</div>
              <div className="dash-service-track">
                <div
                  className="dash-service-bar"
                  style={{ width: `${Math.max((item.count / maxCount) * 100, 4)}%` }}
                />
              </div>
              <div className="dash-service-value">{formatNumber(item.count)} 次</div>
            </div>
          ))}
        </div>
      )}
      <div className="dash-depth-row">
        <div className="dash-depth-item">
          <div className="dash-depth-value">{formatNumber(session_depth.session_count)}</div>
          <div className="dash-depth-label">会话总数</div>
        </div>
        <div className="dash-depth-item">
          <div className="dash-depth-value">{session_depth.avg_user_turns.toFixed(1)}</div>
          <div className="dash-depth-label">平均提问轮次</div>
        </div>
        <div className="dash-depth-item">
          <div className="dash-depth-value">{formatNumber(session_depth.max_user_turns)}</div>
          <div className="dash-depth-label">单会话最深轮次</div>
        </div>
      </div>
    </section>
  );
}

export function DashboardPage() {
  const clock = useClock();
  const dashboardQuery = useQuery({
    queryKey: ['admin-dashboard'],
    queryFn: getDashboard,
    refetchInterval: 10_000
  });

  return (
    <div className="dash-page">
      <div className="dash-inner">
        <div className="dash-topbar">
          <div className="dash-topbar-title">
            <div className="dash-logo"><Landmark size={20} /></div>
            <div>
              <h1>粮达健康 · 集团经营驾驶舱</h1>
              <div className="dash-topbar-sub">B2B2C 家庭健康数据资产 · 智能营销转化</div>
            </div>
          </div>
          <div className="dash-topbar-right">
            <span className="dash-live-badge"><i className="dash-live-dot" /> 演示数据 · 实时聚合</span>
            <span className="dash-clock">{clock}</span>
            <Link to="/chat" className="dash-back-link"><ArrowLeft size={14} /> 返回家庭端</Link>
          </div>
        </div>

        {dashboardQuery.isLoading && <div className="dash-empty">正在汇总集团经营数据...</div>}
        {dashboardQuery.isError && <div className="dash-empty">经营数据加载失败，请检查后端服务</div>}

        {dashboardQuery.data && (
          <>
            <KpiBand data={dashboardQuery.data} />
            <LiveTicker events={dashboardQuery.data.live_events} />
            <div className="dash-grid-3">
              <BrandMatrixPanel data={dashboardQuery.data} />
              <FunnelPanel data={dashboardQuery.data} />
              <CategoryPanel data={dashboardQuery.data} />
            </div>
            <div className="dash-grid-3">
              <MemberProfilePanel data={dashboardQuery.data} />
              <HealthRiskPanel data={dashboardQuery.data} />
              <HotProductPanel data={dashboardQuery.data} />
            </div>
            <div className="dash-grid-2">
              <TrendPanel data={dashboardQuery.data} />
              <div className="dash-stack">
                <HeatmapPanel data={dashboardQuery.data} />
                <AiServicePanel data={dashboardQuery.data} />
              </div>
            </div>
            <div className="dash-grid-2">
              <FactPanel data={dashboardQuery.data} />
              <AiUsagePanel data={dashboardQuery.data} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
