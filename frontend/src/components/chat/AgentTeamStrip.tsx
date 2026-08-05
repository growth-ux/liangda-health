import type { AgentActivityPayload } from '../../api/agent';

export type TeamAgentKey = AgentActivityPayload['agent'];

export type TeamAgentState = {
  status: 'idle' | 'working' | 'done';
  detail: string;
};

export type TeamState = Record<TeamAgentKey, TeamAgentState>;

export const INITIAL_TEAM_STATE: TeamState = {
  supervisor: { status: 'idle', detail: '' },
  meal_planner: { status: 'idle', detail: '' },
  shopping_guide: { status: 'idle', detail: '' },
  report_reader: { status: 'idle', detail: '' }
};

const TEAM_AGENTS: { key: TeamAgentKey; label: string; emoji: string }[] = [
  { key: 'supervisor', label: '调度中心', emoji: '🧭' },
  { key: 'meal_planner', label: '餐单规划师', emoji: '🥗' },
  { key: 'shopping_guide', label: '商品导购师', emoji: '🛒' },
  { key: 'report_reader', label: '报告解读师', emoji: '📋' }
];

export function applyTeamActivity(state: TeamState, payload: AgentActivityPayload): TeamState {
  return {
    ...state,
    [payload.agent]: {
      status: payload.action === 'start' ? 'working' : 'done',
      detail: payload.detail ?? ''
    }
  };
}

export function AgentTeamStrip({ team }: { team: TeamState }) {
  const activeDetail = TEAM_AGENTS.map(({ key }) => team[key])
    .filter((item) => item.status === 'working')
    .map((item) => item.detail)
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="agent-team-strip">
      <div className="agent-team-nodes">
        {TEAM_AGENTS.map(({ key, label, emoji }) => (
          <span key={key} className={`agent-team-node agent-team-node-${team[key].status}`}>
            <span className="agent-team-emoji">{emoji}</span>
            <span className="agent-team-label">{label}</span>
            {team[key].status === 'done' && <span className="agent-team-check">✓</span>}
          </span>
        ))}
      </div>
      {activeDetail && <div className="agent-team-detail">{activeDetail}</div>}
    </div>
  );
}
