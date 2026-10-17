// A Calibragem: os Reels já editados do criador (as referências). A IA descobre como cada um foi dirigido; aqui ele sobe
// os vídeos, acompanha a análise e revisa a direção de cada um (planos-base, elementos, marcação). Cada referência
// revisada vira um roteiro de exemplo que o Claude lê antes de dirigir (ferramentas/calibragem.py regenera sozinho).
import { $, $$, ELEMENTOS, ICONE, ICONE_ATALHO, PLANOS, barraDaLinha, ajuda, aviso, chipCodigo, codigos, confirmar, dataHora, enviar, esc, modalAberto, mmss, nomePlano, num, preferencia, tempo, tocarTrecho, urlRef } from './comum.js'
import { botaoCategorias, carregarCategorias, editarCategorias, pilulasCategoria, seletorCategoria } from './categorias.js'

const STATUS = {
  na_fila: ['Na fila', 'selo-amarelo'],
  analisando: ['Analisando', 'selo-azul-claro'],
  a_revisar: ['A revisar', 'selo-coral'],
  revisado: ['Revisado', 'selo-menta'],
  erro: ['Erro', 'selo-erro'],
}
const PASSOS = { proxy: 'Preparando o vídeo', transcricao: 'Transcrevendo', cenas: 'Detectando cortes', analise: 'Analisando trechos', montagem: 'Montando a direção', inserts: 'Descrevendo os inserts' }
const VIDEO = /\.(mp4|mov|m4v|webm)$/i
const emAndamento = (r) => r.status === 'na_fila' || r.status === 'analisando'
const abrivel = (r) => r.status === 'a_revisar' || r.status === 'revisado'
/** "do projeto <slug> · vN" numa referência que veio de um projeto aprovado (calibragem.py de-projeto). */
const seloOrigem = (o, classe) => (o?.projeto
  ? `<span class="${classe} selo-origem" title="Veio da v${o.versao} ${o.aprovado_em ? `aprovada em ${dataHora(o.aprovado_em)}` : '(não aprovada no app)'} do projeto ${esc(o.projeto)}">do projeto ${esc(o.projeto)} · v${o.versao}</span>`
  : '')

// ---------- a grade ----------

const OLHO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/></svg>'
const OLHO_FECHADO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="m2 2 20 20"/></svg>'

/** O interruptor "Ensina" do card: ligado, o vídeo entra nos roteiros de exemplo da Heurística (que a direção lê). */
const interruptor = (r) => {
  const liga = r.ensina !== false
  return `<button class="interruptor${liga ? ' ligado' : ''}" role="switch" aria-checked="${liga}" data-ensina
    title="${liga ? 'Ativo: entra nos exemplos da direção (clique para desativar)' : 'Inativo: fora dos exemplos da direção (clique para ativar)'}"><span>${liga ? 'Ativo' : 'Inativo'}</span><i></i></button>`
}

