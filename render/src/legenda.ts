// do 18: frontend/src/legenda/legenda.ts (sem os hooks: a página de render só calcula os blocos)
import type { ItemBanco, ItemRef } from './tipos'
import { comentarioDe } from './comentario'
import type { PalavraSaida } from './direcaoProjeto'
import { geometriaDoAtor, topoDoAtor, type Geometria } from './ator'
import { alturaDoComentario, aspectosDe, divisaoDe, lugarDoComentario, noQuadro, type Divisao } from './divisao'
import type { PedidoNoTempo as Pedido } from './inserts'
import type { Preset } from './presets'

/** A legenda (SPEC §8.10; docs/legenda.md), no estilo medido nas referências (`ferramentas/legenda_analisar.py`): a SF
 *  Pro Display em negrito, branca, com sombra difusa, centralizada, **uma palavra por vez** (o mais comum: 7 das 10
 *  referências) ou frases curtas (até 3 palavras), na altura de cada tipo de plano e desviando do card do comentário.
 *  Os blocos saem daqui para a prévia, para a etapa e para a página de render (o ASS da exportação, `legenda.py`). */
export type Modo = 'palavra' | 'frase'
/** Um ajuste preso às palavras: o bloco vai até `fim`, com `texto` corrigido ('' esconde). `modo`: uma presilha (só o
 *  `fim`) que o Separar pôs no Frase curta para o agrupamento automático não desfazer a separação; ela só vale nesse
 *  modo (no Palavra a palavra, juntaria palavras que o criador nunca juntou ali). */
export type Ajuste = { fim?: string; texto?: string; modo?: Modo }
/** O ajuste como vale no modo de agora: uma presilha de outro modo não vale (é como se não houvesse ajuste). */
export const ajusteNoModo = (aj: Ajuste | undefined, modo: Modo): Ajuste | undefined => (aj?.modo && aj.modo !== modo ? undefined : aj)
export type Legenda = { ligada: boolean; modo: Modo; ajustes: Record<string, Ajuste> }
/** Um bloco no tempo da saída: as palavras (ids), o texto, quando aparece e some, o centro do texto (fração da altura)
 *  e se foi mexido à mão (`ajustado`) ou escondido (`oculto`: texto vazio). */
export type Bloco = { id: string; palavras: string[]; texto: string; ini: number; fim: number; y: number; ajustado: boolean; oculto: boolean }

/** O estilo: o tamanho em fração da altura do quadro (56 px num 1080×1920; o ASS usa 66 no libass, que mede a fonte de
 *  outro jeito), a sombra (escolhida lado a lado com as referências) e a altura do centro do texto em cada tipo de plano
 *  (a mediana medida nas referências; `alturaDaLegenda` acerta pela costura real e pelo card do comentário). */
export const ESTILO = {
  fonte: "'SF Pro Display', system-ui, sans-serif",
  peso: 700,
  tamanho: 56 / 1920,
  espaco: '-0.01em',
  sombra: { y: 3 / 1920, blur: 12 / 1920, cor: 'rgba(0,0,0,0.67)' },
  margem: 0.06,
}
const ALTURA_POR_PLANO: Record<string, number> = {
  full_ator: 0.554,
  full_ator_zoom: 0.554,
  full_ator_lettering: 0.524,
  tela_dividida_insert: 0.453,
  tela_dividida_motion: 0.476,
  insert_tela_cheia: 0.428,
  motion_tela_cheia: 0.504,
  comentario_insert_ator: 0.409,
}
const ALTURA_PADRAO = 0.554
/** O tempo, medido nas referências (`ferramentas/legenda_ritmo.py`, a mesma transcrição do ElevenLabs dos projetos):
 *  o bloco entra 0,17 s antes da 1ª palavra (a mediana; de 0,15 a 0,21 s nas 10 referências) e sai ~0,1 s antes do fim
 *  da última; numa pausa de 0,3 s ou mais ele some antes da próxima palavra (8 de 10 pausas), numa menor fica até o
 *  próximo bloco. */
const ANTECIPA = 0.17
const SEGURA = 0.3
const MINIMO = 0.12 // s: o mínimo que um bloco fica na tela antes do próximo (3 quadros a 24 fps)
const SOBRA = 0.07 // depois do fim (antecipado) da última palavra: sai ~0,1 s antes do fim da fala
/** Frase curta: escolhido (não medido) — até 3 palavras e 18 letras, quebrando na pontuação e nas pausas de 0,3 s
 *  (três referências usam frases, com mediana de 2 a 3 palavras). */
