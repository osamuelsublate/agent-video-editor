// As categorias de vídeo (📱 Reels, 💰 Ad, 📺 VSL, 🎥 YouTube, 📚 Aula…): cada referência da Calibragem e cada projeto tem
// uma, e cada categoria tem a sua Heurística (exemplos/<categoria>/). O cadastro é o painel Categorias (o mesmo jeito do
// painel de produtos dos CTAs).
import { $, $$, ICONE, aviso, enviar, esc, janela, json } from './comum.js'

let cache = null
const PEGADOR = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>'
/** As categorias cadastradas (lidas uma vez; `esquecerCategorias` depois de gravar). */
export const carregarCategorias = () => (cache ??= json('/api/categorias', { categorias: [] }).then((d) => d.categorias))
export const esquecerCategorias = () => (cache = null)

/** Uma categoria de CTA: "CTA" no nome (CTA, CTA LP, CTA VSL…). Os projetos dela moram na página CTAs, à parte. */
export const categoriaCta = (lista, id) => /\bcta\b/i.test(lista.find((c) => c.id === id)?.nome || id)

export const rotuloCategoria = (lista, id) => {
  const c = lista.find((x) => x.id === id)
  return c ? `${c.emoji ? `${c.emoji} ` : ''}${c.nome}` : id
}

/** As pílulas de filtro: Todas (se `todas`) e uma por categoria, com a contagem (`contar`). Clique: [data-categoria]. */
export function pilulasCategoria(lista, atual, { todas = true, contar = null } = {}) {
  const conta = (id) => (contar ? ` <span class="conta">${contar(id)}</span>` : '')
  return `<div class="filtro-produtos">${todas ? `<button class="pilula pequena${atual === '' ? ' ativa' : ''}" data-categoria="">Todas${conta('')}</button>` : ''}${lista
    .map((c) => `<button class="pilula pequena${atual === c.id ? ' ativa' : ''}" data-categoria="${esc(c.id)}">${c.emoji ? `${esc(c.emoji)} ` : ''}${esc(c.nome)}${conta(c.id)}</button>`)
    .join('')}</div>`
}

/** Trocar a categoria de uma referência ou de um projeto: uma lista pequena. Mudou: [data-mudar-categoria]. */
export function seletorCategoria(lista, valor) {
  const opcoes = lista.some((c) => c.id === valor) ? lista : [{ id: valor, nome: valor, emoji: '' }, ...lista]
  return `<label class="cta-categoria cta-produto" title="Categoria"><span>${esc(rotuloCategoria(lista, valor))}</span>${ICONE.seta_baixo}
    <select data-mudar-categoria aria-label="Categoria">${opcoes.map((c) => `<option value="${esc(c.id)}"${c.id === valor ? ' selected' : ''}>${esc(rotuloCategoria(lista, c.id))}</option>`).join('')}</select></label>`
}

/** O botão que abre o cadastro. */
export const botaoCategorias = () => `<button class="botao pequeno" data-editar-categorias title="Cadastrar e renomear as categorias">${ICONE.ajustes} Categorias</button>`

/** O painel das categorias: emoji e nome editáveis, adicionar e tirar; grava a lista inteira (uma em uso não sai). */
export function editarCategorias(lista, depois) {
  const l = lista.map((c) => ({ ...c }))
  const { el, fechar } = janela(`<header class="janela-cabeca"><h2>Categorias</h2><span class="dica">cada uma tem a sua Calibragem e a sua Heurística</span>
      <button class="botao-icone" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button></header>
    <div class="produtos-lista"></div>
    <div class="produtos-acoes"><button class="botao pequeno" data-novo>${ICONE.mais} Nova categoria</button>
      <button class="botao botao-coral" data-gravar>Salvar</button></div>`, { classe: 'janela-produtos' })
  const desenhar = () => {
    $('.produtos-lista', el).innerHTML = l.map((c, k) => `<div class="produto-linha${k === arrastando ? ' arrastando' : ''}" data-k="${k}">
        <button class="pegador" data-pegar title="Arraste para mudar a ordem (a das pílulas de filtro)" aria-label="Mudar a ordem">${PEGADOR}</button>
        <input class="produto-emoji" value="${esc(c.emoji || '')}" maxlength="8" data-campo="emoji" aria-label="Emoji" placeholder="🎬">
        <input class="produto-nome" value="${esc(c.nome)}" maxlength="40" data-campo="nome" aria-label="Nome" placeholder="Nome da categoria">
        <button class="botao-icone pequeno" data-tirar ${c.id === 'reels' ? 'disabled title="O Reels é a categoria padrão"' : 'title="Tirar (só sem referências e projetos dela)"'}>${ICONE.lixo}</button></div>`).join('')
  }
  // a ordem: arrastar pelo pegador (a lista se reordena enquanto arrasta; Salvar grava)
  let arrastando = null
  el.addEventListener('pointerdown', (e) => {
    const p = e.target.closest('[data-pegar]')
    if (!p || e.button !== 0) return
    e.preventDefault()
    arrastando = +p.closest('.produto-linha').dataset.k
    desenhar()
    const mover = (ev) => {
      const linhas = $$('.produto-linha', el)
      const alvo = linhas.findIndex((x) => { const r = x.getBoundingClientRect(); return ev.clientY < r.top + r.height / 2 })
      const para = alvo < 0 ? linhas.length - 1 : alvo > arrastando ? alvo - 1 : alvo
      if (para === arrastando) return
      l.splice(para, 0, ...l.splice(arrastando, 1))
      arrastando = para
      desenhar()
    }
    const soltar = () => {
      removeEventListener('pointermove', mover)
      removeEventListener('pointerup', soltar)
      arrastando = null
      desenhar()
    }
    addEventListener('pointermove', mover)
    addEventListener('pointerup', soltar)
  })
  desenhar()
  el.addEventListener('input', (e) => {
    const linha = e.target.closest('.produto-linha')
    if (linha) l[+linha.dataset.k][e.target.dataset.campo] = e.target.value
  })
  el.addEventListener('click', async (e) => {
    if (e.target.closest('[data-novo]')) {
      l.push({ id: '', nome: '', emoji: '' })
      desenhar()
      return $$('.produto-nome', el).at(-1).focus()
    }
    const t = e.target.closest('[data-tirar]')
    if (t) {
      l.splice(+t.closest('.produto-linha').dataset.k, 1)
      return desenhar()
    }
    if (e.target.closest('[data-gravar]')) {
      try {
        await enviar('PUT', '/api/categorias', { categorias: l })
        esquecerCategorias()
        aviso('Categorias salvas')
        fechar()
        depois?.()
      } catch (x) {
        aviso(x.message, 'erro')
      }
    }
  })
}
