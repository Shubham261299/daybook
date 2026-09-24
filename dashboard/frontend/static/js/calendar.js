const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const today = new Date();
let state = {
  year: today.getFullYear(),
  month: today.getMonth() + 1, // 1-12
  selected: null,
};

const todayStr = today.toISOString().slice(0, 10);

// Populated by loadQuietBanner() on every month load — read synchronously
// wherever a project picker is needed (e.g. the note form), no extra fetch.
let cachedProjects = [];

function monthLabel(year, month) {
  return new Date(year, month - 1, 1).toLocaleString("default", { month: "long", year: "numeric" });
}

async function loadMonth() {
  document.getElementById("month-label").textContent = monthLabel(state.year, state.month);
  const data = await apiGet(`/api/days/overview?year=${state.year}&month=${state.month}`);
  renderGrid(data.days);
  document.getElementById("day-detail-panel").hidden = true;
  state.selected = null;
  loadQuietBanner();
}

async function loadQuietBanner() {
  const projects = await apiGet("/api/projects");
  cachedProjects = projects;
  const quiet = projects.filter((p) => p.status === "active" && p.is_quiet);
  const bannerEl = document.getElementById("quiet-banner");
  if (quiet.length) {
    bannerEl.hidden = false;
    bannerEl.innerHTML = `&#9888;&#65039; ${quiet.length} active project${quiet.length === 1 ? "" : "s"} gone quiet: ` +
      quiet.map((p) => escapeHtml(p.name) + (p.days_since_last_commit !== null ? ` (${p.days_since_last_commit}d)` : " (no commits yet)")).join(", ") +
      ` <a href="/settings" style="color:inherit;">manage &rarr;</a>`;
  } else {
    bannerEl.hidden = true;
  }
}

function renderGrid(days) {
  const grid = document.getElementById("calendar-grid");
  grid.innerHTML = "";

  WEEKDAYS.forEach((w) => {
    const el = document.createElement("div");
    el.className = "weekday-label";
    el.textContent = w;
    grid.appendChild(el);
  });

  const firstWeekday = new Date(state.year, state.month - 1, 1).getDay();
  for (let i = 0; i < firstWeekday; i++) {
    const el = document.createElement("div");
    el.className = "day-cell empty";
    grid.appendChild(el);
  }

  days.forEach((day) => {
    const cell = document.createElement("div");
    cell.className = "day-cell";
    if (day.date === todayStr) cell.classList.add("today");
    cell.dataset.date = day.date;

    const dayNum = day.date.split("-")[2].replace(/^0/, "");
    let badges = "";
    (day.projects || []).forEach((p) => {
      badges += `<span class="badge proj-badge" style="--proj-color:${projectColor(p.name)}" title="${escapeHtml(p.name)}: ${p.count} commit${p.count === 1 ? "" : "s"}">${p.count}</span>`;
    });
    if (day.note_count > 0) badges += `<span class="badge">${day.note_count} note${day.note_count === 1 ? "" : "s"}</span>`;
    [...new Set(day.tags || [])].forEach((tag) => {
      badges += `<span class="badge tag-badge" title="tagged ${escapeHtml(tag)}">&#127991;&#65039; ${escapeHtml(tag)}</span>`;
    });
    if (day.has_summary) badges += `<span class="badge summary">summary</span>`;

    cell.innerHTML = `<div class="day-num">${dayNum}</div><div class="day-badges">${badges}</div>`;
    cell.addEventListener("click", () => selectDay(day.date, cell));
    grid.appendChild(cell);
  });
}

async function selectDay(dateStr, cellEl) {
  document.querySelectorAll(".day-cell.selected").forEach((c) => c.classList.remove("selected"));

  if (state.selected === dateStr) {
    state.selected = null;
    document.getElementById("day-detail-panel").hidden = true;
    return;
  }

  cellEl.classList.add("selected");
  state.selected = dateStr;

  const panel = document.getElementById("day-detail-panel");
  panel.hidden = false;
  panel.innerHTML = `<div class="spinner">Loading ${dateStr}...</div>`;

  const data = await apiGet(`/api/days/${dateStr}`);
  renderDayDetail(dateStr, data);
}

