// as marcações com @ nos comentários da revisão: o @ abre um seletor (Banco, Motions, Presets, Transições, Trilhas,
// Sons) e o escolhido entra no texto como o código (@BAN-074), que o Claude resolve com codigo.py; no card do
// comentário, o código vira um chip com o nome
import { $, $$, ICONE, esc, janela, json } from './comum.js'

const ABAS = [
  ['midia', 'Banco'], ['motion', 'Motions'], ['preset', 'Presets'], ['transicao', 'Transições'], ['trilha', 'Trilhas'], ['som', 'Sons'],
]
const MENCAO = /@((?:PRE|MOT|TRA|TRI|BAN|SOM)-\d+(?:\.\d+)?)/g

let itens = null // [{codigo, tipo, id, nome, mini?, clipe?, audio?}]
let porCodigo = new Map()
let aba = 'midia'

/** Carrega a lista uma vez (os chips dos comentários usam o nome). */
export async function carregarMarcaveis() {
  if (itens) return itens
  itens = (await json('/api/marcaveis', { itens: [] })).itens || []
  porCodigo = new Map(itens.map((x) => [x.codigo, x]))
  return itens
}

/** O texto de um comentário, escapado, com cada @CÓDIGO como chip (código e nome). */
export function htmlComMencoes(texto) {
  return esc(texto).replace(MENCAO, (m, c) => {
    const x = porCodigo.get(c)
    return `<span class="mencao" title="${esc(x ? `${c} · ${x.nome}` : c)}">@${esc(c)}${x ? `<span class="mencao-nome">${esc(x.nome)}</span>` : ''}</span>`
  })
}

/** O @ acabou de ser digitado no campo (no começo ou depois de um espaço): abre o seletor. */
export function seDigitouArroba(campo, e) {
  if (e.data !== '@') return
  const p = campo.selectionStart
  const antes = campo.value[p - 2]
  if (p >= 2 && antes && !/\s/.test(antes)) return // e-mail ou palavra@: não é marcação
  abrirSeletor(campo, p - 1)
}

async function abrirSeletor(campo, posArroba) {
  await carregarMarcaveis()
  let busca = ''
  let escolhido = false
  const { el, fechar } = janela(`<div class="seletor-mencao">
      <header class="janela-cabeca"><nav class="mencao-abas">${ABAS.map(([k, n]) => `<button class="pilula pequena" data-aba-mencao="${k}">${n} <span class="conta">${itens.filter((x) => x.tipo === k).length}</span></button>`).join('')}</nav>
        <button class="botao-icone" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button></header>
      <input class="mencao-busca" placeholder="Buscar pelo nome ou pelo código" autocomplete="off">
      <div class="mencao-grade"></div></div>`, {
    classe: 'janela-mencao',
    aoFechar: () => {
      campo.focus()
      if (!escolhido) campo.setSelectionRange(posArroba + 1, posArroba + 1)
    },
  })
  const lista = () => {
    const b = busca.trim().toLowerCase()
    return itens.filter((x) => x.tipo === aba && (!b || x.nome.toLowerCase().includes(b) || x.codigo.toLowerCase().includes(b)))
  }
  const desenhar = () => {
    for (const t of $$('[data-aba-mencao]', el)) t.classList.toggle('ativa', t.dataset.abaMencao === aba)
    const l = lista()
    $('.mencao-grade', el).innerHTML = l.length ? l.map((x) => `<button class="mencao-card" data-mencao="${esc(x.codigo)}">
        <span class="mencao-mini">${x.mini ? `<img src="${esc(x.mini)}" alt="" loading="lazy">` : x.clipe ? `<video muted loop playsinline preload="none" data-src="${esc(x.clipe)}"></video>` : `<span class="mencao-icone">${x.audio ? ICONE.tocar : ICONE.motion || ''}</span>`}</span>
        <span class="mencao-rotulo"><b>${esc(x.codigo)}</b><span>${esc(x.nome)}</span></span>${x.audio ? `<audio preload="none" src="${esc(x.audio)}"></audio>` : ''}</button>`).join('')
      : '<p class="vazio">Nada com essa busca.</p>'
    for (const card of $$('.mencao-card', el)) {
      const v = $('video', card)
      const a = $('audio', card)
      card.addEventListener('mouseenter', () => {
        if (v) {
          if (!v.src) v.src = v.dataset.src
          v.play().catch(() => {})
        }
        if (a) a.play().catch(() => {})
      })
      card.addEventListener('mouseleave', () => {
        v?.pause()
        if (a) {
          a.pause()
          a.currentTime = 0
        }
      })
    }
  }
  const escolher = (codigo) => {
    escolhido = true
    // o @ digitado vira @CÓDIGO e um espaço; o cursor fica depois
    const v = campo.value
    const novo = `@${codigo} `
    campo.value = v.slice(0, posArroba) + novo + v.slice(posArroba + 1)
    fechar()
    const p = posArroba + novo.length
    campo.setSelectionRange(p, p)
    campo.dispatchEvent(new Event('input', { bubbles: true }))
  }
  el.addEventListener('click', (e) => {
    const t = e.target.closest('[data-aba-mencao]')
    if (t) {
      aba = t.dataset.abaMencao
      return desenhar()
    }
    const c = e.target.closest('[data-mencao]')
    if (c) escolher(c.dataset.mencao)
  })
  const entrada = $('.mencao-busca', el)
  entrada.addEventListener('input', () => {
    busca = entrada.value
    desenhar()
  })
  entrada.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      const primeiro = lista()[0]
      if (primeiro) escolher(primeiro.codigo)
    }
  })
  desenhar()
  entrada.focus()
}
