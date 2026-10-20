// Marcar trechos de um vídeo do banco (do 18: inserts/EditorVideo.tsx): o vídeo, a linha do tempo com a tira de quadros e
// a lista. Arrastar no vazio cria um trecho; arrastar o trecho o move; as alças ajustam as pontas. I / O marcam entrada e
// saída, espaço toca (com um trecho escolhido e o vídeo parado, toca só ele), ← → um quadro (Shift: 1 s), Delete apaga.
// Nada vai para o disco até "Salvar trechos"; cada trecho salvo vira um item do banco, com o código próprio.
import { $, ICONE, aviso, confirmar, enviar, esc, janela, json, num, tempo } from './comum.js'

const QUADRO = 1 / 30
const MIN = 0.2 // como o MIN_TRECHO do banco.py
const q = (t) => Math.round(t / QUADRO) * QUADRO

/** `op`: {base (a pasta do vídeo), um (um trecho só: o CTA), titulo, salvar(t) (grava o trecho único)} — sem `op`, o banco. */
export async function marcarTrechos(item, trechos, aoSalvar, op = {}) {
  const dur = item.duracao || 0
  const base = op.base || `/biblioteca/banco/${item.id}/`
  const tira = (await json(op.tira || `/api/banco/${item.id}/tira`, null))?.url
  // a lista: os trechos que já existem (com id) e os novos; os apagados saem no Salvar
  let lista = trechos.map((t) => ({ id: t.id, nome: t.nome, inicio: t.inicio, fim: t.fim, orig: `${t.nome}|${t.inicio}|${t.fim}` }))
  const apagados = []
  let sel = -1
  let entrada = null
  let parar = null
  const { el, fechar } = janela(`
    <header class="janela-cabeca"><h2>${esc(op.titulo || 'Marcar trechos')} · ${esc(item.nome)}</h2><span class="dica">${tempo(dur)}</span>
      <button class="botao-icone" data-fechar title="Fechar (Esc)">${ICONE.fechar}</button></header>
    <div class="te">
      <div class="te-esq">
        <div class="te-video"><video src="${base}${item.proxy || item.arquivo}" playsinline preload="auto"></video></div>
        <div class="te-controles"><button class="botao-icone" data-te="tocar" title="Tocar / pausar (Espaço)">${ICONE.tocar}</button>
          <span class="te-tempo"><b id="te-t">0:00,0</b> / ${tempo(dur)}</span><span class="te-aviso" id="te-aviso"></span>
          <span class="dica te-dica">arraste para criar · I / O · ← → um quadro · espaço toca</span></div>
      </div>
      <aside class="te-dir"><span class="eyebrow" id="te-titulo"></span><div class="te-lista" id="te-lista"></div>
        <button class="botao botao-coral" data-te="salvar">${op.um ? 'Salvar' : 'Salvar trechos'}</button></aside>
        <div class="te-linha">
          <div class="te-regua" id="te-regua"></div>
          <div class="te-faixa" id="te-faixa" style="${tira ? `background-image:url('${tira}')` : ''}">
            <div class="te-novo" id="te-novo" hidden></div><div id="te-trechos"></div><div class="te-agulha" id="te-agulha"></div></div>
        </div>
    </div>`, { classe: 'janela-trechos', aoFechar: () => document.removeEventListener('keydown', tecla, true) })
  const v = $('video', el)
  const faixa = $('#te-faixa', el)
  const pct = (t) => `${Math.max(0, Math.min(1, t / Math.max(dur, 0.001))) * 100}%`
  const emT = (x) => {
    const r = faixa.getBoundingClientRect()
    return q(Math.max(0, Math.min(1, (x - r.left) / r.width)) * dur)
  }
  // a busca não faz fila: enquanto o vídeo busca, guarda só o último alvo
  let alvo = null
  const buscar = (t) => {
    if (v.seeking) alvo = t
    else v.currentTime = t
  }
  v.addEventListener('seeked', () => {
    if (alvo != null) {
      const t = alvo
      alvo = null
      v.currentTime = t
    }
  })

  // a régua: o passo que dá até ~12 marcas
  const passo = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300].find((p) => dur / p <= 12) || 600
  $('#te-regua', el).innerHTML = Array.from({ length: Math.floor(dur / passo) + 1 }, (_, k) => `<span style="left:${pct(k * passo)}">${tempo(k * passo).replace(/,\d$/, '')}</span>`).join('')

  const desenhar = () => {
    $('#te-trechos', el).innerHTML = lista.map((t, k) => `<div class="te-trecho${k === sel ? ' sel' : ''}" data-k="${k}" style="left:${pct(t.inicio)};width:calc(${pct(t.fim)} - ${pct(t.inicio)})">
        <i class="te-alca" data-alca="a"></i><span>${k + 1}</span><i class="te-alca" data-alca="b"></i></div>`).join('')
    $('#te-titulo', el).textContent = `Trechos · ${lista.length}`
    $('#te-lista', el).innerHTML = lista.length
      ? lista.map((t, k) => `<div class="te-item${k === sel ? ' sel' : ''}" data-k="${k}"><b>${k + 1}</b>
          <input value="${esc(t.nome)}" data-nome="${k}" aria-label="Nome do trecho ${k + 1}">
          <span class="dica">${num(t.fim - t.inicio, 1)} s</span>
          <button class="botao-icone pequeno" data-tocar-trecho="${k}" title="Tocar o trecho">${ICONE.tocar}</button>
          <button class="botao-icone pequeno" data-apagar-trecho="${k}" title="Apagar o trecho">${ICONE.lixo}</button></div>`).join('')
      : '<p class="dica">Arraste na linha do tempo para criar um trecho.</p>'
  }
  const novo = (a, b) => {
    const ini = q(Math.max(0, Math.min(a, b)))
    const fim = q(Math.min(dur, Math.max(a, b)))
    if (fim - ini < MIN) return
    if (op.um) {  // um trecho só: arrastar de novo substitui o anterior
      const t = lista[0] || { id: item.id, nome: item.nome }
      lista = [{ ...t, inicio: ini, fim }]
      sel = 0
      return desenhar()
    }
    lista.push({ id: null, nome: `${item.nome} · trecho ${lista.length + 1}`, inicio: ini, fim })
    sel = lista.length - 1
    desenhar()
  }
  const tocarTrecho = (k) => {
    const t = lista[k]
    sel = k
    desenhar()
    v.currentTime = t.inicio
    parar = t.fim
    v.play().catch(() => {})
  }
  const apagar = async (k) => {
    const t = lista[k]
    if (t.id && !(await confirmar({ titulo: `Apagar “${t.nome}”?`, texto: 'O trecho sai do banco quando você salvar.', ok: 'Apagar', perigo: true }))) return
    if (t.id) apagados.push(t)
    lista.splice(k, 1)
    sel = -1
    desenhar()
  }
  const relogio = () => {
    $('#te-t', el).textContent = tempo(v.currentTime)
    $('#te-agulha', el).style.left = pct(v.currentTime)
    if (parar != null && v.currentTime >= parar) {
      v.pause()
      parar = null
    }
    $('[data-te="tocar"]', el).innerHTML = v.paused ? ICONE.tocar : ICONE.pausar
    if (el.isConnected) requestAnimationFrame(relogio)
  }
  requestAnimationFrame(relogio)
  const alternar = () => {
    if (!v.paused) return v.pause()
    if (sel >= 0 && parar == null) return tocarTrecho(sel)
    v.play().catch(() => {})
  }

  // arrastar na faixa: no vazio cria; no trecho move; na alça ajusta a ponta (os movimentos seguem a janela inteira)
  const segue = (mover, soltar) => {
    const m = (e) => mover(e)
    const s = (e) => {
      window.removeEventListener('pointermove', m)
      window.removeEventListener('pointerup', s)
      soltar?.(e)
    }
    window.addEventListener('pointermove', m)
    window.addEventListener('pointerup', s)
  }
  faixa.addEventListener('pointerdown', (e) => {
    e.preventDefault()
    const x0 = e.clientX
    // arrastar a caixa a desliza na linha do tempo; as alças ajustam as pontas; arrastar no vazio marca um trecho novo
    // (num trecho só, o novo substitui o anterior)
    const caixa = e.target.closest('.te-trecho')
    if (caixa) {
      const k = +caixa.dataset.k
      const t = lista[k]
      sel = k
      const lado = e.target.dataset.alca
      const [i0, f0] = [t.inicio, t.fim]
      desenhar()
      segue((ev) => {
        const tt = emT(ev.clientX)
        if (lado === 'a') t.inicio = Math.min(tt, t.fim - MIN)
        else if (lado === 'b') t.fim = Math.max(tt, t.inicio + MIN)
        else {
          const d = f0 - i0
          t.inicio = q(Math.max(0, Math.min(i0 + tt - emT(x0), dur - d)))
          t.fim = t.inicio + d
        }
        buscar(lado === 'b' ? t.fim : t.inicio)
        desenhar()
      })
      return
    }
    const a = emT(x0)
    let b = a
    let criando = false
    buscar(a)
    sel = -1
    desenhar()
    const caixaNova = $('#te-novo', el)
    segue((ev) => {
      criando ||= Math.abs(ev.clientX - x0) >= 6
      b = emT(ev.clientX)
      if (criando) {
        caixaNova.hidden = false
        caixaNova.style.left = pct(Math.min(a, b))
        caixaNova.style.width = `calc(${pct(Math.max(a, b))} - ${pct(Math.min(a, b))})`
      }
      buscar(b)
    }, () => {
      caixaNova.hidden = true
      if (criando && Math.abs(b - a) >= MIN) novo(a, b)
    })
  })
  // a régua só navega
  $('#te-regua', el).addEventListener('pointerdown', (e) => {
    buscar(emT(e.clientX))
    segue((ev) => buscar(emT(ev.clientX)))
  })

  el.addEventListener('input', (e) => {
    const k = e.target.dataset?.nome
    if (k != null) lista[+k].nome = e.target.value
  })
  el.addEventListener('click', async (e) => {
    const b = e.target.closest('button')
    if (!b) {
      const linha = e.target.closest('.te-item')
      if (linha && !e.target.closest('input')) {
        sel = +linha.dataset.k
        buscar(lista[sel].inicio)
        desenhar()
      }
      if (e.target.closest('.te-video')) alternar()
      return
    }
    if (b.dataset.tocarTrecho != null) return tocarTrecho(+b.dataset.tocarTrecho)
    if (b.dataset.apagarTrecho != null) return apagar(+b.dataset.apagarTrecho)
    if (b.dataset.te === 'tocar') return alternar()
    if (b.dataset.te === 'salvar') return salvar(b)
  })
  const tecla = (e) => {
    if (!el.isConnected || e.target.closest?.('input, textarea')) return
    const k = e.key
    if (k === ' ') alternar()
    else if (k === 'ArrowLeft' || k === 'ArrowRight') {
      v.pause()
      buscar(q(Math.max(0, Math.min(dur, v.currentTime + (k === 'ArrowLeft' ? -1 : 1) * (e.shiftKey ? 1 : QUADRO)))))
    } else if (k === 'i' || k === 'I') {
      entrada = q(v.currentTime)
      $('#te-aviso', el).textContent = `entrada em ${tempo(entrada)} · aperte O para fechar`
    } else if ((k === 'o' || k === 'O') && entrada != null) {
      novo(entrada, v.currentTime)
      entrada = null
      $('#te-aviso', el).textContent = ''
    } else if ((k === 'Delete' || k === 'Backspace') && sel >= 0) apagar(sel)
    else return
    e.preventDefault()
    e.stopPropagation()
  }
  document.addEventListener('keydown', tecla, true)

  async function salvar(botao) {
    if (op.um) {
      if (!lista.length) return aviso('Marque o trecho na linha do tempo', 'erro')
      try {
        await op.salvar({ inicio: +lista[0].inicio.toFixed(3), fim: +lista[0].fim.toFixed(3), nome: lista[0].nome.trim() || undefined })
      } catch (x) {
        return aviso(x.message, 'erro')
      }
      aviso('Salvo')
      fechar()
      return aoSalvar?.()
    }
    botao.disabled = true
    const erros = []
    for (const t of apagados) {
      try {
        await enviar('DELETE', `/api/banco/${t.id}`)
      } catch (x) {
        erros.push(`${t.nome}: ${x.message}`)
      }
    }
    // na ordem da linha do tempo: os códigos (BAN-012.1, .2…) seguem a ordem dos trechos no vídeo
    for (const t of [...lista].sort((x, y) => x.inicio - y.inicio)) {
      const corpo = { nome: t.nome.trim() || undefined, inicio: +t.inicio.toFixed(3), fim: +t.fim.toFixed(3) }
      try {
        if (!t.id) await enviar('POST', `/api/banco/${item.id}/trechos`, corpo)
        else if (`${t.nome}|${t.inicio}|${t.fim}` !== t.orig) await enviar('PUT', `/api/banco/${t.id}`, corpo)
      } catch (x) {
        erros.push(`${t.nome}: ${x.message}`)
      }
    }
    botao.disabled = false
    if (erros.length) return aviso(erros.join(' · '), 'erro')
    aviso('Trechos salvos')
    fechar()
    aoSalvar?.()
  }
  desenhar()
}
