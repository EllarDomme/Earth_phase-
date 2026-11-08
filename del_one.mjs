// del_one.mjs —— 精确删除一条：找到同名行 → 点该行「更多」→ 点「删除」→ 确认
//   用法: node del_one.mjs "标题"
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const want = process.argv[2]
if (!want) { console.log('缺少标题'); process.exit(1) }
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const click = async (x, y) => {
  await b.session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y })
  await sleep(150)
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
    await sleep(60)
  }
}

// ① 找到目标行的 y（以及同行「更多」按钮）
const info = await b.session.evaluate(`(() => {
  const want = ${JSON.stringify(want)}
  let rowY = null
  for (const el of document.querySelectorAll('div,span,a,li')) {
    const t = (el.textContent || '').trim()
    if (!t.startsWith(want)) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 120 || r.height < 18 || r.height > 50) continue
    rowY = Math.round(r.top); break
  }
  if (rowY === null) return { ok: false, why: '没找到该行' }
  let btn = null
  for (const el of document.querySelectorAll('[aria-label]')) {
    const a = el.getAttribute('aria-label') || ''
    if (!/更多|more/i.test(a)) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 4) continue
    if (Math.abs((r.top + r.height / 2) - (rowY + 16)) > 18) continue
    btn = { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
    break
  }
  return { ok: true, rowY, btn }
})()`)
console.log('[1] 目标行:', JSON.stringify(info))
if (!info.ok || !info.btn) { console.log('拿不到「更多」按钮'); process.exit(2) }

// ② 点「更多」
await click(info.btn.x, info.btn.y)
await sleep(1200)

// ③ 列出菜单里的「删除」
const menu = await b.session.evaluate(`(() => {
  const out = []
  for (const el of document.querySelectorAll('div,span,li,button,a')) {
    const t = (el.textContent || '').trim()
    if (!t.startsWith('删除')) continue
    const r = el.getBoundingClientRect()
    if (r.width < 30 || r.height < 12) continue
    out.push({ t: t.slice(0, 12), x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
  }
  return out
})()`)
console.log('[2] 菜单项:', JSON.stringify(menu))
if (!menu.length) { console.log('菜单没弹出'); process.exit(3) }

// ④ 点「删除」
await click(menu[0].x, menu[0].y)
await sleep(1200)

// ⑤ 确认框
const conf = await b.session.evaluate(`(() => {
  const out = []
  for (const el of document.querySelectorAll('button,div,span')) {
    const t = (el.textContent || '').trim()
    if (t !== '删除' && t !== '确定' && t !== '确认') continue
    const r = el.getBoundingClientRect()
    if (r.width < 30 || r.height < 14) continue
    out.push({ t, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), top: r.top })
  }
  out.sort((a, b) => b.top - a.top)
  return out
})()`)
console.log('[3] 确认框按钮:', JSON.stringify(conf.slice(0, 3)))
if (conf.length) { await click(conf[0].x, conf[0].y); await sleep(1200) }

// ⑥ 复查
const still = await b.session.evaluate(`(() => {
  const want = ${JSON.stringify(want)}
  for (const el of document.querySelectorAll('div,span,a,li')) {
    const t = (el.textContent || '').trim()
    if (!t.startsWith(want)) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 120 || r.height < 18 || r.height > 50) continue
    return true
  }
  return false
})()`)
console.log(still ? '[4] ❌ 还在' : '[4] ✅ 已消失')
