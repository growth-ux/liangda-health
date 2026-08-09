import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Bell,
  Check,
  ChevronDown,
  MessageSquare,
  Plus,
  Save,
  Send,
  Shield,
  Trash2
} from 'lucide-react';
import {
  createAlertRule,
  deleteAlertRule,
  getSmsConfig,
  listAlertRules,
  listSmsLogs,
  saveSmsConfig,
  testSmsConfig,
  updateAlertRule,
  type AlertRuleCreatePayload,
  type AlertRuleItem,
  type Channel,
  type MetricType,
  type Operator
} from '../api/alert';
import { listMembers } from '../api/members';
import { AppShell } from '../components/AppShell';

const DEVICE_METRIC_OPTIONS: { value: MetricType; label: string; icon: string }[] = [
  { value: 'systolic_bp', label: '收缩压', icon: '❤️' },
  { value: 'diastolic_bp', label: '舒张压', icon: '❤️' },
  { value: 'heart_rate', label: '心率', icon: '' },
  { value: 'steps', label: '步数', icon: '' },
  { value: 'sleep_hours', label: '睡眠时长', icon: '' },
  { value: 'blood_oxygen', label: '血氧', icon: '' }
];

const AI_METRIC_OPTIONS: { value: MetricType; label: string; desc: string; icon: string }[] = [
  { value: 'health_fact', label: '报告异常指标', desc: 'AI 自动识别报告中的 danger/warning 指标', icon: '' },
  { value: 'health_trend', label: 'AI 趋势分析', desc: 'AI 检测指标连续恶化趋势（如血压连升 3 天）', icon: '' },
  { value: 'recheck', label: '复诊提醒', desc: '报告中建议复查的项目自动提醒', icon: '' }
];

const AI_METRIC_TYPES = new Set<MetricType>(['health_fact', 'health_trend', 'recheck']);

const OPERATOR_OPTIONS: { value: Operator; label: string }[] = [
  { value: '>=', label: '≥' },
  { value: '>', label: '>' },
  { value: '<=', label: '≤' },
  { value: '<', label: '<' }
];

const CHANNEL_OPTIONS: { value: Channel; label: string }[] = [
  { value: 'in_app', label: '仅站内通知' },
  { value: 'sms', label: '仅短信' },
  { value: 'both', label: '站内 + 短信' }
];

const PROVIDER_OPTIONS = [
  { value: 'aliyun', label: '阿里云短信' },
  { value: 'tencent', label: '腾讯云短信' },
  { value: 'huawei', label: '华为云短信' }
];

const METRIC_UNIT: Record<MetricType, string> = {
  systolic_bp: 'mmHg',
  diastolic_bp: 'mmHg',
  heart_rate: 'bpm',
  steps: '步',
  sleep_hours: '小时',
  blood_oxygen: '%',
  health_fact: '',
  health_trend: '',
  recheck: ''
};

type TabKey = 'rules' | 'sms' | 'logs';

