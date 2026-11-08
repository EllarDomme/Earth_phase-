// doubao_quote.mjs —— 【流水线组件】引用"最新生成的那张图" → 输入提示词 → 发送 → 下载结果
//
//   用法:
//     node doubao_quote.mjs --prompt "<提示词>" --out <输出目录> [--dry-run] [--conv "<对话标题>"]
//
//   原理（2026-11-04 实测打通）：
//     · 每张生成图下面有一组 div.action-nxGadz（无文字图标，28×28，间距 34px）
//       从左到右 = 引用 / 再次生图 / 下载原图 / 创建画布
//     · 这些图标一直存在于 DOM（opacity:1, pointer-events:auto），
//       只是被上层容器视觉遮挡 —— 所以 element.click() 直接有效，不需要真实鼠标、不需要提权
//     · 引用后输入框会出现该图的缩略图；用它和"最新图"的 URL 哈希比对，确认引用的是对的那张
import fs from 'node:fs'
import path from 'node:path'
import {
  DoubaoBridge, pickBestImageUrls,
} from './tools/lib/bridge.mjs'

const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const arg = (name, def = null) => {
  const i = process.argv.indexOf('--' + name)
  return i >= 0 ? process.argv[i + 1] : def
}
const has = (name) => process.argv.includes('--' + name)

