// find_delete.mjs —— 只读：列出当前页面里所有"删除/更多"入口及位置
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const dump = async (tag) => {
  const r = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('*')) {
      const t = (el.textContent || '').trim()
      const a = el.getAttribute && (el.getAttribute('aria-label') || '')
      const title = el.getAttribute && (el.getAttribute('title') || '')
      const hitText = t === '删除' || t.startsWith('删除')
      const hitAria = /删除|更多|more|delete/i.test(a) || /删除|更多|delete/i.test(title)
      if (!hitText && !hitAria) continue
      const rc = el.getBoundingClientRect()
      if (rc.width < 8 || rc.height < 8) continue
      if (rc.width * rc.height > 40000) continue          // 跳过超大的容器
      out.push({
        txt: t.slice(0, 16),
        aria: a.slice(0, 20),
        title: title.slice(0, 16),
        tag: el.tagName,
        x: Math.round(rc.left + rc.width / 2),
        y: Math.round(rc.top + rc.height / 2),
        w: Math.round(rc.width),
        h: Math.round(rc.height),
      })
    }
    return out.slice(0, 25)
  })()`)
  console.log('--- ' + tag + ' ---')
  if (!r || !r.length) { console.log('  （没有找到删除/更多入口）'); return }
  for (const o of r) {
    console.log(`  [${o.tag}] "${o.txt}" aria="${o.aria}" title="${o.title}" 位置(${o.x},${o.y}) ${o.w}x${o.h}`)
  }
}

await dump('当前页面')

// 点开侧栏第一条对话，再看一次
const clicked = await b.session.evaluate(`(() => {
  let ry = null
  for (const el of document.querySelectorAll('div,span')) {
    if ((el.textContent || '').trim() === '最近') {
      const r = el.getBoundingClientRect()
      if (r.left < 300) { ry = r.top; break }
    }
  }
  if (ry === null) return null
  const rows = []
  for (const el of document.querySelectorAll('div,span,a,li')) {
    const t = (el.textContent || '').trim()
    if (!t || t.length > 80) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 120 || r.height < 18 || r.height > 50) continue
    if (r.top < ry + 10) continue
    rows.push({ t, y: r.top, x: r.left + r.width / 2 })
  }
  rows.sort((a, b) => a.y - b.y)
  if (!rows.length) return null
  const e = document.elementFromPoint(rows[0].x, rows[0].y)
  if (e) { e.click(); return rows[0].t.slice(0, 20) }
  return null
})()`)
console.log('点开对话:', clicked)
await new Promise(r => setTimeout(r, 3000))
await dump('点开对话后')
