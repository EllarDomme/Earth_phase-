// delete_conv.mjs —— 删除指定标题的对话
//   用法: node delete_conv.mjs "<标题片段>"
//   流程: 找到侧边栏那一行 → 点它的「更多」→ 点「删除」→ 确认
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const want = process.argv[2] || ''
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const click = async (x, y) => {
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
  }
}

// ① 找到这一行
const row = await b.session.evaluate(`(() => {
  const want = ${JSON.stringify(want)}
  const rows = []
  for (const el of document.querySelectorAll('div,a,li')) {
    const t = (el.textContent || '').trim()
    if (!t.includes(want)) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300) continue                 // 只要左侧栏
    if (r.height < 18 || r.height > 48) continue
    if (r.width < 120) continue
    rows.push({ t: t.slice(0, 40), x: Math.round(r.left), y: Math.round(r.top),
                w: Math.round(r.width), h: Math.round(r.height) })
  }
  return rows
})()`)
console.log('匹配到的行:', JSON.stringify(row))
if (!row || !row.length) { console.log('没找到该对话'); process.exit(1) }

const R = row[0]
// ② 鼠标移到这一行，让「更多」出现
await b.session.send('Input.dispatchMouseEvent', {
  type: 'mouseMoved', x: R.x + R.w - 30, y: R.y + R.h / 2,
})
await sleep(900)

// ③ 在同一行里找「更多」按钮
const more = await b.session.evaluate(`(() => {
  const out = []
  for (const el of document.querySelectorAll('[aria-label]')) {
    const a = el.getAttribute('aria-label') || ''
    if (!/更多|more/i.test(a)) continue
    const r = el.getBoundingClientRect()
    if (r.width < 4) continue
    if (Math.abs(r.top - ${R.y}) > 12) continue      // 同一水平高度
    if (r.left > 300) continue
    out.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
  }
  return out
})()`)
console.log('该行的「更多」:', JSON.stringify(more))
if (!more || !more.length) { console.log('没找到更多按钮'); process.exit(2) }

await click(more[0].x, more[0].y)
await sleep(1200)

// ④ 菜单里点「删除」
const del = await b.session.evaluate(`(() => {
  const out = []
  for (const el of document.querySelectorAll('div,span,li,button')) {
    const t = (el.textContent || '').trim()
    if (!t.startsWith('删除')) continue
    const r = el.getBoundingClientRect()
    if (r.width < 30 || r.height < 10) continue
    out.push({ t, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
  }
  return out
})()`)
console.log('菜单里的删除项:', JSON.stringify(del))
if (!del || !del.length) { console.log('菜单里没有删除'); process.exit(3) }

await click(del[0].x, del[0].y)
await sleep(1200)

// ⑤ 确认框（如果有）
const confirm = await b.session.evaluate(`(() => {
  const out = []
  for (const el of document.querySelectorAll('button,div,span')) {
    const t = (el.textContent || '').trim()
    if (t !== '删除' && t !== '确定' && t !== '确认') continue
    const r = el.getBoundingClientRect()
    if (r.width < 30 || r.height < 14) continue
    out.push({ t, x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
  }
  return out
})()`)
if (confirm && confirm.length) {
  // 取最靠下的那个（通常是弹窗里的按钮）
  const c = confirm[confirm.length - 1]
  console.log('点确认:', JSON.stringify(c))
  await click(c.x, c.y)
  await sleep(1500)
} else {
  console.log('没有确认框')
}

const after = await b.session.evaluate('document.title')
console.log('删除后页面标题:', after)
console.log('DONE')
process.exit(0)
