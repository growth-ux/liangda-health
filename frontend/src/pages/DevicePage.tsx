import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, Heart, Moon, Smartphone, Waves } from 'lucide-react';
import { getDeviceOverview, syncDevice, type DeviceOverviewResponse } from '../api/device';
import { listMembers } from '../api/members';
import { AppShell } from '../components/AppShell';

function formatDateLabel(value: string): string {
  const date = new Date(value);
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  return week[date.getDay()] ?? value;
}

function formatSteps(value: number): string {
  return value.toLocaleString('zh-CN');
}

function formatSyncTime(value: string | null): string {
  if (!value) return '未同步';
  const date = new Date(value);
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  const hour = `${date.getHours()}`.padStart(2, '0');
  const minute = `${date.getMinutes()}`.padStart(2, '0');
  return `${month}-${day} ${hour}:${minute}`;
}

function buildChartGrid(maxValue: number, count = 5): number[] {
  const safeMax = Math.max(maxValue, count - 1);
  const step = safeMax / (count - 1);
  return Array.from({ length: count }, (_, index) => Math.round(safeMax - step * index));
}

const LINE_CHART_WIDTH = 600;
const LINE_CHART_HEIGHT = 200;
const LINE_CHART_X_PADDING = 40;
const LINE_CHART_Y_BASELINE = 180;
const LINE_CHART_Y_RANGE = 140;

