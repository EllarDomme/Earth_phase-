// delete_many.mjs —— 批量删除侧栏里"图片/云层相关"的对话
//   用法: node delete_many.mjs [--all]
//   策略: 滚到顶 → 每轮只删"可见且匹配"的行 → 向下滚一屏 → 重复
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const ALL = process.argv.includes('--all')

const KEY = ['云层', '拼接', '条带', '地球', '图片', '图像', '模糊', '黑线',
             '修复', '背景色', '黑色背景', '截图', '抠图', 'NASA', '卫星图',
             '评价', '点评', '梭形', '抠像', '调色']

const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const click = async (x, y) => {
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
  }
}

// 找到侧栏可滚动容器并滚到顶
await b.session.evaluate(`(() => {
  let best = null, bestH = 0
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 120 || r.height < 200) continue
    if (el.scrollHeight > el.clientHeight + 50 && r.height > bestH) { best = el; bestH = r.height }
  }
  if (best) { best.scrollTop = 0; window.__sb = best }
  return !!best
})()`)
await sleep(800)

let removed = 0
for (let round = 0; round < 40; round++) {
  const rows = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('div,span,a,li')) {
      const t = (el.textContent || '').trim()
      if (!t || t.length > 60) continue
      const r = el.getBoundingClientRect()
      if (r.left > 300 || r.width < 120 || r.height < 18 || r.height > 48) continue
      if (r.top < 60 || r.top > window.innerHeight - 20) continue
      out.push({ t, x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) })
    }
    // 去重（同一行会被多个元素匹配）
    const seen = new Set(), uniq = []
    for (const o of out) { const k = o.y + '|' + o.t; if (!seen.has(k)) { seen.add(k); uniq.push(o) } }
    return uniq
  })()`)

  if (!rows || !rows.length) break

  let target = null
  for (const r of rows) {
    const hit = ALL || KEY.some(k => r.t.includes(k))
    if (hit) { target = r; break }
  }
  if (!target) {
    // 这一屏没有目标，向下滚
    const moved = await b.session.evaluate(`(() => {
      const sb = window.__sb
      if (!sb) return false
      const before = sb.scrollTop
      sb.scrollTop = before + 400
      return sb.scrollTop > before
    })()`)
    if (!moved) break
    await sleep(700)
    continue
  }

  // 悬停 → 更多 → 删除 → 确认
  await b.session.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved', x: target.x + target.w - 30, y: target.y + target.h / 2,
  })
  await sleep(800)

  const more = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('[aria-label]')) {
      const a = el.getAttribute('aria-label') || ''
      if (!/更多|more/i.test(a)) continue
      const r = el.getBoundingClientRect()
      if (r.width < 4 || r.left > 300) continue
      if (Math.abs(r.top - ${target.y}) > 14) continue
      out.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
    }
    return out
  })()`)
  if (!more || !more.length) { await sleep(600); continue }

  await click(more[0].x, more[0].y)
  await sleep(1000)

  const del = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('div,span,li,button')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 12) continue
      out.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
    }
    return out
  })()`)
  if (!del || !del.length) { await sleep(600); continue }

  await click(del[0].x, del[0].y)
  await sleep(1000)

  const conf = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('button,div,span')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除' && t !== '确定' && t !== '确认') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 14) continue
      out.push({ y: r.top, x: Math.round(r.left + r.width / 2), yy: Math.round(r.top + r.height / 2) })
    }
    out.sort((a, b) => b.y - a.y)
    return out
  })()`)
  if (conf && conf.length) { await click(conf[0].x, conf[0].yy); await sleep(1000) }

  removed++
  console.log(`删除 ${removed}: ${target.t.slice(0, 24)}`)
}

console.log(`共删除 ${removed} 个对话`)
