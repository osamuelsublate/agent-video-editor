// O app de revisão: roteamento pelo endereço e o início (os projetos). As páginas: #/ (projetos), #/p/<slug>[/vN] (a
// revisão de uma versão), #/calibragem[/<id>], #/referencias, #/heuristica, #/aprendizados[/<área>] e as da biblioteca
// (#/presets, #/transicoes[/<de>><para>], #/banco (os inserts), #/motions, #/trilhas).
import { $, $$, ICONE, abasAbertas, aviso, preferencia, chipCodigo, codigos, confirmar, copiar, enviar, esc, fecharAba, json, mmss } from './comum.js'
import { abrirRevisao } from './revisao.js'
import { abrirCtas } from './ctas.js'
import { abrirBiblioteca, PAGINAS_BIBLIOTECA } from './biblioteca.js'
import { abrirCalibragem, abrirRevisaoReferencia } from './calibragem.js'
import { abrirAprendizados, abrirHeuristica, abrirReferencias } from './referencias.js'
import { botaoCategorias, carregarCategorias, editarCategorias, pilulasCategoria, rotuloCategoria, seletorCategoria } from './categorias.js'

const ESTADOS = {
  em_revisao: ['Em revisão', 'selo-coral'],
  enviada: ['Revisão enviada', 'selo-amarelo'],
  aprovado: ['Aprovado', 'selo-menta'],
}


// a ordem dos projetos (lembrada neste navegador)
const ORDENS = { recentes: 'Recentes', antigos: 'Antigos', nome: 'A–Z' }
const lembrar = (k, v) => {
  try {
    if (v === undefined) return localStorage.getItem(k)
    localStorage.setItem(k, v)
  } catch {
    return null
  }
}

/** Dias de calendário entre a data e hoje (0 = hoje). */
const diasAtras = (ts) => {
  const d = new Date(ts * 1000), h = new Date()
  return Math.round((new Date(h.getFullYear(), h.getMonth(), h.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5)
}

/** "hoje às 14:32", "ontem às 9:10", "há 3 dias", "há 2 semanas", "há 4 meses". */
function quandoFoi(ts) {
  const n = diasAtras(ts)
  const hora = new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: 'numeric', minute: '2-digit' })
  if (n <= 0) return `hoje às ${hora}`
  if (n === 1) return `ontem às ${hora}`
  if (n < 7) return `há ${n} dias`
  if (n < 30) return n < 14 ? 'há 1 semana' : `há ${Math.floor(n / 7)} semanas`
  if (n < 365) return n < 60 ? 'há 1 mês' : `há ${Math.floor(n / 30)} meses`
  return n < 730 ? 'há 1 ano' : `há ${Math.floor(n / 365)} anos`
}

/** O grupo de um projeto na lista por data. */
function grupo(ts) {
  const n = diasAtras(ts)
  return n <= 0 ? 'Hoje' : n === 1 ? 'Ontem' : n < 7 ? 'Esta semana' : n < 30 ? 'Este mês' : 'Antes'
}

