// doubao_run.mjs —— 替代 paint.mjs 的调用层
//   1) 先确保页面在"对话"模式（不在"图像生成"面板，否则没有上传入口）
//   2) 上传参考图（DOM.getDocument depth:1 + setFileInputFiles，实测可用）
//   3) 提交提示词、等出图、下载到 outDir
//
// 用法: node doubao_run.mjs <请求.json>
//   { prompt, refImages:[], outDir, newChat:true|false, timeoutMs }
import fs from 'node:fs'
import path from 'node:path'
import { DoubaoBridge } from './tools/lib/bridge.mjs'

const EXE = 'E:\\豆包\\Doubao\\app\\Doubao.exe'
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
const reqFile = process.argv[2]
const req = JSON.parse(fs.readFileSync(reqFile, 'utf8').replace(/^\uFEFF/, ''))

const b = new DoubaoBridge({ exe: EXE, cdpPort: 9225 })
await b.connect({ launchTimeoutMs: 60000 })

const clickByText = async (text) => {
  const rect = await b.session.evaluate(`(() => {
    const all = [...document.querySelectorAll('div,a,button,span')]
    const hit = all.filter(el => {
      const r = el.getBoundingClientRect()
      if (!(r.width > 4 && r.height > 4)) return false
      return (el.textContent || '').trim() === ${JSON.stringify(text)}
    })
    if (!hit.length) return null
    const el = hit[hit.length - 1]
    const r = el.getBoundingClientRect()
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
  })()`)
  if (!rect) return false
  for (const type of ['mousePressed', 'mouseReleased']) {
    await b.session.send('Input.dispatchMouseEvent', { type, x: rect.x, y: rect.y, button: 'left', clickCount: 1 })
  }
  return true
}

const placeholderOf = async () => await b.session.evaluate(`(() => {
  const ed = document.querySelector('[contenteditable=true]')
  return ed ? (ed.getAttribute('data-placeholder') || ed.innerText || '') : ''
})()`)

// ── ① 确保"对话"模式 + 新对话 ──
let ph = String((await placeholderOf()) || '')
if (ph.includes('图片') || ph.includes('描述')) {
  console.log('[页面] 在图像生成面板 → 切回对话')
  await clickByText('对话')
  await sleep(2000)
}
// 判断"是不是新对话"：只看对话 id 有没有变
const currentId = async () => {
  const href = String((await b.session.evaluate('location.href')) || '')
  const m = href.match(/\/chat\/(\d+)/)
  return m ? m[1] : ''
}

if (req.newChat !== false) {
  const beforeId = await currentId()
  let okFresh = false
  for (let attempt = 1; attempt <= 3 && !okFresh; attempt++) {
    const ok = await clickByText('新对话')
    await sleep(2600)
    const nowId = await currentId()
    // 空白对话没有 id，此时看"主区里有没有大图"（元素 left>300，侧边栏缩略图不算）
    const mainImgs = await b.session.evaluate(`(() => {
      return [...document.querySelectorAll('img')].filter(i => {
        if (i.naturalWidth < 1024) return false
        const r = i.getBoundingClientRect()
        return r.left > 300
      }).length
    })()`)
    okFresh = (nowId !== beforeId) || (beforeId === '' && mainImgs === 0)
    console.log(`[页面] 新对话(第${attempt}次): ${beforeId || 'none'} → ${nowId || 'none'}  主区大图=${mainImgs}  换了=${okFresh}`)
    if (!okFresh) await sleep(1000)
  }
  if (!okFresh) console.log('[页面] ⚠ 对话 id 没变，可能仍在旧对话里')
  else console.log('[页面] 已确认：这是新对话')
}

ph = String((await placeholderOf()) || '')
console.log('[页面] 输入框:', JSON.stringify(ph).slice(0, 60))

// ── ② 上传参考图 ──
// ── 清空输入框里的旧附件（关键：附件会累积，导致第二轮把第一轮的图一起发出去）──
const clearAttachments = async () => {
  const before = await b.session.evaluate(`(() => {
    const ed = document.querySelector('[contenteditable=true]')
    if (!ed) return 0
    let box = ed
    for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
    return [...box.querySelectorAll('img')].filter(i => {
      const r = i.getBoundingClientRect()
      return r.width >= 32 && r.height >= 32
    }).length
  })()`)

  // 优先点每个附件右上角的"删除/移除"按钮
  for (let round = 0; round < 6; round++) {
    const n = await b.session.evaluate(`(() => {
      const ed = document.querySelector('[contenteditable=true]')
      if (!ed) return 0
      let box = ed
      for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
      const imgs = [...box.querySelectorAll('img')].filter(i => {
        const r = i.getBoundingClientRect()
        return r.width >= 32 && r.height >= 32
      })
      if (!imgs.length) return 0
      // 找附件容器上的删除按钮
      for (const img of imgs) {
        let host = img
        for (let k = 0; k < 5 && host.parentElement; k++) host = host.parentElement
        const btns = [...host.querySelectorAll('button,[role=button],svg')]
        const del = btns.find(e => {
          const a = (e.getAttribute && (e.getAttribute('aria-label') || e.getAttribute('title'))) || ''
          return /删除|移除|remove|delete|close|clear/i.test(a)
        })
        if (del) { del.click(); return imgs.length }
      }
      // 兜底：点最后一个 attachment 的 × （常见结构是 hover 出现的 button）
      const last = imgs[imgs.length - 1]
      let host = last
      for (let k = 0; k < 4 && host.parentElement; k++) host = host.parentElement
      const btn = host.querySelector('button')
      if (btn) { btn.click(); return imgs.length }
      return -1
    })()`)
    if (n === 0) break
    await sleep(600)
  }

  const after = await b.session.evaluate(`(() => {
    const ed = document.querySelector('[contenteditable=true]')
    if (!ed) return 0
    let box = ed
    for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
    return [...box.querySelectorAll('img')].filter(i => {
      const r = i.getBoundingClientRect()
      return r.width >= 32 && r.height >= 32
    }).length
  })()`)
  console.log(`[附件] 清理前 ${before} 个 → 清理后 ${after} 个`)
  return after
}

