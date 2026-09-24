const log = document.getElementById("chat-log");
const form = document.getElementById("ask-form");
const input = document.getElementById("ask-input");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function addMessage(role, html) {
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.innerHTML = html;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  addMessage("user", escapeHtml(question));

  const pending = addMessage("assistant", `<span class="spinner">Thinking...</span>`);

  try {
    const result = await apiPost("/api/chat", { question });
    const meta = `Interpreted as: ${result.interpreted_range.start_date} to ${result.interpreted_range.end_date}` +
      (result.interpreted_project ? ` · project: ${escapeHtml(result.interpreted_project)}` : "");
    pending.innerHTML = `${escapeHtml(result.answer)}<div class="chat-meta">${meta}</div>`;
  } catch (err) {
    pending.innerHTML = `Something went wrong: ${escapeHtml(err.message)}`;
  }
  log.scrollTop = log.scrollHeight;
});