function renderDayDetail(dateStr, data) {
  const panel = document.getElementById("day-detail-panel");
  const projectsByName = {};
  data.commits.forEach((c) => {
    (projectsByName[c.project_name] ??= []).push(c);
  });

  let commitsHtml = "";
  if (Object.keys(projectsByName).length) {
    commitsHtml = Object.entries(projectsByName).map(([name, commits]) => `
      <div class="project-block proj-card" style="--proj-color:${projectColor(name)}">
        <h4 class="solid">${escapeHtml(name)}</h4>
        ${commits.map((c) => `
          <div class="commit-row">
            <span class="msg">
              ${escapeHtml(c.message.split("\n")[0])}
              ${(c.git_tags || "").split(",").filter(Boolean).map((t) => `<span class="badge tag-badge" title="tagged ${escapeHtml(t)}">&#127991;&#65039; ${escapeHtml(t)}</span>`).join(" ")}
            </span>
            <span class="stats">+${c.insertions}/-${c.deletions}</span>
          </div>
        `).join("")}
      </div>
    `).join("");
  } else {
    commitsHtml = `<div class="empty-state">No commits on this day.</div>`;
  }

  let notesHtml = data.notes.map((n) => `
    <div class="note-row" data-note-id="${n.id}">
      <div class="note-row-text">
        ${n.tag ? `<span class="tag">${escapeHtml(n.tag)}</span>` : ""}
        ${escapeHtml(n.text)}
        ${n.duration_minutes ? ` <span class="chat-meta">(${n.duration_minutes} min)</span>` : ""}
        ${n.project_name ? ` <span class="badge" style="background:transparent; color:${projectColor(n.project_name)}; padding:0; font-weight:600;">— ${escapeHtml(n.project_name)}</span>` : ""}
      </div>
      <button class="secondary note-delete-btn" title="Delete note">&times;</button>
    </div>
  `).join("") || `<div class="empty-state">No notes for this day.</div>`;

  panel.innerHTML = `
    <div class="day-detail">
      <div class="day-detail-header">
        <h2>${dateStr}</h2>
        <div class="actions">
          <a class="btn secondary" href="/api/export/day/${dateStr}">Export .md</a>
          ${data.summary ? `<button class="secondary" id="edit-btn">Edit</button>` : ""}
          <button id="regen-btn">${data.summary ? "Regenerate summary" : "Generate summary"}</button>
        </div>
      </div>
      <div id="summary-section">${summaryViewHtml(data.summary)}</div>
      <h3 style="margin-top:18px;">Commits</h3>
      ${commitsHtml}
      <h3 style="margin-top:18px;">Notes</h3>
      ${notesHtml}
      <form id="note-form" class="row" style="margin-top:10px; align-items:flex-end;">
        <div class="field" style="flex:3;">
          <label>Add note</label>
          <input type="text" id="note-text" placeholder="What happened..." required />
        </div>
        <div class="field" style="flex:1;">
          <label>Tag</label>
          <select id="note-tag">
            <option value="">(none)</option>
            <option value="meeting">meeting</option>
            <option value="demo">demo</option>
            <option value="discussion">discussion</option>
            <option value="blocker">blocker</option>
            <option value="idea">idea</option>
          </select>
        </div>
        <div class="field" style="flex:1;">
          <label>Minutes</label>
          <input type="number" id="note-duration" min="0" />
        </div>
        <div class="field" style="flex:1;">
          <label>Project</label>
          <select id="note-project">
            <option value="">(general)</option>
            ${cachedProjects.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("")}
          </select>
        </div>
        <div class="field" style="flex:0;">
          <button type="submit">Add</button>
        </div>
      </form>
    </div>
  `;

  document.getElementById("regen-btn").addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.textContent = "Generating...";
    try {
      await apiPost(`/api/summaries/${dateStr}/generate`);
      const fresh = await apiGet(`/api/days/${dateStr}`);
      renderDayDetail(dateStr, fresh);
      loadMonth();
    } catch (err) {
      alert("Failed to generate summary: " + err.message);
      e.target.disabled = false;
    }
  });

  const editBtn = document.getElementById("edit-btn");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      const section = document.getElementById("summary-section");
      section.innerHTML = summaryEditHtml(data.summary);
      wireSummaryEditForm(
        section,
        async (payload) => {
          await apiPatch(`/api/summaries/${dateStr}`, payload);
          const fresh = await apiGet(`/api/days/${dateStr}`);
          renderDayDetail(dateStr, fresh);
          loadMonth();
        },
        () => { section.innerHTML = summaryViewHtml(data.summary); }
      );
    });
  }

  document.querySelectorAll(".note-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const row = e.target.closest(".note-row");
      const noteId = row.dataset.noteId;
      if (!confirm("Delete this note?")) return;
      await apiDelete(`/api/notes/${noteId}`);
      const fresh = await apiGet(`/api/days/${dateStr}`);
      renderDayDetail(dateStr, fresh);
      loadMonth();
    });
  });

  document.getElementById("note-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = document.getElementById("note-text").value.trim();
    const tag = document.getElementById("note-tag").value || null;
    const duration = document.getElementById("note-duration").value || null;
    const projectId = document.getElementById("note-project").value || null;
    if (!text) return;
    await apiPost("/api/notes", {
      note_date: dateStr,
      text,
      tag,
      duration_minutes: duration ? parseInt(duration, 10) : null,
      project_id: projectId ? parseInt(projectId, 10) : null,
    });
    const fresh = await apiGet(`/api/days/${dateStr}`);
    renderDayDetail(dateStr, fresh);
    loadMonth();
  });
}

