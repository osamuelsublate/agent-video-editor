# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.63.0"]
# ///
"""Dá para ler os textos de um preset de motion? Abre render/motion.html, caminha o tempo com window.__ir(t) e lê do DOM
os textos visíveis, com caixa e opacidade reais (nada novo é pedido ao motion; inspirado no readcheck do lemo-opuscar).

    uv run ferramentas/leitura.py <preset> [--formato vertical] [--duracao N]

Use --duracao com a duração do plano: a padrão do preset costuma ser a de um vídeo antigo. Os campos ficam nos padrões.
Sai 0 se passa, 1 se reprova, 2 se não deu para checar (o preset não existe, ou nunca ficou pronto).

Reprova: texto que nunca fica inteiro no palco (ou fica mais de 0,6 s cortado na borda) e texto que fica menos que
caracteres ÷ 15 + 1,5 s (mínimo 1,5 s), com tolerância de 0,15 s. Conta só opacidade ≥ 0,5, sem desfoque forte e sem máscara
cobrindo a maior parte. O tempo é o maior trecho contínuo; o texto que cresce (digitação) conta do primeiro quadro, e um
contador em que só os números mudam é um texto só.
Exceção, palavra por palavra: palavras soltas do mesmo pai que entram em tempos diferentes (acumulando, como no
`lettering`, ou uma trocando a outra), ou um bloco que cresce em palavras inteiras. O olho já está ali e a fala
acompanha: sem a folga de 1,5 s, o conjunto fica caracteres ÷ 15 e cada palavra, ao menos 0,2 s.
Fora da regra, sem reprovar (a saída diz): até 2 letras (cursor, seta, número de lista); menos de 35 px no palco (o miúdo
de uma interface); e 20 textos ou mais num motion só (uma parede ou cascata, em que ninguém lê um a um).
Não vê: texto em canvas ou dentro de imagem (avisa do canvas) e texto coberto por outro elemento (conta como visível).
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA  # noqa: E402

FORMATOS = {'vertical': (1080, 1920), 'dividida': (1080, 960)}  # os de render/motion.html
PASSO = 0.05  # s entre as leituras (um texto que ficou menos que isso pode nem ser visto)
LETRAS_POR_S, FOLGA, MINIMO = 15, 1.5, 1.5  # a regra: caracteres ÷ 15 + 1,5 s, nunca menos de 1,5 s
FALHA = 0.2  # um sumiço até isso não quebra o tempo do texto (um brilho, um cursor piscando)
FORA_MAX = 0.6  # s com o texto cortado na borda do palco: acima disso não é mais a entrada ou a saída dele
PALAVRA_MIN = 0.2  # s que cada palavra tem de ficar, quando o motion mostra uma de cada vez
TAMANHO_MIN = 35  # px no palco: abaixo disso é o miúdo de uma interface (barra de título, atalho, status), não é para ler
TEXTURA = 20  # textos num motion só: daí para cima é uma parede ou uma cascata (capas, cards), ninguém lê um a um
TOLERANCIA = 0.15  # s: abaixo disso ninguém nota, e a medida anda de PASSO em PASSO
JUNCAO = 0.4  # s entre o mesmo texto em dois elementos (o digitado que vira balão) para ser um texto só

# Roda na página: os textos visíveis agora, agrupados por bloco (o que está em linha com o texto conta como o mesmo bloco).
LER = r"""
async ({ passo, duracao }) => {
  document.querySelectorAll('video').forEach((v) => v.remove()) // o vídeo não tem texto e o __ir espera cada busca nele
  const palco = document.getElementById('palco')
  const P = palco.getBoundingClientRect()
  const ids = new WeakMap()
  let prox = 0
  const id = (e) => { if (!ids.has(e)) ids.set(e, ++prox); return ids.get(e) }
  const EM_LINHA = new Set(['inline', 'inline-block', 'inline-flex', 'contents'])
  const alfa = (cor) => { const m = cor.match(/rgba?\(([^)]+)\)/); if (!m) return 1; const p = m[1].split(/[,\s/]+/); return p.length > 3 ? parseFloat(p[3]) : 1 }

  function ler() {
    const est = new Map()
    const css = (e) => { if (!est.has(e)) est.set(e, getComputedStyle(e)); return est.get(e) }
    // a opacidade real: a do texto vezes a de todos os ancestrais; desfocado ou de display:none não se lê
    const opacidade = (e) => {
      const s = css(e)
      if (s.visibility !== 'visible') return 0
      let op = s.backgroundClip === 'text' ? 1 : alfa(s.webkitTextFillColor || s.color)
      for (let a = e; a && a !== document.body; a = a.parentElement) {
        const c = css(a)
        if (c.display === 'none') return 0
        op *= parseFloat(c.opacity)
        const b = c.filter.match(/blur\(([\d.]+)px/)
        if (b && +b[1] >= 3) return 0
      }
      return op
    }
    // a parte da caixa que os ancestrais não cortam (overflow e clip-path: inset), sem contar o palco
    const cortada = (r, e) => {
      let [x0, y0, x1, y1] = [r.left, r.top, r.right, r.bottom]
      for (let a = e; a && a !== palco; a = a.parentElement) {
        const c = css(a), q = a.getBoundingClientRect()
        if (c.overflowX !== 'visible') { x0 = Math.max(x0, q.left); x1 = Math.min(x1, q.right) }
        if (c.overflowY !== 'visible') { y0 = Math.max(y0, q.top); y1 = Math.min(y1, q.bottom) }
        const m = c.clipPath.match(/^inset\(([^)]*)\)/)
        if (m) {
          const v = m[1].split(' round ')[0].trim().split(/\s+/)
          const med = (k, base) => { const x = v[k] ?? v[k % 2] ?? v[0]; return x.endsWith('%') ? (parseFloat(x) / 100) * base : parseFloat(x) || 0 }
          y0 = Math.max(y0, q.top + med(0, q.height)); x1 = Math.min(x1, q.right - med(1, q.width))
          y1 = Math.min(y1, q.bottom - med(2, q.height)); x0 = Math.max(x0, q.left + med(3, q.width))
        }
      }
      return Math.max(0, x1 - x0) * Math.max(0, y1 - y0)
    }
    // o tamanho que aparece: a fonte vezes a escala dos transforms até o palco
    const tamanho = (e) => {
      let k = parseFloat(css(e).fontSize)
      for (let a = e; a && a !== palco; a = a.parentElement) {
        const m = css(a).transform
        if (m !== 'none') { const d = new DOMMatrix(m); k *= Math.hypot(d.a, d.b) }
      }
      return k
    }
    const bloco = (e) => {
      while (e !== palco && e.parentElement !== palco && e.tagName !== 'text' && EM_LINHA.has(css(e).display)) e = e.parentElement
      return e
    }
    const blocos = new Map()
    const w = document.createTreeWalker(palco, NodeFilter.SHOW_TEXT)
    const faixa = document.createRange()
    while (w.nextNode()) {
      const n = w.currentNode, e = n.parentElement
      if (!n.data.trim() || ['SCRIPT', 'STYLE'].includes(e.tagName) || opacidade(e) < 0.5) continue
      faixa.selectNodeContents(n)
      const r = faixa.getBoundingClientRect()
      if (r.width < 1 || r.height < 10) continue
      if (cortada(r, e) < 0.5 * r.width * r.height) continue // quase toda escondida por uma máscara
      if (r.right <= P.left || r.left >= P.right || r.bottom <= P.top || r.top >= P.bottom) continue
      const b = bloco(e)
      const g = blocos.get(b) || { el: id(b), pai: id(b.parentElement), texto: '', x0: r.left, y0: r.top, x1: r.right, y1: r.bottom, pais: e, tam: 0 }
      // palavras em caixas separadas não trazem o espaço; letra a letra (digitação), não se separa
      g.texto += (g.texto && g.pais !== e && n.data.trim().length > 1 ? ' ' : '') + n.data
      g.pais = e
      g.tam = Math.max(g.tam, tamanho(e))
      g.x0 = Math.min(g.x0, r.left); g.y0 = Math.min(g.y0, r.top); g.x1 = Math.max(g.x1, r.right); g.y1 = Math.max(g.y1, r.bottom)
      blocos.set(b, g)
    }
    return [...blocos.values()].map((g) => ({ el: g.el, pai: g.pai, texto: g.texto.replace(/\s+/g, ' ').trim(), tam: g.tam,
      dentro: g.x0 >= P.left - 2 && g.y0 >= P.top - 2 && g.x1 <= P.right + 2 && g.y1 <= P.bottom + 2 }))
  }

  // nunca chamou motion.pronto: cada __ir levaria os 8 s do limite do runtime
  const pronto = await Promise.race([window.__sons().then(() => true), new Promise((r) => setTimeout(() => r(false), 10000))])
  if (!pronto) return { quadros: [], canvas: 0, pronto }
  const quadros = []
  const n = Math.round(duracao / passo)
  for (let k = 0; k <= n; k++) {
    const t = Math.min(k * passo, duracao)
    await window.__ir(t)
    quadros.push({ t, textos: ler() })
  }
  return { quadros, canvas: document.querySelectorAll('canvas').length, pronto }
}
"""


def precisa(texto: str) -> float:
    return max(MINIMO, len(re.sub(r'\s', '', texto)) / LETRAS_POR_S + FOLGA)


def _letras(t: str) -> str:
    """Só letras e números: um cursor, um spinner (✢ ✳ ✶) ou a pontuação de outra cor não fazem outro texto."""
    return re.sub(r'[\W_]+', '', t)


def _mesmo_texto(a: str, b: str) -> bool:
    """O mesmo texto: crescendo ou apagando (digitação), ou um contador (só os números mudam)."""
    ca, cb = _letras(a), _letras(b)
    return ca.startswith(cb) or cb.startswith(ca) or re.sub(r'[\d.,:]+', '#', a) == re.sub(r'[\d.,:]+', '#', b)


def _pecas(quadros: list[dict]) -> list[dict]:
    """Junta as leituras em peças: o mesmo elemento com o mesmo texto (ou o texto crescendo)."""
    pecas: list[dict] = []
    por_el: dict[int, list[dict]] = {}
    for q in quadros:
        for x in q['textos']:
            doel = por_el.setdefault(x['el'], [])
            p = next((c for c in reversed(doel) if _mesmo_texto(c['texto'], x['texto'])), None)
            if p is None:
                p = {'el': x['el'], 'pai': x['pai'], 'texto': x['texto'], 'ini': q['t'], 'vezes': [], 'estados': [], 'tam': 0}
                doel.append(p)
                pecas.append(p)
            if len(x['texto']) > len(p['texto']):
                p['texto'] = x['texto']
            if not p['estados'] or p['estados'][-1] != x['texto']:
                p['estados'].append(x['texto'])
            p['tam'] = max(p['tam'], x.get('tam', TAMANHO_MIN))
            p['vezes'].append((q['t'], x['dentro']))
    return [p for p in _juntar_iguais(pecas) if _letras(p['texto'])]  # fora: um cursor, uma seta


def _juntar_iguais(pecas: list[dict]) -> list[dict]:
    """O mesmo texto em outro elemento, sem intervalo, é o mesmo texto: o digitado que vira balão, as cópias em camadas."""
    fora: list[dict] = []
    for p in sorted(pecas, key=lambda x: x['ini']):
        ant = next((a for a in reversed(fora) if _letras(a['texto']) == _letras(p['texto']) and p['ini'] - a['vezes'][-1][0] <= JUNCAO), None)
        if ant is None:
            fora.append(p)
            continue
        # no mesmo instante, basta uma das cópias estar inteira
        vezes = dict(ant['vezes'])
        for t, d in p['vezes']:
            vezes[t] = vezes.get(t, False) or d
        ant['vezes'] = sorted(vezes.items())
        ant['estados'] += p['estados']
        ant['tam'] = max(ant['tam'], p['tam'])
    return fora


def _tempo(vezes: list[float], passo: float, duracao: float) -> float:
    """O maior trecho contínuo (um sumiço de até FALHA não interrompe)."""
    melhor, ini, ant = 0.0, None, None
    for t in vezes:
        if ini is None or t - ant > FALHA:
            ini = t
        ant = t
        melhor = max(melhor, min(t + passo, duracao) - ini)
    return melhor


def _por_palavra(p: dict) -> bool:
    """Um bloco que cresce de palavra em palavra (spans em linha, sem digitação): cada estado acaba onde a palavra acaba."""
    final = p['estados'][-1].split(' ')
    return len(final) >= 2 and len(p['estados']) >= 2 and all(' '.join(final[:len(e.split(' '))]) == e for e in p['estados'])


def avaliar(quadros: list[dict], passo: float, duracao: float) -> list[dict]:
    """A nota de cada texto: {texto, ini, tempo, precisa, ok, motivo, tipo} (a regra está no topo do arquivo). Pura: os
    testes passam `quadros` sintéticos: [{t, textos: [{el, pai, texto, tam, dentro}]}]."""
    pecas = _pecas(quadros)
    notas: list[dict] = []
    if len(pecas) >= TEXTURA:
        return [{'texto': f'{len(pecas)} textos', 'ini': min(p['ini'] for p in pecas), 'tempo': duracao, 'precisa': 0.0, 'ok': True, 'motivo': '', 'tipo': 'textura, fora da regra'}]
    grupos: dict[int, list[dict]] = {}
    for p in pecas:
        if ' ' not in p['texto'] and p['tam'] >= TAMANHO_MIN:
            grupos.setdefault(p['pai'], []).append(p)
    em_grupo = set()
    for g in grupos.values():
        if len(g) >= 2 and max(x['ini'] for x in g) - min(x['ini'] for x in g) > 0.1:
            em_grupo.update(id(x) for x in g)
            g.sort(key=lambda x: x['ini'])
            texto = ' '.join(x['texto'] for x in g)
            fim = max(t for x in g for t, _ in x['vezes'])
            tempo = min(fim + passo, duracao) - g[0]['ini']
            alvo = len(re.sub(r'\s', '', texto)) / LETRAS_POR_S
            curtas = [x['texto'] for x in g if _tempo([t for t, d in x['vezes'] if d], passo, duracao) + passo < PALAVRA_MIN]
            fora = [x['texto'] for x in g if not any(d for _, d in x['vezes'])]
            motivo = (f'nunca inteira no palco: {", ".join(fora)}' if fora else
                      f'palavra rápida demais (< {PALAVRA_MIN} s): {", ".join(curtas)}' if curtas else
                      '' if tempo + TOLERANCIA >= alvo else f'curto: {tempo:.1f} s, precisa de {alvo:.1f} s')
            notas.append({'texto': texto, 'ini': g[0]['ini'], 'tempo': tempo, 'precisa': alvo, 'ok': not motivo, 'motivo': motivo, 'tipo': 'palavra a palavra'})
    for p in pecas:
        if id(p) in em_grupo or len(_letras(p['texto'])) <= 2:  # solto, "to" ou um número de lista não pedem leitura
            continue
        if p['tam'] < TAMANHO_MIN:  # não reprova: é aviso na saída
            notas.append({'texto': p['texto'], 'ini': p['ini'], 'tempo': _tempo([t for t, _ in p['vezes']], passo, duracao), 'precisa': 0.0, 'ok': True, 'motivo': '', 'tipo': 'miúdo, fora da regra'})
            continue
        tempo = _tempo([t for t, d in p['vezes'] if d], passo, duracao)
        cortado = sum(passo for _, d in p['vezes'] if not d)
        if _por_palavra(p):
            alvo = len(re.sub(r'\s', '', p['texto'])) / LETRAS_POR_S
            tipo = 'palavra a palavra'
        else:
            alvo = precisa(p['texto'])
            tipo = 'cresce' if len(p['estados']) > 1 else ''
        motivo = ('nunca inteiro no palco' if not any(d for _, d in p['vezes']) else
                  f'cortado na borda do palco por {cortado:.1f} s' if cortado > FORA_MAX else
                  '' if tempo + TOLERANCIA >= alvo else f'curto: {tempo:.1f} s, precisa de {alvo:.1f} s')
        notas.append({'texto': p['texto'], 'ini': p['ini'], 'tempo': tempo, 'precisa': alvo, 'ok': not motivo, 'motivo': motivo, 'tipo': tipo})
    notas.sort(key=lambda n: n['ini'])
    return notas


def medir(preset: str, formato: str, duracao: float | None) -> tuple[dict, list[str], float]:
    from playwright.sync_api import sync_playwright

    import servidor  # o mesmo servidor do render (porta livre)
    srv = servidor.servir(0)
    w, h = FORMATOS[formato]
    erros: list[str] = []
    url = f'http://127.0.0.1:{srv.server_address[1]}/render/motion.html?preset={preset}&formato={formato}'
    if duracao:
        url += f'&duracao={duracao}'
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel='chromium')
            pg = b.new_page(viewport={'width': w, 'height': h})
            pg.on('pageerror', lambda e: erros.append(str(e)))
            pg.goto(url, wait_until='load', timeout=60_000)
            pg.wait_for_function('() => !!window.__ir', timeout=30_000)
            dur = pg.evaluate('() => MOTION.duracao')
            r = pg.evaluate(LER, {'passo': PASSO, 'duracao': dur})
            b.close()
    finally:
        srv.shutdown()
    return r, erros, dur


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Confere o tempo de leitura dos textos de um preset de motion.')
    ap.add_argument('preset')
    ap.add_argument('--formato', default='vertical', choices=sorted(FORMATOS))
    ap.add_argument('--duracao', type=lambda v: float(v.replace(',', '.')))  # o brief escreve "2,5"
    a = ap.parse_args()
    if not (BIBLIOTECA / 'motions' / 'presets' / f'{a.preset}.html').is_file():
        print(f'Preset de motion não encontrado: {a.preset}', file=sys.stderr)
        sys.exit(2)
    r, erros, dur = medir(a.preset, a.formato, a.duracao)
    if not r['pronto']:
        print(f'{a.preset}: o motion nunca ficou pronto (motion.pronto não foi chamado). {" ".join(erros)}', file=sys.stderr)
        sys.exit(2)
    notas = avaliar(r['quadros'], PASSO, dur)
    print(f'{a.preset} · {a.formato} · {dur:.1f} s')
    for e in erros:
        print(f'ERRO na página: {e}')
    if r['canvas']:
        print(f'Aviso: {r["canvas"]} canvas; texto desenhado nele não é lido.')
    for n in notas:
        tipo = f' [{n["tipo"]}]' if n['tipo'] else ''
        print(f'{"OK " if n["ok"] else "RUIM"} {n["ini"]:5.2f} s  fica {n["tempo"]:4.1f} s, precisa {n["precisa"]:4.1f} s{tipo}  “{n["texto"][:60]}”'
              + (f'  → {n["motivo"]}' if n['motivo'] else ''))
    if not notas:
        print('Nenhum texto visível.')
        sys.exit(0)
    ruins = sum(not n['ok'] for n in notas)
    print(f'REPROVADO: {ruins} de {len(notas)} textos' if ruins else f'OK: {len(notas)} texto(s)')
    sys.exit(1 if ruins else 0)
