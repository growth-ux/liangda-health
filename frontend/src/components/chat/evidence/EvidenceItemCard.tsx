import type { EvidenceItem } from '../../../schemas/agentResponse';

type Props = {
  item: EvidenceItem;
};

const EVIDENCE_TYPE_LABEL: Record<EvidenceItem['type'], string> = {
  report_fact: '报告事实',
  device: '手环状态',
  memory: '互动记忆',
  product: '商品匹配',
};

export function EvidenceItemCard({ item }: Props) {
  return (
    <article className="evidence-item-card">
      <div className="evidence-item-meta">
        <div className={`evidence-item-type type-${item.type}`}>{EVIDENCE_TYPE_LABEL[item.type]}</div>
        <div className="evidence-item-source">{item.source_label}</div>
      </div>
      <div className="evidence-item-title">{item.title}</div>
      <div className="evidence-item-excerpt">{item.excerpt}</div>
    </article>
  );
}
