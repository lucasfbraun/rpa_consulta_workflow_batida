const encoder = new TextEncoder();
const COOKIE = "rpa_session";
const PUBLIC_PATHS = new Set(["/login", "/manifest.webmanifest", "/icon.svg", "/sw.js"]);
const TIME_ZONE = "America/Sao_Paulo";

function base64url(value) { return btoa(value).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", ""); }
function decodeBase64url(value) { const normalized = value.replaceAll("-", "+").replaceAll("_", "/"); return atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")); }
function base64urlBytes(value) { return Uint8Array.from(decodeBase64url(value), (character) => character.charCodeAt(0)); }

async function hmacKey(password, usages) {
  return crypto.subtle.importKey("raw", encoder.encode(password), { name: "HMAC", hash: "SHA-256" }, false, usages);
}
async function signature(payload, password) {
  const key = await hmacKey(password, ["sign"]);
  const bytes = new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(payload)));
  return base64url(String.fromCharCode(...bytes));
}
async function matches(left, right, password) {
  const key = await hmacKey(password, ["sign", "verify"]);
  const expected = await crypto.subtle.sign("HMAC", key, encoder.encode(right));
  return crypto.subtle.verify("HMAC", key, expected, encoder.encode(left));
}
async function validSignature(payload, supplied, password) {
  try { const key = await hmacKey(password, ["verify"]); return crypto.subtle.verify("HMAC", key, base64urlBytes(supplied), encoder.encode(payload)); }
  catch { return false; }
}
async function createSession(username, password) {
  const payload = base64url(JSON.stringify({ u: username, exp: Date.now() + 12 * 60 * 60 * 1000 }));
  return `${payload}.${await signature(payload, password)}`;
}
async function validSession(request, username, password) {
  const match = request.headers.get("Cookie")?.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  if (!match) return false;
  const [payload, supplied] = match[1].split(".");
  if (!payload || !supplied || !(await validSignature(payload, supplied, password))) return false;
  try { const decoded = JSON.parse(decodeBase64url(payload)); return decoded.u === username && decoded.exp > Date.now(); }
  catch { return false; }
}

function redirect(location, cookie) {
  const headers = { Location: location, "Cache-Control": "no-store" };
  if (cookie) headers["Set-Cookie"] = cookie;
  return new Response(null, { status: 303, headers });
}
function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}
function securedResponse(original, cacheControl = "private, no-store") {
  const response = new Response(original.body, original);
  response.headers.set("Cache-Control", cacheControl);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}
function sameOrigin(request) {
  const origin = request.headers.get("Origin");
  if (origin && origin !== "null") return origin === new URL(request.url).origin;
  return request.headers.get("Sec-Fetch-Site") === "same-origin";
}
async function body(request) {
  if (Number(request.headers.get("Content-Length") || 0) > 8192) throw new Error("too_large");
  return request.json();
}