const FRASE = { palavras: 3, letras: 18, pausa: 0.3 }
/** A legenda num insert de tela cheia com mídia deitada: abaixo do card centrado (o 16:9 na largura toda vai de ~34%
 *  a ~66% da altura; mvi-0717 v3 c3: a legenda caía em cima do vídeo). */
const ALTURA_DEITADA = 0.76

/** Meia altura da linha (a fonte com a entrelinha) e a folga até um card que a legenda contorna. */
const MEIA = (ESTILO.tamanho * 1.15) / 2
const FOLGA = 0.015

/** O texto de uma palavra na legenda (a vírgula e o ponto e vírgula saem; a pergunta e a exclamação ficam). */
const limpar = (t: string) => t.replace(/[,;:]+$/, '')

/** O que há na tela num trecho (um insert) e muda a altura da legenda: a divisão da tela (onde fica a costura), o ator
 *  no "ator embaixo" (a geometria, `ator/ator.ts`; sem o rosto, que só muda o x) e o card do comentário (`y`: o
 *  centro, `h`: a altura, frações do quadro). */
export type Zona = { ini: number; fim: number; divisao: Divisao | null; ator?: Geometria | null; card: { y: number; h: number } | null; deitada?: boolean; y?: number }

export function zonasDaLegenda(pedidos: Pedido[], banco: Map<string, ItemBanco> | null | undefined, presets: Preset[] | null | undefined): Zona[] {
  return pedidos.map((x) => {
    const divisao = x.midias.length > 0 ? divisaoDe(x, banco, presets) : null
    const ator = geometriaDoAtor(divisao, x.enriquecimento?.ator, null)
    let card = null
    if (x.tipo === 'comentario_insert_ator') {
      const c = comentarioDe(x, lugarDoComentario(x, divisao, ator))
      const texto = c.texto ?? x.texto ?? ''
      card = { y: noQuadro(c, texto).y / 100, h: alturaDoComentario(texto, c.escala) } // onde ele aparece (inteiro no quadro)
    }
    // um insert em tela cheia só com mídias deitadas: o card fica no meio do quadro, e a legenda desce para baixo dele
    const as = x.formato !== 'dividida' && x.midias.length ? aspectosDe(x.midias, banco) : []
    const deitada = as.length > 0 && as.every((a) => a >= 1.2)
    return { ini: x.t.inicio, fim: x.t.fim, divisao, ator, card, deitada }
  })
}

/** A altura do centro da legenda num instante: a medida para o tipo de plano; na tela dividida, a costura real do
 *  trecho (a divisão de cada insert, `divisaoDe`; o motion dividido é meio a meio); no "ator embaixo", a mesma altura
 *  do Full ator dentro do ator encolhido (na janela ou no recortado, onde ele estiver; no canto, logo acima da caixa);
 *  e, se houver um card de comentário ali, logo acima dele (ou abaixo, se não couber). Inserts em tela cheia e motions não são lidos (o conteúdo é desenhado na hora): fica a
 *  altura medida. */
function alturaDaLegenda(tipo: string | undefined, z: Zona | null): number {
  if (z?.y != null) return z.y // o motion diz onde a legenda não atrapalha (`legenda_y` no edicao.motions)
  let y = ALTURA_POR_PLANO[tipo ?? ''] ?? ALTURA_PADRAO
  const d = z?.divisao
  if (d?.modo === 'metade') y = Math.min(Math.max(d.f, 0.3), 0.7)
  else if (d?.modo === 'atras') {
    // na janela e no recortado, a altura do Full ator dentro do ator encolhido; no canto (o ator pequeno), logo acima dele
    const g: Geometria = z?.ator ?? { modo: 'janela', s: 0.55, tx: 0.225, ty: 0.45 }
    y = g.modo === 'canto' ? topoDoAtor(g) - MEIA - FOLGA : g.ty + ALTURA_POR_PLANO.full_ator * g.s
  }
  else if (tipo === 'tela_dividida_motion') y = 0.5
  else if (tipo === 'insert_tela_cheia' && z?.deitada) y = ALTURA_DEITADA
  return z?.card ? desviar(y, z.card) : y
}

/** A altura `y` fora do card `c`: logo acima dele (ou abaixo, se não couber); sem bater nele, fica. */
function desviar(y: number, c: { y: number; h: number }) {
  if (!(y + MEIA + FOLGA > c.y - c.h / 2 && y - MEIA - FOLGA < c.y + c.h / 2)) return y
  const acima = c.y - c.h / 2 - FOLGA - MEIA
  const abaixo = c.y + c.h / 2 + FOLGA + MEIA
  return acima >= 0.08 ? acima : abaixo <= 0.92 ? abaixo : y
}

