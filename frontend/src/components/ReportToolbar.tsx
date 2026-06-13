import { Upload } from 'lucide-react';

type Props = {
  activeFamily: string;
  counts: Record<'all' | 'mom' | 'dad' | 'me' | 'kid', number>;
  sortMode: string;
  onFamilyChange: (family: 'all' | 'mom' | 'dad' | 'me' | 'kid') => void;
  onSortModeChange: (mode: 'uploaded' | 'exam' | 'family') => void;
  onUploadClick: () => void;
};

const filters = [
  { label: '全部', value: 'all' },
  { label: '妈妈', value: 'mom' },
  { label: '爸爸', value: 'dad' },
  { label: '我', value: 'me' },
  { label: '女儿', value: 'kid' }
] as const;

export function ReportToolbar({
  activeFamily,
  counts,
  sortMode,
  onFamilyChange,
  onSortModeChange,
  onUploadClick
}: Props) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        {filters.map((filter) => (
          <button
            key={filter.value}
            className={`filter-btn ${activeFamily === filter.value ? 'active' : ''}`}
            onClick={() => onFamilyChange(filter.value)}
          >
            {filter.label} ({counts[filter.value]})
          </button>
        ))}
      </div>
      <div className="toolbar-actions">
        <select
          className="form-select"
          value={sortMode}
          onChange={(event) => onSortModeChange(event.target.value as 'uploaded' | 'exam' | 'family')}
        >
          <option value="uploaded">按上传时间</option>
          <option value="exam">按检查日期</option>
          <option value="family">按家人</option>
        </select>
        <button className="btn-primary" onClick={onUploadClick}>
          <Upload size={16} />
          上传新报告
        </button>
      </div>
    </div>
  );
}
