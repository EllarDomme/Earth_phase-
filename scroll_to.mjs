// scroll_to.mjs —— 把指定标题的对话行滚到侧栏可视区（只滚动，不删除）
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const want = process.argv[2] || ''
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const findSb = `(() => {
  let best = null, bestH = 0
  for (const el of document.querySelectorAll('*')) {
    const r = el.getBoundingClientRect()
    if (r.left > 300 || r.width < 120 || r.height < 200) continue
    if (el.scrollHeight > el.clientHeight + 50 && r.height > bestH) { best = el; bestH = r.height }
  }
  window.__sb = best
  return !!best
})()`
await b.session.evaluate(findSb)

// 逐段往下滚，直到目标行出现在可视区中部
for (let i = 0; i < 20; i++) {
  const st = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('div,span,a,li')) {
      const t = (el.textContent || '').trim()
      if (!t.startsWith(${JSON.stringify(want)})) continue
      const r = el.getBoundingClientRect()
      if (r.left > 300 || r.width < 120 || r.height < 18 || r.height > 50) continue
      out.push({ y: Math.round(r.top), t: t.slice(0, 24) })
    }
    return { rows: out, top: window.__sb ? window.__sb.scrollTop : -1 }
  })()`)

  const vis = st.rows.filter(r => r.y > 300 && r.y < 780)
  if (vis.length) {
    console.log(`找到并已可见: ${vis[0].t}  y=${vis[0].y}  scrollTop=${st.top}`)
    process.exit(0)
  }
  if (st.rows.length) {
    // 存在但在屏幕外：按方向调整
    const y = st.rows[0].y
    const delta = y < 300 ? -300 : 300
    await b.session.evaluate(`(() => { if (window.__sb) window.__sb.scrollTop += ${delta}; return true })()`)
  } else {
    await b.session.evaluate(`(() => { if (window.__sb) window.__sb.scrollTop += 350; return true })()`)
  }
  await new Promise(r => setTimeout(r, 600))
}

console.log('滚到底也没找到:', want)
process.exit(2)
