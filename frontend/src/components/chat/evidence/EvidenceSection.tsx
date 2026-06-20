import type { EvidenceItem } from '../../../schemas/agentResponse';
import { EvidenceItemCard } from './EvidenceItemCard';

type Props = {
  title: string;
  items: EvidenceItem[];
};

export function EvidenceSection({ title, items }: Props) {
  if (items.length === 0) return null;

  return (
    <section className="evidence-section">
      <div className="evidence-section-title">{title}</div>
      <div className="evidence-section-list">
        {items.map((item, index) => (
          <EvidenceItemCard key={`${item.source_id}-${index}`} item={item} />
        ))}
      </div>
    </section>
  );
}
