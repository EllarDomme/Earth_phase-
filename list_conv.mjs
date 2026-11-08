// list_conv.mjs —— 列出豆包侧栏里的对话条目，确认到底删没删
import http from "node:http";

const PORT = 9225;

function get(path) {
  return new Promise((res, rej) => {
    http.get({ host: "127.0.0.1", port: PORT, path }, (r) => {
      let b = "";
      r.on("data", (d) => (b += d));
      r.on("end", () => res(b));
    }).on("error", rej);
  });
}

const list = JSON.parse(await get("/json"));
const pages = list.filter((t) => t.type === "page" && /chat/.test(t.url || ""));
if (!pages.length) {
  console.log("没有聊天页");
  process.exit(0);
}
const target = pages[0];
console.log("聊天页:", target.url);

const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((res) => {
    const i = ++id;
    pending.set(i, res);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
}
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m.result);
    pending.delete(m.id);
  }
};
await new Promise((r) => (ws.onopen = r));

const expr = `
(() => {
  const out = [];
  const nodes = [...document.querySelectorAll('div,span,a,li')];
  for (const el of nodes) {
    const t = (el.textContent || '').trim();
    if (t !== '图像云层处理') continue;
    if (el.children.length) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    out.push({ x: Math.round(r.x), y: Math.round(r.y) });
  }
  return JSON.stringify({ count: out.length, first: out.slice(0, 5) });
})()`;

const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
console.log("侧栏「图像云层处理」条目:", r.result?.value);
ws.close();
