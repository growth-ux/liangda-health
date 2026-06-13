/* ============================================
   手环页交互：家人 Tab、柱状图、面积图、立即同步
   ============================================ */

(function () {
    const stepData = [
        { day: "周一", steps: 6500, target: 8000 },
        { day: "周二", steps: 8200, target: 8000 },
        { day: "周三", steps: 7800, target: 8000 },
        { day: "周四", steps: 9100, target: 8000 },
        { day: "周五", steps: 7400, target: 8000 },
        { day: "周六", steps: 10500, target: 8000 },
        { day: "周日", steps: 9800, target: 8000 },
    ];

    const heartData = [
        { time: "00:00", rate: 58 },
        { time: "04:00", rate: 55 },
        { time: "08:00", rate: 72 },
        { time: "12:00", rate: 78 },
        { time: "16:00", rate: 82 },
        { time: "20:00", rate: 70 },
        { time: "23:59", rate: 60 },
    ];

    function renderBarChart() {
        const el = document.getElementById("barChart");
        if (!el) return;
        const max = Math.max(...stepData.map(d => d.target)) * 1.2;
        const html = stepData.map(d => {
            const actualH = (d.steps / max) * 100;
            const targetH = (d.target / max) * 100;
            const over = d.steps > d.target;
            return `<div class="bar-col">
                <div class="bar-stack" style="height:${actualH}%" title="${d.day} ${d.steps.toLocaleString()} 步">
                    <div class="bar-actual" style="height:100%;background:${over ? "#16a34a" : "#22c55e"}"></div>
                    <div class="bar-target" style="height:${targetH}%;"></div>
                </div>
                <span class="bar-label">${d.day}</span>
            </div>`;
        }).join("");
        el.innerHTML = html;
    }

    function renderAreaChart() {
        const el = document.getElementById("areaChart");
        if (!el) return;

        const W = 480, H = 220;
        const padL = 36, padR = 12, padT = 14, padB = 26;
        const innerW = W - padL - padR;
        const innerH = H - padT - padB;

        const yMin = 40, yMax = 120;
        const x = i => padL + (i / (heartData.length - 1)) * innerW;
        const y = v => padT + (1 - (v - yMin) / (yMax - yMin)) * innerH;

        // 网格线 y = 60, 80, 100
        const yTicks = [60, 80, 100];
        const gridLines = yTicks.map(t => {
            const yy = y(t);
            return `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}" stroke="#f1f5f9" stroke-dasharray="3 3"/>` +
                `<text x="${padL - 8}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#94a3b8">${t}</text>`;
        }).join("");

        // 平滑路径
        const points = heartData.map((d, i) => [x(i), y(d.rate)]);
        let path = `M ${points[0][0]},${points[0][1]}`;
        for (let i = 1; i < points.length; i++) {
            const [px, py] = points[i - 1];
            const [cx, cy] = points[i];
            const mx = (px + cx) / 2;
            path += ` C ${mx},${py} ${mx},${cy} ${cx},${cy}`;
        }
        const areaPath = path + ` L ${points[points.length - 1][0]},${padT + innerH} L ${points[0][0]},${padT + innerH} Z`;

        // x 轴标签
        const xLabels = heartData.map((d, i) =>
            `<text x="${x(i)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#94a3b8">${d.time}</text>`
        ).join("");

        // 折线点
        const dots = heartData.map((d, i) =>
            `<circle cx="${x(i)}" cy="${y(d.rate)}" r="3" fill="#fff" stroke="#ef4444" stroke-width="2"/>`
        ).join("");

        el.innerHTML = `
            <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
                <defs>
                    <linearGradient id="hrGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#ef4444" stop-opacity="0.25"/>
                        <stop offset="100%" stop-color="#ef4444" stop-opacity="0"/>
                    </linearGradient>
                </defs>
                ${gridLines}
                <path d="${areaPath}" fill="url(#hrGrad)"/>
                <path d="${path}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                ${dots}
                ${xLabels}
            </svg>
        `;
    }

    function setupTabs() {
        const tabs = document.querySelectorAll(".member-tab");
        tabs.forEach(tab => {
            tab.addEventListener("click", () => {
                if (tab.disabled) return;
                tabs.forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
            });
        });
    }

    function setupSync() {
        const btn = document.getElementById("syncBtn");
        const text = document.getElementById("syncText");
        if (!btn) return;
        btn.addEventListener("click", () => {
            btn.classList.add("syncing");
            text.textContent = "同步中…";
            setTimeout(() => {
                btn.classList.remove("syncing");
                text.textContent = "已同步";
                setTimeout(() => {
                    text.textContent = "立即同步";
                }, 1500);
            }, 1500);
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderBarChart();
        renderAreaChart();
        setupTabs();
        setupSync();
    });
})();