export async function abrirCalibragem(tela) {
  tela.className = 'pagina pagina-calibragem'
  let refs = []
  let assinatura = ''
  let recusadas = []
  let enviando = null // "2/3" enquanto sobe
  let editando = null // o id sendo renomeado (a grade não se redesenha por cima)
  let cod = {}
  // a categoria de vídeo (Reels, Ad…): filtra a grade, e os vídeos que sobem entram nela
  let cats = []
  let filtro = preferencia('calibragem.categoria', '')
  let verOcultos = false // a vista dos ocultos (fora da direção: os vídeos que não quer usar por ora)

  const card = (r) => {
    const [rotulo, cor] = STATUS[r.status] || [r.status, 'selo-coral']
    const passo = r.passo ? `${PASSOS[r.passo] || r.passo_rotulo || r.passo}${r.passo === 'analise' && r.passos?.analise?.total ? ` ${r.passos.analise.feitos || 0}/${r.passos.analise.total}` : r.progresso != null ? ` ${Math.round(r.progresso * 100)}%` : ''}` : ''
    const mini = `<div class="mini mini-916">${r.miniatura ? `<img src="${r.miniatura}" alt="" loading="lazy">` : ''}
        <span class="selo ${cor}">${rotulo}</span>${r.duracao ? `<span class="duracao">${mmss(r.duracao)}</span>` : ''}
        ${r.status === 'analisando' || r.status === 'na_fila' ? `<span class="progresso"><i style="width:${Math.round((r.progresso ?? 0) * 100)}%"></i></span>` : ''}
        <span class="acoes-card"><button class="botao-icone pequeno" data-ocultar title="${r.oculto ? 'Mostrar de novo (volta a ensinar a direção)' : 'Ocultar (sai da grade e da direção)'}">${r.oculto ? OLHO : OLHO_FECHADO}</button>
          <button class="botao-icone pequeno" data-renomear title="Renomear">${ICONE.lapis}</button>
          <button class="botao-icone pequeno" data-apagar title="Apagar">${ICONE.lixo}</button></span>
        ${r.oculto ? '' : interruptor(r)}</div>`
    return `<article class="card-ref${abrivel(r) ? ' abrivel' : ''}" data-id="${esc(r.id)}">
      ${abrivel(r) ? `<a href="#/calibragem/${encodeURIComponent(r.id)}" title="Abrir a revisão">${mini}</a>` : mini}
      ${editando === r.id ? `<input class="renomear" value="${esc(r.nome)}" maxlength="120">` : `<div class="card-titulo"><h3 data-renomear title="Dois cliques para renomear">${esc(r.nome)}</h3><span class="sub data-ref" title="${r.largura ? `${r.largura}×${r.altura}` : ''}">${emAndamento(r) ? esc(passo || 'Na fila') : esc(dataHora(r.criado_em).slice(0, 5))}</span></div>`}
      <div class="pe-ref">${seletorCategoria(cats, r.tipo || 'reels')}${chipCodigo(cod[r.id], r.nome)}</div>
      ${r.status === 'erro' ? `<p class="erro-ref">${esc(r.erro || 'A análise falhou.')}</p><button class="botao pequeno" data-tentar>${ICONE.refazer} Tentar de novo</button>` : ''}
    </article>`
  }

  const desenhar = () => {
    const naVista = refs.filter((r) => !!r.oculto === verOcultos)
    const visiveis = naVista.filter((r) => !filtro || (r.tipo || 'reels') === filtro)
    // dois grupos: os ativos (ensinam a direção) em cima, os inativos embaixo; dentro de cada um, a ordem de sempre
    const grupos = [['Ativos', visiveis.filter((r) => r.ensina !== false)], ['Inativos', visiveis.filter((r) => r.ensina === false)]].filter(([, l]) => l.length)
    const nOcultos = refs.filter((r) => r.oculto).length
    const n = (s) => visiveis.filter((r) => r.status === s).length
    const numeros = [[n('revisado'), 'revisada', 'revisadas'], [n('a_revisar'), 'a revisar', 'a revisar'], [n('analisando'), 'analisando', 'analisando'], [n('na_fila'), 'na fila', 'na fila'], [n('erro'), 'com erro', 'com erro']]
      .filter(([q]) => q).map(([q, um, varios]) => `${q} ${q === 1 ? um : varios}`).join(' · ')
    tela.innerHTML = `<div class="cabeca-secao"><span class="eyebrow">Calibragem · ${String(visiveis.length).padStart(2, '0')} vídeos${numeros ? ` <span class="numeros">· ${numeros}</span>` : ''}</span>
        ${pilulasCategoria(cats, filtro, { contar: (id) => naVista.filter((r) => !id || (r.tipo || 'reels') === id).length })}
        <button class="pilula pequena${verOcultos ? ' ativa' : ''}" data-ver-ocultos title="Os vídeos que você ocultou">${OLHO_FECHADO} Ocultos <span class="conta">${nOcultos}</span></button>${botaoCategorias()}
        ${ajuda('Seus Reels já editados: a IA descobre como cada um foi dirigido, você corrige e marca como revisado. Cada um vira um roteiro de exemplo que o Claude lê antes de dirigir.')}
        <label class="botao botao-coral"><input type="file" accept="video/*,.mp4,.mov,.m4v,.webm" multiple hidden>${enviando ? `Enviando ${enviando}…` : `${ICONE.subir} Adicionar vídeos`}</label></div>
      ${recusadas.length ? `<div class="caixa-erro"><b>${recusadas.length} ${recusadas.length === 1 ? 'vídeo não entrou' : 'vídeos não entraram'}:</b><ul>${recusadas.map((x) => `<li><b>${esc(x.nome)}</b> — ${esc(x.motivo)}</li>`).join('')}</ul><button class="botao pequeno" data-ok>ok</button></div>` : ''}
      ${visiveis.length ? grupos.map(([g, l]) => `<h4 class="grupo-data">${g} · ${l.length}</h4><div class="grade grade-projetos">${l.map(card).join('')}</div>`).join('') : verOcultos ? '<p class="vazio">Nenhum vídeo oculto.</p>' : refs.length ? '<p class="vazio">Nenhum vídeo desta categoria ainda: os que você subir agora entram nela.</p>' : '<p class="vazio">Nenhuma referência ainda. Comece com 5 a 10 Reels editados que você considera bons: arraste os vídeos para cá.</p>'}
      <div class="soltar-aqui">Solte os vídeos para analisar</div>`
    const campo = $('.renomear', tela)
    if (campo) {
      campo.focus()
      campo.select()
    }
  }

  const carregar = async () => {
    let l
    try {
      l = await enviar('GET', '/api/referencias')
      if (l.some((r) => !cod[r.id])) cod = (await codigos()).referencia || {}
    } catch (e) {
      tela.innerHTML = `<p class="vazio">${esc(e.message)}</p>`
      return
    }
    const a = JSON.stringify(l)
    if (a === assinatura) return
    assinatura = a
    refs = l
    if (!editando) desenhar()
  }

  const subir = async (arquivos) => {
    const videos = [...arquivos].filter((f) => VIDEO.test(f.name) || f.type.startsWith('video/'))
    recusadas = [...arquivos].filter((f) => !videos.includes(f)).map((f) => ({ nome: f.name, motivo: 'não é um vídeo (mp4, mov, m4v ou webm)' }))
    for (const [k, f] of videos.entries()) {
      enviando = `${k + 1}/${videos.length}`
      desenhar()
      try {
        const r = await fetch('/api/referencias', { method: 'POST', headers: { 'X-Nome': encodeURIComponent(f.name), 'X-Categoria': encodeURIComponent(filtro || 'reels'), 'Content-Type': 'application/octet-stream' }, body: f })
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(d.erro || `Erro ${r.status}`)
      } catch (e) {
        recusadas.push({ nome: f.name, motivo: e.message })
      }
      assinatura = ''
      await carregar()
    }
    enviando = null
    assinatura = ''
    await carregar()
    desenhar()
    if (videos.length > recusadas.length) aviso('Na fila: a análise começa sozinha')
  }

  const renomear = async (id, nome) => {
    editando = null
    const r = refs.find((x) => x.id === id)
    if (r && nome && nome !== r.nome) {
      try {
        await enviar('PUT', `/api/referencias/${encodeURIComponent(id)}/nome`, { nome })
        r.nome = nome
      } catch (e) {
        aviso(e.message, 'erro')
      }
    }
    assinatura = ''
    desenhar()
    carregar()
  }

  tela.addEventListener('click', async (e) => {
    const c = e.target.closest('.card-ref')
    const id = c?.dataset.id
    if (e.target.closest('[data-ok]')) {
      recusadas = []
      return desenhar()
    }
    if (e.target.closest('[data-ver-ocultos]')) {
      verOcultos = !verOcultos
      return desenhar()
    }
    const f = e.target.closest('[data-categoria]')
    if (f) {
      filtro = preferencia('calibragem.categoria', '', f.dataset.categoria)
      return desenhar()
    }
    if (e.target.closest('[data-editar-categorias]'))
      return editarCategorias(cats, async () => {
        cats = await carregarCategorias()
        desenhar()
      })
    if (!c) return
    if (e.target.closest('.acoes-card [data-renomear]')) {
      e.preventDefault()
      editando = id
      return desenhar()
    }
    if (e.target.closest('[data-apagar]')) {
      e.preventDefault()
      const r = refs.find((x) => x.id === id)
      const ok = await confirmar({ titulo: `Apagar “${r.nome}”?`, texto: 'A referência sai da calibragem, das Referências e dos roteiros de exemplo (vai para a lixeira da biblioteca).', ok: 'Apagar', perigo: true })
      if (!ok) return
      try {
        await enviar('DELETE', `/api/referencias/${encodeURIComponent(id)}`)
        aviso('Referência apagada')
      } catch (x) {
        aviso(x.message, 'erro')
      }
      assinatura = ''
      return carregar()
    }
    if (e.target.closest('[data-ocultar]')) {
      e.preventDefault()
      const r = refs.find((x) => x.id === id)
      try {
        await enviar('PUT', `/api/referencias/${encodeURIComponent(id)}/oculto`, { oculto: !r.oculto })
        aviso(r.oculto ? 'De volta: entra na direção da categoria' : 'Ocultado: saiu da direção (está em Ocultos)')
      } catch (x) {
        aviso(x.message, 'erro')
      }
      assinatura = ''
      return carregar()
    }
    if (e.target.closest('[data-ensina]')) {
      e.preventDefault()
      const r = refs.find((x) => x.id === id)
      const liga = r.ensina === false
      try {
        await enviar('PUT', `/api/referencias/${encodeURIComponent(id)}/ensina`, { ensina: liga })
        aviso(liga ? 'Entra nos exemplos da direção' : 'Sai dos exemplos da direção')
      } catch (x) {
        aviso(x.message, 'erro')
      }
      assinatura = ''
      return carregar()
    }
    if (e.target.closest('[data-tentar]')) {
      try {
        await enviar('POST', `/api/referencias/${encodeURIComponent(id)}/tentar`)
        aviso('De volta à fila')
      } catch (x) {
        aviso(x.message, 'erro')
      }
      assinatura = ''
      return carregar()
    }
  })
  tela.addEventListener('dblclick', (e) => {
    const h = e.target.closest('h3[data-renomear]')
    if (!h) return
    editando = h.closest('.card-ref').dataset.id
    desenhar()
  })
  tela.addEventListener('keydown', (e) => {
    const campo = e.target.closest('.renomear')
    if (!campo) return
    if (e.key === 'Enter') renomear(editando, campo.value.trim())
    if (e.key === 'Escape') {
      editando = null
      desenhar()
    }
  })
  tela.addEventListener('focusout', (e) => {
    const campo = e.target.closest('.renomear')
    if (campo && editando) renomear(editando, campo.value.trim())
  })
  tela.addEventListener('change', async (e) => {
    if (e.target.type === 'file') return subir(e.target.files)
    if (!e.target.matches('[data-mudar-categoria]')) return
    const id = e.target.closest('.card-ref').dataset.id
    try {
      await enviar('PUT', `/api/referencias/${encodeURIComponent(id)}/categoria`, { categoria: e.target.value })
      aviso('Categoria mudada: os roteiros de exemplo dela foram para a pasta da categoria')
    } catch (x) {
      aviso(x.message, 'erro')
    }
    assinatura = ''
    carregar()
  })
  // arrastar arquivos para qualquer lugar da página
  let dentro = 0
  const temArquivos = (e) => [...(e.dataTransfer?.types || [])].includes('Files')
  tela.addEventListener('dragenter', (e) => {
    if (!temArquivos(e)) return
    dentro++
    tela.classList.add('soltando')
  })
  tela.addEventListener('dragleave', () => --dentro <= 0 && tela.classList.remove('soltando'))
  tela.addEventListener('dragover', (e) => temArquivos(e) && e.preventDefault())
  tela.addEventListener('drop', (e) => {
    if (!temArquivos(e)) return
    e.preventDefault()
    dentro = 0
    tela.classList.remove('soltando')
    subir(e.dataTransfer.files)
  })

  tela.innerHTML = '<p class="vazio">Carregando…</p>'
  cats = await carregarCategorias()
  if (filtro && !cats.some((c) => c.id === filtro)) filtro = ''
  await carregar()
  // a cada 2 s enquanto alguma está na fila ou analisando (e logo depois de subir)
  const relogio = setInterval(() => !document.hidden && (enviando || refs.some(emAndamento)) && carregar(), 2000)
  return () => clearInterval(relogio)
}

