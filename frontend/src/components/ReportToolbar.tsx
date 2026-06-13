import { Upload } from 'lucide-react';

type Props = {
  activeFamily: string;
  filters: Array<{ value: string; label: string; count: number }>;
  sortMode: string;
  onFamilyChange: (family: string) => void;
  onSortModeChange: (mode: 'uploaded' | 'exam' | 'family') => void;
  onUploadClick: () => void;
};

export function ReportToolbar({
  activeFamily,
  filters,
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
            {filter.label} ({filter.count})
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
