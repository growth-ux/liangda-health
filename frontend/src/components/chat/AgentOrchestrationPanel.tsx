import { useState, useEffect } from 'react';
import type { AgentActivityPayload } from '../../api/agent';

type AgentKey = AgentActivityPayload['agent'];

type AgentTrace = {
  status: 'idle' | 'working' | 'done';
  detail: string;
  task?: string;
  resultSummary?: string;
  elapsedSeconds?: number;
  userQuery?: string;
  outputSummary?: string;
  startedAt?: number;
};

type TraceState = Record<AgentKey, AgentTrace>;

const INITIAL_TRACE: TraceState = {
  supervisor: { status: 'idle', detail: '' },
  meal_planner: { status: 'idle', detail: '' },
  shopping_guide: { status: 'idle', detail: '' },
  report_reader: { status: 'idle', detail: '' }
};

const AGENTS: { key: AgentKey; label: string; emoji: string }[] = [
  { key: 'supervisor', label: '调度中心', emoji: '🧭' },
  { key: 'meal_planner', label: '餐单规划师', emoji: '🥗' },
  { key: 'shopping_guide', label: '商品导购师', emoji: '🛒' },
  { key: 'report_reader', label: '报告解读师', emoji: '📋' }
];

function formatElapsed(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  return `${seconds}s`;
}

function ElapsedTimer({ startedAt, finalSeconds }: { startedAt?: number; finalSeconds?: number }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!startedAt || finalSeconds != null) return;
    const interval = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(interval);
  }, [startedAt, finalSeconds]);

  if (finalSeconds != null) {
    return <span className="aoa-time">{formatElapsed(finalSeconds)}</span>;
  }
  if (startedAt) {
    return <span className="aoa-time aoa-time-live">{formatElapsed((now - startedAt) / 1000)}</span>;
  }
  return null;
}

function AgentCard({ agent, trace }: { agent: typeof AGENTS[number]; trace: AgentTrace }) {
  if (trace.status === 'idle') return null;

  return (
    <div className={`aoa-card aoa-card-${trace.status}`}>
      <div className="aoa-card-header">
        <span className="aoa-card-emoji">{agent.emoji}</span>
        <span className="aoa-card-label">{agent.label}</span>
        <span className={`aoa-card-badge aoa-card-badge-${trace.status}`}>
          {trace.status === 'working' ? '执行中' : '已完成'}
        </span>
        <span className="aoa-card-timer">
          <ElapsedTimer startedAt={trace.startedAt} finalSeconds={trace.elapsedSeconds} />
        </span>
      </div>
      {trace.userQuery && (
        <div className="aoa-card-section">
          <div className="aoa-card-section-label">用户问题</div>
          <div className="aoa-card-section-text">{trace.userQuery}</div>
        </div>
      )}
      {trace.task && (
        <div className="aoa-card-section">
          <div className="aoa-card-section-label">分派任务</div>
          <div className="aoa-card-section-text">{trace.task}</div>
        </div>
      )}
      {trace.resultSummary && (
        <div className="aoa-card-section">
          <div className="aoa-card-section-label">处理结果</div>
          <div className="aoa-card-section-text aoa-card-result">{trace.resultSummary}</div>
        </div>
      )}
      {trace.outputSummary && (
        <div className="aoa-card-section">
          <div className="aoa-card-section-label">生成回复</div>
          <div className="aoa-card-section-text aoa-card-result">{trace.outputSummary}</div>
        </div>
      )}
    </div>
  );
}

function ConnectorArrow({ visible }: { visible: boolean }) {
  if (!visible) return <div className="aoa-connector aoa-connector-hidden" />;
  return (
    <div className="aoa-connector">
      <svg width="16" height="24" viewBox="0 0 16 24" fill="none">
        <path d="M8 0 L8 18 M3 14 L8 20 L13 14" stroke="#d1d5db" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function applyTrace(state: TraceState, payload: AgentActivityPayload): TraceState {
  const now = Date.now();
  const prev = state[payload.agent];

  if (payload.action === 'start') {
    return {
      ...state,
      [payload.agent]: {
        status: 'working',
        detail: payload.detail ?? '',
        task: payload.task ?? prev.task,
        userQuery: payload.user_query ?? prev.userQuery,
        startedAt: now
      }
    };
  }

  return {
    ...state,
    [payload.agent]: {
      ...prev,
      status: 'done',
      detail: payload.detail ?? prev.detail,
      resultSummary: payload.result_summary ?? prev.resultSummary,
      outputSummary: payload.output_summary ?? prev.outputSummary,
      elapsedSeconds: payload.elapsed_seconds ?? prev.elapsedSeconds
    }
  };
}

type Props = {
  visible: boolean;
  trace: TraceState;
  onReset: () => void;
};

export function AgentOrchestrationPanel({ visible, trace, onReset }: Props) {
  const [collapsed, setCollapsed] = useState(true);

  const activeAgents = AGENTS.filter(({ key }) => trace[key].status !== 'idle');
  const workingCount = AGENTS.filter(({ key }) => trace[key].status === 'working').length;
  const doneCount = AGENTS.filter(({ key }) => trace[key].status === 'done').length;
  const allDone = doneCount > 0 && workingCount === 0;

  if (!visible) return null;

  return (
    <aside className={`aoa-panel ${collapsed ? 'aoa-panel-collapsed' : ''}`}>
      <div className="aoa-panel-header">
        <div className="aoa-panel-title-row">
          <span className="aoa-panel-icon">⚡</span>
          <span className="aoa-panel-title">Agent 编排</span>
          {workingCount > 0 && <span className="aoa-panel-badge">{workingCount} 执行中</span>}
          {allDone && <span className="aoa-panel-badge aoa-panel-badge-done">✓ 完成</span>}
        </div>
        <button
          className="aoa-panel-toggle"
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? '展开' : '收起'}
        >
          {collapsed ? '◀' : '▶'}
        </button>
      </div>

      {!collapsed && (
        <div className="aoa-panel-body">
          {activeAgents.length === 0 && (
            <div className="aoa-panel-empty">等待调度…</div>
          )}

          {activeAgents.map((agent, index) => (
            <div key={agent.key}>
              {index > 0 && (
                <ConnectorArrow visible={trace[agent.key].status !== 'idle'} />
              )}
              <AgentCard agent={agent} trace={trace[agent.key]} />
            </div>
          ))}

          {allDone && (
            <div className="aoa-panel-footer">
              <span>本次调度 {doneCount} 个 Agent</span>
              <button className="aoa-panel-reset" onClick={onReset}>重置</button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

export { INITIAL_TRACE, applyTrace };
export type { TraceState };
