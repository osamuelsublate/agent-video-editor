// as marcações com @ nos comentários da revisão: o @ abre um seletor (Banco, Motions, Presets, Transições, Trilhas,
// Sons) e o escolhido entra no texto como o código (@BAN-074), que o Claude resolve com codigo.py; no card do
// comentário, o código vira um chip com o nome
import { $, $$, ICONE, esc, janela, json, preferencia } from './comum.js'
import { barraDeTags, temTag } from './tags.js'

// [tipo, nome, o ícone (o da aba de cima com o mesmo destino)]
const ABAS = [
  ['midia', 'Banco', 'banco'], ['referencia', 'Referências', 'referencias'], ['motion', 'Motions', 'motions'], ['preset', 'Presets', 'presets'],
  ['transicao', 'Transições', 'transicoes'], ['trilha', 'Trilhas', 'trilhas'], ['som', 'Sons', null],
]
const ORDENS = { uso: 'Usados recentemente', novos: 'Mais novos', nome: 'Nome', codigo: 'Código' }
const MENCAO = /@((?:PRE|MOT|TRA|TRI|BAN|SOM)-\d+(?:\.\d+)?|REF-\d+·p\d+)/g
const iconeAba = (destino) => (destino && document.querySelector(`.navbar [data-aba="${destino}"] svg, [data-aba="${destino}"] svg`)?.outerHTML) || ICONE.tocar

