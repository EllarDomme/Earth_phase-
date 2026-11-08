// del_top.mjs —— 循环删「最近」区最上面那条（每次删完重新取）
//   用法: node del_top.mjs [次数]
import { execFileSync } from 'node:child_process'
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const LIMIT = parseInt(process.argv[2] || '3', 10)
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
const HERE = dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

async function topTitle() {
  await b.session.evaluate(`(() => {
    let best = null, bestH = 0
    for (const el of document.querySelectorAll('*')) {
      const r = el.getBoundingClientRect()
      if (r.left > 300 || r.width < 120 || r.height < 200) continue
      if (el.scrollHeight > el.clientHeight + 50 && r.height > bestH) { best = el; bestH = r.height }
    }
    window.__sb = best
    if (best) best.scrollTop = 0
    return !!best
  })()`)
  await sleep(700)
  return await b.session.evaluate(`(() => {
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
      rows.push({ t, y: r.top })
    }
    rows.sort((a, b) => a.y - b.y)
    return rows.length ? rows[0].t : null
  })()`)
}

let done = 0
for (let i = 0; i < LIMIT; i++) {
  const raw = await topTitle()
  if (!raw) { console.log('拿不到最上面那条，停'); break }
  // 标题在 DOM 里可能重复拼接，取 1/3 长度那段
  const title = raw.length > 24 ? raw.slice(0, Math.ceil(raw.length / 3)) : raw
  console.log(`\n[${i + 1}] 目标是: ${title}`)
  try {
    const out = execFileSync('node', [HERE + '\\delete_conv.mjs', title],
      { encoding: 'utf-8', timeout: 120000, maxBuffer: 8 * 1024 * 1024 })
    console.log('    delete_conv 返回码 0')
    done++
  } catch (e) {
    console.log('    delete_conv 返回码', e.status)
    console.log('   ', (e.stdout || '').trim().split('\n').slice(-2).join(' | '))
  }
  await sleep(1500)
}
console.log(`\n共处理 ${done} 条`)
