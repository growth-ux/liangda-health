/* ============================================
   侧边栏与顶栏渲染（所有页面共用）
   ============================================ */

const ICONS = {
    chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`,
    search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
    upload: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>`,
    members: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
    report: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
    mall: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>`,
    device: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="2"/><line x1="9" y1="2" x2="9" y2="6"/><line x1="15" y1="2" x2="15" y2="6"/><line x1="9" y1="18" x2="9" y2="22"/><line x1="15" y1="18" x2="15" y2="22"/><line x1="6" y1="12" x2="18" y2="12"/></svg>`,
    notice: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
    more: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></svg>`,
    plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
};

const NAV = [
    { id: "chat", icon: "chat", label: " Agent", href: "chat.html" },
    { id: "reports", icon: "upload", label: "上传报告", href: "reports.html" },
    { id: "report", icon: "report", label: "健康分析", href: "report.html" },
    { id: "mall", icon: "mall", label: "商城", href: "mall.html" },
    { id: "members", icon: "members", label: "家人", href: "members.html" },
    { id: "device", icon: "device", label: "手环", href: "device.html" },
    { id: "notice", icon: "notice", label: "通知", href: "notice.html" },
];

function renderSidebar(activeId) {
    const html = NAV.map(item => {
        const active = item.id === activeId ? "active" : "";
        return `<a class="nav-item ${active}" href="${item.href}">
            <span class="nav-icon">${ICONS[item.icon]}</span>
            <span>${item.label}</span>
        </a>`;
    }).join("");

    return `
    <aside class="sidebar">
        <div class="brand">
            <div class="brand-logo">粮</div>
            <div class="brand-text">粮达健康</div>
        </div>
        <nav class="nav">${html}</nav>
    </aside>`;
}

function renderTopbar(title, extra = "") {
    return `
    <header class="topbar">
        <div class="topbar-title">${title}</div>
        ${extra}
        <div class="topbar-spacer"></div>
        <div class="topbar-icon">${ICONS.search}</div>
        <a href="notice.html" class="topbar-icon">
            ${ICONS.notice}
            <span class="badge">3</span>
        </a>
        <div class="user-chip">
            <div class="user-avatar">张</div>
            <span style="font-size: 13px;">张雨微</span>
        </div>
    </header>`;
}

document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("app");
    if (!app) return;

    const active = app.dataset.active;
    const title = app.dataset.title;
    const topbarExtra = app.dataset.topbarExtra || "";

    app.innerHTML = `
        <div class="app">
            ${renderSidebar(active)}
            <div class="main">
                ${renderTopbar(title, topbarExtra)}
                <main class="content">${app.innerHTML}</main>
            </div>
        </div>
        <div class="proto-label">原型 v0.2 · 克制留白</div>
    `;
});
