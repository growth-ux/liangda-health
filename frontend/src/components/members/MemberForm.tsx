import { useMemo, useState } from 'react';
import type { Member, MemberPayload } from '../../api/members';
import { HealthTagPicker } from './HealthTagPicker';

type Props = {
  initialValue?: Member | null;
  saving: boolean;
  error: string | null;
  mode: 'create' | 'edit';
  onCancel: () => void;
  onSubmit: (payload: MemberPayload, action: 'save' | 'save-and-upload') => void;
};

type FormState = {
  name: string;
  relation: string;
  gender: string;
  birth_year: string;
  phone: string;
  height_cm: string;
  weight_kg: string;
  health_tags: string[];
  allergies: string;
  taste_preferences: string;
};

function toFormState(member?: Member | null): FormState {
  return {
    name: member?.name ?? '',
    relation: member?.relation ?? '',
    gender: member?.gender ?? '女',
    birth_year: member?.birth_year ? String(member.birth_year) : '',
    phone: member?.phone ?? '',
    height_cm: member?.height_cm ? String(member.height_cm) : '',
    weight_kg: member?.weight_kg ? String(member.weight_kg) : '',
    health_tags: member?.health_tags ?? [],
    allergies: member?.allergies ?? '',
    taste_preferences: member?.taste_preferences ?? ''
  };
}

function buildPayload(form: FormState): MemberPayload {
  return {
    name: form.name.trim(),
    relation: form.relation,
    gender: form.gender,
    birth_year: Number(form.birth_year),
    phone: form.phone.trim() || null,
    height_cm: form.height_cm ? Number(form.height_cm) : null,
    weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
    health_tags: form.health_tags,
    allergies: form.allergies.trim() || null,
    taste_preferences: form.taste_preferences.trim() || null
  };
}

export function MemberForm({ initialValue, saving, error, mode, onCancel, onSubmit }: Props) {
  const [form, setForm] = useState<FormState>(() => toFormState(initialValue));
  const [localError, setLocalError] = useState<string | null>(null);

  const title = useMemo(() => (mode === 'create' ? '添加家人' : '编辑家人'), [mode]);

  const submit = (action: 'save' | 'save-and-upload') => {
    if (!form.name.trim()) {
      setLocalError('请填写姓名');
      return;
    }
    if (!form.relation.trim()) {
      setLocalError('请填写关系');
      return;
    }
    if (!form.birth_year.trim()) {
      setLocalError('请填写出生年');
      return;
    }
    setLocalError(null);
    onSubmit(buildPayload(form), action);
  };

  return (
    <div className="member-form-card">
      <div className="steps">
        <div className="step-dot active" />
        <div className={`step-dot ${mode === 'edit' ? 'active' : ''}`} />
      </div>
      <div className="dialog-title">{title}</div>
      <div className="dialog-subtitle">填写基本信息后，可以上传报告来完善档案。</div>

      <div className="member-form-grid">
        <label className="field-block">
          <span>姓名 *</span>
          <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </label>

        <label className="field-block">
          <span>关系 *</span>
          <input
            placeholder="如：妈妈、爸爸、丈夫..."
            value={form.relation}
            onChange={(event) => setForm({ ...form, relation: event.target.value })}
          />
        </label>

        <label className="field-block">
          <span>性别 *</span>
          <select value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })}>
            <option value="女">女</option>
            <option value="男">男</option>
          </select>
        </label>

        <label className="field-block">
          <span>出生年 *</span>
          <input
            inputMode="numeric"
            value={form.birth_year}
            onChange={(event) => setForm({ ...form, birth_year: event.target.value })}
          />
        </label>

        <label className="field-block">
          <span>手机号</span>
          <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
        </label>

        <label className="field-block">
          <span>身高（cm）</span>
          <input
            inputMode="numeric"
            value={form.height_cm}
            onChange={(event) => setForm({ ...form, height_cm: event.target.value })}
          />
        </label>

        <label className="field-block">
          <span>体重（kg）</span>
          <input
            inputMode="numeric"
            value={form.weight_kg}
            onChange={(event) => setForm({ ...form, weight_kg: event.target.value })}
          />
        </label>
      </div>

      <div className="field-block">
        <span>已知慢病 / 健康标签</span>
        <HealthTagPicker selected={form.health_tags} onChange={(health_tags) => setForm({ ...form, health_tags })} />
      </div>

      <div className="member-form-grid">
        <label className="field-block">
          <span>过敏 / 忌口</span>
          <input value={form.allergies} onChange={(event) => setForm({ ...form, allergies: event.target.value })} />
        </label>

        <label className="field-block">
          <span>口味偏好</span>
          <input
            value={form.taste_preferences}
            onChange={(event) => setForm({ ...form, taste_preferences: event.target.value })}
          />
        </label>
      </div>

      {(localError || error) && <div className="error-box">{localError || error}</div>}

      <div className="member-form-actions">
        <button className="btn-secondary" disabled={saving} onClick={onCancel} type="button">
          取消
        </button>
        <div className="member-form-actions-right">
          <button className="btn-primary" disabled={saving} onClick={() => submit('save')} type="button">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
}
