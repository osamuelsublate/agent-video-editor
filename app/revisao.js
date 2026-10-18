// A revisão de uma versão: o player do proxy, a linha do tempo (planos, fala e comentários) e os
// comentários do criador, gravados sozinhos em projetos/<slug>/revisoes/vN.json (o Claude responde no mesmo arquivo).
import { $, $$, ICONE, ICONE_ATALHO, abrirAba, barraDaLinha, agora, aviso, chipCodigo, codigos, confirmar, copiar, dataHora, enviar, esc, fecharAba, janela, json, mmss, modalAberto, nomePlano, num, PLANOS, preferencia, tempo } from './comum.js'
import { carregarCategorias, categoriaCta } from './categorias.js'

const QUADRO = 1 / 24
const VELOCIDADES = [0.5, 1, 1.5, 2]
const r3 = (t) => Math.round(t * 1000) / 1000
const listaDe = (x, chave) => (Array.isArray(x) ? x : x?.[chave] || [])
const limpar = (s) => s.replace(/^[\s,.;:!?…]+|[\s,.;:!?]+$/g, '')
/** O status que o Claude escreve (revisao.py responder): rótulo e classe. */
const STATUS = {
  aplicado: ['Aplicado', 'aplicado'],
  respondido: ['Respondido', 'respondido'],
  nao_aplicado: ['Não aplicado', 'nao-aplicado'],
  'não aplicado': ['Não aplicado', 'nao-aplicado'],
}
const chaveStatus = (s) => (s === 'não aplicado' ? 'nao_aplicado' : s || 'pendente')
const quando = (c) => (c.geral ? 'Geral' : c.fim != null ? `${tempo(c.t)}–${tempo(c.fim)}` : tempo(c.t))
/** Ordem da lista: os gerais primeiro, depois pelo tempo. */
const ordem = (c) => (c.geral ? -1 : c.t)
/** Um comentário que conta: com texto ou com print anexado. */
const temConteudo = (c) => !!(c.texto?.trim() || c.anexos?.length)
const numero = (id) => parseInt(String(id).replace(/\D/g, ''), 10) || 0
const VIDEO = /\.(mp4|mov|webm)$/i
/** Uma caixa de texto que cresce com o que se escreve (até 40% da tela). */
const crescer = (el) => {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight + 2, Math.round(innerHeight * 0.4))}px`
}
/** O botão de clipe de uma caixa de comentário (`alvo`: nova ou editor). */
// a barra acima da linha do tempo (comum.js): os atalhos da revisão
const ATALHOS = () => [
  ['R', 'plano', ICONE_ATALHO.plano], ['C', 'geral', ICONE.balao], ['arrastar', 'trecho', ICONE_ATALHO.trecho],
  ['Espaço', 'tocar', ICONE.tocar], ['← →', 'quadro', ICONE.quadroDepois], ['⇧ ← →', 'corte', ICONE.segDepois], ['⌘ + −', 'zoom', ICONE_ATALHO.zoom],
]

const clipe = (alvo) =>
  `<label class="botao-icone pequeno botao-clipe" title="Anexar imagens ou vídeos (também dá para colar com ⌘V ou arrastar)"><input type="file" accept="image/*,video/*" multiple hidden data-anexar="${alvo}">${ICONE.clipe}</label>`
/** O estado da revisão de uma versão, no seletor de versões (GET /api/projetos/<slug>/versoes). */
const ESTADO_VERSAO = {
  sem: () => 'sem revisão',
  em_revisao: (n) => `em revisão (${n} ${n === 1 ? 'comentário' : 'comentários'})`,
  enviada: () => 'revisão enviada',
  aprovada: () => 'aprovada',
}

export async function abrirRevisao(tela, slug, vPedida) {
  const projetos = await json('/api/projetos', [])
  const proj = projetos.find((p) => p.slug === slug)
  if (!proj) {
    fecharAba(slug)
    tela.className = 'pagina'
    tela.innerHTML = `<p class="vazio">O projeto <b>${esc(slug)}</b> não existe ou ainda não tem versão. <a href="#/">Voltar aos projetos</a></p>`
    return null
  }
  const r = new Revisao(tela, proj, proj.versoes.includes(vPedida) ? vPedida : proj.ultima)
  await r.abrir()
  return () => r.fechar()
}

class Revisao {
  constructor(tela, proj, v) {
    Object.assign(this, { tela, proj, v, slug: proj.slug })
    const s = encodeURIComponent(proj.slug)
    this.base = `/projetos/${s}/versoes/v${v}/`
    this.urlRevisao = `/projetos/${s}/revisoes/v${v}.json`
    this.pxs = 1
    this.ajustar = true // a linha do tempo cabe inteira na largura
    this.entrada = null // a marca I (s)
    this.editor = null // editando um comentário: {t, fim, id?, texto?, anexos?}
    this.nova = { preso: false, geral: false, t: 0, fim: null, anexos: [], novoId: null } // a caixa de baixo: o comentário novo
    this.sel = null
    this.fila = Promise.resolve()
    this.sujo = false
    this.iPalavra = this.iPlano = -2
  }

  async abrir() {
    const [palavras, planos, info, rev, cods, edicao] = await Promise.all([
      json(this.base + 'palavras.json', []),
      json(this.base + 'planos.json', []),
      json(this.base + 'info.json', {}),
      json(this.urlRevisao, null),
      codigos(),
      json(this.base + 'edicao.json', {}),
    ])
    this.codigo = cods.projeto?.[this.slug]
    this.cods = cods
    // o que entrou em cada plano nesta versão: as mídias do banco, o preset do enriquecimento e o motion
    this.usado = {}
    for (const q of edicao.inserts?.pedidos || []) this.usado[q.plano] = { midias: (q.midias || []).map((m) => m.banco).filter(Boolean), preset: q.enriquecimento?.preset }
    for (const [pl, m] of Object.entries(edicao.motions || {})) (this.usado[pl] ||= {}).motion = m
    for (const [pl, t] of Object.entries(edicao.transicoes || {})) if (t?.id) (this.usado[pl] ||= {}).transicao = t.id
    this.receitas = {} // os JSONs dos presets e das transições já buscados (o nome), por 'preset:<id>' / 'transicao:<id>'
    this.midias = {} // os itens do banco já buscados (nome, fonte, vídeo)
    this.palavras = listaDe(palavras, 'palavras').slice().sort((a, b) => a.ini - b.ini)
    this.planos = listaDe(planos, 'planos')
    this.info = info || {}
    this.rev = rev || { projeto: this.slug, versao: this.v, aprovado: false, enviado_em: null, comentarios: [] }
    this.rev.comentarios ||= []
    if (this.rev.geral?.trim() || this.rev.anexos_geral?.length) {
      const g = this.rev.resposta_geral || {}
      const n = Math.max(0, ...this.rev.comentarios.map((c) => numero(c.id))) + 1
      this.rev.comentarios.push({ id: `c${n}`, geral: true, t: null, fim: null, palavra: null, fala: '', texto: (this.rev.geral || '').trim(),
        criado_em: agora(), de: 'rodrigo', status: g.status || 'pendente', resposta: g.resposta || null, ...(this.rev.anexos_geral?.length ? { anexos: this.rev.anexos_geral } : {}) })
      delete this.rev.geral
      delete this.rev.anexos_geral
      delete this.rev.resposta_geral
    }
    await this.carregarAnteriores()
    this.dur = this.info.duracao || this.palavras.at(-1)?.fim || 60
    this.prepararBlocos()
    this.montar()
    if (this.blocosNovos && this.v === this.proj.ultima) this.agendarSalvar() // os blocos nascem (ou vêm da versão anterior) no arquivo desta
    this.ligar()
    this.mostrarSalvo(rev ? 'salvo' : '')
    this.relogio = setInterval(() => this.verDisco(), 4000)
  }

  // ---------- os blocos (~30 s, nos vídeos de mais de 2 min): revisar, aprovar e mandar por trecho ----------
  // Cada bloco começa numa palavra (o id da transcrição): continua o mesmo trecho nas versões seguintes, mesmo que os
  // cortes antes dele mudem os tempos. O arquivo da revisão guarda {id, palavra, aprovado}; a versão nova herda os da
  // anterior (com as aprovações: um bloco aprovado fica travado para o Claude).

  prepararBlocos() {
    if (!this.rev.blocos?.length) {
      const herdado = Object.keys(this.anteriores).map(Number).sort((a, b) => b - a).map((x) => this.anteriores[x]).find((r) => r?.blocos?.length)
      const novos = herdado ? herdado.blocos.map((b) => ({ ...b })) : this.dur > 120 ? this.cortarBlocos() : null
      if (novos?.length) {
        this.rev.blocos = novos
        this.blocosNovos = true
      }
    }
    this.calcularBlocos()
  }

  /** Os blocos de uma versão sem blocos: a cada ~30 s, na troca de plano mais perto (até 12 s para cada lado); sem
   *  troca de plano por perto, na palavra mais perto dos 30 s. Nenhum bloco com menos de 15 s. */
  cortarBlocos() {
    const ws = this.palavras
    if (!ws.length) return null
    const inicios = []
    let ant = 0
    for (let alvo = 30; alvo < this.dur - 15; alvo += 30) {
      const perto = this.planos.map((q) => q.ini).filter((t) => t > ant + 15 && t < this.dur - 15 && Math.abs(t - alvo) <= 12)
      const t = perto.length ? perto.reduce((a, b) => (Math.abs(b - alvo) < Math.abs(a - alvo) ? b : a)) : alvo
      if (t <= ant + 15) continue
      inicios.push(t)
      ant = t
    }
    const palavras = [ws[0].id, ...inicios.map((t) => (ws.find((w) => w.ini >= t - 0.05) || ws.at(-1)).id)]
    return [...new Set(palavras)].map((palavra, k) => ({ id: `B${k + 1}`, palavra, aprovado: false }))
  }

  /** Onde cada bloco cai nesta versão: do começo da palavra dele até o começo do próximo. */
  calcularBlocos() {
    const defs = this.rev.blocos || []
    if (!defs.length) return (this.blocos = null)
    const inicio = (id) => (this.palavras.find((w) => w.id === id) || this.palavras.find((w) => w.id > id))?.ini
    const l = defs.map((def, k) => ({ id: def.id, def, ini: k === 0 ? 0 : inicio(def.palavra) ?? this.dur })).sort((a, b) => a.ini - b.ini)
    l.forEach((b, k) => (b.fim = l[k + 1]?.ini ?? this.dur))
    this.blocos = l.filter((b) => b.fim - b.ini > 0.05)
  }

  blocoEm(t) {
    return this.blocos?.find((b) => t >= b.ini && t < b.fim) || (t != null ? this.blocos?.at(-1) : null)
  }

  /** Os comentários (e réplicas) que caem num bloco. */
  doBloco(b) {
    return this.rev.comentarios.filter((c) => temConteudo(c) && !c.geral && this.blocoEm(c.t)?.id === b.id)
  }

  renderBlocos() {
    const el = $('#f-blocos')
    if (!el || !this.blocos) return
    const px = this.pxs
    // as divisas atravessam todas as faixas; o bloco escolhido fica marcado de cima a baixo
    const foco = this.blocos.find((b) => b.id === this.blocoSel)
    $('#divisas').innerHTML = this.blocos.slice(1).map((b) => `<i class="divisa" style="left:${(b.ini * px).toFixed(1)}px"></i>`).join('')
      + (foco ? `<i class="bloco-faixa-sel" style="left:${(foco.ini * px).toFixed(1)}px;width:${((foco.fim - foco.ini) * px).toFixed(1)}px"></i>` : '')
    el.innerHTML = this.blocos.map((b) => {
      const n = this.doBloco(b).length
      const cls = b.def.aprovado ? 'bloco-aprovado' : n ? 'bloco-com' : ''
      return `<button class="bloco-faixa ${cls}${this.loop?.id === b.id ? ' bloco-loop' : ''}${this.blocoSel === b.id ? ' bloco-escolhido' : ''}" data-bloco="${b.id}" data-ir="${b.ini}" style="left:${(b.ini * px).toFixed(1)}px;width:${((b.fim - b.ini) * px).toFixed(1)}px"
        title="${b.id} · ${tempo(b.ini)}–${tempo(b.fim)}${b.def.aprovado ? ' · finalizado (travado)' : n ? ` · ${n} comentário(s)` : ''}">${b.id}${b.def.aprovado ? ` ${ICONE.check}` : n ? ` <i>${n}</i>` : ''}</button>`
    }).join('')
  }

  htmlCabecaBloco(b, n) {
    const ok = b.def.aprovado
    return `<div class="bloco-cabeca${ok ? ' bloco-ok' : ''}" data-cab-bloco="${b.id}">
      <button class="bloco-nome" data-bloco="${b.id}" data-ir="${b.ini}" title="${b.id} · ${tempo(b.ini)}–${tempo(b.fim)} · ir ao começo">${b.id}</button>${n ? `<span class="conta">${n}</span>` : ''}
      <span class="bloco-acoes">
        <button class="botao-icone pequeno${this.loop?.id === b.id ? ' ativo' : ''}" data-loop-bloco="${b.id}" title="${this.loop?.id === b.id ? 'Parar o loop' : 'Tocar só este bloco, em loop'}">${ICONE_ATALHO.plano}</button>
        <button class="botao pequeno${ok ? ' feito' : ''}" data-aprovar-bloco="${b.id}" title="${ok ? 'Reabrir o bloco' : 'Marcar o bloco como finalizado: ele fica travado para o Claude'}">${ICONE.check} ${ok ? 'Finalizado' : 'Finalizar'}</button></span></div>`
  }

  /** Escolher um bloco (na faixa ou no cabeçalho): o painel mostra só ele e o seletor de cima, a versão dele; `null`
   *  volta a todos. */
  escolherBloco(id) {
    this.blocoSel = id
    this.menuVersoes = null
    this.renderLista()
    this.renderMarcas()
    this.renderVersoes()
    $('#lista').scrollTop = 0
    if (id) this.carregarVersoesBlocos().then(() => !this.fechado && this.blocoSel === id && this.renderVersoes())
  }

  /** As versões de cada bloco: o bloco só ganha versão nova quando o que há nele mudou de uma versão do vídeo para a
   *  outra (as palavras que ficaram, os planos com o tipo, o texto e a mídia, os motions e os presets). Lido uma vez,
   *  na primeira escolha de bloco. `this.versoesBloco[id]`: [{bv, vs: [versões do vídeo com esse conteúdo]}]. */
  async carregarVersoesBlocos() {
    if (this.versoesBloco) return
    const s = encodeURIComponent(this.slug)
    const vs = this.proj.versoes.filter((x) => x <= this.proj.ultima)
    const dados = await Promise.all(vs.map((x) => Promise.all(['palavras', 'planos', 'edicao'].map((f) => json(`/projetos/${s}/versoes/v${x}/${f}.json`, null)))))
    const assinatura = (def, prox, [pal, pla, ed]) => {
      const ws = listaDe(pal, 'palavras').slice().sort((a, b) => a.ini - b.ini)
      const ini = (ws.find((w) => w.id === def.palavra) || ws.find((w) => w.id > def.palavra))?.ini ?? 0
      const fim = prox ? (ws.find((w) => w.id === prox.palavra) || ws.find((w) => w.id > prox.palavra))?.ini ?? Infinity : Infinity
      const dentro = (a, b) => a < fim - 0.05 && b > ini + 0.05
      const midias = {}
      for (const q of ed?.inserts?.pedidos || []) midias[q.plano] = [(q.midias || []).map((m) => m.banco || m.id), q.enriquecimento?.preset]
      for (const [pl, m] of Object.entries(ed?.motions || {})) midias[pl] = [...(midias[pl] || []), m.preset || m.tipo, m.valores]
      return JSON.stringify([
        ws.filter((w) => dentro(w.ini, w.fim)).map((w) => w.id),
        listaDe(pla, 'planos').filter((q) => dentro(q.ini, q.fim)).map((q) => [q.tipo, q.texto, Math.round((q.ini - ini) * 4), Math.round((q.fim - ini) * 4), midias[q.id]]),
      ])
    }
    this.versoesBloco = {}
    const defs = this.rev.blocos || []
    defs.forEach((def, k) => {
      const l = []
      vs.forEach((x, i) => {
        if (!dados[i][0]) return
        const a = assinatura(def, defs[k + 1], dados[i])
        if (l.at(-1)?.a === a) l.at(-1).vs.push(x)
        else l.push({ bv: l.length + 1, a, vs: [x] })
      })
      this.versoesBloco[def.id] = l
    })
  }

  aprovarBloco(id) {
    const b = this.blocos.find((x) => x.id === id)
    b.def.aprovado = !b.def.aprovado
    aviso(b.def.aprovado ? `${id} finalizado: o Claude não mexe mais nele` : `${id} reaberto`)
    this.renderLista()
    this.renderMarcas()
    this.agendarSalvar()
  }

  alternarLoop(id) {
    const b = this.blocos.find((x) => x.id === id)
    this.loop = this.loop?.id === id ? null : b
    if (this.loop) {
      this.buscar(b.ini)
      this.video.play().catch(() => {})
    }
    this.renderLista()
    this.renderMarcas()
  }

  // ---------- as versões anteriores: o que já foi pedido e respondido em cada bloco (só para ler) ----------

  /** As revisões das versões antes desta (o histórico de cada bloco e os blocos que esta herda). */
  async carregarAnteriores() {
    this.anteriores = {}
    const s = encodeURIComponent(this.slug)
    const vs = this.proj.versoes.filter((x) => x < this.v)
    const revs = await Promise.all(vs.map((x) => json(`/projetos/${s}/revisoes/v${x}.json`, null)))
    vs.forEach((x, k) => revs[k] && (this.anteriores[x] = revs[k]))
  }

  /** Onde um comentário de outra versão cai nesta: pela palavra em que ele foi feito (os ids da transcrição não mudam
   *  entre as versões); se ela foi cortada, a próxima que ficou. */
  ondeAgora(c) {
    if (c.geral) return { t: null, fim: null }
    let w = c.palavra ? this.palavras.find((x) => x.id === c.palavra) : null
    if (!w && c.palavra) w = this.palavras.find((x) => x.id > c.palavra) || this.palavras.at(-1)
    const t = w ? w.ini : Math.min(c.t || 0, this.dur)
    return { t, fim: c.fim != null ? Math.min(t + (c.fim - c.t), this.dur) : null }
  }

  /** As versões anteriores de um bloco: em cada uma, os comentários que caíram nele e a resposta do Claude. */
  htmlHistoricoBloco(b) {
    const vs = Object.keys(this.anteriores).map(Number).sort((a, b) => b - a)
    const grupos = vs.map((x) => [x, (this.anteriores[x].comentarios || []).filter((c) => temConteudo(c) && !c.geral && this.blocoEm(this.ondeAgora(c).t)?.id === b.id)])
      .filter(([, cs]) => cs.length)
    if (!grupos.length) return ''
    return `<div class="historico-bloco"><span class="eyebrow">Versões anteriores deste bloco</span>${grupos.map(([x, cs]) => `<details class="versao-bloco"${x === grupos[0][0] ? ' open' : ''}>
        <summary><b>v${x}</b> · ${cs.length} ${cs.length === 1 ? 'comentário' : 'comentários'}</summary>
        ${cs.sort((a, b) => a.t - b.t).map((c) => `<div class="item-velho"><p class="texto">${esc(c.texto || '(só o print)')}</p>${this.htmlResposta(c)}</div>`).join('')}</details>`).join('')}</div>`
  }

  // ---------- o provador de look (LUT, intensidade e vinheta do ator; servidor.py, render.py amostra-look) ----------

  /** O provador de look num modal: as opções à esquerda, as duas amostras (o atual e o testado) grandes ao lado. */
  async abrirLook() {
    this.video.pause()
    const d = await json(`/api/projetos/${encodeURIComponent(this.slug)}/look`, null)
    if (!d) return aviso('Não consegui ler o look do projeto', 'erro')
    const { el, fechar } = janela('<div class="look-modal"></div>', { classe: 'janela-look', aoFechar: () => clearInterval(this.relogioRender) })
    this.lk = { el, fechar, atual: d.look, teste: { ...d.look }, luts: d.luts, vinhetas: d.vinhetas, nitidezes: d.nitidezes || ['sem'], renderizando: d.renderizando, t: this.video.currentTime }
    el.addEventListener('click', (e) => {
      const b = e.target.closest('[data-look]')
      if (!b) return
      const [campo, valor] = b.dataset.look.split(':')
      if (campo === 'aplicar') return this.aplicarLook()
      this.lk.teste[campo] = valor === '-' ? null : valor
      this.renderLook()
      this.provarLook(this.lk.t)
    })
    el.addEventListener('change', (e) => {
      if (!e.target.matches('[data-look-intensidade]')) return
      this.lk.teste.intensidade = +e.target.value / 100
      this.renderLook()
      this.provarLook(this.lk.t)
    })
    this.renderLook()
    this.provarLook(this.lk.t)
    if (d.renderizando) this.esperarRender()
  }

  renderLook() {
    const lk = this.lk
    const igual = JSON.stringify(lk.teste) === JSON.stringify(lk.atual)
    const pilula = (campo, valor, nome) => `<button class="pilula pequena${(lk.teste[campo] ?? '-') === valor ? ' ativa' : ''}" data-look="${campo}:${valor}">${esc(nome)}</button>`
    const nomeV = { sem: 'Sem', leve: 'Leve', normal: 'Normal', forte: 'Forte', mais: 'Mais' }
    lk.teste.nitidez ??= 'sem'
    lk.atual.nitidez ??= 'sem'
    if (!lk.el?.isConnected) return
    $('.look-modal', lk.el).innerHTML = `<header class="janela-cabeca"><h2>Look do ator</h2><span class="dica">em ${tempo(lk.t)} · 3 s do bruto, sem inserts nem legenda</span>
        <button class="botao-icone" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button></header>
      <div class="look-corpo"><div class="look-opcoes">
      <div class="look-linha"><span class="dica">LUT</span>${pilula('lut', '-', 'Sem')}${Object.entries(lk.luts).map(([id, nome]) => pilula('lut', id, nome)).join('')}</div>
      <label class="look-linha"><span class="dica">Intensidade</span><input type="range" min="0" max="100" step="5" value="${Math.round((lk.teste.intensidade ?? 1) * 100)}" data-look-intensidade ${lk.teste.lut ? '' : 'disabled'}><b>${Math.round((lk.teste.intensidade ?? 1) * 100)}%</b></label>
      <div class="look-linha"><span class="dica">Vinheta</span>${lk.vinhetas.map((v) => pilula('vinheta', v, nomeV[v] || v)).join('')}</div>
      <div class="look-linha"><span class="dica">Nitidez</span>${lk.nitidezes.map((v) => pilula('nitidez', v, nomeV[v] || v)).join('')}</div>
      <div class="look-acoes"><button class="botao pequeno botao-coral" data-look="aplicar" ${igual || lk.renderizando ? 'disabled' : ''} title="Grava o look no projeto e renderiza a próxima versão (~1 min)">${lk.renderizando ? 'Renderizando…' : `Aplicar · v${this.proj.ultima + 1}`}</button></div></div>
        <div class="look-amostras">${['atual', 'teste'].map((k) => `<figure><video data-amostra="${k}" muted loop playsinline autoplay${lk.amostras?.[k] ? ` src="${lk.amostras[k]}"` : ''}></video><figcaption>${k === 'atual' ? 'Atual' : 'Testando'}</figcaption></figure>`).join('')}</div></div>`
  }

  async provarLook(t) {
    const lk = this.lk
    lk.t = t
    const vez = (lk.vez = (lk.vez || 0) + 1)
    const pedir = (look) => enviar('POST', `/api/projetos/${encodeURIComponent(this.slug)}/look/amostra`, { t, ...look }).then((r) => r.video)
    const amostras = () => $$('[data-amostra]', lk.el)
    for (const v of amostras()) v.closest('figure').classList.add('carregando')
    try {
      const [atual, teste] = await Promise.all([pedir(lk.atual), pedir(lk.teste)])
      if (vez !== lk.vez || this.fechado) return
      lk.amostras = { atual, teste }
      for (const [k, src] of Object.entries(lk.amostras)) {
        const v = $(`[data-amostra="${k}"]`, lk.el)
        if (v) v.src = src
      }
    } catch (e) {
      aviso(e.message, 'erro')
    } finally {
      for (const v of amostras()) v.closest('figure').classList.remove('carregando')
    }
  }

  async aplicarLook() {
    const lk = this.lk
    try {
      const r = await enviar('PUT', `/api/projetos/${encodeURIComponent(this.slug)}/look`, lk.teste)
      lk.atual = { ...lk.teste }
      lk.renderizando = true
      this.renderLook()
      aviso(`Renderizando a v${r.proxima} com o look novo: ela aparece aqui quando ficar pronta`)
      this.esperarRender()
    } catch (e) {
      aviso(e.message, 'erro')
    }
  }

  /** Enquanto o render do look roda, o botão fica em "Renderizando…" (a versão nova, quando chega, o `verDisco` avisa). */
  esperarRender() {
    clearInterval(this.relogioRender)
    this.relogioRender = setInterval(async () => {
      if (this.fechado) return clearInterval(this.relogioRender)
      const d = await json(`/api/projetos/${encodeURIComponent(this.slug)}/look`, null)
      if (d && !d.renderizando) {
        clearInterval(this.relogioRender)
        this.lk.renderizando = false
        this.renderLook()
      }
    }, 3000)
  }

  // ---------- a tela ----------

  montar() {
    abrirAba(this.slug, this.proj.nome) // o nome do projeto fica na aba; a versão, logo ao lado dela na barra
    carregarCategorias().then((cats) => abrirAba(this.slug, this.proj.nome, categoriaCta(cats, this.proj.formato || 'reels'))) // o ícone: projeto ou CTA
    $('#barra-versao').innerHTML = '<div class="seletor-versao" id="versoes"></div><span class="aviso-versao" id="aviso-versao"></span>'
    this.tela.className = 'pagina-revisao'
    this.tela.innerHTML = `<div class="revisao">
      <section class="palco">
        <div class="lado lado-esq">
          <div class="bloco"><span class="eyebrow">Plano agora</span><div id="plano-atual" class="plano-atual"></div></div>
          <div class="bloco"><span class="eyebrow">Fala</span><p id="fala-atual" class="fala-atual"></p></div>
        </div>
        <div class="video-caixa"><video id="video" src="${this.base}proxy.mp4" preload="auto" playsinline></video>
          <button class="video-tocar" data-acao="tocar" aria-label="Tocar">${ICONE.tocar}</button></div>
        <div class="lado lado-dir">
          <div class="bloco" id="usado"></div>
        </div>
      </section>
      <div class="controles">
        <div class="grupo">
          <button class="botao-icone" data-acao="corte-" title="O corte anterior (Shift+←)">${ICONE.segAntes}</button>
          <button class="botao-icone" data-acao="quadro-" title="−1 quadro (←)">${ICONE.quadroAntes}</button>
          <button class="botao-icone botao-tocar" data-acao="tocar" id="b-tocar" title="Tocar / pausar (Espaço)">${ICONE.tocar}</button>
          <button class="botao-icone" data-acao="quadro+" title="+1 quadro (→)">${ICONE.quadroDepois}</button>
          <button class="botao-icone" data-acao="corte+" title="O próximo corte (Shift+→)">${ICONE.segDepois}</button>
          <span class="tempo"><b id="t-atual">0:00,0</b> / <span id="t-total">${tempo(this.dur)}</span></span>
        </div>
        <div class="grupo velocidades">${VELOCIDADES.map((x) => `<button class="pilula pequena${x === 1 ? ' ativa' : ''}" data-vel="${x}">${num(x, x % 1 ? 1 : 0)}×</button>`).join('')}</div>
        <div class="grupo">
          <button class="botao" data-acao="look" title="Testar LUT, intensidade e vinheta do ator">${ICONE.ajustes} Look</button>
          <button class="botao" data-acao="entrada" id="b-entrada">Entrada <kbd>I</kbd></button>
          <button class="botao" data-acao="saida">Saída <kbd>O</kbd></button>
        </div>
      </div>
      <section class="linha">
        ${barraDaLinha(ATALHOS())}
        <div class="linha-rotulos"><span class="r-regua"></span>${this.blocos ? '<span title="Os blocos de ~30 s: revise, aprove e mande um de cada vez">Blocos</span>' : ''}<span class="r-planos">Planos</span><span>Fala</span><span>Você</span></div>
        <div class="linha-rolo" id="rolo"><div class="linha-conteudo" id="conteudo">
          <div class="regua" id="regua"></div>
          ${this.blocos ? '<div class="faixa faixa-blocos" id="f-blocos"></div>' : ''}
          <div class="faixa faixa-planos" id="f-planos"></div>
          <div class="faixa faixa-palavras" id="f-palavras"></div>
          <div class="faixa faixa-comentarios" id="f-comentarios"></div>
          <div id="divisas"></div>
          <div id="io"></div>
          <div class="cabeca" id="cabeca"></div>
        </div></div>
      </section>
      <aside class="painel">
        <div class="painel-cabeca"><div class="painel-titulo"><span class="resumo" id="resumo"></span><span class="salvo" id="salvo"></span></div>
          <span class="bloco-acoes" id="acoes-bloco"></span>
          <button class="botao botao-coral" data-acao="aprovar" id="b-aprovar" title="Aprovar o vídeo todo: o Claude exporta o final em 4K">Aprovar</button></div>
        <div id="estado"></div>
        <div class="lista" id="lista"></div>

        <div class="caixa-nova" id="caixa-nova">
          <div class="item-cabeca"><span class="eyebrow" id="nova-rotulo">Comentar em</span><button class="chip-tempo chip-alternar" data-acao="alternar-tempo" id="nova-quando" title="Desligar o tempo: vira um comentário geral (C)">0:00,0</button>
            <button class="botao-icone pequeno" data-acao="soltar" id="nova-soltar" hidden title="Soltar: a caixa volta a acompanhar o vídeo">${ICONE.fechar}</button></div>
          <textarea id="nova-texto" rows="3" placeholder="O que mudar aqui? Ao escrever, o vídeo pausa e o comentário fica neste instante."></textarea>
          <div id="nova-anexos"></div>
          <div class="editor-acoes">${clipe('nova')}<span class="dica">Enter grava · Shift+Enter quebra a linha · ⌘V cola print ou vídeo</span>
            <button class="botao pequeno botao-coral" data-acao="salvar-nova">Comentar</button></div></div>
      </aside>
    </div>`
    this.video = $('#video')
    this.renderVersoes()
    this.renderEstado()
    this.renderLista()
    this.renderLinha()
  }

  /** A caixa do comentário novo: o instante (acompanha o vídeo até começar a escrever; com I e O, o trecho). */
  quandoNova() {
    const n = this.nova
    if (n.geral) return { geral: true, t: null, fim: null }
    if (n.preso) return { t: n.t, fim: n.fim }
    const t = this.video.currentTime
    if (this.entrada != null) {
      const [a, b] = [Math.min(this.entrada, t), Math.max(this.entrada, t)]
      return { t: a, fim: b - a < 0.05 ? null : b }
    }
    return { t, fim: null }
  }

  renderNova() {
    const q = this.quandoNova()
    const rotulo = quando(q)
    if (rotulo !== this.rotuloNova || this.nova.preso !== this.presoNova) {
      this.rotuloNova = rotulo
      this.presoNova = this.nova.preso
      const geral = !!q.geral
      const chip = $('#nova-quando')
      chip.innerHTML = geral ? `<s>${tempo(this.video?.currentTime || 0)}</s> sem tempo` : rotulo
      chip.classList.toggle('desligado', geral)
      chip.title = geral ? 'Religar o tempo: o comentário fica no instante do vídeo (C)' : 'Desligar o tempo: vira um comentário geral (C)'
      $('#nova-rotulo').textContent = geral ? 'Comentário geral' : this.nova.preso ? 'Comentário em' : 'Comentar em'
      $('#nova-soltar').hidden = geral || !this.nova.preso
      $('#caixa-nova').classList.toggle('presa', this.nova.preso && !geral)
      $('#caixa-nova').classList.toggle('geral', geral)
      $('#nova-texto').placeholder = geral ? 'Sobre o vídeo todo (ex.: legenda um pouco mais baixa).' : 'O que mudar aqui? Ao escrever, o vídeo pausa e o comentário fica neste instante.'
    }
  }

  renderNovaAnexos() {
    $('#nova-anexos').innerHTML = this.htmlAnexos(this.nova.anexos, 'nova')
  }

  /** Começou a escrever (ou anexou): pausa o vídeo e prende o comentário no instante (ou no trecho de I a agora). */
  prenderNova() {
    if (this.nova.preso || this.nova.geral) return
    this.video.pause()
    Object.assign(this.nova, this.quandoNova(), { preso: true })
    this.entrada = null
    this.renderNova()
    this.renderMarcas()
  }

  /** O tempo da caixa: desligado, o comentário é geral (sobre o vídeo todo); religado, volta a seguir o vídeo. */
  alternarTempo(foco = false) {
    this.nova.geral = !this.nova.geral
    this.nova.preso = false
    this.nova.fim = null
    this.entrada = null
    this.rotuloNova = null
    this.renderNova()
    this.renderMarcas()
    if (!this.nova.geral && $('#nova-texto').value.trim()) this.prenderNova() // religou com texto: fica no instante
    if (foco || this.nova.geral) $('#nova-texto').focus()
  }

  /** A caixa volta a acompanhar o vídeo (o texto escrito fica). */
  soltarNova() {
    this.nova.preso = false
    this.nova.fim = null
    this.entrada = null
    this.renderNova()
    this.renderMarcas()
  }

  salvarNova() {
    const campo = $('#nova-texto')
    const texto = campo.value.trim()
    const n = this.nova
    if (!texto && !n.anexos.length) return
    const q = this.quandoNova()
    const c = this.novoComentario({ ...q, novoId: n.novoId, anexos: n.anexos }, texto)
    this.rev.comentarios.push(c)
    const b = c.geral ? null : this.blocoEm(c.t)
    if (b?.def.aprovado) {
      b.def.aprovado = false
      aviso(`${b.id} estava finalizado: com o comentário, ele volta a ficar aberto`)
    }
    this.sel = c.id
    this.nova = { preso: false, geral: false, t: 0, fim: null, anexos: [], novoId: null }
    this.entrada = null
    this.rotuloNova = null
    campo.value = ''
    crescer(campo)
    this.renderNovaAnexos()
    this.renderNova()
    this.renderLista()
    this.renderMarcas()
    this.agendarSalvar()
  }

  renderVersoes() {
    const s = encodeURIComponent(this.slug)
    const ultima = this.proj.ultima
    const lista = this.menuVersoes
    const vb = this.blocoSel && this.versoesBloco?.[this.blocoSel]
    if (vb?.length) {
      // um bloco escolhido: a versão dele (só sobe quando o bloco mudou); cada uma abre a versão do vídeo onde nasceu
      const id = this.blocoSel
      const agora = vb.find((x) => x.vs.includes(this.v))
      const ultimaB = vb.at(-1)
      $('#versoes').innerHTML = `<button class="botao botao-versao" data-acao="versoes" aria-haspopup="listbox" aria-expanded="${!!lista}" title="A versão do ${id} (o vídeo está na v${this.v})">
          <b>${id} · v${agora?.bv ?? '?'}</b>${agora === ultimaB ? '<span class="atual">atual</span>' : ''}${ICONE.seta_baixo}</button>
        ${lista ? `<div class="menu-versoes" role="listbox">${vb.slice().reverse().map((x) => `<a class="item-versao${x === agora ? ' ativa' : ''}" role="option" aria-selected="${x === agora}" href="#/p/${s}/v${x.vs[0]}" data-versao-bloco="${x.vs[0]}">
            <b>${id} · v${x.bv}</b>${x === ultimaB ? '<span class="atual">atual</span>' : ''}
            <span class="versao-dados">${x.vs.length > 1 ? `nos vídeos v${x.vs[0]}–v${x.vs.at(-1)}` : `no vídeo v${x.vs[0]}`}</span></a>`).join('')}</div>` : ''}`
      $('#aviso-versao').innerHTML = this.v < ultima ? `Você está vendo o vídeo v${this.v} (há uma v${ultima} mais nova) · <a href="#/p/${s}/v${ultima}">abrir a v${ultima}</a>` : ''
      return this.renderAprovar()
    }
    $('#versoes').innerHTML = `<button class="botao botao-versao" data-acao="versoes" aria-haspopup="listbox" aria-expanded="${!!lista}" title="Trocar de versão">
        <b>v${this.v}</b>${this.v === ultima ? '<span class="atual">atual</span>' : ''}${ICONE.seta_baixo}</button>
      ${lista ? `<div class="menu-versoes" role="listbox">${lista.map((x) => `<a class="item-versao${x.v === this.v ? ' ativa' : ''}" role="option" aria-selected="${x.v === this.v}" href="#/p/${s}/v${x.v}">
          <b>v${x.v}</b>${x.v === ultima ? '<span class="atual">atual</span>' : ''}
          <span class="versao-dados">${x.criado_em ? dataHora(x.criado_em) : '—'}${x.duracao ? ` · ${mmss(x.duracao)}` : ''}</span>
          <span class="versao-estado ve-${x.estado}">${(ESTADO_VERSAO[x.estado] || ESTADO_VERSAO.sem)(x.comentarios)}${x.aplicados ? ` · <b>${x.aplicados} ${x.aplicados === 1 ? 'aplicado' : 'aplicados'}</b>` : ''}</span></a>`).join('')}</div>` : ''}`
    $('#aviso-versao').innerHTML = this.v < ultima ? `Você está vendo a v${this.v} (há uma v${ultima} mais nova) · <a href="#/p/${s}/v${ultima}">abrir a v${ultima}</a>` : ''
    this.renderAprovar()
  }

  renderAprovar() {
    const b = $('#b-aprovar')
    b.innerHTML = this.rev.aprovado ? `${ICONE.check} Aprovado` : 'Aprovar'
    b.classList.toggle('botao-menta', !!this.rev.aprovado)
    b.classList.toggle('botao-coral', !this.rev.aprovado)
  }

  /** O seletor de versões: abre com a lista fresca (data do render, duração e o estado da revisão de cada uma). */
  async alternarVersoes(abrir = !this.menuVersoes) {
    if (!abrir) {
      this.menuVersoes = null
      return this.renderVersoes()
    }
    if (this.blocoSel && this.versoesBloco?.[this.blocoSel]?.length) { // as versões do bloco já estão na memória
      await new Promise((r) => setTimeout(r)) // depois do clique: senão o "clicou fora" vê o botão já trocado e fecha
      this.menuVersoes = true
      return this.renderVersoes()
    }
    const l = await json(`/api/projetos/${encodeURIComponent(this.slug)}/versoes`, null)
    if (this.fechado) return
    this.menuVersoes = l || this.proj.versoes.slice().reverse().map((v) => ({ v, estado: 'sem', comentarios: 0, aplicados: 0 }))
    this.renderVersoes()
  }

  renderEstado() {
    const r = this.rev
    const ultima = this.proj.ultima
    let html = ''
    if (r.aprovado) html += `<div class="faixa-estado estado-aprovado">${ICONE.check} Aprovada. O Claude exporta o final em 4K.</div>`
    else if (r.enviado_em) html += `<div class="faixa-estado estado-enviada">Revisão enviada em ${dataHora(r.enviado_em)}.${this.v < ultima ? '' : ` Esperando a v${this.v + 1}.`}</div>`
    $('#estado').innerHTML = html
  }

  renderResumo() {
    // um bloco escolhido: a linha de cima é a dele (voltar, o nome e a contagem; à direita, o loop e o Finalizar)
    const foco = this.blocos?.find((b) => b.id === this.blocoSel)
    $('#acoes-bloco').innerHTML = foco ? `<button class="botao-icone pequeno${this.loop?.id === foco.id ? ' ativo' : ''}" data-loop-bloco="${foco.id}" title="${this.loop?.id === foco.id ? 'Parar o loop' : 'Tocar só este bloco, em loop'}">${ICONE_ATALHO.plano}</button>
      <button class="botao pequeno${foco.def.aprovado ? ' feito' : ''}" data-aprovar-bloco="${foco.id}" title="${foco.def.aprovado ? 'Reabrir o bloco' : 'Finalizar o bloco: ele está pronto e o Claude não mexe mais nele'}">${ICONE.check} ${foco.def.aprovado ? 'Finalizado' : 'Finalizar'}</button>` : ''
    if (foco) {
      const n = this.doBloco(foco).length
      $('#resumo').innerHTML = `<span class="titulo-bloco${foco.def.aprovado ? ' bloco-ok' : ''}"><button class="botao-icone pequeno" data-sair-bloco title="Voltar a todos os blocos">${ICONE.voltar}</button>
        <button class="bloco-nome" data-bloco="${foco.id}" data-ir="${foco.ini}" title="${foco.id} · ${tempo(foco.ini)}–${tempo(foco.fim)} · ir ao começo">${foco.id}</button>${n ? `<span class="conta">${n} ${n === 1 ? 'comentário' : 'comentários'}</span>` : ''}</span>`
      return
    }
    const cs = this.rev.comentarios.filter(temConteudo)
    const n = (k) => cs.filter((c) => chaveStatus(c.status) === k).length
    const partes = [`${cs.length} ${cs.length === 1 ? 'comentário' : 'comentários'}`]
    for (const [k, um, varios] of [['aplicado', 'aplicado', 'aplicados'], ['respondido', 'respondido', 'respondidos'], ['nao_aplicado', 'não aplicado', 'não aplicados']]) {
      const q = n(k)
      if (q) partes.push(`<b class="t-${STATUS[k][1]}">${q} ${q === 1 ? um : varios}</b>`)
    }
    $('#resumo').innerHTML = partes.join(' · ')
  }

  // ---------- a lista de comentários ----------

  renderLista() {
    const campo0 = $('#editor-texto')
    if (campo0 && this.editor) this.editor.texto = campo0.value // o que já foi digitado sobrevive ao redesenho
    const comentarios = this.rev.comentarios.slice().sort((a, b) => ordem(a) - ordem(b))
    this.numeros = new Map(comentarios.map((c, k) => [c.id, k + 1]))
    let html = comentarios.map((c) => this.htmlComentario(c)).join('')
    const foco = this.blocos?.find((b) => b.id === this.blocoSel)
    if (foco) {
      // um bloco escolhido: só os comentários dele e, embaixo, o que já foi pedido nele nas versões anteriores
      const cs = comentarios.filter((c) => !c.geral && this.blocoEm(c.t)?.id === foco.id)
      html = `<section class="bloco-grupo bloco-foco${foco.def.aprovado ? ' bloco-grupo-ok' : ''}">
        ${cs.map((c) => this.htmlComentario(c)).join('') || `<p class="vazio-lista">Nenhum comentário no ${foco.id} nesta versão.<br>Comente na caixa abaixo, com o vídeo dentro do bloco.</p>`}
        ${this.htmlHistoricoBloco(foco)}</section>`
    } else if (this.blocos) {
      const gerais = comentarios.filter((c) => c.geral)
      html = gerais.map((c) => this.htmlComentario(c)).join('') + this.blocos.map((b) => {
        const cs = comentarios.filter((c) => !c.geral && this.blocoEm(c.t)?.id === b.id)
        return `<section class="bloco-grupo${b.def.aprovado ? ' bloco-grupo-ok' : ''}">${this.htmlCabecaBloco(b, cs.length)}${cs.map((c) => this.htmlComentario(c)).join('')}</section>`
      }).join('')
    }
    if (!comentarios.length && !this.blocos) html = `<p class="vazio-lista">Nenhum comentário ainda.<br>Escreva na caixa abaixo: o vídeo pausa e o comentário fica naquele instante (<kbd>I</kbd> e <kbd>O</kbd> marcam um trecho).</p>`
    $('#lista').innerHTML = html
    this.renderResumo()
    const campo = $('#editor-texto')
    if (campo) {
      crescer(campo)
      campo.focus()
      campo.setSelectionRange(campo.value.length, campo.value.length)
      campo.closest('.editor').scrollIntoView({ block: 'nearest' })
    }
  }

  htmlComentario(c) {
    if (this.editor?.id === c.id) return this.htmlEditor()
    return `<article class="item${this.sel === c.id ? ' item-sel' : ''}" data-id="${c.id}"${c.geral ? '' : ` data-ir="${c.t}"`}>
      <header class="item-cabeca"><span class="num">${this.numeros.get(c.id)}</span>
        ${c.geral ? '<span class="chip-tempo estatico">Geral</span>' : `<button class="chip-tempo" data-ir="${c.t}">${quando(c)}</button>`}
        <span class="item-acoes"><button class="botao-icone pequeno" data-editar="${c.id}" title="Editar">${ICONE.lapis}</button>
        <button class="botao-icone pequeno" data-apagar="${c.id}" title="Apagar">${ICONE.lixo}</button></span></header>
      ${c.texto ? `<p class="texto">${esc(c.texto)}</p>` : ''}${this.htmlAnexos(c.anexos, c.id)}
      ${this.htmlResposta(c)}
    </article>`
  }

  /** As miniaturas dos prints de um comentário (`dono`: o id dele, "nova" ou "editor"): clicar amplia; × tira. */
  htmlAnexos(lista, dono) {
    if (!lista?.length) return ''
    return `<div class="anexos">${lista.map((a) => `<span class="anexo"><button class="anexo-img" data-ampliar="${esc(a)}" title="${VIDEO.test(a) ? 'Tocar o vídeo' : 'Ampliar o print'}">${VIDEO.test(a)
      ? `<video muted playsinline preload="metadata" src="${this.urlAnexo(a)}#t=0.1"></video><span class="anexo-play">${ICONE.tocar}</span>`
      : `<img src="${this.urlAnexo(a)}" alt="print" loading="lazy">`}</button>
      <button class="anexo-tirar" data-tirar-anexo="${esc(`${dono}|${a}`)}" title="Tirar o print" aria-label="Tirar o print">${ICONE.fechar}</button></span>`).join('')}</div>`
  }

  urlAnexo(a) {
    return `/projetos/${encodeURIComponent(this.slug)}/${a.split('/').map(encodeURIComponent).join('/')}`
  }

  /** O que o Claude respondeu a um comentário (status + texto). */
  htmlResposta(c) {
    const k = chaveStatus(c.status)
    if (k === 'pendente' && !c.resposta) return ''
    const [rotulo, cls] = STATUS[k] || [k, 'respondido']
    return `<div class="resposta resposta-${cls}"><span class="status">${k === 'aplicado' ? ICONE.check : ''}Claude · ${rotulo}</span>
      ${c.resposta ? `<p>${esc(c.resposta)}</p>` : ''}</div>`
  }

  htmlEditor() {
    const ed = this.editor
    return `<div class="editor">
      <div class="item-cabeca"><span class="eyebrow">Editar comentário</span><span class="chip-tempo estatico">${quando(ed)}</span></div>
      <textarea id="editor-texto" rows="3" placeholder="O que mudar aqui? (⌘V ou arraste para anexar print ou vídeo)">${esc(ed.texto || '')}</textarea>
      ${this.htmlAnexos(ed.anexos, 'editor')}
      <div class="editor-acoes">${clipe('editor')}<span class="dica">Enter salva · Shift+Enter quebra a linha · Esc cancela</span>
        <button class="botao pequeno" data-acao="cancelar">Cancelar</button>
        <button class="botao pequeno botao-coral" data-acao="salvar-editor">Salvar</button></div>
    </div>`
  }

  // ---------- a linha do tempo ----------

  renderLinha() {
    if (this.blocos) this.calcularBlocos() // a duração pode ter mudado (o vídeo carregou): o último bloco vai até o fim
    const rolo = $('#rolo')
    const ajuste = Math.max(rolo.clientWidth - 2, 100) / this.dur
    if (this.ajustar || this.pxs < ajuste) {
      this.pxs = ajuste
      this.ajustar = true
    }
    $('#conteudo').style.width = `${this.dur * this.pxs}px`
    this.renderRegua()
    this.renderPlanos()
    this.renderPalavras()
    this.renderMarcas()
    this.renderBlocos()
    this.iPalavra = this.iPlano = -2
    this.atualizar()
  }

  renderRegua() {
    const px = this.pxs
    const passo = [0.5, 1, 2, 5, 10, 15, 30, 60].find((s) => s * px >= 56) || 60
    const sub = passo >= 5 ? passo / 5 : passo / 2
    let html = ''
    for (let t = 0; t <= this.dur + 1e-6; t += sub) {
      const k = Math.round(t / sub)
      const grande = k % Math.round(passo / sub) === 0
      if (!grande && sub * px < 6) continue
      const rotulo = grande ? (passo < 1 ? tempo(t) : `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}`) : ''
      html += `<span class="tique${grande ? ' tique-grande' : ''}" style="left:${(t * px).toFixed(1)}px">${rotulo ? `<i>${rotulo}</i>` : ''}</span>`
    }
    $('#regua').innerHTML = html
  }

  renderPlanos() {
    $('#f-planos').innerHTML = this.planos
      .map((p) => {
        const x = p.ini * this.pxs
        const w = Math.max((p.fim - p.ini) * this.pxs - 1, 1)
        const [nome, curto] = PLANOS[p.tipo] || [p.tipo, p.tipo]
        const rot = w >= 130 ? `<b>${esc(p.id)}</b> ${esc(nome)}` : w >= 70 ? `<b>${esc(p.id)}</b> ${esc(curto)}` : w >= 24 ? `<b>${esc(p.id)}</b>` : ''
        const cod = this.codigoPlano(p)
        const dica = `${cod ? `${cod.codigo} · ` : `${p.id} · `}${nome} · ${tempo(p.ini)}–${tempo(p.fim)}${p.descricao ? `\n${p.descricao}` : ''}${p.texto ? `\nTexto: ${p.texto}` : ''}`
        const copia = cod && w >= 90 ? `<button type="button" class="copiar-codigo" data-copiar-codigo="${esc(cod.texto)}" title="Copiar “${esc(cod.texto)}”" aria-label="Copiar o código do plano">${ICONE.copiar}</button>` : ''
        return `<div class="plano tipo-${esc(p.tipo)}" style="left:${x.toFixed(1)}px;width:${w.toFixed(1)}px" title="${esc(dica)}">${rot}${copia}</div>`
      })
      .join('')
  }

  /** O código de um plano desta versão (PRJ-04·p5) e o texto que o botão copia (com a versão e o tempo). */
  codigoPlano(p) {
    if (!this.codigo) return null
    const codigo = `${this.codigo}·${p.id}`
    return { codigo, texto: `${codigo} · ${nomePlano(p.tipo)} (v${this.v}, ${tempo(p.ini)})` }
  }

  renderPalavras() {
    const ctx = (this.medidor ||= document.createElement('canvas').getContext('2d'))
    ctx.font = '400 11px Manrope, sans-serif'
    $('#f-palavras').innerHTML = this.palavras
      .map((w, i) => {
        const x = w.ini * this.pxs
        const larg = Math.max((w.fim - w.ini) * this.pxs - 1, 1)
        const cabe = larg >= ctx.measureText(w.texto).width + 5
        return `<span class="palavra${cabe ? '' : ' sem-texto'}" data-i="${i}" style="left:${x.toFixed(1)}px;width:${larg.toFixed(1)}px" title="${esc(w.texto)} · ${tempo(w.ini)}">${cabe ? esc(w.texto) : ''}</span>`
      })
      .join('')
  }

  renderMarcas() {
    const px = this.pxs
    const marca = (id, t, fim, rotulo, cls, dica) => {
      const sel = this.sel === id ? ' marca-sel' : ''
      if (fim != null && (fim - t) * px >= 10)
        return `<button class="marca marca-intervalo ${cls}${sel}" data-marca="${id}" data-ir="${t}" style="left:${(t * px).toFixed(1)}px;width:${((fim - t) * px).toFixed(1)}px" title="${esc(dica)}">${rotulo}</button>`
      return `<button class="marca marca-ponto ${cls}${sel}" data-marca="${id}" data-ir="${t}" style="left:${(t * px).toFixed(1)}px" title="${esc(dica)}">${rotulo}</button>`
    }
    this.renderBlocos()
    $('#f-comentarios').innerHTML = this.rev.comentarios
      .filter((c) => !c.geral)
      .map((c) => {
        const k = chaveStatus(c.status)
        return marca(c.id, c.t, c.fim, this.numeros.get(c.id), k === 'pendente' ? '' : `marca-${STATUS[k]?.[1] || 'respondido'}`, `${quando(c)} · ${c.texto}`)
      })
      .join('')
    // a marca de entrada (I) e o trecho do comentário sendo escrito na caixa
    const n = this.nova
    let io = ''
    if (n?.preso && n.fim != null) io = `<div class="io-trecho" style="left:${n.t * px}px;width:${(n.fim - n.t) * px}px"></div>`
    else if (n?.preso) io = `<div class="io-entrada io-ponto" style="left:${n.t * px}px"><i>✎</i></div>`
    else if (this.entrada != null) io = `<div class="io-entrada" style="left:${this.entrada * px}px"><i>I</i></div>`
    $('#io').innerHTML = io
    $('#b-entrada').classList.toggle('ativo', this.entrada != null)
  }

  // ---------- o tempo ----------

  atualizar() {
    if (this.fechado) return // o vídeo ainda solta eventos depois de sair da tela
    if (this.loop && !this.video.paused && (this.video.currentTime >= this.loop.fim - 0.03 || this.video.currentTime < this.loop.ini - 0.1)) this.video.currentTime = this.loop.ini
    const t = this.video.currentTime
    $('#t-atual').textContent = tempo(t)
    this.renderNova()
    const x = t * this.pxs
    $('#cabeca').style.transform = `translateX(${x}px)`
    const tocando = !this.video.paused
    if (tocando !== this.tocando) {
      this.tocando = tocando
      const ic = tocando ? ICONE.pausar : ICONE.tocar
      $('#b-tocar').innerHTML = ic
      $('.video-tocar').classList.toggle('escondido', tocando)
    }
    if (tocando) {
      const rolo = $('#rolo')
      if (x < rolo.scrollLeft || x > rolo.scrollLeft + rolo.clientWidth - 30) rolo.scrollLeft = x - 40
    }
    // a palavra sob o cursor
    const i = this.palavras.findIndex((w) => t >= w.ini && t < w.fim)
    if (i !== this.iPalavra) {
      $('.palavra.agora')?.classList.remove('agora')
      if (i >= 0) $(`.palavra[data-i="${i}"]`)?.classList.add('agora')
      const k = i >= 0 ? i : this.palavras.indexOf(this.palavraPerto(t))
      this.iPalavra = i
      const de = Math.max(0, k - 5)
      $('#fala-atual').innerHTML = k < 0 ? '<span class="apagado">—</span>'
        : (de > 0 ? '… ' : '') + this.palavras.slice(de, k + 6).map((w, j) => (de + j === i ? `<b>${esc(w.texto)}</b>` : esc(w.texto))).join(' ') + (k + 6 < this.palavras.length ? ' …' : '')
    }
    // o plano sob o cursor
    const p = this.planos.findIndex((q) => t >= q.ini && t < q.fim)
    if (p !== this.iPlano) {
      this.iPlano = p
      const q = this.planos[p]
      const cod = q && this.codigoPlano(q)
      $('#plano-atual').innerHTML = q
        ? `<span class="plano-linha" data-chip-copia><span class="chip-plano tipo-${esc(q.tipo)}"><b>${esc(q.id)}</b> ${esc(nomePlano(q.tipo))}</span>${cod ? `<button type="button" class="copiar-codigo" data-copiar-codigo="${esc(cod.texto)}" title="Copiar “${esc(cod.texto)}”" aria-label="Copiar o código do plano">${ICONE.copiar}</button>` : ''}</span>${q.texto ? `<p class="plano-texto">“${esc(q.texto)}”</p>` : ''}`
        : '<span class="apagado">—</span>'
      $('#usado').innerHTML = q ? this.htmlUsado(q.id) : ''
      this.carregarMidias(q?.id)
    }
  }

  /** O que entrou no plano: as mídias do banco (miniatura que abre o vídeo, código, fonte), o motion e o preset. */
  htmlUsado(pl) {
    const u = this.usado[pl]
    if (!u) return ''
    const c = this.cods || {}
    const midias = (u.midias || []).map((id) => {
      const m = this.midias[id]
      const nome = m?.nome || ''
      const fonte = m?.origem?.url
      const dur = m ? (m.pai ? m.fim - m.inicio : m.duracao) : null
      return `<div class="midia-usada">
        <button class="midia-mini" data-ver-midia="${id}" title="Assistir">${m?.tipo === 'imagem' ? '' : `<span class="midia-play">${ICONE.tocar}</span>`}<img src="/biblioteca/banco/${id}/miniatura.jpg" alt="" loading="lazy">${dur ? `<span class="duracao">${tempo(dur)}</span>` : ''}</button>
        <div class="midia-linha"><span class="midia-nome" title="${esc(nome)}">${esc(nome)}</span></div>
        <div class="midia-linha">${chipCodigo(c.midia?.[id], nome || id)}${fonte ? `<a class="midia-fonte" href="${esc(fonte)}" target="_blank" rel="noopener" title="${esc(fonte)}">${esc(new URL(fonte).hostname.replace(/^www\./, ''))} ↗</a>` : ''}</div></div>`
    }).join('')
    const linhas = [
      u.motion && `<div class="midia-linha"><span>Motion · ${esc(u.motion.nome || u.motion.preset || 'novo')}</span>${chipCodigo(c.motion?.[u.motion.preset], u.motion.nome || u.motion.preset)}</div>`,
    ].filter(Boolean).join('')
    // o preset do insert e a transição de entrada do plano: o clipe de referência de cada um, pequeno, em laço
    const receita = (tipo, id, rotulo) => {
      if (!id) return ''
      const nome = this.receitas[`${tipo}:${id}`]?.nome || id
      const clipe = `/biblioteca/${tipo === 'preset' ? 'presets' : 'transicoes'}/clipes/${id}.mp4`
      return `<div class="receita-usada"><button class="receita-mini" data-ver-clipe="${clipe}" title="Assistir com som">
          <video src="${clipe}" muted loop autoplay playsinline preload="metadata" onerror="this.parentNode.classList.add('sem-clipe')"></video></button>
        <div class="receita-info"><span class="dica">${rotulo}</span><span class="midia-nome" title="${esc(nome)}">${esc(nome)}</span>${chipCodigo(c[tipo]?.[id], nome)}</div></div>`
    }
    const receitas = receita('preset', u.preset, 'Preset') + receita('transicao', u.transicao, 'Transição de entrada')
    return midias || linhas || receitas ? `<span class="eyebrow">No plano</span>${midias}${linhas}${receitas}` : ''
  }

  /** A mídia do banco num modal (um trecho toca só o pedaço usado, em laço). */
  verMidia(id) {
    const m = this.midias[id]
    if (!m) return
    this.video.pause()
    const pasta = `/biblioteca/banco/${m.pai || id}/`
    const arq = m.proxy || m.arquivo
    const fechar = `<button class="botao-icone anexo-fechar" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button>`
    if (m.tipo === 'imagem') return janela(`${fechar}<img class="anexo-grande" src="${pasta}${arq}" alt="">`, { classe: 'janela-anexo' })
    // um player próprio: a barra e o tempo são só do trecho usado (o nativo mostraria o vídeo de origem inteiro)
    const ini = m.pai ? m.inicio : 0
    const { el } = janela(`${fechar}<video class="anexo-grande" src="${pasta}${arq}#t=${ini}" autoplay playsinline></video>
      <div class="player-trecho"><button class="botao-icone pequeno" data-tocar-trecho title="Tocar / pausar (Espaço)">${ICONE.pausar}</button>
        <div class="trecho-barra"><i></i></div><span class="trecho-tempo">0:00,0</span></div>`, { classe: 'janela-anexo' })
    const v = $('video', el), bar = $('.trecho-barra', el), b = $('[data-tocar-trecho]', el)
    const fim = () => (m.pai ? m.fim : v.duration || m.duracao || 0)
    const dur = () => Math.max(0.01, fim() - ini)
    const mostrar = () => {
      const t = Math.min(Math.max(v.currentTime - ini, 0), dur())
      $('i', bar).style.width = `${(100 * t) / dur()}%`
      $('.trecho-tempo', el).textContent = `${tempo(t)} / ${tempo(dur())}`
      b.innerHTML = v.paused ? ICONE.tocar : ICONE.pausar
    }
    v.addEventListener('timeupdate', () => {
      if (v.currentTime >= fim() - 0.02) v.currentTime = ini // em laço
      mostrar()
    })
    for (const ev of ['play', 'pause', 'loadedmetadata']) v.addEventListener(ev, mostrar)
    const alternar = () => (v.paused ? v.play() : v.pause())
    b.addEventListener('click', alternar)
    v.addEventListener('click', alternar)
    bar.addEventListener('click', (e) => {
      const r = bar.getBoundingClientRect()
      v.currentTime = ini + ((e.clientX - r.left) / r.width) * dur()
    })
    el.addEventListener('keydown', (e) => e.key === ' ' && (e.preventDefault(), alternar()))
    b.focus()
  }

  /** Busca no banco o nome e a fonte das mídias do plano (uma vez cada) e redesenha o bloco. */
  async carregarMidias(pl) {
    const u = this.usado[pl] || {}
    const faltam = (u.midias || []).filter((id) => !(id in this.midias))
    const receitas = [['preset', u.preset], ['transicao', u.transicao]].filter(([t, id]) => id && !(`${t}:${id}` in this.receitas))
    if (!faltam.length && !receitas.length) return
    await Promise.all([
      ...faltam.map(async (id) => (this.midias[id] = (await json(`/api/banco/${id}`, null))?.item || null)),
      ...receitas.map(async ([t, id]) => (this.receitas[`${t}:${id}`] = await json(`/biblioteca/${t === 'preset' ? 'presets' : 'transicoes'}/${id}.json`, null))),
    ])
    if (this.fechado || this.planos[this.iPlano]?.id !== pl) return
    this.iPlano = -2 // força o redesenho do plano atual
    this.atualizar()
  }

  laco() {
    cancelAnimationFrame(this.raf)
    const passo = () => {
      this.atualizar()
      if (!this.video.paused && !this.fechado) this.raf = requestAnimationFrame(passo)
    }
    passo()
  }

  buscar(t) {
    this.video.currentTime = Math.min(Math.max(t, 0), Math.max(this.dur - 0.01, 0))
    this.atualizar()
  }

  passo(d) {
    this.video.pause()
    if (Math.abs(d) < 0.5) this.buscar((Math.round(this.video.currentTime * 24) + Math.sign(d)) / 24 + 0.001)
    else this.buscar(this.video.currentTime + d)
  }

  /** Shift + setas (como no 18): o começo do plano seguinte ou anterior (o corte); no anterior, a 1ª vez volta ao começo
   *  do plano em que se está. */
  irAoCorte(dir) {
    this.video.pause()
    const t = this.video.currentTime
    const inicios = this.planos.map((p) => p.ini).sort((a, b) => a - b)
    const alvo = dir > 0 ? inicios.find((x) => x > t + 0.02) : inicios.filter((x) => x < t - 0.02).at(-1)
    this.buscar(alvo ?? (dir > 0 ? this.dur : 0))
  }

  /** R (como no 18): toca de novo o plano em que se está, do começo; apertado logo depois de voltar, vai ao anterior. */
  replano() {
    const t = this.video.currentTime
    const inicios = this.planos.map((p) => p.ini).sort((a, b) => a - b)
    let ini = inicios.filter((x) => x <= t + 0.001).at(-1) ?? 0
    if (t - ini < 0.35 && Date.now() - (this.ultimoR || 0) < 1500) ini = inicios.filter((x) => x < ini - 0.001).at(-1) ?? 0
    this.ultimoR = Date.now()
    this.buscar(ini + 0.001)
    this.video.play().catch(() => {})
  }

  alternar() {
    if (this.video.paused) this.video.play().catch(() => {})
    else this.video.pause()
  }

  zoom(fator, ancora) {
    const rolo = $('#rolo')
    const a = ancora ?? (this.video.currentTime * this.pxs - rolo.scrollLeft)
    const tAncora = (rolo.scrollLeft + a) / this.pxs
    const ajuste = Math.max(rolo.clientWidth - 2, 100) / this.dur
    this.pxs = Math.min(Math.max(this.pxs * fator, ajuste), 400) // fator 0: o vídeo inteiro na largura (Ajustar)
    this.ajustar = this.pxs <= ajuste * 1.0001
    this.renderLinha()
    rolo.scrollLeft = tAncora * this.pxs - a
  }

  // ---------- palavras e fala ----------

  palavraPerto(t) {
    let melhor = null
    let dist = Infinity
    for (const w of this.palavras) {
      const d = t < w.ini ? w.ini - t : t >= w.fim ? t - w.fim : 0
      if (d < dist) [melhor, dist] = [w, d]
      if (d === 0 || w.ini > t + dist) break
    }
    return melhor
  }

  falaPonto(t) {
    const k = this.palavras.indexOf(this.palavraPerto(t))
    return k < 0 ? '' : limpar(this.palavras.slice(Math.max(0, k - 1), k + 2).map((w) => w.texto).join(' '))
  }

  falaIntervalo(a, b) {
    const ws = this.palavras.filter((w) => w.fim > a && w.ini < b).map((w) => w.texto)
    if (!ws.length) return this.falaPonto(a)
    return limpar(ws.length > 10 ? `${ws.slice(0, 4).join(' ')} … ${ws.slice(-4).join(' ')}` : ws.join(' '))
  }

  // ---------- comentar ----------

  abrirEditor(ed) {
    if (this.editor) this.salvarEditor()
    this.video.pause()
    this.editor = ed
    this.renderLista()
    this.renderMarcas()
  }

  fecharEditor() {
    const ed = this.editor
    // os prints colados neste editor e não salvos saem do disco
    const antes = (ed?.id && this.rev.comentarios.find((x) => x.id === ed.id)?.anexos) || []
    for (const a of ed?.anexos || []) if (!antes.includes(a)) this.apagarAnexo(a)
    this.editor = null
    this.renderLista()
    this.renderMarcas()
  }

  salvarEditor() {
    const ed = this.editor
    if (!ed) return
    const texto = ($('#editor-texto')?.value ?? ed.texto ?? '').trim()
    const anexos = ed.anexos || []
    const cs = this.rev.comentarios
    if (ed.id) {
      const c = cs.find((x) => x.id === ed.id)
      for (const a of c?.anexos || []) if (!anexos.includes(a) || (!texto && !anexos.length)) this.apagarAnexo(a)
      if (c && !texto && !anexos.length) cs.splice(cs.indexOf(c), 1)
      else if (c) {
        c.texto = texto
        if (anexos.length) c.anexos = anexos
        else delete c.anexos
      }
    } else if (texto || anexos.length) {
      const c = this.novoComentario(ed, texto)
      cs.push(c)
      this.sel = c.id
    }
    this.editor = null
    this.renderLista()
    this.renderMarcas()
    this.agendarSalvar()
  }

  /** O id do próximo comentário (reservado ao colar um print num comentário ainda não salvo: o arquivo leva o id). */
  proximoId() {
    this.reservado = Math.max(this.reservado || 0, ...this.rev.comentarios.map((c) => numero(c.id))) + 1
    return `c${this.reservado}`
  }

  novoComentario({ t, fim, novoId, anexos, geral }, texto) {
    const n = novoId ? numero(novoId) : Math.max(this.reservado || 0, ...this.rev.comentarios.map((c) => numero(c.id))) + 1
    if (geral)
      return { id: `c${n}`, geral: true, t: null, fim: null, palavra: null, fala: '', texto, criado_em: agora(), de: 'rodrigo', status: 'pendente', resposta: null, ...(anexos?.length ? { anexos } : {}) }
    const fala = fim != null ? this.falaIntervalo(t, fim) : this.falaPonto(t)
    return {
      id: `c${n}`, t: r3(t), fim: fim == null ? null : r3(fim), palavra: this.palavraPerto(t)?.id ?? null, fala, texto,
      criado_em: agora(), de: 'rodrigo', status: 'pendente', resposta: null, ...(anexos?.length ? { anexos } : {}),
    }
  }

  /** I: a entrada de um trecho; a caixa passa a mostrar o trecho da entrada até o cursor (solta, se estava presa). */
  marcarEntrada(calado = false) {
    this.nova.geral = false
    this.nova.preso = false
    this.nova.fim = null
    this.entrada = this.video.currentTime
    this.renderNova()
    this.renderMarcas()
    if (!calado) aviso(`Entrada em ${tempo(this.entrada)}. Agora O marca a saída.`)
  }

  /** O: a saída; o trecho fica preso na caixa, pronta para escrever. */
  marcarSaida() {
    if (this.entrada == null) return aviso('Marque a entrada com I antes.', 'erro')
    this.video.pause()
    Object.assign(this.nova, this.quandoNova(), { preso: true })
    this.entrada = null
    this.renderNova()
    this.renderMarcas()
    $('#nova-texto').focus()
  }

  async apagar(id) {
    const c = this.rev.comentarios.find((x) => x.id === id)
    if (!c) return
    const ok = await confirmar({ titulo: 'Apagar este comentário?', texto: c.texto || (c.anexos?.length ? 'O comentário e os prints dele.' : ''), ok: 'Apagar', perigo: true })
    if (!ok) return
    this.rev.comentarios.splice(this.rev.comentarios.indexOf(c), 1)
    for (const a of c.anexos || []) this.apagarAnexo(a)
    this.renderLista()
    this.renderMarcas()
    this.agendarSalvar()
  }

  selecionar(id, t) {
    this.sel = id
    if (t != null) this.buscar(t)
    this.renderLista()
    this.renderMarcas()
    $(`.item[data-id="${id}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }

  // ---------- gravar, copiar, aprovar ----------

  mostrarSalvo(estado) {
    const el = $('#salvo')
    if (!el) return
    el.className = `salvo salvo-${estado}`
    el.innerHTML = estado === 'erro' ? 'Erro ao salvar' : '' // grava sozinho: só o erro aparece
  }

  agendarSalvar() {
    this.sujo = true
    this.mostrarSalvo('salvando')
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.salvar(), 600)
  }

  salvar(keepalive = false) {
    clearTimeout(this.timer)
    this.sujo = false
    const corpo = JSON.stringify(this.rev)
    const url = `/api/revisao/${encodeURIComponent(this.slug)}/v${this.v}`
    this.fila = this.fila
      .then(() => fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: corpo, keepalive }))
      .then((r) => {
        if (!r.ok) throw new Error(r.status)
        if (!this.sujo) this.mostrarSalvo('salvo')
      })
      .catch(() => this.mostrarSalvo('erro'))
    return this.fila
  }

  async aprovar() {
    if (this.editor) this.salvarEditor()
    const texto = `Aprovado · ${this.slug} · v${this.v}`
    if (!this.rev.aprovado) {
      const ok = await confirmar({ titulo: `Aprovar a v${this.v}?`, texto: 'O Claude exporta o vídeo final em 4K a partir desta versão.', ok: 'Aprovar e copiar' })
      if (!ok) return
      this.rev.aprovado = true
      await this.salvar()
      this.renderVersoes()
      this.renderEstado()
    }
    await copiar(texto)
    aviso('Copiado — cole no chat do Claude Code')
  }

  /** O Claude responde no arquivo e entrega versões novas: a cada 4 s, traz as respostas e as versões. */
  async verDisco() {
    if (this.fechado || this.sujo || document.hidden) return
    const disco = await json(this.urlRevisao, null)
    if (this.fechado || this.sujo) return
    let mudou = false
    for (const d of disco?.comentarios || []) {
      const c = this.rev.comentarios.find((x) => x.id === d.id)
      if (c && (d.status !== c.status || d.resposta !== c.resposta)) {
        c.status = d.status
        c.resposta = d.resposta
        mudou = true
      }
    }
    // uma gravação que se perdeu (o arquivo foi regravado ao mesmo tempo por outro lado): grava de novo
    if (disco && this.rev.comentarios.some((c) => !disco.comentarios?.some((d) => d.id === c.id))) this.agendarSalvar()
    if (mudou) {
      if (!this.editor) this.renderLista()
      this.renderMarcas()
      this.renderEstado()
      aviso('O Claude respondeu a revisão')
    }
    const p = (await json('/api/projetos', null))?.find((x) => x.slug === this.slug)
    if (p && !this.fechado && p.versoes.join() !== this.proj.versoes.join()) {
      const nova = p.versoes.find((x) => !this.proj.versoes.includes(x))
      this.proj = p
      this.renderVersoes()
      this.renderEstado()
      if (nova) aviso(`A v${nova} chegou`)
    }
  }

  // ---------- os prints (colar com ⌘V ou arrastar no comentário) ----------

  /** Envia as imagens e os vídeos ao servidor (revisoes/anexos/<comentário>-<n>.<ext>) e os prende à caixa do
   *  comentário novo (`alvo` "nova": prende o instante, como começar a escrever), ao comentário sendo editado
   *  ("editor"). */
  async anexar(arquivos, alvo) {
    const imagens = [...arquivos].filter((f) => f.type?.startsWith('image/') || f.type?.startsWith('video/'))
    if (!imagens.length) return aviso('Só imagens e vídeos entram como anexo.', 'erro')
    let cid
    if (alvo === 'nova') {
      this.prenderNova()
      cid = this.nova.novoId ||= this.proximoId()
    } else if (alvo === 'editor') {
      const ed = this.editor
      if (!ed) return
      ed.texto = $('#editor-texto')?.value ?? ed.texto
      cid = ed.id || (ed.novoId ||= this.proximoId())
    }
    let n = 0
    for (const f of imagens) {
      try {
        const r = await fetch(`/api/revisao/${encodeURIComponent(this.slug)}/v${this.v}/anexo?comentario=${cid}`, { method: 'POST', headers: { 'Content-Type': f.type }, body: f })
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(d.erro || `Erro ${r.status}`)
        if (alvo === 'nova') this.nova.anexos.push(d.caminho)
        else if (this.editor) (this.editor.anexos ||= []).push(d.caminho)
        else this.apagarAnexo(d.caminho) // o editor fechou enquanto enviava
        n++
      } catch (x) {
        aviso(`O print não entrou: ${x.message}`, 'erro')
      }
    }
    if (alvo === 'nova') this.renderNovaAnexos()
    else if (this.editor) this.renderLista()
    if (n) aviso(n === 1 ? 'Anexado' : `${n} anexados`)
  }

  apagarAnexo(caminho) {
    fetch(`/api/revisao/${encodeURIComponent(this.slug)}/v${this.v}/anexo?caminho=${encodeURIComponent(caminho)}`, { method: 'DELETE' }).catch(() => {})
  }

  /** O × de uma miniatura: no editor, sai ao salvar; num comentário salvo, sai já. */
  tirarAnexo(dono, caminho) {
    if (dono === 'nova') {
      this.nova.anexos = this.nova.anexos.filter((a) => a !== caminho)
      this.renderNovaAnexos()
      return this.apagarAnexo(caminho)
    }
    if (dono === 'editor') {
      if (!this.editor) return
      this.editor.texto = $('#editor-texto')?.value ?? this.editor.texto
      this.editor.anexos = (this.editor.anexos || []).filter((a) => a !== caminho)
      const salvo = this.editor.id && this.rev.comentarios.find((x) => x.id === this.editor.id)?.anexos?.includes(caminho)
      if (!salvo) this.apagarAnexo(caminho)
      return this.renderLista()
    }
    {
      const c = this.rev.comentarios.find((x) => x.id === dono)
      if (!c) return
      c.anexos = (c.anexos || []).filter((a) => a !== caminho)
      if (!c.anexos.length) delete c.anexos
      if (!temConteudo(c)) this.rev.comentarios.splice(this.rev.comentarios.indexOf(c), 1)
      this.renderLista()
      this.renderMarcas()
    }
    this.apagarAnexo(caminho)
    this.agendarSalvar()
  }

  ampliar(caminho) {
    const midia = VIDEO.test(caminho)
      ? `<video class="anexo-grande" src="${this.urlAnexo(caminho)}" controls autoplay playsinline></video>`
      : `<img class="anexo-grande" src="${this.urlAnexo(caminho)}" alt="print">`
    janela(`<button class="botao-icone anexo-fechar" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button>${midia}`, { classe: 'janela-anexo' })
  }

  // ---------- eventos ----------

  ligar() {
    const v = this.video
    // volta ao instante onde o criador estava nesta versão (ao trocar de página e voltar, ou recarregar)
    const onde = preferencia(`posicao.${this.slug}.v${this.v}`, 0)
    v.addEventListener('loadedmetadata', () => onde > 0 && this.buscar(onde), { once: true })
    v.addEventListener('loadedmetadata', () => {
      if (isFinite(v.duration) && Math.abs(v.duration - this.dur) > 0.05) {
        this.dur = v.duration
        $('#t-total').textContent = tempo(this.dur)
        this.renderLinha()
      }
    })
    v.addEventListener('play', () => this.laco())
    for (const ev of ['pause', 'seeked', 'timeupdate']) v.addEventListener(ev, () => v.paused && this.atualizar())

    this.cliques = (e) => this.clique(e)
    this.tela.addEventListener('click', this.cliques)
    $('#barra-versao').addEventListener('click', this.cliques)
    this.teclas = (e) => this.tecla(e)
    window.addEventListener('keydown', this.teclas)
    this.redim = () => this.ajustar && this.renderLinha()
    window.addEventListener('resize', this.redim)
    this.saida = () => {
      this.guardarPosicao()
      if (this.sujo) this.salvar(true)
    }
    window.addEventListener('pagehide', this.saida)

    // a caixa do comentário novo: escrever prende o instante (e pausa); apagar tudo solta
    $('#nova-texto').addEventListener('input', (e) => {
      crescer(e.target)
      if (e.target.value.trim()) this.prenderNova()
      else if (!this.nova.anexos.length && this.nova.fim == null) this.soltarNova()
    })
    // o painel (aba, editor, réplica, rolagem) e o rascunho que ficou na caixa ao sair
    this.voltarPainel()
    const r = preferencia(`rascunho.${this.slug}.v${this.v}`, null)
    if (r) {
      const { texto, ...nova } = r
      Object.assign(this.nova, nova)
      $('#nova-texto').value = texto
      crescer($('#nova-texto'))
      this.rotuloNova = null
      this.renderNova()
    }
    // o botão de clipe
    this.tela.addEventListener('change', (e) => {
      const alvo = e.target.dataset?.anexar
      if (!alvo) return
      this.anexar(e.target.files, alvo)
      e.target.value = ''
    })
    // colar (⌘V) ou arrastar um print ou vídeo na caixa do comentário novo ou no comentário sendo editado
    const alvoDe = (el) => (el?.closest?.('.caixa-nova') ? 'nova' : el?.closest?.('.editor') ? 'editor' : null)
    this.tela.addEventListener('paste', (e) => {
      const alvo = alvoDe(e.target)
      const arquivos = [...(e.clipboardData?.files || [])]
      if (!alvo || !arquivos.some((f) => /^(image|video)\//.test(f.type))) return // texto: cola normal
      e.preventDefault()
      this.anexar(arquivos, alvo)
    })
    const comArquivo = (e) => [...(e.dataTransfer?.types || [])].includes('Files')
    this.tela.addEventListener('dragover', (e) => {
      const alvo = alvoDe(e.target)
      if (!alvo || !comArquivo(e)) return
      e.preventDefault()
      e.target.closest('.caixa-nova, .editor').classList.add('soltando')
    })
    this.tela.addEventListener('dragleave', (e) => e.target.closest?.('.caixa-nova, .editor')?.classList.remove('soltando'))
    this.tela.addEventListener('drop', (e) => {
      const alvo = alvoDe(e.target)
      if (!alvo || !comArquivo(e)) return
      e.preventDefault()
      e.target.closest('.caixa-nova, .editor').classList.remove('soltando')
      this.anexar(e.dataTransfer.files, alvo)
    })
    // o seletor de versões fecha ao clicar fora
    this.foraMenu = (e) => this.menuVersoes && !e.target.closest?.('.seletor-versao') && this.alternarVersoes(false)
    document.addEventListener('click', this.foraMenu)

    // clicar/arrastar na linha do tempo busca; ⌘/Ctrl + rolagem aproxima
    const conteudo = $('#conteudo')
    // clicar busca; arrastar na régua percorre o vídeo; arrastar nas faixas marca um trecho (como I e O)
    conteudo.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.marca, .bloco-faixa') || e.button !== 0) return
      e.preventDefault()
      const tDe = (ev) => Math.min(Math.max((ev.clientX - conteudo.getBoundingClientRect().left) / this.pxs, 0), this.dur)
      const naRegua = !!e.target.closest('#regua')
      const x0 = e.clientX
      const t0 = tDe(e)
      let trecho = false
      this.buscar(t0)
      conteudo.setPointerCapture(e.pointerId)
      const mover = (ev) => {
        if (!naRegua && !trecho && Math.abs(ev.clientX - x0) > 4) {
          trecho = true
          this.video.pause()
          this.buscar(t0)
          this.marcarEntrada(true)
        }
        this.buscar(tDe(ev))
        if (trecho) this.renderMarcas()
      }
      const soltar = () => {
        conteudo.removeEventListener('pointermove', mover)
        conteudo.removeEventListener('pointerup', soltar)
        if (trecho) {
          if (Math.abs(this.video.currentTime - this.entrada) < 0.05) return this.soltarNova()
          this.marcarSaida()
        }
      }
      conteudo.addEventListener('pointermove', mover)
      conteudo.addEventListener('pointerup', soltar)
    })
    const rolo = $('#rolo')
    rolo.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()
        this.zoom(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - rolo.getBoundingClientRect().left)
      } else if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && rolo.scrollWidth > rolo.clientWidth) {
        e.preventDefault()
        rolo.scrollLeft += e.deltaY
      }
    }, { passive: false })
  }

  clique(e) {
    if (e.target === this.video) return this.alternar()
    const b = e.target.closest('button, a, [data-ir]')
    const editor = e.target.closest('.editor')
    if (!b || (editor && !editor.contains(b))) return // dentro do campo de comentário, só os botões dele
    if (b.tagName === 'BUTTON') b.blur()
    if (b.dataset.versaoBloco) preferencia(`painel.${this.slug}.v${b.dataset.versaoBloco}`, null, { bloco: this.blocoSel, irAoBloco: true }) // lá, o bloco segue escolhido, desde o começo
    if (b.classList.contains('item-versao')) return setTimeout(() => this.alternarVersoes(false)) // a versão abre pelo endereço
    const d = b.dataset
    if (d.acao) return this.acao(d.acao)
    if (d.vel) {
      this.video.playbackRate = +d.vel
      for (const x of $$('[data-vel]')) x.classList.toggle('ativa', x === b)
      return
    }
    if (d.ampliar) return this.ampliar(d.ampliar)
    if (d.verMidia) return this.verMidia(d.verMidia)
    if (d.verClipe) {
      this.video.pause()
      return janela(`<button class="botao-icone anexo-fechar" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button><video class="anexo-grande" src="${d.verClipe}" autoplay loop playsinline controls></video>`, { classe: 'janela-anexo' })
    }
    if (d.tirarAnexo) {
      const k = d.tirarAnexo.indexOf('|')
      return this.tirarAnexo(d.tirarAnexo.slice(0, k), d.tirarAnexo.slice(k + 1))
    }
    if (d.editar) {
      const c = this.rev.comentarios.find((x) => x.id === d.editar)
      return c && this.abrirEditor({ id: c.id, t: c.t, fim: c.fim, geral: c.geral, texto: c.texto, anexos: [...(c.anexos || [])] })
    }
    if (d.apagar) return this.apagar(d.apagar)
    if (d.aprovarBloco) return this.aprovarBloco(d.aprovarBloco)
    if (d.loopBloco) return this.alternarLoop(d.loopBloco)
    if (d.sairBloco != null) return this.escolherBloco(null)
    if (d.bloco) {
      this.buscar(+d.ir)
      return this.escolherBloco(d.bloco)
    }
    if (d.marca) return this.selecionar(d.marca, +d.ir)
    if (d.ir != null) {
      const item = b.closest('.item')
      if (window.getSelection()?.toString()) return // selecionando texto
      return this.selecionar(item?.dataset.id || null, +d.ir)
    }
  }

  acao(nome) {
    const a = {
      tocar: () => this.alternar(),
      'quadro-': () => this.passo(-QUADRO),
      'quadro+': () => this.passo(QUADRO),
      look: () => this.abrirLook(),
      'corte-': () => this.irAoCorte(-1),
      'corte+': () => this.irAoCorte(1),
      ajustar: () => this.zoom(0),
      'alternar-tempo': () => this.alternarTempo(true),
      soltar: () => this.soltarNova(),
      'salvar-nova': () => this.salvarNova(),
      entrada: () => this.marcarEntrada(),
      saida: () => this.marcarSaida(),
      'zoom-': () => this.zoom(1 / 1.6),
      'zoom+': () => this.zoom(1.6),
      cancelar: () => this.fecharEditor(),
      'salvar-editor': () => this.salvarEditor(),
      aprovar: () => this.aprovar(),
      versoes: () => this.alternarVersoes(),
    }[nome]
    a?.()
  }

  tecla(e) {
    if (modalAberto()) return
    const campo = e.target.closest?.('input, textarea, select, [contenteditable]')
    if (campo) {
      const enter = e.key === 'Enter' && !e.shiftKey && !e.isComposing
      if (campo.id === 'editor-texto' && enter) {
        e.preventDefault()
        this.salvarEditor()
        document.activeElement?.blur?.()
      } else if (campo.id === 'nova-texto' && enter) {
        e.preventDefault()
        this.salvarNova()
        campo.blur() // sai da caixa: o Espaço volta a tocar o vídeo
      } else if (e.key === 'Escape') {
        e.preventDefault()
        if (campo.id === 'editor-texto') this.fecharEditor()
        else {
          campo.blur()
          if (campo.id === 'nova-texto' && !campo.value.trim() && !this.nova.anexos.length) this.soltarNova()
        }
      }
      return
    }
    if ((e.metaKey || e.ctrlKey) && !e.altKey && ['=', '+', '-', '_', '0'].includes(e.key)) {
      e.preventDefault() // ⌘+ ⌘− ⌘0: o zoom da linha do tempo, não o da página
      return this.zoom(e.key === '0' ? 0 : e.key === '-' || e.key === '_' ? 0.8 : 1.25)
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key
    const f = {
      ' ': () => this.alternar(),
      ArrowLeft: () => (e.shiftKey ? this.irAoCorte(-1) : this.passo(-QUADRO)),
      ArrowRight: () => (e.shiftKey ? this.irAoCorte(1) : this.passo(QUADRO)),
      r: () => this.replano(),
      c: () => this.alternarTempo(true),
      i: () => this.marcarEntrada(),
      o: () => this.marcarSaida(),
      Escape: () => {
        if (this.menuVersoes) this.alternarVersoes(false)
        else if (this.editor) this.fecharEditor()
        else if (this.entrada != null || this.nova.preso) this.soltarNova()
        else if (this.sel) this.selecionar(null)
      },
    }[k]
    if (f) {
      e.preventDefault()
      f()
    }
  }

  /** Ao sair da página: o instante do vídeo, o rascunho da caixa (texto, instante preso, prints) e onde o painel estava
   *  (o bloco escolhido, o comentário sendo editado com o texto e a rolagem) desta versão. */
  guardarPosicao() {
    if (!this.video) return
    preferencia(`posicao.${this.slug}.v${this.v}`, 0, +this.video.currentTime.toFixed(3))
    const texto = $('#nova-texto')?.value || ''
    preferencia(`rascunho.${this.slug}.v${this.v}`, null, texto.trim() || this.nova.anexos.length ? { ...this.nova, texto } : null)
    const editor = this.editor ? { ...this.editor, texto: $('#editor-texto')?.value ?? this.editor.texto } : null
    preferencia(`painel.${this.slug}.v${this.v}`, null, { bloco: this.blocoSel || null, sel: this.sel, editor, rolagem: $('#lista')?.scrollTop || 0 })
  }

  /** Volta o painel para onde estava ao sair (guardarPosicao): o bloco, o editor aberto com o texto e a rolagem. */
  voltarPainel() {
    const p = preferencia(`painel.${this.slug}.v${this.v}`, null)
    if (!p) return
    this.sel = p.sel ?? null
    if (p.editor && (!p.editor.id || this.rev.comentarios.some((c) => c.id === p.editor.id))) this.editor = p.editor
    const bloco = this.blocos?.find((b) => b.id === p.bloco)
    if (bloco) {
      this.blocoSel = bloco.id
      this.carregarVersoesBlocos().then(() => !this.fechado && this.renderVersoes())
      if (p.irAoBloco) this.video.addEventListener('loadedmetadata', () => this.buscar(bloco.ini), { once: true })
    }
    this.renderLista()
    this.renderMarcas()
    requestAnimationFrame(() => $('#lista') && ($('#lista').scrollTop = p.rolagem || 0)) // depois do foco no campo aberto
  }

  fechar() {
    $('#barra-versao').removeEventListener('click', this.cliques)
    this.guardarPosicao()
    this.fechado = true
    if (this.sujo) this.salvar(true)
    clearInterval(this.relogio)
    clearInterval(this.relogioRender)
    clearTimeout(this.timer)
    cancelAnimationFrame(this.raf)
    window.removeEventListener('keydown', this.teclas)
    window.removeEventListener('resize', this.redim)
    window.removeEventListener('pagehide', this.saida)
    document.removeEventListener('click', this.foraMenu)
    this.video.pause()
    this.video.removeAttribute('src')
    this.video.load()
  }
}
