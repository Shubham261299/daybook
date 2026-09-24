function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function sparklineSvg(values) {
  const w = 280, h = 32, pad = 2;
  const max = Math.max(1, ...values);
  const stepX = values.length > 1 ? (w - pad * 2) / (values.length - 1) : 0;
  const points = values.map((v, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (v / max) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `
    <svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <polyline points="${points}" fill="none" stroke="var(--accent-2)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  `;
}

async function loadHeatmap() {
  const data = await apiGet("/api/days/heatmap");
  const max = Math.max(1, ...data.days.map((d) => d.count));

  const levelFor = (count) => {
    if (count === 0) return 0;
    const ratio = count / max;
    if (ratio > 0.75) return 4;
    if (ratio > 0.5) return 3;
    if (ratio > 0.25) return 2;
    return 1;
  };

  document.getElementById("heatmap-grid").innerHTML = data.days.map((d) => {
    const level = levelFor(d.count);
    const label = `${d.date}: ${d.count} activit${d.count === 1 ? "y" : "ies"}`;
    return `<div class="heatmap-cell" data-level="${level}" title="${escapeHtml(label)}"></div>`;
  }).join("");
}

async function loadOverview() {
  const data = await apiGet("/api/overview");

  const bannerEl = document.getElementById("quiet-banner");
  if (data.quiet_projects.length) {
    bannerEl.hidden = false;
    bannerEl.innerHTML = `&#9888;&#65039; ${data.quiet_projects.length} active project${data.quiet_projects.length === 1 ? "" : "s"} gone quiet: ` +
      data.quiet_projects.map((p) => escapeHtml(p.name) + (p.days_since_last_commit !== null ? ` (${p.days_since_last_commit}d)` : " (no commits yet)")).join(", ") +
      ` <a href="/settings" style="color:inherit;">manage &rarr;</a>`;
  } else {
    bannerEl.hidden = true;
  }

  document.getElementById("stat-row").innerHTML = `
    <div class="gradient-stat">
      <div class="label">Active Projects</div>
      <div class="value">${data.active_project_count}</div>
    </div>
    <div class="gradient-stat">
      <div class="label">Commits This Month</div>
      <div class="value">${data.total_commits_this_month}</div>
    </div>
    <div class="gradient-stat">
      <div class="label">Activity This Month</div>
      ${sparklineSvg(data.sparkline_this_month)}
    </div>
  `;

  document.getElementById("projects-list").innerHTML = data.projects.map((p) => `
    <div class="proj-list-item" style="--proj-color:${projectColor(p.name)}">
      <div>
        <div class="proj-name">${escapeHtml(p.name)} ${p.is_quiet ? `<span class="badge warn">quiet</span>` : ""}</div>
        <div class="proj-meta">${[p.phase, p.department].filter(Boolean).map(escapeHtml).join(" · ") || "&mdash;"}</div>
      </div>
      <div class="proj-right">
        <div class="status-${p.status}">${p.status}</div>
        <div>${p.days_since_last_commit !== null ? `${p.days_since_last_commit}d since last commit` : ""}</div>
      </div>
    </div>
  `).join("") || `<div class="empty-state">No projects yet — add one in Projects.</div>`;

  const rs = data.recent_summary;
  document.getElementById("recent-summary").innerHTML = rs
    ? `
      <div class="chat-meta" style="margin-top:0;">${escapeHtml(rs.summary_date)}</div>
      <div class="narrative">${escapeHtml(rs.narrative)}</div>
      <a class="btn secondary" href="/">Open in Calendar &rarr;</a>
    `
    : `<div class="empty-state">No summaries generated yet.</div>`;

  const backfillPanel = document.getElementById("backfill-panel");
  const missing = data.missing_summary_dates;
  if (missing.length) {
    backfillPanel.hidden = false;
    document.getElementById("backfill-content").innerHTML = `
      <p class="empty-state" style="margin-top:-4px;">
        ${missing.length} day${missing.length === 1 ? "" : "s"} with commits or notes have no summary yet:
        ${missing.slice(0, 8).map(escapeHtml).join(", ")}${missing.length > 8 ? ", …" : ""}
      </p>
      <button id="backfill-btn">Generate all missing summaries</button>
      <div class="chat-meta" id="backfill-status"></div>
    `;
    document.getElementById("backfill-btn").addEventListener("click", async (e) => {
      e.target.disabled = true;
      e.target.textContent = "Starting...";
      try {
        const result = await apiPost("/api/backfill/run");
        document.getElementById("backfill-status").textContent =
          `Started in the background — generating ${result.queued_dates.length} summaries (roughly ${result.queued_dates.length} x 20-60s). Reload this page later to see progress; each one appears on the Calendar as it finishes.`;
      } catch (err) {
        alert("Failed to start backfill: " + err.message);
        e.target.disabled = false;
        e.target.textContent = "Generate all missing summaries";
      }
    });
  } else {
    backfillPanel.hidden = true;
  }
}

loadOverview();
loadHeatmap();