async function inicio(tela) {
  tela.className = 'pagina pagina-inicio'
  const [projetos, cods] = await Promise.all([json('/api/projetos', []), codigos()])
  // a categoria do projeto (edicao.formato: Reels, Ad…): filtra a lista e troca no card
  let cats = await carregarCategorias()
  let filtro = preferencia('projetos.categoria', '')
  if (filtro && !cats.some((c) => c.id === filtro)) filtro = ''
  let ordem = ORDENS[lembrar('projetos.ordem')] ? lembrar('projetos.ordem') : 'recentes'
  const card = (p) => {
    const [estado, cor] = ESTADOS[p.estado] || ESTADOS.em_revisao
    const proxy = `/projetos/${encodeURIComponent(p.slug)}/versoes/v${p.ultima}/proxy.mp4`
    const n = p.versoes.length
    return `<div class="caixa-projeto" data-slug="${esc(p.slug)}">
      <button class="apagar-projeto" data-apagar title="Apagar o projeto" aria-label="Apagar ${esc(p.nome)}">${ICONE.lixo}</button>
      <a class="card-projeto" href="#/p/${encodeURIComponent(p.slug)}">
      <div class="mini mini-916"><video muted playsinline preload="metadata" src="${proxy}#t=1.5"></video>
        <span class="selo ${cor}">${estado}</span>${p.duracao ? `<span class="duracao">${mmss(p.duracao)}</span>` : ''}
        <span class="chip-formato">${esc(rotuloCategoria(cats, p.formato || 'reels'))}</span></div>
      <div class="card-titulo"><h3>${esc(p.nome)}</h3>${chipCodigo(cods.projeto?.[p.slug], p.nome)}</div>
      <p class="sub" title="${esc(p.slug)}">${quandoFoi(p.atualizado)} · v${p.ultima}${n > 1 ? ` · ${n} versões` : ''}${p.comentarios ? ` · ${p.comentarios} ${p.comentarios === 1 ? 'comentário' : 'comentários'}` : ''}</p>
    </a>${seletorCategoria(cats, p.formato || 'reels')}</div>`
  }
  const lista = () => {
    const l = projetos.filter((p) => !filtro || (p.formato || 'reels') === filtro)
    if (ordem === 'nome') return [['', l.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))]]
    l.sort((a, b) => (ordem === 'antigos' ? a.atualizado - b.atualizado : b.atualizado - a.atualizado))
    const grupos = []
    for (const p of l) {
      const g = grupo(p.atualizado)
      if (grupos.at(-1)?.[0] !== g) grupos.push([g, []])
      grupos.at(-1)[1].push(p)
    }
    return grupos
  }
  const desenhar = () => {
    $('.filtro-categorias', tela).innerHTML = pilulasCategoria(cats, filtro, { contar: (id) => projetos.filter((p) => !id || (p.formato || 'reels') === id).length }) + botaoCategorias()
    $('.lista-projetos', tela).innerHTML = projetos.length
      ? lista().map(([g, ps]) => `${g ? `<h4 class="grupo-data">${g}</h4>` : ''}<div class="grade grade-projetos">${ps.map(card).join('')}</div>`).join('')
      : '<p class="vazio">Nenhum projeto com versão ainda. Mande um vídeo bruto ao Claude Code: quando ele entregar a v1, ela aparece aqui.</p>'
    for (const b of $$('[data-ordem]', tela)) b.classList.toggle('ativa', b.dataset.ordem === ordem)
    // o vídeo toca mudo com o mouse em cima
    for (const c of $$('.card-projeto', tela)) {
      const v = $('video', c)
      c.addEventListener('mouseenter', () => v.play().catch(() => {}))
      c.addEventListener('mouseleave', () => {
        v.pause()
        v.currentTime = 1.5
      })
    }
  }
  tela.innerHTML = `<div class="cabeca-secao"><span class="eyebrow">Projetos · ${String(projetos.length).padStart(2, '0')}</span>
      <div class="filtro-categorias"></div>
      <div class="ordens">${Object.entries(ORDENS).map(([k, nome]) => `<button class="pilula pequena" data-ordem="${k}">${nome}</button>`).join('')}</div></div>
    <div class="lista-projetos"></div>`
  desenhar()
  tela.addEventListener('change', async (e) => {
    if (!e.target.matches('[data-mudar-categoria]')) return
    const p = projetos.find((x) => x.slug === e.target.closest('.caixa-projeto').dataset.slug)
    try {
      await enviar('PUT', `/api/projetos/${encodeURIComponent(p.slug)}/categoria`, { categoria: e.target.value })
      p.formato = e.target.value
      desenhar()
    } catch (err) {
      aviso(err.message, 'erro')
    }
  })
  // apagar (como no 18): a pasta vai para a lixeira (projetos/_lixeira/), de onde dá para recuperar
  tela.addEventListener('click', async (e) => {
    const o = e.target.closest('[data-ordem]')
    if (o) {
      ordem = o.dataset.ordem
      lembrar('projetos.ordem', ordem)
      return desenhar()
    }
    const f = e.target.closest('[data-categoria]')
    if (f) {
      filtro = preferencia('projetos.categoria', '', f.dataset.categoria)
      return desenhar()
    }
    if (e.target.closest('[data-editar-categorias]'))
      return editarCategorias(cats, async () => {
        cats = await carregarCategorias()
        desenhar()
      })
    const b = e.target.closest('[data-apagar]')
    if (!b) return
    const caixa = b.closest('.caixa-projeto')
    const p = projetos.find((x) => x.slug === caixa.dataset.slug)
    const ok = await confirmar({
      titulo: `Apagar o projeto “${p.nome}”?`,
      texto: 'O projeto sai da lista e vai para a lixeira (projetos/_lixeira/), de onde dá para recuperar.',
      ok: 'Apagar',
      perigo: true,
    })
    if (!ok) return
    try {
      await enviar('DELETE', `/api/projetos/${encodeURIComponent(p.slug)}`)
      fecharAba(p.slug)
      projetos.splice(projetos.indexOf(p), 1)
      desenhar()
      $('.cabeca-secao .eyebrow', tela).textContent = `Projetos · ${String(projetos.length).padStart(2, '0')}`
      aviso(`“${p.nome}” foi para a lixeira`)
    } catch (err) {
      aviso(err.message, 'erro')
    }
  })
}