function MetricSelect({ value, onChange }: { value: MetricType; onChange: (v: MetricType) => void }) {
  const [open, setOpen] = useState(false);
  const allOptions = [
    { group: '硬件指标', groupIcon: '', items: DEVICE_METRIC_OPTIONS },
    { group: 'AI 主动预警', groupIcon: '', items: AI_METRIC_OPTIONS }
  ];
  const current = [...DEVICE_METRIC_OPTIONS, ...AI_METRIC_OPTIONS].find((o) => o.value === value);

  return (
    <div className="metric-select-wrapper">
      <button
        className="metric-select-trigger"
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="metric-select-value">
          {current && current.icon && <span className="metric-select-icon">{current.icon}</span>}
          {current?.label ?? '选择指标'}
          {AI_METRIC_TYPES.has(value) && <span className="metric-select-ai-tag">AI</span>}
        </span>
        <ChevronDown size={14} className={`metric-select-arrow ${open ? 'is-open' : ''}`} />
      </button>
      {open && (
        <>
          <div className="metric-select-backdrop" onClick={() => setOpen(false)} />
          <div className="metric-select-dropdown">
            {allOptions.map((group) => (
              <div className="metric-select-group" key={group.group}>
                <div className="metric-select-group-label">{group.group}</div>
                {group.items.map((opt) => (
                  <button
                    className={`metric-select-option ${opt.value === value ? 'is-selected' : ''}`}
                    key={opt.value}
                    onClick={() => { onChange(opt.value); setOpen(false); }}
                    type="button"
                  >
                    {opt.icon && <span className="metric-select-option-icon">{opt.icon}</span>}
                    <span>{opt.label}</span>
                    {opt.value === value && <Check size={14} className="metric-select-check" />}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function AlertRulesTab() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formMemberId, setFormMemberId] = useState('');
  const [formMetric, setFormMetric] = useState<MetricType>('systolic_bp');
  const [formOperator, setFormOperator] = useState<Operator>('>=');
  const [formThreshold, setFormThreshold] = useState(140);
  const [formChannel, setFormChannel] = useState<Channel>('in_app');
  const [error, setError] = useState<string | null>(null);

  const rulesQuery = useQuery({ queryKey: ['alert-rules'], queryFn: listAlertRules });
  const membersQuery = useQuery({ queryKey: ['members'], queryFn: listMembers });

  const createMutation = useMutation({
    mutationFn: (payload: AlertRuleCreatePayload) => createAlertRule(payload),
    onSuccess: async () => {
      setShowForm(false);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
    },
    onError: (err: Error) => setError(err.message)
  });

  const toggleMutation = useMutation({
    mutationFn: ({ ruleId, enabled }: { ruleId: string; enabled: boolean }) =>
      updateAlertRule(ruleId, { enabled }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => deleteAlertRule(ruleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
    }
  });

  const members = membersQuery.data ?? [];
  const rules = rulesQuery.data?.rules ?? [];

  function handleCreate() {
    if (!formMemberId) {
      setError('请选择家人');
      return;
    }
    const isAi = AI_METRIC_TYPES.has(formMetric);
    createMutation.mutate({
      member_id: formMemberId,
      metric_type: formMetric,
      operator: isAi ? '>=' : formOperator,
      threshold: isAi ? 0 : formThreshold,
      channel: formChannel
    });
  }

  return (
    <>
      <div className="settings-section-header">
        <div className="settings-section-title">
          <Shield size={16} />
          预警规则
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)} type="button">
          {showForm ? '取消' : <><Plus size={14} /> 新增规则</>}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {showForm && (
        <div className="settings-form-card">
          <div className="settings-form-row">
            <label className="settings-form-label">家人</label>
            <select
              className="form-select"
              value={formMemberId}
              onChange={(e) => setFormMemberId(e.target.value)}
            >
              <option value="">选择家人</option>
              {members.map((m) => (
                <option key={m.member_id} value={m.member_id}>
                  {m.name}（{m.relation}）
                </option>
              ))}
            </select>
          </div>
          <div className="settings-form-row">
            <label className="settings-form-label">监测指标</label>
            <MetricSelect value={formMetric} onChange={setFormMetric} />
          </div>
          {AI_METRIC_TYPES.has(formMetric) ? (
            <div className="settings-form-hint-box">
              <span className="settings-form-hint-icon">🤖</span>
              <span>{AI_METRIC_OPTIONS.find((o) => o.value === formMetric)?.desc}</span>
            </div>
          ) : (
            <div className="settings-form-row">
              <label className="settings-form-label">触发条件</label>
              <select
                className="form-select"
                style={{ width: 80 }}
                value={formOperator}
                onChange={(e) => setFormOperator(e.target.value as Operator)}
              >
                {OPERATOR_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <input
                className="settings-form-input"
                type="number"
                value={formThreshold}
                onChange={(e) => setFormThreshold(Number(e.target.value))}
              />
              <span className="settings-form-unit">{METRIC_UNIT[formMetric]}</span>
            </div>
          )}
          <div className="settings-form-row">
            <label className="settings-form-label">通知方式</label>
            <select
              className="form-select"
              value={formChannel}
              onChange={(e) => setFormChannel(e.target.value as Channel)}
            >
              {CHANNEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="settings-form-actions">
            <button
              className="btn-primary"
              disabled={createMutation.isPending}
              onClick={handleCreate}
              type="button"
            >
              <Save size={14} />
              保存规则
            </button>
          </div>
        </div>
      )}

      {rulesQuery.isLoading && <div className="empty-state">正在加载预警规则...</div>}
      {rulesQuery.isError && <div className="error-box">预警规则加载失败</div>}

      {!rulesQuery.isLoading && !rulesQuery.isError && rules.length === 0 && (
        <div className="empty-state">暂无预警规则，点击"新增规则"开始配置</div>
      )}

      {!rulesQuery.isLoading && !rulesQuery.isError && rules.length > 0 && (
        <div className="settings-rule-list">
          {rules.map((rule) => (
            <RuleCard
              key={rule.rule_id}
              rule={rule}
              onToggle={() => toggleMutation.mutate({ ruleId: rule.rule_id, enabled: !rule.enabled })}
              onDelete={() => deleteMutation.mutate(rule.rule_id)}
              toggling={toggleMutation.isPending}
              deleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}
    </>
  );
}

function RuleCard({
  rule,
  onToggle,
  onDelete,
  toggling,
  deleting
}: {
  rule: AlertRuleItem;
  onToggle: () => void;
  onDelete: () => void;
  toggling: boolean;
  deleting: boolean;
}) {
  const channelLabel = CHANNEL_OPTIONS.find((o) => o.value === rule.channel)?.label ?? rule.channel;
  const isAi = AI_METRIC_TYPES.has(rule.metric_type);
  const aiOption = AI_METRIC_OPTIONS.find((o) => o.value === rule.metric_type);
  return (
    <div className={`settings-rule-card ${rule.enabled ? '' : 'is-disabled'}`}>
      <div className="settings-rule-info">
        <div className="settings-rule-title">
          <AlertTriangle size={15} className={rule.enabled ? 'text-amber-500' : 'text-gray-400'} />
          <span className="settings-rule-member">{rule.member_name ?? '未知'}</span>
          <span className="settings-rule-relation">（{rule.member_relation}）</span>
          {isAi && <span className="settings-rule-ai-badge">AI</span>}
        </div>
        <div className="settings-rule-desc">
          {isAi
            ? <>{rule.metric_type_text} · <span className="settings-rule-ai-desc">{aiOption?.desc}</span></>
            : <>{rule.metric_type_text} {rule.operator} {rule.threshold} {METRIC_UNIT[rule.metric_type]}</>
          }
          {' · '}
          <span className="settings-rule-channel">{channelLabel}</span>
        </div>
      </div>
      <div className="settings-rule-actions">
        <button
          className={`settings-toggle ${rule.enabled ? 'is-on' : ''}`}
          disabled={toggling}
          onClick={onToggle}
          type="button"
        >
          <span className="settings-toggle-thumb" />
        </button>
        <button
          className="btn-icon-danger"
          disabled={deleting}
          onClick={onDelete}
          title="删除规则"
          type="button"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

function SmsConfigTab() {
  const queryClient = useQueryClient();
  const configQuery = useQuery({ queryKey: ['sms-config'], queryFn: getSmsConfig });
  const [form, setForm] = useState({
    provider: 'aliyun',
    api_key: '',
    api_secret: '',
    signature: '',
    template_id: '',
    enabled: true
  });
  const [testPhone, setTestPhone] = useState('');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const config = configQuery.data?.config;

  // 回填表单
  if (config && !initialized) {
    setForm({
      provider: config.provider,
      api_key: config.api_key,
      api_secret: config.api_secret,
      signature: config.signature,
      template_id: config.template_id,
      enabled: config.enabled
    });
    setInitialized(true);
  }

  const saveMutation = useMutation({
    mutationFn: saveSmsConfig,
    onSuccess: async () => {
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ['sms-config'] });
    },
    onError: (err: Error) => setError(err.message)
  });

  const testMutation = useMutation({
    mutationFn: (phone: string) => testSmsConfig(phone),
    onSuccess: (result) => {
      setTestResult(result.message);
      queryClient.invalidateQueries({ queryKey: ['sms-logs'] });
    },
    onError: (err: Error) => setTestResult(`发送失败: ${err.message}`)
  });

  function handleSave() {
    if (!form.api_key || !form.api_secret || !form.signature || !form.template_id) {
      setError('请填写完整配置信息');
      return;
    }
    saveMutation.mutate(form);
  }

  return (
    <>
      <div className="settings-section-header">
        <div className="settings-section-title">
          <MessageSquare size={16} />
          短信配置
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div className="settings-form-card">
        <div className="settings-form-row">
          <label className="settings-form-label">服务商</label>
          <select
            className="form-select"
            value={form.provider}
            onChange={(e) => setForm({ ...form, provider: e.target.value })}
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <div className="settings-form-row">
          <label className="settings-form-label">API Key</label>
          <input
            className="settings-form-input"
            placeholder="请输入 AccessKey ID"
            type="text"
            value={form.api_key}
            onChange={(e) => setForm({ ...form, api_key: e.target.value })}
          />
        </div>
        <div className="settings-form-row">
          <label className="settings-form-label">API Secret</label>
          <input
            className="settings-form-input"
            placeholder="请输入 AccessKey Secret"
            type="password"
            value={form.api_secret}
            onChange={(e) => setForm({ ...form, api_secret: e.target.value })}
          />
        </div>
        <div className="settings-form-row">
          <label className="settings-form-label">短信签名</label>
          <input
            className="settings-form-input"
            placeholder="例如：粮达健康"
            type="text"
            value={form.signature}
            onChange={(e) => setForm({ ...form, signature: e.target.value })}
          />
        </div>
        <div className="settings-form-row">
          <label className="settings-form-label">模板 ID</label>
          <input
            className="settings-form-input"
            placeholder="例如：SMS_123456789"
            type="text"
            value={form.template_id}
            onChange={(e) => setForm({ ...form, template_id: e.target.value })}
          />
        </div>
        <div className="settings-form-row">
          <label className="settings-form-label">启用状态</label>
          <button
            className={`settings-toggle ${form.enabled ? 'is-on' : ''}`}
            onClick={() => setForm({ ...form, enabled: !form.enabled })}
            type="button"
          >
            <span className="settings-toggle-thumb" />
          </button>
          <span className="settings-form-hint">{form.enabled ? '已启用' : '已关闭'}</span>
        </div>
        <div className="settings-form-actions">
          <button
            className="btn-primary"
            disabled={saveMutation.isPending}
            onClick={handleSave}
            type="button"
          >
            <Save size={14} />
            保存配置
          </button>
        </div>
      </div>

      <div className="settings-section-header" style={{ marginTop: 24 }}>
        <div className="settings-section-title">
          <Send size={16} />
          测试发送
        </div>
      </div>
      <div className="settings-form-card">
        <div className="settings-form-row">
          <label className="settings-form-label">手机号</label>
          <input
            className="settings-form-input"
            placeholder="输入接收测试短信的手机号"
            type="tel"
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
          />
          <button
            className="btn"
            disabled={!testPhone || testMutation.isPending}
            onClick={() => testMutation.mutate(testPhone)}
            type="button"
          >
            发送测试
          </button>
        </div>
        {testResult && (
          <div className={`settings-test-result ${testResult.includes('失败') ? 'is-error' : 'is-success'}`}>
            {testResult}
          </div>
        )}
      </div>
    </>
  );
}

function SmsLogsTab() {
  const logsQuery = useQuery({ queryKey: ['sms-logs'], queryFn: listSmsLogs });
  const logs = logsQuery.data?.logs ?? [];

  return (
    <>
      <div className="settings-section-header">
        <div className="settings-section-title">
          <Bell size={16} />
          发送记录
        </div>
      </div>

      {logsQuery.isLoading && <div className="empty-state">正在加载发送记录...</div>}
      {logsQuery.isError && <div className="error-box">发送记录加载失败</div>}

      {!logsQuery.isLoading && !logsQuery.isError && logs.length === 0 && (
        <div className="empty-state">暂无发送记录</div>
      )}

      {!logsQuery.isLoading && !logsQuery.isError && logs.length > 0 && (
        <div className="settings-log-list">
          {logs.map((log) => (
            <div className="settings-log-item" key={log.id}>
              <div className="settings-log-header">
                <span className="settings-log-status">{log.status === 'sent' ? '已发送' : log.status}</span>
                <span className="settings-log-time">{new Date(log.created_at).toLocaleString('zh-CN')}</span>
              </div>
              <div className="settings-log-content">{log.content}</div>
              <div className="settings-log-meta">接收号码: {log.phone}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

const TABS: { key: TabKey; label: string; icon: typeof Shield }[] = [
  { key: 'rules', label: '预警规则', icon: Shield },
  { key: 'sms', label: '短信配置', icon: MessageSquare },
  { key: 'logs', label: '发送记录', icon: Bell }
];

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('rules');

  return (
    <AppShell title="预警与通知设置" activeId="settings">
      <div className="settings-tabs">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              className={`settings-tab ${activeTab === tab.key ? 'is-active' : ''}`}
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              type="button"
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="settings-content">
        {activeTab === 'rules' && <AlertRulesTab />}
        {activeTab === 'sms' && <SmsConfigTab />}
        {activeTab === 'logs' && <SmsLogsTab />}
      </div>
    </AppShell>
  );
}
