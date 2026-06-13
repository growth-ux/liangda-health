export const HEALTH_TAG_OPTIONS = [
  '高血压',
  '糖尿病',
  '高血脂',
  '骨质疏松',
  '痛风',
  '心血管疾病',
  '胃肠疾病'
];

export function getMemberTone(relation: string) {
  if (/父|爸/.test(relation)) {
    return { background: '#dbeafe', color: '#2563eb' };
  }
  if (/母|妈/.test(relation)) {
    return { background: '#fce7f3', color: '#db2777' };
  }
  if (/本人|我/.test(relation)) {
    return { background: '#fed7aa', color: '#f97316' };
  }
  if (/儿|女/.test(relation)) {
    return { background: '#d1fae5', color: '#059669' };
  }
  return { background: '#e9d5ff', color: '#7c3aed' };
}

export function getMemberInitial(name: string) {
  return name.trim().slice(0, 1) || '家';
}
