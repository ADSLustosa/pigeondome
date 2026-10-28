// Captura o painel com o Edge ou o Chrome sem interface, pelo protocolo DevTools (CDP).
// Emula o dispositivo de verdade (largura, escala e tema), sem depender de tamanho minimo de janela.
// Uso (pelo capture-screenshots.ps1): node capture-screenshots.mjs <navegador> <url> <pasta> [esperaMs]
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const [browser, url, outDir, waitArg] = process.argv.slice(2)
if (!browser || !url || !outDir) {
  console.error('uso: node capture-screenshots.mjs <navegador> <url> <pasta> [esperaMs]')
  process.exit(2)
}
const waitMs = Number(waitArg ?? 8000)
const port = 9300 + Math.floor(Math.random() * 500)
const profile = mkdtempSync(join(tmpdir(), 'pigeondome-shot-'))
mkdirSync(outDir, { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const proc = spawn(
  browser,
  [
    '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank',
  ],
  { stdio: 'ignore' },
)

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
      const page = list.find((t) => t.type === 'page')
      if (page) return new WebSocket(page.webSocketDebuggerUrl)
    } catch {
      /* o navegador ainda esta subindo */
    }
    await sleep(250)
  }
  throw new Error('nao consegui falar com o navegador')
}

// Cada captura: nome, largura, escala, escuro, recorte.
// 'principal' termina logo antes da secao "Trilha do controlador" (se nao a achar, usa a pagina inteira);
// 'completa' vai ate o fim da pagina.
const shots = [
  ['painel-claro.png', 1280, 1, false, 'principal'],
  ['painel-escuro.png', 1280, 1, true, 'principal'],
  ['painel-completo-claro.png', 1280, 1, false, 'completa'],
  ['painel-completo-escuro.png', 1280, 1, true, 'completa'],
  ['painel-movel-claro.png', 390, 2, false, 'principal'],
  ['painel-movel-escuro.png', 390, 2, true, 'principal'],
]
const MAX_HEIGHT = 8000
const CUT_MARGIN = 20 // folga, em px CSS, acima do titulo da proxima secao

let failed = false
try {
  const ws = await connect()
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  let seq = 0
  const pending = new Map()
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result)
    }
  })
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++seq
      pending.set(id, { resolve, reject })
      ws.send(JSON.stringify({ id, method, params }))
    })

  await send('Page.enable')
  for (const [name, width, scale, dark, crop] of shots) {
    const metrics = (height) => ({ width, height, deviceScaleFactor: scale, mobile: false })
    await send('Emulation.setDeviceMetricsOverride', metrics(900))
    await send('Emulation.setEmulatedMedia', {
      features: [{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }],
    })
    await send('Page.navigate', { url })
    await sleep(waitMs)
    const { cssContentSize } = await send('Page.getLayoutMetrics')
    let height = Math.ceil(cssContentSize.height)
    if (crop === 'principal') {
      const { result } = await send('Runtime.evaluate', {
        returnByValue: true,
        expression: `(() => {
          const h = [...document.querySelectorAll('h1,h2,h3')]
            .find((e) => e.textContent.trim().startsWith('Trilha do controlador'))
          return h ? Math.floor(h.getBoundingClientRect().top + window.scrollY) : null
        })()`,
      })
      if (typeof result.value === 'number') height = result.value - CUT_MARGIN
    }
    height = Math.min(height, MAX_HEIGHT)
    await send('Emulation.setDeviceMetricsOverride', metrics(height))
    await sleep(1500)
    const { data } = await send('Page.captureScreenshot', {
      format: 'png',
      clip: { x: 0, y: 0, width, height, scale: 1 },
    })
    const file = join(outDir, name)
    writeFileSync(file, Buffer.from(data, 'base64'))
    const kb = statSync(file).size / 1024
    console.log(`${name}  ${Math.round(kb)} KB  (${width}x${height} css px)`)
    if (kb < 20) {
      console.error(`falha ao capturar ${name}: imagem pequena demais`)
      failed = true
    }
  }
  ws.close()
} catch (e) {
  console.error(String(e))
  failed = true
} finally {
  proc.kill()
  await sleep(500)
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 })
}
process.exit(failed ? 1 : 0)
