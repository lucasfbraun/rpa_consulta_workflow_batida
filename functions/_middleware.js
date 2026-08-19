const encoder = new TextEncoder();
const COOKIE = "rpa_session";
const PUBLIC_PATHS = new Set(["/login", "/manifest.webmanifest", "/icon.svg", "/sw.js"]);

function base64url(value) {
  return btoa(value).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function decodeBase64url(value) {
  const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
  return atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "="));
}

function base64urlBytes(value) {
  return Uint8Array.from(decodeBase64url(value), (character) => character.charCodeAt(0));
}

async function hmacKey(password, usages) {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    { name: "HMAC", hash: "SHA-256" },
    false,
    usages,
  );
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
  try {
    const key = await hmacKey(password, ["verify"]);
    return crypto.subtle.verify("HMAC", key, base64urlBytes(supplied), encoder.encode(payload));
  } catch { return false; }
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
  try {
    const decoded = JSON.parse(decodeBase64url(payload));
    return decoded.u === username && decoded.exp > Date.now();
  } catch { return false; }
}

function redirect(location, cookie) {
  const headers = { Location: location, "Cache-Control": "no-store" };
  if (cookie) headers["Set-Cookie"] = cookie;
  return new Response(null, { status: 303, headers });
}

function securedResponse(original, cacheControl = "private, no-store") {
  const response = new Response(original.body, original);
  response.headers.set("Cache-Control", cacheControl);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

export async function onRequest(context) {
  const { request, env } = context;
  const path = new URL(request.url).pathname;
  const configured = Boolean(env.PONTO_USERNAME && env.PONTO_PASSWORD);
  if (path === "/api/login" && request.method === "POST") {
    if (!configured) return redirect("/login?error=config");
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
  if (!(await validSession(request, env.PONTO_USERNAME, env.PONTO_PASSWORD))) return redirect("/login");
  return securedResponse(await context.next());
}
