// as tags (como no Obsidian: #grupo/tag) do Banco, dos Motions e das Referências: a árvore na barra lateral (com as
// contagens, expansível, renomear e tirar em todos), as tags no card (+ tag, ×, clicar filtra) e o filtro
import { $, $$, ICONE, aviso, confirmar, enviar, esc, preferencia } from './comum.js'

/** Uma tag limpa: sem o #, sem espaços (viram -), níveis separados por / ("fia/ad-vsl"). */
export const tagLimpa = (t) => String(t || '').trim().replace(/^#+/, '').trim().replace(/\s+/g, '-').replace(/\/+/g, '/').replace(/^\/|\/$/g, '')
/** As tags tem a tag ou uma de dentro dela ("fia" pega "fia/ad-vsl"). */
export const temTag = (tags, t) => (tags || []).some((x) => x === t || x.startsWith(`${t}/`))
/** Várias tags digitadas de uma vez ("#a, #b/c #d"). */
export const tagsDoTexto = (texto) => String(texto || '').split(/[,\s]+(?=#)|,/).map(tagLimpa).filter(Boolean)

/** A árvore: "fia/ad-vsl" fica dentro de "fia"; cada nó conta os itens dele e os de dentro. `itens`: [{chave, tags}]. */
function arvore(itens) {
  const raiz = { filhos: {} }
  for (const it of itens) for (const t of it.tags || []) {
    let no = raiz
    for (const parte of t.split('/')) {
      no = no.filhos[parte] ||= { nome: parte, caminho: no.caminho ? `${no.caminho}/${parte}` : parte, filhos: {}, chaves: new Set() }
      no.chaves.add(it.chave)
    }
  }
  return raiz
}

function htmlArvore(no, abertas, ativa, nivel = 0) {
  return Object.values(no.filhos).sort((a, b) => a.nome.localeCompare(b.nome)).map((f) => {
    const temFilhos = Object.keys(f.filhos).length > 0
    const aberta = abertas.includes(f.caminho) || (ativa || '').startsWith(`${f.caminho}/`)
    return `<li><div class="tag-linha${f.caminho === ativa ? ' ativa' : ''}" data-tag="${esc(f.caminho)}" style="--nivel:${nivel}" title="#${esc(f.caminho)}">
        ${temFilhos ? `<button class="tag-seta${aberta ? ' aberta' : ''}" data-abrir-tag="${esc(f.caminho)}" aria-label="${aberta ? 'Recolher' : 'Expandir'}">›</button>` : '<span class="tag-seta"></span>'}
        <span class="tag-nome">${esc(f.nome)}</span><span class="conta">${f.chaves.size}</span>
        <span class="tag-acoes"><button class="tag-acao" data-renomear-tag="${esc(f.caminho)}" title="Renomear #${esc(f.caminho)} em todos">${ICONE.lapis}</button><button class="tag-acao" data-apagar-tag="${esc(f.caminho)}" title="Tirar #${esc(f.caminho)} de todos">${ICONE.fechar}</button></span></div>
      ${temFilhos && aberta ? `<ul>${htmlArvore(f, abertas, ativa, nivel + 1)}</ul>` : ''}</li>`
  }).join('')
}

/** A barra lateral: Todas e a árvore. `itens`: [{chave, tags}]; `pref`: o prefixo das preferências (banco, motions…). */
export function barraDeTags(itens, ativa, pref, { editar = true } = {}) {
  const a = arvore(itens)
  return `<aside class="tags-banco${editar ? '' : ' sem-editar'}"><span class="eyebrow">Tags</span>
    <div class="tag-linha tag-fixa${ativa ? '' : ' ativa'}" data-tag=""><span class="tag-seta"></span><span class="tag-nome">Todas</span><span class="conta">${itens.length}</span></div>
    ${Object.keys(a.filhos).length ? `<ul class="tags-arvore">${htmlArvore(a, preferencia(`${pref}.tags.abertas`, []), ativa)}</ul>`
      : '<p class="dica">Nenhuma tag ainda: no card, <b>+ tag</b> e escreva <b>#tag</b> ou <b>#grupo/tag</b>.</p>'}</aside>`
}

/** A tag escolhida na barra (a preferência), ou '' se ela não existe mais. */
export function tagEscolhida(pref, itens) {
  const t = preferencia(`${pref}.tag`, '')
  return t && itens.some((it) => temTag(it.tags, t)) ? t : ''
}

/** As tags no card (clicar filtra, × tira) e o + tag. */
export const htmlTagsCard = (tags, antes = '') => `<div class="tags-card">${antes}
    ${(tags || []).map((t) => `<span class="tag"><button class="tag-texto" data-tag-chip="${esc(t)}" title="Mostrar só #${esc(t)}">#${esc(t)}</button><button class="tag-tirar" data-tirar-tag-card="${esc(t)}" title="Tirar #${esc(t)}" aria-label="Tirar #${esc(t)}">×</button></span>`).join('')}
    <button class="tag tag-mais" data-mais-tag title="Pôr uma tag (#tag ou #grupo/tag)">+ tag</button></div>`

export const datalistTags = (id, conhecidas) => `<datalist id="${id}">${conhecidas.map((t) => `<option value="#${esc(t)}">`).join('')}</datalist>`

/** Liga a barra e os cards de uma página. `onde`: banco | motions | referencias (renomear em todos); `pref`: o prefixo das
 *  preferências; `itemDo(el)`: o item do card de um elemento ({tags}); `gravar(item, tags)`; `recarregar()`;
 *  `aposRenomear()`: depois de renomear em todos (quem guarda os itens na memória busca de novo); `lista`: o id do
 *  datalist do autocompletar dos cards; `conhecidas`: todas as tags. */
export function ligarTags(raiz, { onde, pref, itemDo, gravar, recarregar, aposRenomear = recarregar, lista, conhecidas }) {
  const escolher = (t) => {
    preferencia(`${pref}.tag`, '', t)
    recarregar()
  }
  const ativa = preferencia(`${pref}.tag`, '')
  const mudarTag = async (de, para) => {
    try {
      const r = await enviar('POST', `/api/tags/${onde}`, { de, para })
      const n = `${r.mudaram} ${r.mudaram === 1 ? 'item' : 'itens'}`
      aviso(para ? `#${de} virou #${tagLimpa(para)} em ${n}` : `#${de} saiu de ${n}`)
      if (ativa === de || ativa.startsWith(`${de}/`)) preferencia(`${pref}.tag`, '', para ? tagLimpa(para) + ativa.slice(de.length) : '')
      aposRenomear()
    } catch (x) {
      aviso(x.message, 'erro')
    }
  }
  // a barra lateral
  for (const b of $$('[data-tag]', raiz)) b.addEventListener('click', (e) => {
    if (e.target.closest('[data-abrir-tag], .tag-acoes, .tag-campo')) return
    escolher(b.dataset.tag)
  })
  for (const b of $$('[data-abrir-tag]', raiz)) b.addEventListener('click', (e) => {
    e.stopPropagation()
    const t = b.dataset.abrirTag
    const abertas = preferencia(`${pref}.tags.abertas`, [])
    preferencia(`${pref}.tags.abertas`, [], abertas.includes(t) ? abertas.filter((x) => x !== t && !x.startsWith(`${t}/`)) : [...abertas, t])
    if (b.classList.contains('aberta') && ativa.startsWith(`${t}/`)) return escolher(t) // recolher o grupo da tag ativa: a seleção sobe
    recarregar()
  })
  for (const b of $$('[data-apagar-tag]', raiz)) b.addEventListener('click', async (e) => {
    e.stopPropagation()
    const de = b.dataset.apagarTag
    if (await confirmar({ titulo: `Tirar #${de} de todos?`, texto: 'As tags de dentro dela saem junto. Os itens continuam onde estão.', ok: 'Tirar', perigo: true })) mudarTag(de, '')
  })
  for (const b of $$('[data-renomear-tag]', raiz)) b.addEventListener('click', (e) => {
    e.stopPropagation()
    const de = b.dataset.renomearTag
    const linha = b.closest('.tag-linha')
    editarNoLugar($('.tag-nome', linha), { valor: de, classe: 'tag-campo tag-campo-barra', antes: () => linha.classList.add('editando') },
      (texto) => {
        const para = tagLimpa(texto)
        if (para && para !== de) mudarTag(de, para)
        else recarregar()
      }, recarregar)
  })
  // os cards
  for (const b of $$('[data-tag-chip]', raiz)) b.addEventListener('click', (e) => {
    e.stopPropagation()
    escolher(b.dataset.tagChip)
  })
  const gravarTags = async (it, tags) => {
    try {
      await gravar(it, tags)
      recarregar()
    } catch (x) {
      aviso(x.message, 'erro')
    }
  }
  for (const b of $$('[data-tirar-tag-card]', raiz)) b.addEventListener('click', (e) => {
    e.stopPropagation()
    const it = itemDo(b)
    gravarTags(it, (it.tags || []).filter((t) => t !== b.dataset.tirarTagCard))
  })
  for (const b of $$('[data-mais-tag]', raiz)) b.addEventListener('click', (e) => {
    e.stopPropagation()
    const it = itemDo(b)
    editarNoLugar(b, { valor: '', classe: 'tag-campo', placeholder: '#grupo/tag', lista, conhecidas }, (texto) => {
      const novas = tagsDoTexto(texto).filter((t) => !(it.tags || []).includes(t))
      if (novas.length) gravarTags(it, [...(it.tags || []), ...novas])
      else recarregar()
    }, recarregar)
  })
}

/** Troca `alvo` por um campo: Enter (ou sair) grava, Esc desiste. Escolher no autocompletar já grava. */
function editarNoLugar(alvo, { valor, classe, placeholder, lista, conhecidas, antes }, gravar, desistir) {
  const campo = document.createElement('input')
  campo.className = classe
  campo.value = valor
  if (placeholder) campo.placeholder = placeholder
  if (lista) campo.setAttribute('list', lista)
  antes?.()
  alvo.replaceWith(campo)
  campo.focus()
  campo.select()
  let feito = false
  const concluir = (ok) => {
    if (feito) return
    feito = true
    if (ok) gravar(campo.value)
    else desistir()
  }
  campo.addEventListener('keydown', (k) => {
    if (k.key === 'Enter') { k.preventDefault(); concluir(true) }
    if (k.key === 'Escape') { k.preventDefault(); k.stopPropagation(); concluir(false) }
  })
  if (conhecidas) campo.addEventListener('change', () => conhecidas.includes(tagLimpa(campo.value)) && concluir(true))
  campo.addEventListener('blur', () => concluir(true))
  for (const t of ['click', 'mousedown']) campo.addEventListener(t, (k) => k.stopPropagation())
}
