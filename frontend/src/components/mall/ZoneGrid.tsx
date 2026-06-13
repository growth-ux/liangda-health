type Props = {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
};

export function ZoneGrid({ title, children, actions }: Props) {
  return (
    <div className="card">
      <div className="card-title">
        {title}
        {actions && <span className="card-title-actions">{actions}</span>}
      </div>
      <div className="zone-grid">
        {children}
      </div>
    </div>
  );
}