/** Os ajustes que valem no vídeo de agora e os órfãos (SPEC §9, como os planos da direção em `paraTempo`). Um ajuste
 *  cobre as palavras da sua (a chave) até `fim` (sem `fim`, só a sua). Se a 1ª palavra foi cortada, ele passa à 1ª que
 *  sobrou nesse intervalo, e o `fim` à última que sobrou; se nenhuma sobrou, fica órfão — a etapa mostra, para reatar
 *  à próxima palavra que ficou ou descartar. `palavras`: todas, na ordem da fala. */
export type Orfao = { id: string; ajuste: Ajuste; fala: string; reatar: string | null }
export function ajustesNoVideo(ajustes: Record<string, Ajuste>, palavras: { id: string; texto: string }[], saida: PalavraSaida[]) {
  const ordem = new Map(palavras.map((w, k) => [w.id, k]))
  const ficou = new Set(saida.map((w) => w.id))
  const naOrdem = [...saida].sort((a, b) => (ordem.get(a.id) ?? 0) - (ordem.get(b.id) ?? 0))
  const valem: Record<string, Ajuste> = {}
  const orfaos: Orfao[] = []
  const pendentes: [string, Ajuste, number, number][] = []
  for (const [id, aj] of Object.entries(ajustes)) {
    if (ficou.has(id) && (aj.fim == null || ficou.has(aj.fim))) {
      valem[id] = aj
      continue
    }
    const a = ordem.get(id)
    pendentes.push([id, aj, a ?? -1, aj.fim != null ? (ordem.get(aj.fim) ?? a ?? -1) : (a ?? -1)])
  }
  for (const [id, aj, a, b] of pendentes) {
    const dentro = a < 0 ? [] : naOrdem.filter((w) => (ordem.get(w.id) ?? -1) >= a && (ordem.get(w.id) ?? -1) <= b)
    const novo = dentro[0]?.id
    if (novo && !valem[novo] && (novo === id || !ajustes[novo])) {
      valem[novo] = aj.fim != null ? { ...aj, fim: dentro[dentro.length - 1].id } : aj
      continue
    }
    const proxima = naOrdem.find((w) => (ordem.get(w.id) ?? -1) > b && !valem[w.id] && !ajustes[w.id])
    const fala = a < 0 ? '' : palavras.slice(a, Math.max(a, b) + 1).map((w) => w.texto).join(' ')
    orfaos.push({ id, ajuste: aj, fala, reatar: proxima?.id ?? null })
  }
  return { valem, orfaos }
}

/** Os blocos da legenda no tempo da saída. `palavras`: todas, na ordem da fala (para os ajustes de palavras cortadas;
 *  sem elas, valem só os ajustes de palavras que ficaram); `zonas`: os inserts na tela (`zonasDaLegenda`). */
