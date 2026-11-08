// delete_recent.mjs —— 只删「最近」区里指定的对话
//   用法: node delete_recent.mjs "标题1" "标题2" ...
//   硬规则: 目标行的 y 必须大于「最近」标题的 y，否则拒绝（防误删置顶）
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const wants = process.argv.slice(2)
if (!wants.length) { console.log('没给标题'); process.exit(1) }

const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const click = async (x, y) => {
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
  }
}

const recentY = async () => await b.session.evaluate(`(() => {
  for (const el of document.querySelectorAll('div,span')) {
    if ((el.textContent || '').trim() === '最近') {
      const r = el.getBoundingClientRect()
      if (r.left < 300 && r.width > 10) return Math.round(r.top)
    }
  }
  return null
})()`)

let done = 0
for (const want of wants) {
  const ry = await recentY()
  if (ry === null) { console.log('找不到「最近」标题，中止'); break }

  const row = await b.session.evaluate(`(() => {
    for (const el of document.querySelectorAll('div,span,a,li')) {
      const t = (el.textContent || '').trim()
      if (!t.startsWith(${JSON.stringify(want)})) continue
      const r = el.getBoundingClientRect()
      if (r.left > 300 || r.width < 100 || r.height < 16 || r.height > 56) continue
      if (r.top < ${ry}) continue                     // 置顶区一律不碰
      return { t: t.slice(0, 30), x: Math.round(r.left), y: Math.round(r.top),
               w: Math.round(r.width), h: Math.round(r.height) }
    }
    return null
  })()`)

  if (!row) { console.log(`跳过（不在最近区或找不到）: ${want}`); continue }

  await b.session.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved', x: row.x + row.w - 28, y: row.y + row.h / 2,
  })
  await sleep(800)

  const more = await b.session.evaluate(`(() => {
    for (const el of document.querySelectorAll('[aria-label]')) {
      const a = el.getAttribute('aria-label') || ''
      if (!/更多|more/i.test(a)) continue
      const r = el.getBoundingClientRect()
      if (r.width < 4 || r.left > 300) continue
      if (Math.abs(r.top - ${row.y}) > 14) continue
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
    }
    return null
  })()`)
  if (!more) { console.log(`  没找到「更多」: ${want}`); continue }

  await click(more.x, more.y)
  await sleep(1000)

  const del = await b.session.evaluate(`(() => {
    for (const el of document.querySelectorAll('div,span,li,button')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 12) continue
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
    }
    return null
  })()`)
  if (!del) { console.log(`  菜单里没有删除: ${want}`); continue }

  await click(del.x, del.y)
  await sleep(900)

  const conf = await b.session.evaluate(`(() => {
    const a = []
    for (const el of document.querySelectorAll('button,div,span')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除' && t !== '确定' && t !== '确认') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 14) continue
      a.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), top: r.top })
    }
    a.sort((p, q) => q.top - p.top)
    return a[0] || null
  })()`)
  if (conf) { await click(conf.x, conf.y); await sleep(900) }

  done++
  console.log(`已删除 ${done}: ${row.t}`)
  await sleep(600)
}

console.log(`完成，共删 ${done} 条`)