// ---------- a revisão de uma referência ----------

// a barra acima da linha do tempo da direção (comum.js): os atalhos da revisão do vídeo e os desta tela
const ATALHOS_REF = () => [
  ['R', 'plano', ICONE_ATALHO.plano], ['S', 'dividir', ICONE.tesoura], ['E', 'elemento', ICONE.mais], ['⌘Z', 'desfazer', ICONE.desfazer],
  ['Espaço', 'tocar', ICONE.tocar], ['← →', 'quadro', ICONE.quadroDepois], ['⇧ ← →', 'corte', ICONE.segDepois], ['⌘ rolar', 'zoom', ICONE_ATALHO.zoom],
]

const MIN_PLANO = 0.101 // um pouco acima do mínimo do servidor (0,1 s): a conta em ponto flutuante não pode ficar abaixo
const MIN_ELEMENTO = 0.051
const IMA_PX = 6
const r3 = (t) => Math.round(t * 1000) / 1000
const COM_TEXTO = ['full_ator_lettering', 'comentario_insert_ator']
const COM_INSERT = ['insert_tela_cheia', 'tela_dividida_insert', 'comentario_insert_ator']

export async function abrirRevisaoReferencia(tela, id) {
  let d
  try {
    d = await enviar('GET', `/api/referencias/${encodeURIComponent(id)}/revisao`)
  } catch (e) {
    tela.className = 'pagina'
    tela.innerHTML = `<p class="vazio">${esc(e.message)}. <a href="#/calibragem">Voltar à Calibragem</a></p>`
    return null
  }
  const r = new RevisaoReferencia(tela, id, d, ((await codigos()).referencia || {})[id])
  r.abrir()
  return () => r.fechar()
}

class RevisaoReferencia {
  constructor(tela, id, d, codigo) {
    Object.assign(this, { tela, id, ref: d.referencia, codigo })
    this.base = d.base || urlRef(id, '')
    this.itens = d.itens.map((i) => ({ ...i }))
    this.cortes = (Array.isArray(d.cortes) ? d.cortes : d.cortes?.cortes || []).map(Number)
    this.palavras = (d.palavras?.palavras || d.palavras || []).map((w) => ({ id: w.id, texto: w.texto, ini: w.inicio ?? w.ini, fim: w.fim })).sort((a, b) => a.ini - b.ini)
    this.dur = this.ref.video?.duracao || this.planos().at(-1)?.fim || 60
    this.pxs = 1
    this.ajustar = true
    this.historico = []
    this.sel = this.planos()[0]?.id
    this.fila = Promise.resolve()
    this.sujo = false
    this.versao = 0 // sobe a cada mudança: a resposta de um salvamento antigo não sobrescreve o que veio depois
    this.imas = [...this.cortes, ...this.palavras.flatMap((w) => [w.ini, w.fim])].sort((a, b) => a - b)
  }

  planos = () => this.itens.filter((i) => i.camada === 'plano').sort((a, b) => a.inicio - b.inicio)
  elementos = () => this.itens.filter((i) => i.camada === 'elemento').sort((a, b) => a.inicio - b.inicio)
  item = (id) => this.itens.find((i) => i.id === id)
  nomeTipo = (i) => (i.camada === 'plano' ? nomePlano(i.tipo) : ELEMENTOS[i.tipo] || i.tipo)

