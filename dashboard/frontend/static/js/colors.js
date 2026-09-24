// Deterministic per-project color, based on the project name so it stays
// consistent across pages/reloads without needing a DB column.
const PROJECT_COLOR_VARS = [
  "--proj-violet", "--proj-cyan", "--proj-pink", "--proj-amber",
  "--proj-emerald", "--proj-blue", "--proj-rose", "--proj-lime",
];

function projectColorVar(name) {
  let hash = 0;
  const s = String(name || "");
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  }
  return PROJECT_COLOR_VARS[hash % PROJECT_COLOR_VARS.length];
}

function projectColor(name) {
  return `var(${projectColorVar(name)})`;
}
