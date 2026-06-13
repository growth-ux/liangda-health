import { HEALTH_TAG_OPTIONS } from './memberUtils';

type Props = {
  selected: string[];
  onChange: (value: string[]) => void;
};

export function HealthTagPicker({ selected, onChange }: Props) {
  return (
    <div className="tag-picker">
      {HEALTH_TAG_OPTIONS.map((tag) => {
        const active = selected.includes(tag);
        return (
          <button
            key={tag}
            className={`tag-chip ${active ? 'active' : ''}`}
            onClick={() =>
              onChange(active ? selected.filter((item) => item !== tag) : [...selected, tag])
            }
            type="button"
          >
            {active ? tag : `+ ${tag}`}
          </button>
        );
      })}
    </div>
  );
}