function MiniBarChart({
  points,
  formatter,
  tooltipFormatter
}: {
  points: { date: string; value: number }[];
  formatter?: (value: number) => string;
  tooltipFormatter?: (point: { date: string; value: number }) => string;
}) {
  const maxValue = Math.max(...points.map((point) => point.value), 1);
  const grid = buildChartGrid(maxValue);

  return (
    <div className="device-bar-chart">
      <div className="device-chart-grid">
        {grid.map((value) => (
          <span key={value}>{formatter ? formatter(value) : value}</span>
        ))}
      </div>
      <div className="device-bar-chart-bars">
        {points.map((point) => (
          <div className="device-bar-col" key={point.date}>
            <div
              className="device-bar"
              style={{ height: `${(point.value / maxValue) * 100}%` }}
            >
              <span className="device-chart-tooltip">
                {tooltipFormatter ? tooltipFormatter(point) : `${formatDateLabel(point.date)}：${point.value}`}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="device-chart-labels">
        {points.map((point) => (
          <span key={point.date}>{formatDateLabel(point.date)}</span>
        ))}
      </div>
    </div>
  );
}

function MiniLineChart({
  points,
  stroke,
  formatter,
  labelFormatter = (point) => (point.date ? formatDateLabel(point.date) : point.time ?? ''),
  labelEvery = 1
}: {
  points: { date?: string; time?: string; value: number }[];
  stroke: string;
  formatter?: (value: number) => string;
  labelFormatter?: (point: { date?: string; time?: string; value: number }) => string;
  labelEvery?: number;
}) {
  const values = points.map((point) => point.value);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const grid = buildChartGrid(maxValue);

  const plotPoints = points.map((point, index) => {
    const usableWidth = LINE_CHART_WIDTH - LINE_CHART_X_PADDING * 2;
    const x = points.length === 1 ? LINE_CHART_WIDTH / 2 : LINE_CHART_X_PADDING + (usableWidth / (points.length - 1)) * index;
    const y = LINE_CHART_Y_BASELINE - ((point.value - minValue) / range) * LINE_CHART_Y_RANGE;
    return { ...point, x, y };
  });

  const path = plotPoints
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');

  return (
    <div className="device-line-chart">
      <div className="device-chart-grid">
        {grid.map((value) => (
          <span key={value}>{formatter ? formatter(value) : value}</span>
        ))}
      </div>
      <svg className="device-line-svg" viewBox={`0 0 ${LINE_CHART_WIDTH} ${LINE_CHART_HEIGHT}`} preserveAspectRatio="none">
        <path d={path} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {plotPoints.map((point) => (
          <circle
            key={point.date ?? point.time}
            className="device-line-point"
            cx={point.x}
            cy={point.y}
            r="4.5"
            fill="#ffffff"
            stroke={stroke}
            strokeWidth="2"
          />
        ))}
      </svg>
      <div className="device-line-hover-layer">
        {plotPoints.map((point) => (
          <span
            className="device-line-hover-point"
            key={point.date ?? point.time}
            style={{ left: `${(point.x / LINE_CHART_WIDTH) * 100}%`, top: `${(point.y / LINE_CHART_HEIGHT) * 100}%` }}
          >
            <span className="device-chart-tooltip">
              {`${labelFormatter(point)}：${formatter ? formatter(point.value) : point.value}`}
            </span>
          </span>
        ))}
      </div>
      <div className="device-chart-labels">
        {points.map((point, index) => (
          <span key={point.date ?? point.time}>
            {index > 0 && (index % labelEvery === 0 || index === points.length - 1) ? labelFormatter(point) : ''}
          </span>
        ))}
      </div>
    </div>
  );
}

function MiniBloodPressureChart({
  points
}: {
  points: { time: string; systolic: number; diastolic: number }[];
}) {
  const values = points.flatMap((point) => [point.systolic, point.diastolic]);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const grid = buildChartGrid(maxValue);

  const buildPlotPoints = (field: 'systolic' | 'diastolic') =>
    points.map((point, index) => {
      const usableWidth = LINE_CHART_WIDTH - LINE_CHART_X_PADDING * 2;
      const x = points.length === 1 ? LINE_CHART_WIDTH / 2 : LINE_CHART_X_PADDING + (usableWidth / (points.length - 1)) * index;
      const y = LINE_CHART_Y_BASELINE - ((point[field] - minValue) / range) * LINE_CHART_Y_RANGE;
      return { ...point, x, y, value: point[field] };
    });

  const systolicPoints = buildPlotPoints('systolic');
  const diastolicPoints = buildPlotPoints('diastolic');
  const buildPath = (plotPoints: typeof systolicPoints) =>
    plotPoints
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(' ');

  return (
    <div className="device-line-chart">
      <div className="device-chart-grid">
        {grid.map((value) => (
          <span key={value}>{value}</span>
        ))}
      </div>
      <svg className="device-line-svg" viewBox={`0 0 ${LINE_CHART_WIDTH} ${LINE_CHART_HEIGHT}`} preserveAspectRatio="none">
        <path d={buildPath(systolicPoints)} fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d={buildPath(diastolicPoints)} fill="none" stroke="#0ea5e9" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {systolicPoints.map((point) => (
          <circle
            key={`${point.time}-systolic`}
            className="device-line-point"
            cx={point.x}
            cy={point.y}
            r="4.2"
            fill="#ffffff"
            stroke="#ef4444"
            strokeWidth="2"
          />
        ))}
        {diastolicPoints.map((point) => (
          <circle
            key={`${point.time}-diastolic`}
            className="device-line-point"
            cx={point.x}
            cy={point.y}
            r="4.2"
            fill="#ffffff"
            stroke="#0ea5e9"
            strokeWidth="2"
          />
        ))}
      </svg>
      <div className="device-line-hover-layer">
        {systolicPoints.map((point) => (
          <span
            className="device-line-hover-point"
            key={`${point.time}-systolic`}
            style={{ left: `${(point.x / LINE_CHART_WIDTH) * 100}%`, top: `${(point.y / LINE_CHART_HEIGHT) * 100}%` }}
          >
            <span className="device-chart-tooltip">{`${point.time}：收缩压 ${point.value} mmHg`}</span>
          </span>
        ))}
        {diastolicPoints.map((point) => (
          <span
            className="device-line-hover-point"
            key={`${point.time}-diastolic`}
            style={{ left: `${(point.x / LINE_CHART_WIDTH) * 100}%`, top: `${(point.y / LINE_CHART_HEIGHT) * 100}%` }}
          >
            <span className="device-chart-tooltip">{`${point.time}：舒张压 ${point.value} mmHg`}</span>
          </span>
        ))}
      </div>
      <div className="device-chart-labels">
        {points.map((point, index) => (
          <span key={point.time}>{index > 0 && (index % 4 === 0 || index === points.length - 1) ? point.time : ''}</span>
        ))}
      </div>
      <div className="device-chart-legend">
        <span><i className="systolic" />收缩压</span>
        <span><i className="diastolic" />舒张压</span>
      </div>
    </div>
  );
}

function SyncRecordList({ logs }: { logs: DeviceOverviewResponse['sync_logs'] }) {
  return (
    <div className="device-sync-list">
      {logs.map((log, index) => (
        <div className="device-sync-item" key={`${log.date}-${log.time}-${index}`}>
          <div className={`device-sync-icon ${log.status === 'success' ? 'success' : 'warning'}`}>
            {log.status === 'success' ? '✓' : '⚠'}
          </div>
          <div className="device-sync-name">{log.message}</div>
          <div className="device-sync-time">
            {log.date} {log.time}
          </div>
        </div>
      ))}
    </div>
  );
}

export function DevicePage() {
  const queryClient = useQueryClient();
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);

  const membersQuery = useQuery({
    queryKey: ['members'],
    queryFn: listMembers
  });

  const selectedId = useMemo(() => {
    if (selectedMemberId) return selectedMemberId;
    return membersQuery.data?.[0]?.member_id ?? null;
  }, [membersQuery.data, selectedMemberId]);

  const overviewQuery = useQuery({
    queryKey: ['device-overview', selectedId],
    queryFn: () => getDeviceOverview(selectedId!),
    enabled: Boolean(selectedId)
  });

  const syncMutation = useMutation({
    mutationFn: (memberId: string) => syncDevice(memberId),
    onSuccess: async (data) => {
      queryClient.setQueryData(['device-overview', selectedId], data);
      await queryClient.invalidateQueries({ queryKey: ['device-overview', selectedId] });
    }
  });

  if (membersQuery.isLoading) {
    return (
      <AppShell title="手环设备" activeId="device">
        <div className="empty-state">正在加载家人列表...</div>
      </AppShell>
    );
  }

  if (membersQuery.isError) {
    return (
      <AppShell title="手环设备" activeId="device">
        <div className="error-box">家人列表加载失败</div>
      </AppShell>
    );
  }

  if (!membersQuery.data?.length) {
    return (
      <AppShell title="手环设备" activeId="device">
        <div className="device-empty-state">请先创建家人档案</div>
      </AppShell>
    );
  }

  if (overviewQuery.isLoading) {
    return (
      <AppShell title="手环设备" activeId="device">
        <div className="device-page-banner">
          <span>⌚</span>
          <span>
            为家人绑定手环，<strong>每日自动同步</strong>心率/血压/睡眠/血氧/步数。体征异常会触发聊天预警。
          </span>
        </div>
        <div className="empty-state">正在加载设备数据...</div>
      </AppShell>
    );
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return (
      <AppShell title="手环设备" activeId="device">
        <div className="error-box">设备数据加载失败</div>
      </AppShell>
    );
  }

  const overview = overviewQuery.data;

  return (
    <AppShell title="手环设备" activeId="device">
      <div className="device-page-banner">
        <span>⌚</span>
        <span>
          为家人绑定手环，<strong>每日自动同步</strong>心率/血压/睡眠/血氧/步数。体征异常会触发聊天预警。
        </span>
      </div>

      <div className="device-role-switch">
        {membersQuery.data.map((member) => (
          <button
            key={member.member_id}
            className={`device-role-tab ${selectedId === member.member_id ? 'active' : ''}`}
            onClick={() => setSelectedMemberId(member.member_id)}
            type="button"
          >
            <span className="device-role-name">{member.name}</span>
            <span className="device-role-relation">{member.relation}</span>
          </button>
        ))}
      </div>

      <div className="device-stat-grid">
        <div className="device-stat">
          <div className="device-stat-head">
            <Smartphone size={14} />
            设备状态
          </div>
          <div className="device-device-name">{overview.device.device_name}</div>
          <div className="device-status-row">{overview.device.device_status === 'connected' ? '● 已连接' : '● 未连接'}</div>
          <div className="device-battery">电量 {overview.device.battery_level}%</div>
          <div className="device-last-sync">最近同步 {formatSyncTime(overview.device.last_sync_at)}</div>
          <button
            className="device-sync-btn"
            disabled={!selectedId || syncMutation.isPending}
            onClick={() => selectedId && syncMutation.mutate(selectedId)}
            type="button"
          >
            {syncMutation.isPending ? '同步中...' : '↻ 同步'}
          </button>
        </div>

        <div className="device-stat">
          <div className="device-stat-head accent-green">
            <Activity size={14} />
            今日步数
          </div>
          <div className="device-stat-value">{formatSteps(overview.summary.steps)}</div>
          <div className="device-stat-sub">
            目标：{formatSteps(overview.summary.steps_target)}
            <span className="target">血压 {overview.summary.blood_pressure}</span>
          </div>
        </div>

        <div className="device-stat">
          <div className="device-stat-head accent-red">
            <Heart size={14} />
            平均心率
          </div>
          <div className="device-stat-value danger">{overview.summary.avg_heart_rate}</div>
          <div className="device-stat-sub">
            bpm
            <span className="target">{overview.summary.heart_rate_range_text}</span>
          </div>
        </div>

        <div className="device-stat">
          <div className="device-stat-head accent-blue">
            <Moon size={14} />
            昨夜睡眠
          </div>
          <div className="device-stat-value">{overview.summary.sleep_hours.toFixed(1)}h</div>
          <div className="device-stat-sub">
            目标：{overview.summary.sleep_target.toFixed(1)}h
            <span className="target">血氧 {overview.summary.blood_oxygen}%</span>
          </div>
        </div>
      </div>

      <div className="device-chart-row">
        <div className="device-chart-card">
          <div className="device-chart-title">本周步数</div>
          <MiniBarChart
            points={overview.charts.steps_7d.map((point) => ({ ...point, value: Number(point.value) }))}
            formatter={(value) => String(value)}
            tooltipFormatter={(point) => `${formatDateLabel(point.date)}：${formatSteps(point.value)} 步`}
          />
        </div>

        <div className="device-chart-card">
          <div className="device-chart-title">最近 24 小时心率</div>
          <MiniLineChart
            points={overview.charts.heart_rate_24h.map((point) => ({ ...point, value: Number(point.value) }))}
            stroke="#ef4444"
            formatter={(value) => `${value} bpm`}
            labelFormatter={(point) => point.time ?? ''}
            labelEvery={4}
          />
        </div>
      </div>

      <div className="device-chart-row">
        <div className="device-chart-card">
          <div className="device-chart-title">近 7 天睡眠</div>
          <MiniBarChart
            points={overview.charts.sleep_7d.map((point) => ({ ...point, value: Number(point.value) }))}
            formatter={(value) => value.toFixed(1)}
            tooltipFormatter={(point) => `${formatDateLabel(point.date)}：${point.value.toFixed(1)} 小时`}
          />
        </div>

        <div className="device-chart-card">
          <div className="device-chart-title">最近 24 小时血压</div>
          <MiniBloodPressureChart points={overview.charts.blood_pressure_24h} />
        </div>
      </div>

      <div className="card">
        <div className="card-title">数据同步记录</div>
        <SyncRecordList logs={overview.sync_logs} />
      </div>

      <div className="device-privacy-note">
        <div className="device-privacy-icon">
          <Waves size={16} />
        </div>
        <div>
          <strong>数据隐私：</strong>体征数据仅用于生成健康建议与商品推荐，不会用于其他用途。父母无需独立登录账号，由主账号统一管理。
        </div>
      </div>
    </AppShell>
  );
}
