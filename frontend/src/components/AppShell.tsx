import {
  BarChart3,
  Bell,
  Cpu,
  MessageCircle,
  Search,
  ShoppingBag,
  Upload,
  Users
} from 'lucide-react';
import { Link } from 'react-router-dom';

type Props = {
  title: string;
  activeId: string;
  children: React.ReactNode;
};

const navItems = [
  { id: 'chat', icon: MessageCircle, label: ' Agent', href: '' },
  { id: 'reports', icon: Upload, label: '上传报告', href: '/reports' },
  { id: 'report', icon: BarChart3, label: '健康分析', href: '' },
  { id: 'mall', icon: ShoppingBag, label: '商城', href: '' },
  { id: 'members', icon: Users, label: '家人', href: '' },
  { id: 'device', icon: Cpu, label: '手环', href: '' },
  { id: 'notice', icon: Bell, label: '通知', href: '' }
];

export function AppShell({ title, activeId, children }: Props) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">粮</div>
          <div className="brand-text">粮达健康</div>
        </div>
        <nav className="nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            const content = (
              <>
                <span className="nav-icon">
                  <Icon size={20} strokeWidth={1.8} />
                </span>
                <span>{item.label}</span>
              </>
            );

            if (!item.href) {
              return (
                <button key={item.id} className={`nav-item ${item.id === activeId ? 'active' : ''}`} type="button">
                  {content}
                </button>
              );
            }

            return (
              <Link
                key={item.id}
                className={`nav-item ${item.id === activeId ? 'active' : ''}`}
                to={item.href}
              >
                {content}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">{title}</div>
          <div className="topbar-spacer" />
          <div className="topbar-icon">
            <Search size={18} strokeWidth={1.8} />
          </div>
          <div className="topbar-icon">
            <Bell size={18} strokeWidth={1.8} />
            <span className="badge">3</span>
          </div>
          <div className="user-chip">
            <div className="user-avatar">李</div>
            <span>张小李</span>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