let itens = null // [{codigo, tipo, id, nome, mini?, clipe?, audio?}]
let porCodigo = new Map()
let aba = 'midia'
const tagDa = {} // a tag escolhida em cada aba (no seletor)
// o Banco sem os trechos individuais (a mídia inteira basta para marcar)
const daAba = (k) => itens.filter((x) => x.tipo === k && !x.trecho)

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
  let escolhido = false
  let ordem = ORDENS[preferencia('mencao.ordem', 'uso')] ? preferencia('mencao.ordem', 'uso') : 'uso'
  const { el, fechar } = janela(`<div class="seletor-mencao">
      <header class="janela-cabeca"><nav class="mencao-abas">${ABAS.map(([k, n, ic]) => `<button class="pilula pequena" data-aba-mencao="${k}">${iconeAba(ic)}${n} <span class="conta">${daAba(k).length}</span></button>`).join('')}</nav>
        <label class="caixa mencao-ordem">Ordenar <select data-ordem-mencao>${Object.entries(ORDENS).map(([k, n]) => `<option value="${k}"${k === ordem ? ' selected' : ''}>${n}</option>`).join('')}</select></label>
        <button class="botao-icone" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button></header>
      <div class="mencao-corpo"><div class="mencao-tags"></div><div class="mencao-grade"></div></div></div>`, {
    classe: 'janela-mencao',
    aoFechar: () => {
      campo.focus()
      if (!escolhido) campo.setSelectionRange(posArroba + 1, posArroba + 1)
    },
  })
  const ordenar = (l) => {
    const cod = (x) => x.codigo.split(/(\d+)/).map((n) => (/^\d+$/.test(n) ? n.padStart(6, '0') : n)).join('')
    const por = {
      uso: (a, b) => (b.usado_em || '').localeCompare(a.usado_em || '') || (b.favorito ? 1 : 0) - (a.favorito ? 1 : 0) || (b.criado_em || '').localeCompare(a.criado_em || '') || cod(a).localeCompare(cod(b)),
      novos: (a, b) => (b.criado_em || '').localeCompare(a.criado_em || '') || cod(b).localeCompare(cod(a)),
      nome: (a, b) => a.nome.localeCompare(b.nome, 'pt-BR'),
      codigo: (a, b) => cod(a).localeCompare(cod(b)),
    }[ordem]
    return [...l].sort(por)
  }
  const lista = () => ordenar(daAba(aba).filter((x) => !tagDa[aba] || temTag(x.tags, tagDa[aba])))
  // a prévia: vídeo (o trecho, em laço), motion (a animação) ou áudio; uma de cada vez
  let tocando = null
  const parar = () => {
    if (!tocando) return
    tocando.parar()
    tocando = null
  }
  const tocar = (card) => {
    const x = porCodigo.get(card.dataset.mencao)
    if (tocando?.card === card) return parar()
    parar()
    const mini = $('.mencao-mini', card)
    let fim = () => {}
    if (x.clipe) {
      const v = document.createElement('video')
      v.muted = true
      v.playsInline = true
      v.src = x.clipe + (x.inicio != null ? `#t=${x.inicio},${x.fim}` : '')
      v.className = 'mencao-video'
      const laco = () => x.inicio != null && v.currentTime >= x.fim - 0.05 && (v.currentTime = x.inicio)
      v.addEventListener('timeupdate', laco)
      v.addEventListener('loadedmetadata', () => { if (x.inicio != null) v.currentTime = x.inicio; v.play().catch(() => {}) }, { once: true })
      if (x.inicio == null) v.loop = true
      mini.append(v)
      fim = () => v.remove()
    } else if (x.tipo === 'motion') {
      const f = document.createElement('iframe')
      f.src = `/render/motion.html?preset=${encodeURIComponent(x.id)}&formato=vertical&tocar=1`
      f.className = 'mencao-iframe'
      f.tabIndex = -1
      f.style.setProperty('--escala-mencao', String(mini.clientHeight / 1920)) // o palco em pé (1080×1920) cabe na altura do card
      f.style.left = `${(mini.clientWidth - 1080 * (mini.clientHeight / 1920)) / 2}px`
      mini.append(f)
      fim = () => f.remove()
    } else if (x.audio) {
      const a = new Audio(x.audio)
      a.play().catch(() => {})
      fim = () => a.pause()
    }
    card.classList.add('tocando')
    tocando = { card, parar: () => { fim(); card.classList.remove('tocando') } }
  }
  const desenhar = () => {
    parar()
    for (const t of $$('[data-aba-mencao]', el)) t.classList.toggle('ativa', t.dataset.abaMencao === aba)
    // as tags no canto (Banco, Motions, Referências): só filtram aqui; editar é na página de cada um
    const comTags = daAba(aba).some((x) => x.tags?.length)
    if (tagDa[aba] && !daAba(aba).some((x) => temTag(x.tags, tagDa[aba]))) tagDa[aba] = ''
    $('.mencao-tags', el).innerHTML = comTags ? barraDeTags(daAba(aba).map((x) => ({ chave: x.codigo, tags: x.tags })), tagDa[aba] || '', `mencao.${aba}`, { editar: false }) : ''
    el.querySelector('.mencao-corpo').classList.toggle('com-tags', comTags)
    const l = lista()
    const quando = (d) => (d ? new Date(d).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) : '')
    $('.mencao-grade', el).innerHTML = l.length ? l.map((x) => `<div class="mencao-card" data-mencao="${esc(x.codigo)}" title="Clique para tocar a prévia">
        <span class="mencao-mini${x.tipo === 'referencia' || x.tipo === 'motion' ? ' em-pe' : ''}">${x.mini ? `<img src="${esc(x.mini)}" alt="" loading="lazy">` : `<span class="mencao-icone">${x.audio ? ICONE.tocar : iconeAba(x.tipo === 'motion' ? 'motions' : x.tipo === 'preset' ? 'presets' : 'transicoes')}</span>`}
          ${x.clipe || x.audio || x.tipo === 'motion' ? `<span class="mencao-play">${ICONE.tocar}</span>` : ''}
          ${x.usado_em ? `<span class="mencao-uso" title="Usado por último em ${esc(quando(x.usado_em))}">usado ${esc(quando(x.usado_em))}</span>` : ''}</span>
        <span class="mencao-rotulo"><b>${esc(x.codigo)}</b><span>${esc(x.nome)}</span></span>
        <button class="botao pequeno mencao-usar" data-usar="${esc(x.codigo)}" title="Marcar no comentário">Usar</button></div>`).join('')
      : '<p class="vazio">Nada aqui ainda.</p>'
  }
  const escolher = (codigo) => {
    escolhido = true
    parar()
    // o @ digitado vira @CÓDIGO e um espaço; o cursor fica depois
    const v = campo.value
    const novo = `@${codigo} `
    campo.value = v.slice(0, posArroba) + novo + v.slice(posArroba + 1)
    fechar()
    const p = posArroba + novo.length
    campo.setSelectionRange(p, p)
    campo.dispatchEvent(new Event('input', { bubbles: true }))
  }
  el.addEventListener('change', (e) => {
    if (!e.target.matches('[data-ordem-mencao]')) return
    ordem = preferencia('mencao.ordem', 'uso', e.target.value)
    desenhar()
  })
  el.addEventListener('click', (e) => {
    const u = e.target.closest('[data-usar]')
    if (u) return escolher(u.dataset.usar)
    const ab = e.target.closest('[data-abrir-tag]')
    if (ab) {
      const chave = `mencao.${aba}.tags.abertas`
      const l = preferencia(chave, [])
      preferencia(chave, [], l.includes(ab.dataset.abrirTag) ? l.filter((x) => x !== ab.dataset.abrirTag) : [...l, ab.dataset.abrirTag])
      return desenhar()
    }
    const tg = e.target.closest('[data-tag]')
    if (tg) {
      tagDa[aba] = tg.dataset.tag
      return desenhar()
    }
    const t = e.target.closest('[data-aba-mencao]')
    if (t) {
      aba = t.dataset.abaMencao
      return desenhar()
    }
    const c = e.target.closest('.mencao-card')
    if (c) tocar(c)
  })
  el.addEventListener('dblclick', (e) => {
    const c = e.target.closest('.mencao-card')
    if (c && !e.target.closest('[data-usar]')) escolher(c.dataset.mencao) // duplo clique também usa
  })
  desenhar()
}
