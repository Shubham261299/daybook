function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function loadTaskProjects() {
  const projects = await apiGet("/api/projects");
  const select = document.getElementById("task-project");
  const currentSelection = select.value;
  select.innerHTML = `<option value="">(general)</option>` +
    projects.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
  select.value = currentSelection;
}

function taskRowHtml(t) {
  const today = new Date().toISOString().slice(0, 10);
  const overdue = t.status === "open" && t.due_date && t.due_date < today;
  return `
    <div class="task-row" data-task-id="${t.id}">
      <input type="checkbox" class="task-checkbox" ${t.status === "done" ? "checked" : ""} />
      <div class="task-text ${t.status === "done" ? "task-done" : ""}">
        ${escapeHtml(t.text)}
        ${t.project_name ? ` <span style="color:${projectColor(t.project_name)}; font-weight:600; font-size:11px;">— ${escapeHtml(t.project_name)}</span>` : ""}
      </div>
      ${t.due_date ? `<div class="task-due ${overdue ? "task-overdue" : ""}">${escapeHtml(t.due_date)}</div>` : ""}
      <button class="secondary task-delete-btn" title="Delete task">&times;</button>
    </div>
  `;
}

async function loadTasks() {
  const allTasks = await apiGet("/api/tasks");
  const open = allTasks.filter((t) => t.status === "open");
  const done = allTasks.filter((t) => t.status === "done");

  document.getElementById("tasks-open-list").innerHTML = open.length
    ? open.map(taskRowHtml).join("")
    : `<div class="empty-state">No open tasks.</div>`;

  const doneListEl = document.getElementById("tasks-done-list");
  doneListEl.innerHTML = done.map(taskRowHtml).join("");

  const toggleEl = document.getElementById("tasks-done-toggle");
  if (done.length) {
    toggleEl.innerHTML = `<button class="secondary" id="tasks-done-toggle-btn" style="margin-top:8px;">${doneListEl.hidden ? "Show" : "Hide"} ${done.length} completed</button>`;
    document.getElementById("tasks-done-toggle-btn").addEventListener("click", () => {
      doneListEl.hidden = !doneListEl.hidden;
      loadTasks();
    });
  } else {
    toggleEl.innerHTML = "";
  }

  document.querySelectorAll(".task-checkbox").forEach((cb) => {
    cb.addEventListener("change", async (e) => {
      const row = e.target.closest(".task-row");
      await apiPatch(`/api/tasks/${row.dataset.taskId}`, { status: e.target.checked ? "done" : "open" });
      loadTasks();
    });
  });

  document.querySelectorAll(".task-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const row = e.target.closest(".task-row");
      if (!confirm("Delete this task?")) return;
      await apiDelete(`/api/tasks/${row.dataset.taskId}`);
      loadTasks();
    });
  });
}

document.getElementById("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = document.getElementById("task-text").value.trim();
  const due = document.getElementById("task-due").value || null;
  const projectId = document.getElementById("task-project").value || null;
  if (!text) return;
  await apiPost("/api/tasks", { text, due_date: due, project_id: projectId ? parseInt(projectId, 10) : null });
  e.target.reset();
  loadTasks();
});

loadTaskProjects();
loadTasks();