  /** Os comentários das revisões do projeto de origem (referencia.json `revisoes`), num painel recolhível. */
  htmlCorrecoes() {
    const cs = this.ref.revisoes || []
    if (!this.ref.origem?.projeto || !cs.length) return ''
    return `<details class="sanfona correcoes"><summary>${ICONE.seta_baixo}<b>O que o criador corrigiu</b><span class="conta">${cs.length}</span></summary>
      <div class="lista-correcoes">${cs.map((c) => `<div class="correcao"><span class="dica">v${c.versao}${c.tempo != null ? ` · ${tempo(c.tempo)}` : ' · geral'}</span>
        <p>${esc(c.texto)}</p>${c.resposta ? `<p class="resposta-correcao">↳ ${esc(c.resposta)}</p>` : ''}</div>`).join('')}</div></details>`
  }

  abrir() {
    this.tela.className = 'pagina-revisao'
    this.tela.innerHTML = `<div class="revisao revisao-ref">
      <section class="palco">
        <div class="lado lado-esq">
          <div class="bloco"><span class="eyebrow">No cursor</span><div id="plano-atual" class="plano-atual"></div></div>
          <div class="bloco"><span class="eyebrow">Fala</span><p id="fala-atual" class="fala-atual"></p></div>
        </div>
        <div class="video-caixa"><video id="video" src="${urlRef(this.id, 'proxy.mp4')}" preload="auto" playsinline></video>
          <button class="video-tocar" aria-label="Tocar">${ICONE.tocar}</button></div>
        <div class="lado lado-dir">${this.htmlCorrecoes()}
          <div class="bloco"><span class="eyebrow">Arrastar</span><p class="dica">A borda entre dois planos muda o momento da troca; as pontas de um elemento, a duração. O ímã gruda nas palavras e nos cortes de cena (tracejados); <kbd>Alt</kbd> solta.</p></div>
        </div>
      </section>
      <div class="controles">
        <div class="grupo">
          <button class="botao-icone" data-acao="corte-" title="O corte anterior (Shift+←)">${ICONE.segAntes}</button>
          <button class="botao-icone" data-acao="passo-" title="−1 quadro (←)">${ICONE.quadroAntes}</button>
          <button class="botao-icone botao-tocar" data-acao="tocar" id="b-tocar" title="Tocar / pausar (Espaço)">${ICONE.tocar}</button>
          <button class="botao-icone" data-acao="passo+" title="+1 quadro (→)">${ICONE.quadroDepois}</button>
          <button class="botao-icone" data-acao="corte+" title="O próximo corte (Shift+→)">${ICONE.segDepois}</button>
          <span class="tempo"><b id="t-atual">0:00,0</b> / <span>${tempo(this.dur)}</span></span>
        </div>
        <div class="grupo velocidades">${[0.5, 1, 2].map((x) => `<button class="pilula pequena${x === 1 ? ' ativa' : ''}" data-vel="${x}">${num(x, x % 1 ? 1 : 0)}×</button>`).join('')}</div>
        <div class="grupo">
          <button class="botao" data-acao="dividir" title="Divide o plano no cursor em dois">${ICONE.tesoura} Dividir plano <kbd>S</kbd></button>
          <button class="botao" data-acao="elemento">${ICONE.mais} Elemento <kbd>E</kbd></button>
          <button class="botao" data-acao="desfazer" id="b-desfazer" title="Desfazer (⌘Z)">${ICONE.desfazer} Desfazer</button>
        </div>
      </div>
      <section class="linha linha-ref">
        ${barraDaLinha(ATALHOS_REF())}
        <div class="linha-rotulos"><span class="r-regua"></span><span class="r-planos">Planos</span><span id="r-elementos">Elementos</span><span>Fala</span></div>
        <div class="linha-rolo" id="rolo"><div class="linha-conteudo" id="conteudo">
          <div class="regua" id="regua"></div>
          <div class="faixa faixa-planos" id="f-planos"></div>
          <div class="faixa faixa-elementos" id="f-elementos"></div>
          <div class="faixa faixa-palavras" id="f-palavras"></div>
          <div id="f-cortes"></div>
          <div class="cabeca" id="cabeca"></div>
        </div></div>
      </section>
      <aside class="painel"><div class="painel-acoes painel-acoes-ref">${`<div class="trilha-projeto"><a href="#/calibragem" class="botao-icone" title="Calibragem">${ICONE.voltar}</a>
        <span class="nome-projeto">${esc(this.ref.nome)}</span>${chipCodigo(this.codigo, this.ref.nome)}${seloOrigem(this.ref.origem, 'selo-linha selo-azul')}<span class="dica">referência · ${mmss(this.dur)}</span></div>`}<div class="acoes-ref">${`<span class="salvo" id="salvo"></span>
      <button class="botao" data-acao="reanalisar" title="A IA refaz a análise deste vídeo do zero (o proxy e a transcrição ficam)">${ICONE.refazer} Reanalisar</button>
      <button class="botao" data-acao="revisada" id="b-revisada"></button>`}</div></div><div id="detalhe" class="detalhe"></div></aside>
    </div>`
    this.video = $('#video')
    this.renderBotoes()
    this.renderLinha()
    this.renderDetalhe()
    this.ligar()
    this.mostrarSalvo('')
  }

  // ---------- a tela ----------

  renderBotoes() {
    const b = $('#b-revisada')
    const revisado = this.ref.status === 'revisado'
    b.innerHTML = revisado ? `${ICONE.check} Revisada · desmarcar` : `${ICONE.check} Marcar como revisada`
    b.className = `botao ${revisado ? 'botao-menta' : 'botao-coral'}`
    b.disabled = this.sujo
    $('#b-desfazer').disabled = !this.historico.length
  }

  renderLinha() {
    const rolo = $('#rolo')
    const ajuste = Math.max(rolo.clientWidth - 2, 100) / this.dur
    if (this.ajustar || this.pxs < ajuste) {
      this.pxs = ajuste
      this.ajustar = true
    }
    $('#conteudo').style.width = `${this.dur * this.pxs}px`
    this.renderRegua()
    this.renderPlanos()
    this.renderElementos()
    this.renderPalavras()
    $('#f-cortes').innerHTML = this.cortes.map((c) => `<span class="corte-cena" style="left:${(c * this.pxs).toFixed(1)}px" title="Corte de cena ${tempo(c)}"></span>`).join('')
    this.iPalavra = this.iPlano = -2
    this.atualizar()
  }

  renderRegua() {
    const px = this.pxs
    const passo = [0.5, 1, 2, 5, 10, 15, 30, 60].find((s) => s * px >= 56) || 60
    const sub = passo >= 5 ? passo / 5 : passo / 2
    let html = ''
    for (let t = 0; t <= this.dur + 1e-6; t += sub) {
      const grande = Math.round(t / sub) % Math.round(passo / sub) === 0
      if (!grande && sub * px < 6) continue
      const rotulo = grande ? (passo < 1 ? tempo(t) : `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}`) : ''
      html += `<span class="tique${grande ? ' tique-grande' : ''}" style="left:${(t * px).toFixed(1)}px">${rotulo ? `<i>${rotulo}</i>` : ''}</span>`
    }
    $('#regua').innerHTML = html
  }