function localNow(date = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit",
    minute: "2-digit", hourCycle: "h23", weekday: "short",
  }).formatToParts(date).filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  const weekday = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 }[parts.weekday];
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}`, weekday };
}
function validSchedule(value) {
  if (!value || typeof value !== "object") return null;
  const name = String(value.name || "").trim();
  const time = String(value.time || "");
  const weekdays = [...new Set(Array.isArray(value.weekdays) ? value.weekdays.map(Number) : [])].sort();
  if (!name || name.length > 60 || !/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) return null;
  if (!weekdays.length || weekdays.some((day) => !Number.isInteger(day) || day < 0 || day > 6)) return null;
  return { name, time, weekdays, enabled: value.enabled !== false };
}

async function materializeSchedules(db) {
  const local = localNow();
  const { results } = await db.prepare("SELECT id, time, weekdays FROM schedules WHERE enabled = 1").all();
  const now = new Date().toISOString();
  for (const schedule of results) {
    let weekdays;
    try { weekdays = JSON.parse(schedule.weekdays); } catch { continue; }
    if (!weekdays.includes(local.weekday) || schedule.time > local.time) continue;
    const commandId = `schedule:${schedule.id}:${local.date}`;
    await db.batch([
      db.prepare("INSERT OR IGNORE INTO commands (id, source, schedule_id, requested_at, scheduled_for, status) VALUES (?, 'schedule', ?, ?, ?, 'pending')").bind(commandId, schedule.id, now, `${local.date} ${schedule.time}`),
      db.prepare("UPDATE schedules SET last_enqueued_on = ?, updated_at = ? WHERE id = ?").bind(local.date, now, schedule.id),
    ]);
  }
}
async function agentAuthorized(request, env) {
  const supplied = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "") || "";
  return Boolean(env.CONTROL_AGENT_TOKEN && supplied && await matches(supplied, env.CONTROL_AGENT_TOKEN, env.CONTROL_AGENT_TOKEN));
}

async function agentApi(request, env, path) {
  if (!(await agentAuthorized(request, env))) return json({ error: "unauthorized" }, 401);
  if (!env.CONTROL_DB) return json({ error: "CONTROL_DB não configurado" }, 503);
  if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (path === "/api/agent/claim") {
    const now = new Date();
    const stale = new Date(now.getTime() - 45 * 60 * 1000).toISOString();
    await env.CONTROL_DB.prepare("UPDATE commands SET status = 'pending', claimed_at = NULL WHERE status = 'running' AND claimed_at < ?").bind(stale).run();
    await materializeSchedules(env.CONTROL_DB);
    await env.CONTROL_DB.prepare("INSERT INTO control_meta (key, value) VALUES ('agent_last_seen', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value").bind(now.toISOString()).run();
    const command = await env.CONTROL_DB.prepare("UPDATE commands SET status = 'running', claimed_at = ? WHERE id = (SELECT id FROM commands WHERE status = 'pending' ORDER BY requested_at LIMIT 1) RETURNING id, source, scheduled_for").bind(now.toISOString()).first();
    return json({ command: command || null });
  }
  if (path === "/api/agent/complete") {
    let data;
    try { data = await body(request); } catch { return json({ error: "invalid_body" }, 400); }
    if (typeof data?.id !== "string" || typeof data?.success !== "boolean") return json({ error: "invalid_body" }, 400);
    const status = data.success ? "completed" : "failed";
    const updated = await env.CONTROL_DB.prepare("UPDATE commands SET status = ?, finished_at = ?, result = ? WHERE id = ? AND status = 'running'").bind(status, new Date().toISOString(), String(data.result || "").slice(0, 500), data.id).run();
    return updated.meta.changes ? json({ ok: true }) : json({ error: "command_not_running" }, 409);
  }
  return json({ error: "not_found" }, 404);
}

async function userApi(request, env, path) {
  if (!env.CONTROL_DB) return json({ error: "CONTROL_DB não configurado" }, 503);
  if (request.method !== "GET" && !sameOrigin(request)) return json({ error: "invalid_origin" }, 403);
  if (path === "/api/control" && request.method === "GET") {
    const [schedules, commands, agent] = await Promise.all([
      env.CONTROL_DB.prepare("SELECT id, name, time, weekdays, enabled, created_at FROM schedules ORDER BY time, created_at").all(),
      env.CONTROL_DB.prepare("SELECT id, source, schedule_id, requested_at, scheduled_for, status, claimed_at, finished_at, result FROM commands ORDER BY requested_at DESC LIMIT 20").all(),
      env.CONTROL_DB.prepare("SELECT value FROM control_meta WHERE key = 'agent_last_seen'").first(),
    ]);
    return json({ schedules: schedules.results.map((item) => ({ ...item, weekdays: JSON.parse(item.weekdays), enabled: Boolean(item.enabled) })), commands: commands.results, agent_last_seen: agent?.value || null, timezone: TIME_ZONE });
  }
  if (path === "/api/control/run" && request.method === "POST") {
    const active = await env.CONTROL_DB.prepare("SELECT id FROM commands WHERE status IN ('pending', 'running') LIMIT 1").first();
    if (active) return json({ error: "Já existe uma execução pendente ou em andamento." }, 409);
    const id = crypto.randomUUID();
    await env.CONTROL_DB.prepare("INSERT INTO commands (id, source, requested_at, status) VALUES (?, 'manual', ?, 'pending')").bind(id, new Date().toISOString()).run();
    return json({ id, status: "pending" }, 201);
  }
  const match = path.match(/^\/api\/control\/schedules(?:\/([^/]+))?$/);
  if (!match) return json({ error: "not_found" }, 404);
  const id = match[1];
  if (!id && request.method === "POST") {
    let data;
    try { data = validSchedule(await body(request)); } catch { data = null; }
    if (!data) return json({ error: "Agendamento inválido." }, 400);
    const scheduleId = crypto.randomUUID();
    const now = new Date().toISOString();
    await env.CONTROL_DB.prepare("INSERT INTO schedules (id, name, time, weekdays, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)").bind(scheduleId, data.name, data.time, JSON.stringify(data.weekdays), data.enabled ? 1 : 0, now, now).run();
    return json({ id: scheduleId }, 201);
  }
  if (id && request.method === "PATCH") {
    let data;
    try { data = await body(request); } catch { return json({ error: "invalid_body" }, 400); }
    const fullSchedule = data && ("name" in data || "time" in data || "weekdays" in data);
    const schedule = fullSchedule ? validSchedule(data) : null;
    if (fullSchedule && !schedule) return json({ error: "Agendamento inválido." }, 400);
    if (!fullSchedule && typeof data?.enabled !== "boolean") return json({ error: "invalid_body" }, 400);
    const updated = fullSchedule
      ? await env.CONTROL_DB.prepare("UPDATE schedules SET name = ?, time = ?, weekdays = ?, enabled = ?, last_enqueued_on = NULL, updated_at = ? WHERE id = ?").bind(schedule.name, schedule.time, JSON.stringify(schedule.weekdays), schedule.enabled ? 1 : 0, new Date().toISOString(), id).run()
      : await env.CONTROL_DB.prepare("UPDATE schedules SET enabled = ?, updated_at = ? WHERE id = ?").bind(data.enabled ? 1 : 0, new Date().toISOString(), id).run();
    if (updated.meta.changes && (fullSchedule || !data.enabled)) {
      await env.CONTROL_DB.prepare("DELETE FROM commands WHERE schedule_id = ? AND status = 'pending'").bind(id).run();
    }
    return updated.meta.changes ? json({ ok: true }) : json({ error: "not_found" }, 404);
  }
  if (id && request.method === "DELETE") {
    await env.CONTROL_DB.prepare("DELETE FROM commands WHERE schedule_id = ? AND status = 'pending'").bind(id).run();
    const deleted = await env.CONTROL_DB.prepare("DELETE FROM schedules WHERE id = ?").bind(id).run();
    return deleted.meta.changes ? json({ ok: true }) : json({ error: "not_found" }, 404);
  }
  return json({ error: "method_not_allowed" }, 405);
}

export async function onRequest(context) {
  const { request, env } = context;
  const path = new URL(request.url).pathname;
  if (path.startsWith("/api/agent/")) return securedResponse(await agentApi(request, env, path));
  const configured = Boolean(env.PONTO_USERNAME && env.PONTO_PASSWORD);
  if (path === "/api/login" && request.method === "POST") {
    if (!configured) return redirect("/login?error=config");
    if (!sameOrigin(request)) return redirect("/login?error=invalid");
    const form = await request.formData();
    const username = String(form.get("username") || "");
    const password = String(form.get("password") || "");
    const usernameOk = await matches(username, env.PONTO_USERNAME, env.PONTO_PASSWORD);
    const passwordOk = await matches(password, env.PONTO_PASSWORD, env.PONTO_PASSWORD);
    if (!usernameOk || !passwordOk) return redirect("/login?error=invalid");
    const token = await createSession(env.PONTO_USERNAME, env.PONTO_PASSWORD);
    return redirect("/", `${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200`);
  }
  if (path === "/logout") return redirect("/login", `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0`);
  if (PUBLIC_PATHS.has(path)) return securedResponse(await context.next(), "no-store");
  if (!configured) return redirect("/login?error=config");
  if (!(await validSession(request, env.PONTO_USERNAME, env.PONTO_PASSWORD))) return path.startsWith("/api/") ? json({ error: "unauthorized" }, 401) : redirect("/login");
  if (path.startsWith("/api/control")) return securedResponse(await userApi(request, env, path));
  return securedResponse(await context.next());
}