b.attachImages = async function (filePaths) {
  if (!filePaths?.length) return false
  for (const p of filePaths) if (!fs.existsSync(p)) throw new Error('参考图不存在: ' + p)
  let ids = []
  for (let i = 0; i < 20; i++) {
    const doc = await this.session.send('DOM.getDocument', { depth: 1 }).catch(() => null)
    const rootId = doc?.root?.nodeId || doc?.result?.root?.nodeId
    if (rootId) {
      const q = await this.session.send('DOM.querySelectorAll', {
        nodeId: rootId, selector: 'input[type="file"]',
      }).catch(() => null)
      ids = q?.nodeIds || q?.result?.nodeIds || []
      if (ids.length) break
    }
    await sleep(500)
  }
  if (!ids.length) throw new Error('没有 file input（等了 10 秒）')
  // ★ 先清空旧附件，避免"上一轮的图 + 这一轮的图"一起发出去
  await clearAttachments()
  // 优先用 data-testid=upload-file-input 那个（真正给对话用的）
  let target = ids[0]
  for (const id of ids) {
    const d = await this.session.send('DOM.describeNode', { nodeId: id }).catch(() => null)
    const at = JSON.stringify(d?.node?.attributes || d?.result?.node?.attributes || [])
    if (at.includes('upload-file-input')) { target = id; break }
  }
  await this.session.send('DOM.setFileInputFiles', { nodeId: target, files: filePaths })
  await sleep(4000)

  // 上传后核对：必须只有 1 个附件
  const cnt = await this.session.evaluate(`(() => {
    const ed = document.querySelector('[contenteditable=true]')
    if (!ed) return -1
    let box = ed
    for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
    return [...box.querySelectorAll('img')].filter(i => {
      const r = i.getBoundingClientRect()
      return r.width >= 32 && r.height >= 32
    }).length
  })()`)
  console.log('[上传] 已投喂 ' + filePaths.length + ' 张（input 节点 ' + target + '）  当前附件数=' + cnt)

  // ★ 关键：读回附件的原始像素尺寸，证明"发出去的到底是哪张图"
  {
    const dims = await this.session.evaluate(`(() => {
      const ed = document.querySelector('[contenteditable=true]')
      if (!ed) return ''
      let box = ed
      for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
      const imgs = [...box.querySelectorAll('img')].filter(i => {
        const r = i.getBoundingClientRect()
        return r.width >= 32 && r.height >= 32
      })
      return imgs.map(i => i.naturalWidth + 'x' + i.naturalHeight).join(',')
    })()`)
    console.log('ATTACH_SIZE=' + (dims || 'none'))
    console.log('[上传] 附件实际尺寸: ' + (dims || '读不到'))
  }
  if (cnt > 1) {
    console.log('[上传] ⚠ 附件多于 1 个，先清理再重传')
    await clearAttachments()
    await this.session.send('DOM.setFileInputFiles', { nodeId: target, files: filePaths })
    await sleep(3000)
    const c2 = await this.session.evaluate(`(() => {
      const ed = document.querySelector('[contenteditable=true]')
      if (!ed) return -1
      let box = ed
      for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement
      return [...box.querySelectorAll('img')].filter(i => {
        const r = i.getBoundingClientRect()
        return r.width >= 32 && r.height >= 32
      }).length
    })()`)
    console.log('[上传] 重传后附件数=' + c2)
  }
  return true
}

// ── ③ 生成 ──
const outDir = req.outDir || path.join(process.cwd(), 'doubao-images')
fs.mkdirSync(outDir, { recursive: true })
const res = await b.generate({
  prompt: req.prompt,
  outDir,
  refImages: req.refImages || [],
  newChat: false,
  archiveToProject: false,
  timeoutMs: req.timeoutMs || 600000,
})

const convTitle = String((await b.session.evaluate('document.title')) || '')
const convUrl = String((await b.session.evaluate('location.href')) || '')
console.log('CONV_TITLE=' + convTitle)
console.log('CONV_URL=' + convUrl)
console.log('RESULT_JSON=' + JSON.stringify({ ok: true, files: res.files, urls: res.urls,
  convTitle, convUrl }))
process.exit(0)
