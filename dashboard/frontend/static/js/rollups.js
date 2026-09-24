let rollupState = { periodType: "week", which: "this", start: null, end: null };

async function loadRollupTab(periodType, which, btnEl) {
  document.querySelectorAll("#rollup-tabs button").forEach((b) => b.classList.remove("active-tab"));
  if (btnEl) btnEl.classList.add("active-tab");

  rollupState.periodType = periodType;
  rollupState.which = which;

  const content = document.getElementById("rollup-content");
  content.innerHTML = `<div class="spinner">Loading...</div>`;

  const { period_start, period_end } = await apiGet(`/api/rollups/bounds?period_type=${periodType}&which=${which}`);
  rollupState.start = period_start;
  rollupState.end = period_end;

  const rollup = await apiGet(`/api/rollups?period_type=${periodType}&period_start=${period_start}`);
  renderRollup(rollup);
}

function renderRollup(rollup) {
  const content = document.getElementById("rollup-content");
  const { periodType, start, end } = rollupState;
  const rangeLabel = start === end ? start : `${start} to ${end}`;

  content.innerHTML = `
    <div class="day-detail-header" style="margin-top:2px;">
      <div class="chat-meta" style="margin-top:0;">${escapeHtml(rangeLabel)}</div>
      <div class="actions">
        <a class="btn secondary" href="/api/export/rollup?period_type=${periodType}&period_start=${start}">Export .md</a>
        ${rollup ? `<button class="secondary" id="rollup-edit-btn">Edit</button>` : ""}
        <button id="rollup-regen-btn">${rollup ? "Regenerate" : "Generate"}</button>
      </div>
    </div>
    <div id="rollup-summary-section">${summaryViewHtml(rollup)}</div>
  `;

  document.getElementById("rollup-regen-btn").addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.textContent = "Generating...";
    try {
      const fresh = await apiPost("/api/rollups/generate", {
        period_type: periodType, period_start: start, period_end: end,
      });
      renderRollup(fresh);
    } catch (err) {
      alert("Failed to generate rollup: " + err.message);
      e.target.disabled = false;
    }
  });

  const editBtn = document.getElementById("rollup-edit-btn");
  if (editBtn) {
    editBtn.addEventListener("click", () => {
      const section = document.getElementById("rollup-summary-section");
      section.innerHTML = summaryEditHtml(rollup);
      wireSummaryEditForm(
        section,
        async (payload) => {
          const fresh = await apiSend("PATCH", `/api/rollups?period_type=${periodType}&period_start=${start}`, payload);
          renderRollup(fresh);
        },
        () => { section.innerHTML = summaryViewHtml(rollup); }
      );
    });
  }
}

document.querySelectorAll("#rollup-tabs button").forEach((btn) => {
  btn.addEventListener("click", () => loadRollupTab(btn.dataset.period, btn.dataset.which, btn));
});

loadRollupTab("week", "this", document.querySelector('#rollup-tabs button[data-period="week"][data-which="this"]'));