export function blocosDaLegenda(saida: PalavraSaida[], planos: ItemRef[], lg: Legenda, palavras?: { id: string; texto: string }[], zonas: Zona[] = []): Bloco[] {
  const ws = [...saida].sort((a, b) => a.saida_ini - b.saida_ini)
  const pos = new Map(ws.map((w, i) => [w.id, i]))
  const valem = ajustesNoVideo(lg.ajustes, palavras ?? ws, ws).valem
  const ajustes: Record<string, Ajuste> = {}
  for (const [id, aj] of Object.entries(valem)) if (ajusteNoModo(aj, lg.modo)) ajustes[id] = aj
  const brutos: (Omit<Bloco, 'fim' | 'y'> & { fala: number; fimFala: number })[] = []
  for (let i = 0; i < ws.length; ) {
    const aj = ajustes[ws[i].id]
    let j = i
    const fimManual = aj?.fim != null ? pos.get(aj.fim) : undefined
    if (fimManual != null && fimManual >= i) j = fimManual
    // um texto à mão sem `fim` (gravado antes de o texto prender as palavras) fica só na sua palavra
    else if (aj?.texto != null) j = i
    else if (lg.modo === 'frase') {
      let letras = ws[i].texto.length
      while (
        j + 1 < ws.length &&
        j - i + 1 < FRASE.palavras &&
        !ajustes[ws[j + 1].id] &&
        !/[.!?,;:…]$/.test(ws[j].texto) &&
        ws[j + 1].saida_ini - ws[j].saida_fim < FRASE.pausa &&
        letras + 1 + ws[j + 1].texto.length <= FRASE.letras
      ) {
        j++
        letras += 1 + ws[j].texto.length
      }
    }
    const grupo = ws.slice(i, j + 1)
    const auto = grupo.map((w) => limpar(w.texto)).join(' ')
    const texto = aj?.texto ?? auto
    // antecipado, mas nunca antes do zero nem a menos de `MINIMO` do anterior: no começo do vídeo (a 1ª palavra colada
    // no zero), os primeiros blocos ficam legíveis e a antecipação volta em poucas palavras
    const ant = brutos[brutos.length - 1]
    const ini = Math.max(ws[i].saida_ini - ANTECIPA, 0, ant ? Math.min(ant.ini + MINIMO, ws[i].saida_ini) : 0)
    brutos.push({
      id: ws[i].id,
      palavras: grupo.map((w) => w.id),
      texto,
      ini,
      ajustado: !!aj,
      oculto: !texto.trim(),
      fala: ws[i].saida_ini,
      fimFala: ws[j].saida_fim,
    })
    i = j + 1
  }
  const ps = [...planos].sort((a, b) => a.inicio - b.inicio)
  return brutos.map(({ fala, fimFala, ...b }, k) => {
    const prox = brutos[k + 1]
    let fim = prox && prox.fala - fimFala < SEGURA ? prox.ini : fimFala - ANTECIPA + SOBRA
    fim = Math.max(fim, b.ini + 0.05)
    // nunca por cima do próximo (duas palavras que começam quase juntas: no ASS, as duas apareceriam sobrepostas)
    if (prox) fim = Math.min(fim, prox.ini)
    const plano = ps.find((p) => p.inicio <= fala + 0.001 && fala < p.fim)
    const zona = zonas.find((z) => z.ini <= fala + 0.001 && fala < z.fim) ?? null
    // o bloco entra antes da fala (`ANTECIPA`): a 1ª palavra de um plano aparece ainda no anterior, e desvia também do
    // card do comentário de lá enquanto ele está na tela
    let y = alturaDaLegenda(plano?.tipo, zona)
    for (const z of zonas) if (z !== zona && z.card && z.ini < fim && b.ini < z.fim) y = desviar(y, z.card)
    return { ...b, fim, y }
  })
}

/** A legenda sem o que um lettering já mostra (o Full ator com lettering e o elemento Lettering, `elementos.ts`; nas
 *  referências os dois nunca aparecem juntos): some o bloco cujas palavras caem todas (pelo meio delas) dentro de um
 *  lettering; o que entraria durante ele (a antecipação) entra quando ele sai, os seguintes a `MINIMO` um do outro, e o
 *  que ficaria na tela quando ele entra sai ali (colado num bloco que sumiu, fica até o lettering entrar). */
export function semOsLetterings(bs: Bloco[], saida: PalavraSaida[], letterings: { ini: number; fim: number }[]): Bloco[] {
  if (!letterings.length) return bs
  const ls = [...letterings].sort((x, y) => x.ini - y.ini)
  const meio = new Map(saida.map((w) => [w.id, (w.saida_ini + w.saida_fim) / 2]))
  const dentro = (t: number | undefined) => t != null && ls.some((l) => l.ini <= t && t < l.fim)
  const ficam = bs.flatMap((b, i) => (b.palavras.every((id) => dentro(meio.get(id))) ? [] : [{ b, i, ini: b.ini }]))
  ficam.forEach((x, k) => {
    for (const l of ls) if (x.ini >= l.ini && x.ini < l.fim) x.ini = l.fim
    const ant = ficam[k - 1]
    if (ant && (x.ini !== x.b.ini || ant.ini !== ant.b.ini)) x.ini = Math.max(x.ini, ant.ini + MINIMO)
  })
  return ficam.flatMap((x, k) => {
    const { b, ini } = x
    const prox = ficam[k + 1]
    const colado = bs[x.i + 1] && b.fim >= bs[x.i + 1].ini - 1e-6
    let fim = colado && prox ? prox.ini : ini !== b.ini ? Math.max(b.fim, ini + MINIMO) : b.fim
    if (prox) fim = Math.min(fim, prox.ini)
    for (const l of ls) if (ini < l.ini && fim > l.ini) fim = l.ini
    return fim - ini >= 0.05 ? [{ ...b, ini, fim }] : []
  })
}

/** O bloco que aparece no instante `t` (escondidos não contam). */
export const blocoNoTempo = (bs: Bloco[], t: number) => bs.find((b) => !b.oculto && b.ini <= t && t < b.fim) ?? null

/** Para a página de render: os blocos visíveis no formato do ASS (`legenda.py`). */
export const paraExportar = (bs: Bloco[]) => bs.filter((b) => !b.oculto).map((b) => ({ ini: b.ini, fim: b.fim, texto: b.texto, y: b.y }))