const prompt = arg('prompt', '')
const outDir = arg('out', new URL('./v2/_quote', import.meta.url).pathname.replace(/^\//, ''))
const dryRun = has('dry-run')
fs.mkdirSync(outDir, { recursive: true })

const imgKey = (u) => {
  const m = /rc_gen_image\/([0-9a-f]+)/.exec(u || '')
  return m ? m[1] : (u || '').slice(-40)
}

const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

// ── ① 找到"最新生成图"和它的图标组 ─────────────────────────────
const probe = async () => await b.session.evaluate(`(() => {
  const key = (u) => { const m = /rc_gen_image\\/([0-9a-f]+)/.exec(u || ''); return m ? m[1] : '' }
  const imgs = [...document.querySelectorAll('img')].filter(i => {
    const rc = i.getBoundingClientRect()
    return i.naturalWidth >= 700 && rc.left > 300
  }).map(i => {
    const rc = i.getBoundingClientRect()
    return { el: i, key: key(i.currentSrc || i.src), nw: i.naturalWidth,
             top: rc.top, bottom: rc.bottom, left: rc.left, right: rc.right,
             center: Math.round(rc.top + rc.height / 2) }
  }).filter(o => o.key).sort((a, b2) => a.top - b2.top)
  if (!imgs.length) return { err: 'no generated image' }
  const last = imgs[imgs.length - 1]
  const icons = [...document.querySelectorAll('div.action-nxGadz')].map(el => {
    const rc = el.getBoundingClientRect()
    return { el, x: Math.round(rc.left), y: Math.round(rc.top), w: Math.round(rc.width) }
  }).filter(o => o.y > last.top - 20 && o.y < last.bottom + 60 &&
                 o.x > last.left - 40 && o.x < last.right + 40)
    .sort((a, b2) => a.x - b2.x)
  return {
    lastKey: last.key, lastNw: last.nw,
    lastRect: [Math.round(last.left), Math.round(last.top), Math.round(last.right), Math.round(last.bottom)],
    icons: icons.map(o => ({ x: o.x, y: o.y })),
    count: imgs.length,
  }
})()`)

let p = await probe()
console.log('[引用] 最新图 key=%s  图标 %d 个', p.lastKey, (p.icons || []).length)
if (p.err || !p.icons || !p.icons.length) {
  console.log(JSON.stringify({ ok: false, reason: 'no-icon', probe: p }))
  process.exit(2)
}

// ── ② 点最左边那个图标（引用）──────────────────────────────────
const clicked = await b.session.evaluate(`(() => {
  const target = ${JSON.stringify(p.icons[0])}
  const cands = [...document.querySelectorAll('div.action-nxGadz')].map(el => {
    const rc = el.getBoundingClientRect()
    return { el, x: Math.round(rc.left), y: Math.round(rc.top) }
  }).filter(o => Math.abs(o.x - target.x) <= 2 && Math.abs(o.y - target.y) <= 2)
  if (!cands.length) return false
  cands[0].el.click()
  return true
})()`)
console.log('[引用] 点击图标', JSON.stringify(p.icons[0]), '→', clicked)
await sleep(1500)

// ── ③ 校验：输入框里的引用图 = 最新图 ──────────────────────────
const verify = async () => await b.session.evaluate(`(() => {
  const key = (u) => { const m = /rc_gen_image\\/([0-9a-f]+)/.exec(u || ''); return m ? m[1] : '' }
  const comp = [...document.querySelectorAll('img')].filter(i => {
    const rc = i.getBoundingClientRect()
    return rc.top > 600 && rc.width > 30 && rc.width < 220 && i.naturalWidth >= 200
  }).map(i => ({ key: key(i.currentSrc || i.src) })).filter(o => o.key)
  return { quoted: comp.length ? comp[0].key : null, n: comp.length }
})()`)

let v = await verify()
if (v.quoted !== p.lastKey) {
  console.log('[引用] 校验不符（引用=%s 最新=%s），重试一次', v.quoted, p.lastKey)
  // 取消已有引用，重新点
  await b.session.evaluate(`(() => {
    for (const el of document.querySelectorAll('[aria-label]')) {
      const a = el.getAttribute('aria-label') || ''
      if (/删除|移除|remove|close/i.test(a)) {
        const rc = el.getBoundingClientRect()
        if (rc.width > 6 && rc.top > 600) el.click()
      }
    }
  })()`)
  await sleep(800)
  p = await probe()
  if (p.icons && p.icons.length) {
    await b.session.evaluate(`(() => {
      const t = ${JSON.stringify(p.icons[0])}
      for (const el of document.querySelectorAll('div.action-nxGadz')) {
        const rc = el.getBoundingClientRect()
        if (Math.abs(Math.round(rc.left) - t.x) <= 2 && Math.abs(Math.round(rc.top) - t.y) <= 2) { el.click(); return true }
      }
      return false
    })()`)
    await sleep(1500)
    v = await verify()
  }
}
const quotedOK = v.quoted === p.lastKey
console.log('[引用] 校验 → 引用图=%s 最新图=%s  %s', v.quoted, p.lastKey, quotedOK ? '✅' : '⚠️')

if (dryRun) {
  console.log(JSON.stringify({ ok: true, dryRun: true, quotedOK, quotedKey: v.quoted, lastKey: p.lastKey }))
  process.exit(0)
}
if (!quotedOK) {
  console.log(JSON.stringify({ ok: false, reason: 'quote-mismatch', quoted: v.quoted, last: p.lastKey }))
  process.exit(3)
}

// ── ④ 输入提示词并发送 ─────────────────────────────────────────
if (prompt) {
  await b.session.evaluate(`(() => {
    const ed = document.querySelector('[contenteditable=true]')
    if (ed) ed.focus()
  })()`)
  await b.session.send('Input.insertText', { text: prompt })
  await sleep(700)
  for (const type of ['keyDown', 'keyUp']) {
    await b.session.send('Input.dispatchKeyEvent', {
      type, key: 'Enter', code: 'Enter',
      windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
    })
  }
  console.log('[发送] 提示词已发出')
}

// ── ⑤ 等新图并下载 ─────────────────────────────────────────────
const before = new Set((await b.collectImageUrls()).map(imgKey))
const deadline = Date.now() + 300000
let files = [], urls = []
while (Date.now() < deadline) {
  await sleep(1200)
  const cur = await b.collectImageUrls().catch(() => [])
  const fresh = cur.filter(u => !before.has(imgKey(u)))
  if (fresh.length) {
    // 只要 cgen_（生成图原图），排除 cthumb（缩略图）
    const cgen = fresh.filter(u => u.includes('cgen_'))
    urls = pickBestImageUrls(cgen.length ? cgen : fresh)
    if (urls.length && cgen.length) break
  }
}
// 只要 cgen_（原图）；并逐个校验分辨率 >=1024，避免拿到缩略图（384）
const sizeOf = (buf) => {
  if (buf.slice(0, 8).toString('hex') === '89504e470d0a1a0a') {
    return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }
  }
  if (buf[0] === 0xff && buf[1] === 0xd8) {
    let i = 2
    while (i < buf.length - 9) {
      if (buf[i] !== 0xff) { i++; continue }
      const m = buf[i + 1]
      if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
        return { w: buf.readUInt16BE(i + 7), h: buf.readUInt16BE(i + 5) }
      }
      i += 2 + buf.readUInt16BE(i + 2)
    }
  }
  return { w: 0, h: 0 }
}
for (let i = 0; i < urls.length && i < 3; i++) {
  const dst = path.join(outDir, `quote-${Date.now()}-${i + 1}.png`)
  try {
    const res = await fetch(urls[i], { headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://www.doubao.com/' } })
    if (!res.ok) continue
    const buf = Buffer.from(await res.arrayBuffer())
    const sz = sizeOf(buf)
    if (Math.min(sz.w, sz.h) < 1024) {
      console.log('[下载] 跳过缩略图 %dx%d', sz.w, sz.h)
      continue
    }
    fs.writeFileSync(dst, buf)
    files.push(dst)
  } catch (e) { /* ignore */ }
}
console.log(JSON.stringify({ ok: files.length > 0, files, urls, quotedKey: v.quoted, lastKey: p.lastKey }))
process.exit(files.length ? 0 : 4)