  renderPlanos() {
    const ps = this.planos()
    $('#f-planos').innerHTML = ps.map((p, k) => {
      const x = p.inicio * this.pxs
      const w = Math.max((p.fim - p.inicio) * this.pxs - 1, 1)
      const [nome, curto] = PLANOS[p.tipo] || [p.tipo, p.tipo]
      const rot = w >= 120 ? esc(nome) : w >= 60 ? esc(curto) : ''
      const dica = `${nome} · ${tempo(p.inicio)}–${tempo(p.fim)}${p.texto ? `\n“${p.texto}”` : ''}${p.descricao ? `\n${p.descricao}` : ''}`
      return `<div class="plano tipo-${esc(p.tipo)}${this.sel === p.id ? ' plano-sel' : ''}" data-item="${p.id}" style="left:${x.toFixed(1)}px;width:${w.toFixed(1)}px" title="${esc(dica)}">${rot}</div>
        ${k < ps.length - 1 ? `<span class="borda" data-borda="${k}" style="left:${(p.fim * this.pxs).toFixed(1)}px" title="Arraste para mudar a troca"></span>` : ''}`
    }).join('')
  }

  /** Os elementos em faixas (os que se sobrepõem ficam um embaixo do outro). */
  renderElementos() {
    const fins = []
    const html = this.elementos().map((e) => {
      let k = fins.findIndex((f) => f <= e.inicio + 1e-6)
      if (k < 0) k = fins.length
      fins[k] = e.fim
      const x = e.inicio * this.pxs
      const w = Math.max((e.fim - e.inicio) * this.pxs, 6)
      return `<div class="elemento el-${esc(e.tipo)}${this.sel === e.id ? ' elemento-sel' : ''}" data-item="${e.id}" style="left:${x.toFixed(1)}px;width:${w.toFixed(1)}px;top:${k * 22}px" title="${esc(`${ELEMENTOS[e.tipo] || e.tipo} · ${tempo(e.inicio)}–${tempo(e.fim)}${e.texto ? ` · “${e.texto}”` : ''}`)}">
        <span class="ponta" data-ponta="inicio"></span>${w > 40 ? esc(e.texto || ELEMENTOS[e.tipo] || e.tipo) : ''}<span class="ponta ponta-fim" data-ponta="fim"></span></div>`
    }).join('')
    const alto = Math.max(1, fins.length) * 22 + 2
    const f = $('#f-elementos')
    f.innerHTML = html
    f.style.height = `${alto}px`
    $('#r-elementos').style.height = `${alto}px`
  }

  renderPalavras() {
    const ctx = (this.medidor ||= document.createElement('canvas').getContext('2d'))
    ctx.font = '400 11px Manrope, sans-serif'
    $('#f-palavras').innerHTML = this.palavras.map((w, i) => {
      const larg = Math.max((w.fim - w.ini) * this.pxs - 1, 1)
      const cabe = larg >= ctx.measureText(w.texto).width + 5
      return `<span class="palavra${cabe ? '' : ' sem-texto'}" data-i="${i}" style="left:${(w.ini * this.pxs).toFixed(1)}px;width:${larg.toFixed(1)}px" title="${esc(w.texto)} · ${tempo(w.ini)}">${cabe ? esc(w.texto) : ''}</span>`
    }).join('')
  }

  falaDe(a, b) {
    return this.palavras.filter((w) => w.fim > a + 0.01 && w.ini < b).map((w) => w.texto).join(' ')
  }