function summaryViewHtml(summary) {
  if (!summary) return `<div class="empty-state">No summary generated yet for this day.</div>`;

  let bullets = [];
  let other = [];
  try { bullets = JSON.parse(summary.project_bullets || "[]"); } catch (e) {}
  try { other = JSON.parse(summary.other_activities || "[]"); } catch (e) {}

  let html = `<div class="narrative">${escapeHtml(summary.narrative || "")}</div>`;
  bullets.forEach((pb) => {
    html += `<div class="project-block proj-card" style="--proj-color:${projectColor(pb.project)}"><h4 class="solid">${escapeHtml(pb.project)}</h4><ul>${pb.bullets.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul></div>`;
  });
  if (other.length) {
    html += `<div class="project-block"><h4>Other activities</h4><ul>${other.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul></div>`;
  }
  html += summary.edited
    ? `<div class="chat-meta">edited manually</div>`
    : `<div class="chat-meta">generated by ${escapeHtml(summary.model_used || "?")}</div>`;
  return html;
}

function summaryEditHtml(summary) {
  let bullets = [];
  let other = [];
  try { bullets = JSON.parse(summary.project_bullets || "[]"); } catch (e) {}
  try { other = JSON.parse(summary.other_activities || "[]"); } catch (e) {}

  const projectFields = bullets.map((pb, i) => `
    <div class="field">
      <label>${escapeHtml(pb.project)} — one bullet per line</label>
      <textarea rows="3" data-project="${escapeHtml(pb.project)}" class="edit-bullets">${escapeHtml(pb.bullets.join("\n"))}</textarea>
    </div>
  `).join("");

  return `
    <div class="field">
      <label>Narrative</label>
      <textarea rows="3" class="edit-narrative">${escapeHtml(summary.narrative || "")}</textarea>
    </div>
    ${projectFields}
    <div class="field">
      <label>Other activities — one bullet per line</label>
      <textarea rows="2" class="edit-other">${escapeHtml(other.join("\n"))}</textarea>
    </div>
    <div class="row" style="margin-bottom:6px;">
      <button class="save-summary-btn">Save</button>
      <button class="secondary cancel-edit-btn">Cancel</button>
    </div>
  `;
}

// Generic edit-form wiring shared by the day-detail panel and the rollup
// panel. Scoped to `container` so two edit forms open at once (one on the
// day panel, one on the rollup panel) don't collide. onSave receives
// {narrative, project_bullets, other_activities} and persists + re-renders.
function wireSummaryEditForm(container, onSave, onCancel) {
  container.querySelector(".cancel-edit-btn").addEventListener("click", onCancel);

  container.querySelector(".save-summary-btn").addEventListener("click", async () => {
    const narrative = container.querySelector(".edit-narrative").value.trim();
    const other_activities = container.querySelector(".edit-other").value
      .split("\n").map((s) => s.trim()).filter(Boolean);
    const project_bullets = Array.from(container.querySelectorAll(".edit-bullets")).map((el) => ({
      project: el.dataset.project,
      bullets: el.value.split("\n").map((s) => s.trim()).filter(Boolean),
    }));

    try {
      await onSave({ narrative, project_bullets, other_activities });
    } catch (err) {
      alert("Failed to save: " + err.message);
    }
  });
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

document.getElementById("collect-btn").addEventListener("click", async (e) => {
  const btn = e.target;
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Collecting...";
  const previouslySelected = state.selected;
  try {
    const result = await apiPost("/api/sync");
    btn.textContent = `+${result.total_new_commits} new`;
    await loadMonth();
    if (previouslySelected) {
      const cell = document.querySelector(`.day-cell[data-date="${previouslySelected}"]`);
      if (cell) selectDay(previouslySelected, cell);
    }
  } catch (err) {
    alert("Collection failed: " + err.message);
    btn.textContent = original;
  } finally {
    setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2500);
  }
});

document.getElementById("prev-month").addEventListener("click", () => {
  state.month -= 1;
  if (state.month < 1) { state.month = 12; state.year -= 1; }
  loadMonth();
});

document.getElementById("next-month").addEventListener("click", () => {
  state.month += 1;
  if (state.month > 12) { state.month = 1; state.year += 1; }
  loadMonth();
});

loadMonth();
