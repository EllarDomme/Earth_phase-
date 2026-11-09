// delete_titled.mjs —— 按【精确标题】批量删除侧栏对话
//   用法: node delete_titled.mjs "标题A" "标题B" ...
//   安全: 只在侧栏匹配"整行文字完全等于"指定标题的行，不做模糊匹配
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const TITLES = process.argv.slice(2).filter(Boolean)
if (!TITLES.length) { console.log('用法: node delete_titled.mjs "标题A" "标题B"'); process.exit(1) }

const MAX = 200
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

const click = async (x, y) => {
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 })
  }
}

// 找侧栏里"整行文字 == 某个标题"的第一行
const findRow = async () => b.session.evaluate(`(() => {
  const T = ${JSON.stringify(TITLES)}
  // ★ 侧栏标题在 <span> 里（不是 div/a/li），且页面里有多个同名 span，
  //   取最有代表性的那个：无子元素、宽度 > 150 的整行标签。
  const cands = []
  for (const el of document.querySelectorAll('*')) {
    const t = (el.textContent || '').trim()
    if (!T.includes(t)) continue
    if (el.children.length !== 0) continue
    const r = el.getBoundingClientRect()
    if (r.left > 300) continue
    if (r.width < 150) continue
    if (r.height < 16 || r.height > 50) continue
    cands.push({ t, x: Math.round(r.left), y: Math.round(r.top),
                 w: Math.round(r.width), h: Math.round(r.height) })
  }
  if (!cands.length) return null
  // ★ 先滚到可视区再取坐标：列表长了以后，目标行可能在视口外，点不到
  const el0 = document.querySelectorAll('*')
  for (const el of el0) {
    const t = (el.textContent || '').trim()
    if (t !== cands[0].t) continue
    if (el.children.length !== 0) continue
    const r = el.getBoundingClientRect()
    if (Math.round(r.top) !== cands[0].y || Math.round(r.left) !== cands[0].x) continue
    el.scrollIntoView({ block: 'center' })
    break
  }
  return cands[0]
})()`)

// 滚到顶，保证最新的一批可见
await b.session.evaluate('(() => { const s = document.querySelector("[class*=sidebar],aside"); if (s) s.scrollTop = 0; window.scrollTo(0,0); return 1 })()')
await sleep(800)

let done = 0
let stuck = 0
for (let i = 0; i < MAX; i++) {
  let R = await findRow()
  if (!R) { console.log('没有匹配的行了'); break }
  // 滚动后坐标会变，重新取一次
  await sleep(500)
  const R2 = await findRow()
  if (R2) R = R2
  if (R.y < 60 || R.y > 900) {
    stuck++
    if (stuck > 5) { console.log('[跳过] 目标行始终不在可视区:', R.t); break }
    await sleep(300)
    continue
  }
  stuck = 0

  await b.session.send('Input.dispatchMouseEvent', {
    type: 'mouseMoved', x: R.x + R.w - 30, y: R.y + R.h / 2,
  })
  await sleep(700)

  const more = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('[aria-label]')) {
      const a = el.getAttribute('aria-label') || ''
      if (!/更多|more/i.test(a)) continue
      const r = el.getBoundingClientRect()
      if (r.width < 4 || r.left > 300) continue
      if (Math.abs(r.top - ${R.y}) > 14) continue
      out.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
    }
    return out
  })()`)
  if (!more || !more.length) { console.log('[跳过] 找不到更多按钮:', R.t); break }

  // ★ 点「更多」并重试：菜单偶尔不弹（悬停丢失 / 动画未完成）
  let opend = false
  for (let k = 0; k < 3 && !opend; k++) {
    await b.session.send('Input.dispatchMouseEvent', {
      type: 'mouseMoved', x: R.x + R.w - 30, y: R.y + R.h / 2,
    })
    await sleep(400)
    await click(more[0].x, more[0].y)
    await sleep(900)
    const menu = await b.session.evaluate(`(() => {
      for (const el of document.querySelectorAll('div,span,li,button')) {
        const t = (el.textContent || '').trim()
        if (t !== '删除') continue
        const r = el.getBoundingClientRect()
        if (r.width < 30 || r.height < 10) continue
        return 1
      }
      return 0
    })()`)
    opend = !!menu
  }
  if (!opend) {
    console.log('[跳过] 菜单没弹出，换下一条:', R.t)
    stuck++
    if (stuck > 3) break
    await sleep(400)
    continue
  }

  const del = await b.session.evaluate(`(() => {
    for (const el of document.querySelectorAll('div,span,li,button')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 10) continue
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) }
    }
    return null
  })()`)
  if (!del) { console.log('[跳过] 菜单里没有删除:', R.t); break }

  await click(del.x, del.y)
  await sleep(1100)

  const confirm = await b.session.evaluate(`(() => {
    const out = []
    for (const el of document.querySelectorAll('button,div,span')) {
      const t = (el.textContent || '').trim()
      if (t !== '删除' && t !== '确定' && t !== '确认') continue
      const r = el.getBoundingClientRect()
      if (r.width < 30 || r.height < 14) continue
      out.push({ x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) })
    }
    return out
  })()`)
  if (confirm && confirm.length) {
    const c = confirm[confirm.length - 1]
    await click(c.x, c.y)
    await sleep(1300)
  }

  done++
  if (done % 5 === 0) console.log('已删除', done, '条')
}

console.log('DELETED=' + done)
process.exit(0)