  renderDetalhe() {
    const i = this.item(this.sel)
    const el = $('#detalhe')
    if (!i) {
      el.innerHTML = '<p class="vazio-lista">Clique num plano ou elemento da linha do tempo.</p>'
      return
    }
    const plano = i.camada === 'plano'
    const fala = this.falaDe(i.inicio, i.fim)
    const dentro = plano ? this.elementos().filter((e) => e.fim > i.inicio && e.inicio < i.fim) : []
    const tipos = plano ? Object.fromEntries(Object.entries(PLANOS).map(([k, v]) => [k, v[0]])) : ELEMENTOS
    const unico = plano && this.planos().length < 2
    const texto = !plano || COM_TEXTO.includes(i.tipo)
    el.innerHTML = `<div class="painel-cabeca"><div class="item-cabeca"><span class="eyebrow">${plano ? 'Plano-base' : 'Elemento'} · ${esc(i.id)}</span>
        ${plano && this.codigo ? chipCodigo(`${this.codigo}·${i.id}`, `${this.nomeTipo(i)} · ${this.ref.nome} ${tempo(i.inicio)}`) : ''}</div>
        <div class="item-cabeca"><span class="chip-plano ${plano ? `tipo-${esc(i.tipo)}` : `el-${esc(i.tipo)}`}">${esc(this.nomeTipo(i))}</span>
        <span class="chip-tempo estatico">${tempo(i.inicio)} → ${tempo(i.fim)}</span><b class="dur">${num(i.fim - i.inicio, 2)} s</b></div></div>
      <div class="detalhe-corpo">
        ${i.miniatura ? `<img class="miniatura-item" src="${this.base}${esc(i.miniatura)}?v=${esc(i.miniatura_t ?? '')}" alt="">` : ''}
        ${fala ? `<p class="fala">“${esc(fala)}”</p>` : ''}
        ${dentro.length ? `<div class="campo"><span class="eyebrow">Elementos neste plano</span><div class="chips">${dentro.map((e) => `<button class="chip-plano el-${esc(e.tipo)}" data-selecionar="${e.id}" title="${tempo(e.inicio)} → ${tempo(e.fim)}">${esc(e.texto ? `“${e.texto}”` : ELEMENTOS[e.tipo] || e.tipo)}</button>`).join('')}</div></div>` : ''}
        <label class="campo"><span class="eyebrow">Tipo</span><select data-campo="tipo">${Object.entries(tipos).map(([k, n]) => `<option value="${k}"${k === i.tipo ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
        ${texto ? `<label class="campo"><span class="eyebrow">${i.tipo === 'comentario_insert_ator' ? 'Texto do comentário' : 'Texto exato'}</span><input data-campo="texto" value="${esc(i.texto || '')}"></label>` : ''}
        <label class="campo"><span class="eyebrow">${COM_INSERT.includes(i.tipo) ? 'Marcação · o que acontece no insert' : 'Marcação'}</span><textarea data-campo="descricao" rows="7">${esc(i.descricao || '')}</textarea></label>
        <div class="acoes-linha"><button class="botao pequeno" data-acao="ver">${ICONE.tocar} Ver trecho</button>
          <button class="botao pequeno" data-acao="excluir" ${unico ? 'disabled' : ''} title="${plano ? 'O plano some e o anterior (ou o seguinte) ocupa o lugar dele' : 'Tira o elemento'}">${ICONE.lixo} ${plano ? 'Juntar com o vizinho' : 'Excluir'}</button></div>
        <p class="erro-linha" id="erro-validacao" ${this.erro ? '' : 'hidden'}>${esc(this.erro || '')}</p>
      </div>`
  }

  // ---------- o tempo ----------

  atualizar() {
    if (this.fechado) return // o vídeo ainda solta eventos depois de sair da tela
    const t = this.video.currentTime
    $('#t-atual').textContent = tempo(t)
    const x = t * this.pxs
    $('#cabeca').style.transform = `translateX(${x}px)`
    const tocando = !this.video.paused
    if (tocando !== this.tocando) {
      this.tocando = tocando
      $('#b-tocar').innerHTML = tocando ? ICONE.pausar : ICONE.tocar
      $('.video-tocar').classList.toggle('escondido', tocando)
    }
    if (tocando) {
      const rolo = $('#rolo')
      if (x < rolo.scrollLeft || x > rolo.scrollLeft + rolo.clientWidth - 30) rolo.scrollLeft = x - 40
    }
    const i = this.palavras.findIndex((w) => t >= w.ini && t < w.fim)
    if (i !== this.iPalavra) {
      $('.palavra.agora')?.classList.remove('agora')
      if (i >= 0) $(`.palavra[data-i="${i}"]`)?.classList.add('agora')
      this.iPalavra = i
      let k = i
      if (k < 0) k = this.palavras.findIndex((w) => w.ini > t)
      if (k < 0) k = this.palavras.length - 1
      const de = Math.max(0, k - 5)
      $('#fala-atual').innerHTML = k < 0 ? '<span class="apagado">—</span>'
        : (de > 0 ? '… ' : '') + this.palavras.slice(de, k + 6).map((w, j) => (de + j === i ? `<b>${esc(w.texto)}</b>` : esc(w.texto))).join(' ') + (k + 6 < this.palavras.length ? ' …' : '')
    }
    const ps = this.planos()
    const p = ps.find((q) => t >= q.inicio && t < q.fim) || (t >= this.dur - 0.05 ? ps.at(-1) : null)
    if (p?.id !== this.iPlano) {
      this.iPlano = p?.id
      $('#plano-atual').innerHTML = p
        ? `<span class="chip-plano tipo-${esc(p.tipo)}">${esc(nomePlano(p.tipo))}</span>${p.texto ? `<p class="plano-texto">“${esc(p.texto)}”</p>` : ''}${p.descricao ? `<p class="plano-desc">${esc(p.descricao)}</p>` : ''}`
        : '<span class="apagado">—</span>'
    }
    // o painel mostra o que está sob o cursor: se o selecionado não contém o cursor, passa para o plano dele
    const s = this.item(this.sel)
    const editando = document.activeElement?.closest?.('#detalhe') && document.activeElement.matches('input, textarea, select')
    if (p && !this.arrasto && !editando && (!s || t < s.inicio - 0.001 || t > s.fim + 0.001)) this.selecionar(p.id)
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
    this.pararTrecho?.()
    this.video.currentTime = Math.min(Math.max(t, 0), Math.max(this.dur - 0.01, 0))
    this.atualizar()
  }

  alternar() {
    this.pararTrecho?.()
    if (this.video.paused) this.video.play().catch(() => {})
    else this.video.pause()
  }

  zoom(fator, ancora) {
    const rolo = $('#rolo')
    const a = ancora ?? this.video.currentTime * this.pxs - rolo.scrollLeft
    const tAncora = (rolo.scrollLeft + a) / this.pxs
    const ajuste = Math.max(rolo.clientWidth - 2, 100) / this.dur
    this.pxs = Math.min(Math.max(this.pxs * fator, ajuste), 400)
    this.ajustar = this.pxs <= ajuste * 1.0001
    this.renderLinha()
    rolo.scrollLeft = tAncora * this.pxs - a
  }

  selecionar(id) {
    if (id === this.sel) return
    this.sel = id
    for (const b of $$('.plano-sel, .elemento-sel', this.tela)) b.classList.remove('plano-sel', 'elemento-sel')
    const b = $(`[data-item="${id}"]`, this.tela)
    b?.classList.add(b.classList.contains('plano') ? 'plano-sel' : 'elemento-sel')
    this.renderDetalhe()
  }

  // ---------- editar ----------

  /** Guarda o estado para o ⌘Z e aplica a mudança. */
  mudar(novos, { sel, desenhar = true } = {}) {
    this.historico.push(JSON.stringify(this.itens))
    if (this.historico.length > 100) this.historico.shift()
    this.itens = novos
    if (sel) this.sel = sel
    if (!this.item(this.sel)) this.sel = this.planoEm(this.video.currentTime)?.id
    if (desenhar) {
      this.renderPlanos()
      this.renderElementos()
      this.renderDetalhe()
    }
    this.agendarSalvar()
  }

  desfazer() {
    const antes = this.historico.pop()
    if (!antes) return aviso('Nada para desfazer')
    this.itens = JSON.parse(antes)
    if (!this.item(this.sel)) this.sel = this.planoEm(this.video.currentTime)?.id
    this.renderPlanos()
    this.renderElementos()
    this.renderDetalhe()
    this.agendarSalvar()
  }

  planoEm(t) {
    return this.planos().find((p) => t >= p.inicio && t < p.fim) || this.planos().at(-1)
  }

  novoId(prefixo) {
    return `${prefixo}${Math.max(0, ...this.itens.filter((i) => i.id.startsWith(prefixo)).map((i) => Number(i.id.slice(1)) || 0)) + 1}`
  }

  dividir() {
    const t = this.video.currentTime
    const p = this.planos().find((x) => t > x.inicio + MIN_PLANO && t < x.fim - MIN_PLANO)
    if (!p) return aviso('Ponha o cursor dentro de um plano (longe das bordas) para dividir.', 'erro')
    const id = this.novoId('p')
    const corte = r3(t)
    const segundo = { ...p, id, inicio: corte, miniatura: undefined, miniatura_t: undefined }
    this.mudar([...this.itens.map((i) => (i.id === p.id ? { ...i, fim: corte } : i)), segundo], { sel: id })
    aviso('Plano dividido: troque o tipo do novo à direita')
  }

  novoElemento() {
    const id = this.novoId('e')
    const inicio = r3(Math.min(Math.max(this.video.currentTime, 0), this.dur - 0.5))
    const el = { id, camada: 'elemento', tipo: 'lettering', conteudo: null, inicio, fim: r3(Math.min(inicio + 1.5, this.dur)), descricao: '', texto: '' }
    this.mudar([...this.itens, el], { sel: id })
    $('#detalhe [data-campo="texto"]')?.focus()
  }

  excluir() {
    const item = this.item(this.sel)
    if (!item) return
    if (item.camada === 'elemento') return this.mudar(this.itens.filter((i) => i.id !== item.id))
    const ps = this.planos()
    if (ps.length < 2) return
    const k = ps.findIndex((p) => p.id === item.id)
    const viz = k > 0 ? ps[k - 1] : ps[k + 1]
    this.mudar(this.itens.filter((i) => i.id !== item.id).map((i) => (i.id !== viz.id ? i : k > 0 ? { ...i, fim: item.fim } : { ...i, inicio: item.inicio })), { sel: viz.id })
  }

  verTrecho() {
    const i = this.item(this.sel)
    if (!i) return
    this.pararTrecho?.()
    this.pararTrecho = tocarTrecho(this.video, i.inicio + 0.001, i.fim, { loop: false })
    this.laco()
  }

  imantar(t, livre) {
    if (livre) return t
    let melhor = t
    let dist = IMA_PX / this.pxs
    for (const c of this.imas) {
      const d = Math.abs(c - t)
      if (d < dist) [melhor, dist] = [c, d]
    }
    return melhor
  }

  /** Arrastar a borda entre dois planos ou um elemento (inteiro ou uma ponta). */
  arrastar(e, alvo) {
    e.preventDefault()
    e.stopPropagation()
    this.video.pause()
    const conteudo = $('#conteudo')
    const antes = JSON.stringify(this.itens)
    const t0 = (e.clientX - conteudo.getBoundingClientRect().left) / this.pxs
    const orig = alvo.id ? { ...this.item(alvo.id) } : null
    this.arrasto = alvo
    if (alvo.id) this.selecionar(alvo.id)
    const mover = (ev) => {
      const bruto = (ev.clientX - conteudo.getBoundingClientRect().left) / this.pxs
      if (alvo.borda != null) {
        const ps = this.planos()
        const [a, b] = [ps[alvo.borda], ps[alvo.borda + 1]]
        const t = r3(Math.min(Math.max(this.imantar(bruto, ev.altKey), a.inicio + MIN_PLANO), b.fim - MIN_PLANO))
        a.fim = t
        b.inicio = t
        this.renderPlanos()
        this.buscar(t)
      } else {
        const it = this.item(alvo.id)
        if (alvo.lado === 'inicio') it.inicio = r3(Math.min(Math.max(this.imantar(bruto, ev.altKey), 0), it.fim - MIN_ELEMENTO))
        else if (alvo.lado === 'fim') it.fim = r3(Math.max(Math.min(this.imantar(bruto, ev.altKey), this.dur), it.inicio + MIN_ELEMENTO))
        else {
          const dur = orig.fim - orig.inicio
          let ini = orig.inicio + (bruto - t0)
          const ima = this.imantar(ini, ev.altKey)
          ini = Math.min(Math.max(ima, 0), this.dur - dur)
          it.inicio = r3(ini)
          it.fim = r3(ini + dur)
        }
        this.renderElementos()
      }
    }
    const soltar = () => {
      window.removeEventListener('pointermove', mover)
      window.removeEventListener('pointerup', soltar)
      this.arrasto = null
      if (JSON.stringify(this.itens) === antes) return
      const depois = this.itens
      this.itens = JSON.parse(antes)
      this.mudar(depois)
    }
    window.addEventListener('pointermove', mover)
    window.addEventListener('pointerup', soltar)
  }

  // ---------- gravar ----------

  mostrarSalvo(estado) {
    const el = $('#salvo')
    if (!el) return
    el.className = `salvo salvo-${estado}`
    el.innerHTML = { salvando: 'Salvando…', salvo: `${ICONE.check} Salvo`, erro: 'Não salvou', '': '' }[estado]
    el.title = estado === 'erro' ? this.erro || '' : ''
  }

  agendarSalvar() {
    this.sujo = true
    this.versao++
    this.mostrarSalvo('salvando')
    this.renderBotoes()
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.salvar(), 700)
  }

  salvar() {
    clearTimeout(this.timer)
    const versao = this.versao
    const corpo = { itens: this.itens }
    this.fila = this.fila.then(async () => {
      try {
        const d = await enviar('PUT', `/api/referencias/${encodeURIComponent(this.id)}/direcao`, corpo)
        this.erro = null
        if (versao === this.versao && !this.fechado) {
          this.sujo = false
          // o servidor prende às palavras de novo e refaz as miniaturas: fica com o que ele gravou
          if (Array.isArray(d?.itens) && !this.arrasto && !document.activeElement?.closest?.('#detalhe')) {
            this.itens = d.itens
            if (!this.item(this.sel)) this.sel = this.planoEm(this.video.currentTime)?.id
            this.renderPlanos()
            this.renderElementos()
            this.renderDetalhe()
          }
          this.mostrarSalvo('salvo')
        }
      } catch (e) {
        this.erro = e.message
        if (!this.fechado) {
          this.mostrarSalvo('erro')
          const p = $('#erro-validacao')
          if (p) {
            p.hidden = false
            p.textContent = `Não salvou: ${e.message}`
          }
          aviso(`Não salvou: ${e.message}`, 'erro')
        }
      }
      if (!this.fechado) this.renderBotoes()
    })
    return this.fila
  }

  async alternarRevisada() {
    if (this.sujo) return
    const revisado = this.ref.status !== 'revisado'
    try {
      const r = await enviar('PUT', `/api/referencias/${encodeURIComponent(this.id)}/status`, { revisado })
      this.ref.status = r?.status || (revisado ? 'revisado' : 'a_revisar')
      this.renderBotoes()
      aviso(revisado ? 'Marcada como revisada' : 'De volta para “a revisar”')
    } catch (e) {
      aviso(e.message, 'erro')
    }
  }

  async reanalisar() {
    const ok = await confirmar({ titulo: `Reanalisar “${this.ref.nome}”?`, texto: 'A IA refaz a análise deste vídeo do zero e as correções feitas aqui se perdem (a direção atual fica guardada em direcao.anterior.json). O proxy e a transcrição são reaproveitados.', ok: 'Reanalisar', perigo: true })
    if (!ok) return
    try {
      await this.fila
      await enviar('POST', `/api/referencias/${encodeURIComponent(this.id)}/reanalisar`)
      this.sujo = false
      aviso('Na fila para reanalisar')
      location.hash = '#/calibragem'
    } catch (e) {
      aviso(e.message, 'erro')
    }
  }

  // ---------- eventos ----------

  ligar() {
    const v = this.video
    v.addEventListener('loadedmetadata', () => {
      if (isFinite(v.duration) && !this.ref.video?.duracao) {
        this.dur = v.duration
        this.renderLinha()
      }
    })
    v.addEventListener('play', () => this.laco())
    for (const ev of ['pause', 'seeked', 'timeupdate']) v.addEventListener(ev, () => v.paused && this.atualizar())

    this.cliques = (e) => this.clique(e)
    this.tela.addEventListener('click', this.cliques)
    this.teclas = (e) => this.tecla(e)
    window.addEventListener('keydown', this.teclas)
    this.redim = () => this.ajustar && this.renderLinha()
    window.addEventListener('resize', this.redim)

    // os campos do painel: cada mudança entra no ⌘Z uma vez por foco e grava sozinha
    const detalhe = $('#detalhe')
    let guardado = false
    detalhe.addEventListener('focusin', () => (guardado = false))
    const editar = (e) => {
      const campo = e.target.dataset?.campo
      const i = this.item(this.sel)
      if (!campo || !i) return
      if (!guardado || campo === 'tipo') {
        this.historico.push(JSON.stringify(this.itens))
        guardado = true
      }
      i[campo] = e.target.value
      if (campo === 'tipo') {
        this.renderPlanos()
        this.renderElementos()
        this.renderDetalhe()
      } else if (i.camada === 'elemento') this.renderElementos()
      this.agendarSalvar()
    }
    detalhe.addEventListener('input', (e) => e.target.dataset.campo !== 'tipo' && editar(e))
    detalhe.addEventListener('change', (e) => e.target.dataset.campo === 'tipo' && editar(e))

    // a linha do tempo: clicar/arrastar no vazio busca; a borda e os elementos se arrastam
    const conteudo = $('#conteudo')
    conteudo.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return
      if (document.activeElement?.closest?.('#detalhe')) document.activeElement.blur() // o preventDefault abaixo não tira o foco
      const borda = e.target.closest('[data-borda]')
      if (borda) return this.arrastar(e, { borda: +borda.dataset.borda })
      const el = e.target.closest('.elemento')
      if (el) {
        const t = (e.clientX - conteudo.getBoundingClientRect().left) / this.pxs
        this.buscar(Math.min(Math.max(t, this.item(el.dataset.item).inicio), this.item(el.dataset.item).fim))
        return this.arrastar(e, { id: el.dataset.item, lado: e.target.dataset.ponta || 'corpo' })
      }
      e.preventDefault()
      const mover = (ev) => this.buscar((ev.clientX - conteudo.getBoundingClientRect().left) / this.pxs)
      mover(e)
      conteudo.setPointerCapture(e.pointerId)
      const soltar = () => {
        conteudo.removeEventListener('pointermove', mover)
        conteudo.removeEventListener('pointerup', soltar)
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
    const b = e.target.closest('button, [data-selecionar]')
    if (!b) return
    if (b.tagName === 'BUTTON') b.blur()
    const d = b.dataset
    if (d.selecionar) {
      const el = this.item(d.selecionar)
      this.buscar(el.inicio + 0.001)
      return this.selecionar(el.id)
    }
    if (d.vel) {
      this.video.playbackRate = +d.vel
      for (const x of $$('[data-vel]')) x.classList.toggle('ativa', x === b)
      return
    }
    const a = {
      tocar: () => this.alternar(),
      'passo-': () => this.passo(-1 / 24),
      'passo+': () => this.passo(1 / 24),
      'corte-': () => this.irAoCorte(-1),
      'corte+': () => this.irAoCorte(1),
      ajustar: () => this.zoom(0),
      'zoom-': () => this.zoom(1 / 1.6),
      'zoom+': () => this.zoom(1.6),
      dividir: () => this.dividir(),
      elemento: () => this.novoElemento(),
      desfazer: () => this.desfazer(),
      excluir: () => this.excluir(),
      ver: () => this.verTrecho(),
      revisada: () => this.alternarRevisada(),
      reanalisar: () => this.reanalisar(),
    }[d.acao]
    a?.()
  }

  passo(dt) {
    this.video.pause()
    const t = this.video.currentTime + dt
    this.buscar(Math.abs(dt) < 0.5 ? (Math.round(t * 24) + 0.001) / 24 : t) // um quadro: no grid de 24 por segundo
  }

  /** Shift + setas (como na revisão): o começo do plano seguinte ou anterior (o corte). */
  irAoCorte(dir) {
    this.video.pause()
    const t = this.video.currentTime
    const inicios = this.planos().map((p) => p.inicio)
    const alvo = dir > 0 ? inicios.find((x) => x > t + 0.02) : inicios.filter((x) => x < t - 0.02).at(-1)
    this.buscar(alvo ?? (dir > 0 ? this.dur : 0))
  }

  /** R (como na revisão): toca o plano do cursor de novo, do começo; logo em seguida de novo, o plano anterior. */
  replano() {
    const t = this.video.currentTime
    const inicios = this.planos().map((p) => p.inicio)
    let ini = inicios.filter((x) => x <= t + 0.001).at(-1) ?? 0
    if (t - ini < 0.35 && Date.now() - (this.ultimoR || 0) < 1500) ini = inicios.filter((x) => x < ini - 0.001).at(-1) ?? 0
    this.ultimoR = Date.now()
    this.buscar(ini + 0.001)
    this.video.play().catch(() => {})
  }

  tecla(e) {
    if (modalAberto()) return
    const campo = e.target.closest?.('input, textarea, select, [contenteditable]')
    if (campo) {
      if (e.key === 'Escape') {
        e.preventDefault()
        campo.blur()
      }
      return
    }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
      e.preventDefault()
      return this.desfazer()
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key
    const f = {
      ' ': () => this.alternar(),
      ArrowLeft: () => (e.shiftKey ? this.irAoCorte(-1) : this.passo(-1 / 24)),
      ArrowRight: () => (e.shiftKey ? this.irAoCorte(1) : this.passo(1 / 24)),
      r: () => this.replano(),
      s: () => this.dividir(),
      e: () => this.novoElemento(),
      Delete: () => this.excluir(),
      Backspace: () => this.excluir(),
    }[k]
    if (f) {
      e.preventDefault()
      f()
    }
  }

  fechar() {
    this.fechado = true
    if (this.sujo) this.salvar()
    clearTimeout(this.timer)
    cancelAnimationFrame(this.raf)
    this.pararTrecho?.()
    window.removeEventListener('keydown', this.teclas)
    window.removeEventListener('resize', this.redim)
    this.video.pause()
    this.video.removeAttribute('src')
    this.video.load()
  }
}