// os projetos abertos, como abas logo depois da marca (× fecha; fechar a aberta volta aos projetos)
function desenharAbas() {
  const el = $('#abas-projetos')
  const aberto = location.hash.match(/^#\/p\/([^/]+)/)?.[1]
  el.innerHTML = abasAbertas().map((a) => {
    const ativa = aberto && decodeURIComponent(aberto) === a.slug
    return `<div class="aba-projeto${ativa ? ' ativa' : ''}" data-slug="${esc(a.slug)}" title="${esc(a.nome)}">
      <a href="#/p/${encodeURIComponent(a.slug)}"><i></i><span>${esc(a.nome)}</span></a>
      <button type="button" data-fechar-aba title="Fechar a aba" aria-label="Fechar ${esc(a.nome)}">${ICONE.fechar}</button></div>`
  }).join('')
  $('.aba-projeto.ativa', el)?.scrollIntoView({ inline: 'nearest', block: 'nearest' })
}
window.addEventListener('abas-projetos', desenharAbas)
window.addEventListener('storage', desenharAbas)
document.addEventListener('click', (e) => {
  const b = e.target.closest?.('[data-fechar-aba]')
  if (!b) return
  const aba = b.closest('.aba-projeto')
  fecharAba(aba.dataset.slug)
  if (aba.classList.contains('ativa')) location.hash = '#/'
})

let sair = null
let vez = 0
async function rotear() {
  const minha = ++vez
  sair?.()
  sair = null
  let partes = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  if (partes[0] === 'biblioteca') partes = partes.slice(1).length ? partes.slice(1) : ['banco'] // endereços antigos
  const velha = $('#tela')
  const tela = velha.cloneNode(false) // uma tela nova a cada página: nenhum ouvinte da anterior fica para trás
  tela.className = ''
  velha.replaceWith(tela)
  $('#barra-versao').innerHTML = ''
  desenharAbas()
  // os projetos abrem pela marca; num projeto, acende a aba dele; o endereço antigo dos motions (#/banco/motions) acende Motions
  const aba = partes[0] === 'banco' && partes[1] === 'motions' ? 'motions' : partes[0]
  for (const a of $$('.abas a')) a.classList.toggle('ativa', a.dataset.aba === aba)
  document.body.classList.toggle('em-revisao', (partes[0] === 'p' || partes[0] === 'calibragem') && !!partes[1])
  let s
  // #/p/<slug>/vN/t12.3 (o chip "usado em" do Banco e dos Motions): a revisão abre naquele instante
  if (partes[0] === 'p' && partes[1] && /^v\d+$/.test(partes[2] || '') && /^t[\d.]+$/.test(partes[3] || '')) {
    preferencia(`posicao.${partes[1]}.${partes[2]}`, 0, +partes[3].slice(1))
    history.replaceState(null, '', `#/p/${encodeURIComponent(partes[1])}/${partes[2]}`)
  }
  if (partes[0] === 'p' && partes[1]) s = await abrirRevisao(tela, partes[1], partes[2] ? parseInt(partes[2].replace(/^v/, ''), 10) : null)
  else if (partes[0] === 'calibragem') s = await (partes[1] ? abrirRevisaoReferencia(tela, partes[1]) : abrirCalibragem(tela))
  else if (partes[0] === 'ctas') s = await abrirCtas(tela)
  else if (partes[0] === 'referencias') s = await abrirReferencias(tela)
  else if (partes[0] === 'heuristica') s = await abrirHeuristica(tela)
  else if (partes[0] === 'aprendizados') s = await abrirAprendizados(tela, partes[1])
  else if (PAGINAS_BIBLIOTECA.includes(partes[0])) s = await abrirBiblioteca(tela, partes[0], partes.slice(1))
  else s = await inicio(tela)
  if (minha !== vez) s?.() // já mudou de tela enquanto carregava
  else sair = s
}

// o botão copiar dos códigos (comum.chipCodigo), em qualquer página: na captura, antes do clique do card ou do link
// o chip inteiro copia, não só o botão
const botaoCopiar = (alvo) => alvo.closest?.('[data-copiar-codigo]') || alvo.closest?.('.codigo, [data-chip-copia]')?.querySelector('[data-copiar-codigo]')
document.addEventListener('click', (e) => {
  const b = botaoCopiar(e.target)
  if (!b) return
  e.preventDefault()
  e.stopPropagation()
  copiar(b.dataset.copiarCodigo).then(() => {
    aviso(`Copiado · ${b.dataset.copiarCodigo}`)
    b.classList.add('copiado')
    b.innerHTML = ICONE.check
    setTimeout(() => {
      b.classList.remove('copiado')
      b.innerHTML = ICONE.copiar
    }, 1400)
  })
}, true)
for (const ev of ['pointerdown', 'mousedown']) document.addEventListener(ev, (e) => botaoCopiar(e.target) && e.stopPropagation(), true)

window.addEventListener('hashchange', rotear)
rotear()
