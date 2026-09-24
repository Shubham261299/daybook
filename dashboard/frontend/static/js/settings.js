async function loadProjects() {
  const projects = await apiGet("/api/projects");

  const quiet = projects.filter((p) => p.status === "active" && p.is_quiet);
  const bannerEl = document.getElementById("quiet-banner");
  if (quiet.length) {
    bannerEl.hidden = false;
    bannerEl.innerHTML = `&#9888;&#65039; ${quiet.length} active project${quiet.length === 1 ? "" : "s"} gone quiet: ` +
      quiet.map((p) => escapeHtml(p.name) + (p.days_since_last_commit !== null ? ` (${p.days_since_last_commit}d)` : " (no commits yet)")).join(", ");
  } else {
    bannerEl.hidden = true;
  }

  const tbody = document.getElementById("projects-tbody");
  tbody.innerHTML = projects.map((p) => `
    <tr data-id="${p.id}" data-status="${p.status}">
      <td>${escapeHtml(p.name)} ${p.is_quiet ? `<span class="badge warn">quiet</span>` : ""}</td>
      <td style="font-size:12px; color:var(--text-dim);">${escapeHtml(p.path)}</td>
      <td>${escapeHtml(p.phase || "")}</td>
      <td>${escapeHtml(p.department || "")}</td>
      <td class="status-${p.status}">${p.status}</td>
      <td>
        <button class="secondary toggle-btn">${p.status === "active" ? "Pause" : "Activate"}</button>
      </td>
    </tr>
  `).join("") || `<tr><td colspan="6" class="empty-state">No projects yet.</td></tr>`;

  tbody.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const row = e.target.closest("tr");
      const id = row.dataset.id;
      const currentlyActive = row.dataset.status === "active";
      if (currentlyActive) {
        await apiDelete(`/api/projects/${id}`);
      } else {
        await apiPatch(`/api/projects/${id}`, { status: "active" });
      }
      loadProjects();
    });
  });
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

document.getElementById("add-project-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("add-error");
  errorEl.textContent = "";
  const name = document.getElementById("proj-name").value.trim();
  const path = document.getElementById("proj-path").value.trim();
  const phase = document.getElementById("proj-phase").value.trim() || null;
  const department = document.getElementById("proj-department").value.trim() || null;
  try {
    await apiPost("/api/projects", { name, path, phase, department });
    e.target.reset();
    loadProjects();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

loadProjects();
