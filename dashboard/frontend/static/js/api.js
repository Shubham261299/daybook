// fetch() throws a plain TypeError specifically for network-layer failures
// (DNS, connection reset, blocked request) — never for a real HTTP error
// status, which resolves normally with res.ok = false. So retrying only on
// TypeError retries genuine "never reached the server" blips, not
// legitimate 4xx/5xx application errors.
async function fetchWithRetry(url, options, retries = 2, delayMs = 700) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await fetch(url, options);
    } catch (err) {
      if (!(err instanceof TypeError) || attempt >= retries) throw err;
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
}

async function apiGet(url) {
  const res = await fetchWithRetry(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiSend(method, url, body) {
  const res = await fetchWithRetry(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

const apiPost = (url, body) => apiSend("POST", url, body);
const apiPatch = (url, body) => apiSend("PATCH", url, body);
const apiDelete = (url) => apiSend("DELETE", url);
