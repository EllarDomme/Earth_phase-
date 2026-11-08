// doubao_download.mjs —— 点「下载原图」把最新生成图存到指定目录（官方下载，非 CDN 抓取）
//   用法: node doubao_download.mjs --out <目录> [--wait 60000]
import fs from 'node:fs'
import path from 'node:path'
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const arg = (n, d = null) => {
  const i = process.argv.indexOf('--' + n)
  return i >= 0 ? process.argv[i + 1] : d
}
const outDir = arg('out', new URL('./v2/_dl_official', import.meta.url).pathname.replace(/^\//, ''))
const waitMs = Number(arg('wait', '60000'))
fs.mkdirSync(outDir, { recursive: true })

const b = new DoubaoBridge({ cdpPort: 9225 })
await b.connect()

// 让下载落到 outDir
for (const [method, params] of [
  ['Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: outDir, eventsEnabled: true }],
  ['Page.setDownloadBehavior', { behavior: 'allow', downloadPath: outDir }],
]) {
  try { await b.session.send(method, params) } catch (e) { /* 某些版本只支持其一 */ }
}

// 把目录里已有的文件挪到 _old/，保证"新出现的文件"一定能被识别
const oldDir = path.join(outDir, '_old')
fs.mkdirSync(oldDir, { recursive: true })
if (fs.existsSync(outDir)) {
  for (const f of fs.readdirSync(outDir)) {
    const p = path.join(outDir, f)
    if (!fs.statSync(p).isFile()) continue
    try { fs.renameSync(p, path.join(oldDir, f)) } catch (e) {}
  }
}
const before = new Set(fs.existsSync(outDir) ? fs.readdirSync(outDir) : [])

// 找最新生成图 + 图标组，点第 3 个（下载原图）
const probe = await b.session.evaluate(`(() => {
  const key = (u) => { const m = /rc_gen_image\\/([0-9a-f]+)/.exec(u || ''); return m ? m[1] : '' }
  const imgs = [...document.querySelectorAll('img')].filter(i => {
    const rc = i.getBoundingClientRect()
    return i.naturalWidth >= 700 && rc.left > 300
  }).map(i => {
    const rc = i.getBoundingClientRect()
    return { el: i, key: key(i.currentSrc || i.src), top: rc.top, bottom: rc.bottom,
             left: rc.left, right: rc.right }
  }).filter(o => o.key).sort((a, b2) => a.top - b2.top)
  if (!imgs.length) return { err: 'no image' }
  const last = imgs[imgs.length - 1]
  const icons = [...document.querySelectorAll('div.action-nxGadz')].map(el => {
    const rc = el.getBoundingClientRect()
    return { el, x: Math.round(rc.left), y: Math.round(rc.top) }
  }).filter(o => o.y > last.top - 20 && o.y < last.bottom + 60 &&
                 o.x > last.left - 40 && o.x < last.right + 40)
    .sort((a, b2) => a.x - b2.x)
  return { key: last.key, count: icons.length, icons: icons.map(o => ({ x: o.x, y: o.y })) }
})()`)
console.log('[下载原图] 最新图 key=%s  图标 %d 个', probe.key, (probe.icons || []).length)
if (!probe.icons || probe.icons.length < 3) {
  console.log(JSON.stringify({ ok: false, reason: 'icons<3', probe }))
  process.exit(2)
}

// 第 3 个 = 下载原图（索引 2）
const target = probe.icons[2]
const clickIcon = async (t) => await b.session.evaluate(`(() => {
  const t = ${JSON.stringify(target)}
  for (const el of document.querySelectorAll('div.action-nxGadz')) {
    const rc = el.getBoundingClientRect()
    if (Math.abs(Math.round(rc.left) - t.x) <= 3 && Math.abs(Math.round(rc.top) - t.y) <= 3) {
      el.click(); return true
    }
  }
  return false
})()`)
let clicked = await clickIcon(target)
console.log('[下载原图] 点击 %s → %s', JSON.stringify(target), clicked)

// 等文件出现并稳定
const deadline = Date.now() + waitMs
let picked = null
let tries = 0
while (Date.now() < deadline) {
  if (tries < 3 && Date.now() > deadline - waitMs + (tries + 1) * 8000 &&
      fs.readdirSync(outDir).filter(f => !before.has(f)).length === 0) {
    tries++
    await clickIcon(target)
    console.log('[下载原图] 第 %d 次重试点击', tries)
  }
  await sleep(350)
  const now = fs.readdirSync(outDir)
  const fresh = now.filter(f => !before.has(f) && !f.endsWith('.crdownload') && !f.endsWith('.tmp'))
  if (fresh.length) {
    const f = fresh[fresh.length - 1]
    const p = path.join(outDir, f)
    const s1 = fs.statSync(p).size
    await sleep(350)
    const s2 = fs.statSync(p).size
    if (s1 === s2 && s2 > 0) { picked = { file: p, size: s2 }; break }
  }
}
if (!picked) {
  console.log(JSON.stringify({ ok: false, reason: 'no-file', dir: outDir, files: fs.readdirSync(outDir) }))
  process.exit(3)
}
console.log(JSON.stringify({ ok: true, file: picked.file, size: picked.size, key: probe.key }))
process.exit(0)
