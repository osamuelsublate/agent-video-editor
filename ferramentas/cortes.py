# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cortes: o Claude escolhe quais palavras ficam (por ID); o código monta os clipes da V1 com as bordas nos silêncios reais
e as pausas longas cortadas (do 18: backend/app/cortes.py, sem a LLM).

    uv run ferramentas/cortes.py texto <slug>                    a transcrição, uma palavra por linha (ID<TAB>texto) + pausas
    uv run ferramentas/cortes.py aplicar <slug> <selecao.json>   {"manter": [["w00004","w00011"], …], "duvidas": [{ini, fim, motivo}],
                                                                  "mover": [{"trecho": [ini, fim], "antes_de": id}]}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import gravar, ler, ler_json, pasta  # noqa: E402

PAUSA_NO_TEXTO = 0.3  # todas as pausas detectadas aparecem: recomeços seguidos têm pausas de ~0,4 s
JANELA_ANTES, JANELA_DEPOIS = 0.5, 0.35  # quão longe da borda da palavra o silêncio pode estar (o ASR erra ~0,2 s)
# pausa dentro de um trecho mantido só é cortada se passar de `pausa_max`; `folga_inicio`/`folga_fim`: o ar que fica antes
# da primeira palavra e depois da última de cada trecho (do 18: os padrões das Configurações)
PARAMETROS = {'pausa_max': 2.0, 'folga_inicio': 0.1, 'folga_fim': 0.1}
VELOCIDADE = (1.0, 1.5)


# ---------------------------------------------------------------- dados do projeto

def palavras(slug: str) -> list[dict]:
    t = ler_json(pasta(slug) / 'transcricao.json')
    if not t or not t.get('palavras'):
        raise SystemExit(f'O projeto {slug} não tem transcricao.json (rode preparar.py).')
    return t['palavras']


def silencios(slug: str) -> list[dict]:
    return (ler_json(pasta(slug) / 'silencios.json') or {}).get('silencios', [])


def velocidade(edicao: dict) -> float:
    """A aceleração do ator (1 a 1,5; do 18: projeto.velocidade)."""
    try:
        v = float(edicao.get('velocidade') or 1)
    except (TypeError, ValueError):
        v = 1.0
    return round(min(max(v, VELOCIDADE[0]), VELOCIDADE[1]), 3)


def ordem(c: dict) -> float:
    """Onde o clipe toca: no seu tempo do bruto, ou em `ordem` (um trecho movido, só a pedido do criador)."""
    return c.get('ordem', c['inicio'])


def v1_tocada(edicao: dict) -> list[dict]:
    """Os clipes da V1 em ordem, cada um com a aceleração (`vel`) (do 18: projeto.v1_tocada)."""
    v = velocidade(edicao)
    return [{**c, 'vel': v} for c in sorted((edicao.get('timeline') or {}).get('V1') or [], key=ordem)]


def dur_saida(c: dict) -> float:
    return (c['fim'] - c['inicio']) / c.get('vel', 1)


def mmss(t: float) -> str:
    return f'{int(t // 60)}:{int(t % 60):02d}'


def seg(t: float) -> str:
    return f'{int(t // 60)}:{t % 60:04.1f}'.replace('.', ',')


def num(x: float, casas: int = 2) -> str:
    return f'{x:.{casas}f}'.replace('.', ',')


# ---------------------------------------------------------------- o texto para o Claude decidir

def linhas(palavras: list[dict], silencios: list[dict]) -> str:
    """Uma palavra por linha (ID<TAB>texto), com `[pausa N.Ns]` nas pausas reais (do 18: cortes._linhas)."""
    pausas = iter(s for s in silencios if s['dur'] >= PAUSA_NO_TEXTO)
    prox, out = next(pausas, None), []
    for p in palavras:
        while prox and p['inicio'] >= prox['inicio'] - 0.05:
            out.append(f'[pausa {prox["dur"]:.1f}s]')
            prox = next(pausas, None)
        out.append(f'{p["id"]}\t{p["texto"]}')
    return '\n'.join(out)


# ---------------------------------------------------------------- a seleção → clipes

def validar(manter: list, palavras: list[dict]) -> list[list[str]]:
    """IDs existem, intervalos em ordem e sem sobreposição, seleção não vazia."""
    pos = {p['id']: i for i, p in enumerate(palavras)}
    ultimo, out = -1, []
    for t in manter:
        if not (isinstance(t, (list, tuple)) and len(t) == 2):
            raise SystemExit(f'Cada trecho de "manter" é [ini, fim]: {t!r}')
        ini, fim = t
        if ini not in pos or fim not in pos:
            raise SystemExit(f'ID que não existe na transcrição: {ini}..{fim}')
        a, b = pos[ini], pos[fim]
        if b < a or a <= ultimo:
            raise SystemExit(f'Intervalo invertido, fora de ordem ou sobreposto: {ini}..{fim}')
        out.append([ini, fim])
        ultimo = b
    if not out:
        raise SystemExit('A seleção não mantém nenhuma palavra.')
    return out


def mantidas_por_indice(palavras: list[dict], mantidas: list[list[str]]) -> list[bool]:
    pos = {p['id']: i for i, p in enumerate(palavras)}
    fica = [False] * len(palavras)
    for ini, fim in mantidas:
        for i in range(pos[ini], pos[fim] + 1):
            fica[i] = True
    return fica


def montar_clipes(palavras: list[dict], fica: list[bool], silencios: list[dict], duracao: float,
                  pausa_max: float = PARAMETROS['pausa_max'],
                  folga_inicio: float = PARAMETROS['folga_inicio'], folga_fim: float = PARAMETROS['folga_fim']) -> list[dict]:
    """Transforma as palavras mantidas em clipes da V1 (tempo do bruto). Do 18: cortes.montar_clipes, sem mudanças."""

    # `lim` é a palavra removida vizinha: a borda nunca invade o áudio dela
    def inicio(t: float, lim: float) -> float:
        c = [s for s in silencios if t - JANELA_ANTES <= s['fim'] <= t + JANELA_DEPOIS and s['inicio'] >= lim - 0.02]
        if not c:
            return max(t - folga_inicio, min(lim, t))
        s = min(c, key=lambda s: abs(s['fim'] - t))
        return max(s['fim'] - min(folga_inicio, s['dur']), s['inicio'], min(lim, t))

    def fim(t: float, lim: float) -> float:
        c = [s for s in silencios if t - JANELA_DEPOIS <= s['inicio'] <= t + JANELA_ANTES and s['inicio'] <= lim + 0.02]
        if not c:
            return min(t + folga_fim, max(lim, t), duracao)
        s = min(c, key=lambda s: abs(s['inicio'] - t))
        return min(s['inicio'] + min(folga_fim, s['dur']), s['fim'], max(lim, t))

    # uma pausa longa entre duas palavras mantidas parte o trecho em dois (o vão entre elas ou um silêncio longo detectado)
    def pausa_longa(k: int) -> bool:
        p, q = palavras[k], palavras[k + 1]
        return q['inicio'] - p['fim'] >= pausa_max or any(
            s['dur'] >= pausa_max and s['inicio'] >= p['inicio'] and s['fim'] <= q['fim'] for s in silencios)

    intervalos: list[list[float]] = []
    i = 0
    while i < len(palavras):
        if not fica[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(palavras) and fica[j + 1] and not pausa_longa(j):
            j += 1
        a = inicio(palavras[i]['inicio'], palavras[i - 1]['fim'] if i > 0 else 0.0)
        b = fim(palavras[j]['fim'], palavras[j + 1]['inicio'] if j + 1 < len(palavras) else duracao)
        if intervalos and a <= intervalos[-1][1] + 0.02:  # nada relevante entre os dois: junta
            intervalos[-1][1] = b
        else:
            intervalos.append([a, b])
        i = j + 1

    clipes = []
    for a, b in intervalos:
        dentro = [p for p, ok in zip(palavras, fica) if ok and a <= (p['inicio'] + p['fim']) / 2 <= b]
        if not dentro:
            continue
        clipes.append({'id': f'c{len(clipes) + 1}', 'fonte': 'f1', 'inicio': round(a, 3), 'fim': round(b, 3),
                       'palavra_ini': dentro[0]['id'], 'palavra_fim': dentro[-1]['id']})
    return clipes


def lacunas(clipes: list[dict], duracao: float) -> list[tuple[dict | None, dict | None]]:
    """Os cortes entre os clipes (e antes do 1º e depois do último), como a tela do 18 conta (preprocessamento/cortes.ts)."""
    cs = sorted(clipes, key=lambda c: c['inicio'])
    if not cs:
        return []
    out = [(None, cs[0])] if cs[0]['inicio'] > 0.05 else []
    out += [(a, b) for a, b in zip(cs, cs[1:]) if b['inicio'] - a['fim'] > 0.001]
    if duracao - cs[-1]['fim'] > 0.05:
        out.append((cs[-1], None))
    return out


def resumo(edicao: dict, palavras: list[dict], fica: list[bool]) -> str:
    """Bruto → final, nº de cortes e o texto de cada trecho, com o que saiu antes dele ~riscado~."""
    duracao = edicao['fontes'][0]['duracao']
    clipes = v1_tocada(edicao)
    total = sum(dur_saida(c) for c in clipes)
    vel = velocidade(edicao)
    pos = {p['id']: i for i, p in enumerate(palavras)}
    cortes = lacunas(clipes, duracao)
    saem = fica.count(False)
    out = [f'Bruto {mmss(duracao)} → {mmss(total)} ({num(total, 1)} s{f", velocidade {num(vel)}×" if vel != 1 else ""}) · '
           f'{len(cortes)} cortes · {len(palavras) - saem} palavras ficam, {saem} saem', '']
    t, ultimo = 0.0, -1
    for c in clipes:
        a, b = pos[c['palavra_ini']], pos[c['palavra_fim']]
        fora = [p['texto'] for p, ok in zip(palavras[ultimo + 1:a], fica[ultimo + 1:a]) if not ok]
        if 'ordem' in c:
            out.append('      ↷ movido para cá (gravado depois)')
        elif c is not clipes[0] and 'ordem' in clipes[clipes.index(c) - 1]:
            out.append('      ↩ volta à ordem da fala')
        elif c is not clipes[0] or c['inicio'] > 0.05:
            ant_fim = clipes[clipes.index(c) - 1]['fim'] if c is not clipes[0] else 0.0
            out.append(f'      ✂ −{num(c["inicio"] - ant_fim)} s' + (f'  ~{" ".join(fora)}~' if fora else ' (pausa)'))
        texto = []
        for p, ok in zip(palavras[a:b + 1], fica[a:b + 1]):  # palavras de dentro que saíram (raro: fica junto na mesma borda)
            texto.append(p['texto'] if ok else f'~{p["texto"]}~')
        out.append(f'{c["id"]:>4}  {seg(t)}  {" ".join(texto)}')
        t += dur_saida(c)
        ultimo = max(ultimo, b)
    resto = [p['texto'] for p, ok in zip(palavras[ultimo + 1:], fica[ultimo + 1:]) if not ok]
    if clipes and (resto or duracao - clipes[-1]['fim'] > 0.05):
        out.append(f'      ✂ −{num(duracao - clipes[-1]["fim"])} s' + (f'  ~{" ".join(resto)}~' if resto else ' (pausa)'))
    return '\n'.join(out)


def mover_clipes(clipes: list[dict], mover: list, palavras: list[dict]) -> None:
    """Os trechos que o criador pediu para tocar noutro lugar: os clipes de dentro de `trecho` ganham `ordem` logo antes
    do clipe que começa em `antes_de`."""
    pos = {p['id']: i for i, p in enumerate(palavras)}
    for m in mover:
        (ini, fim), alvo = m['trecho'], m['antes_de']
        if ini not in pos or fim not in pos or alvo not in pos:
            raise SystemExit(f'mover: ID que não existe na transcrição: {m}')
        dentro = [c for c in clipes if pos[ini] <= pos[c['palavra_ini']] and pos[c['palavra_fim']] <= pos[fim]]
        partidos = [c for c in clipes if c not in dentro and pos[c['palavra_ini']] <= pos[fim] and pos[c['palavra_fim']] >= pos[ini]]
        destino = next((c for c in clipes if c['palavra_ini'] == alvo), None)
        if not dentro or partidos or not destino:
            raise SystemExit(f'mover: o trecho precisa ser clipes inteiros e `antes_de` o começo de um clipe: {m}')
        for k, c in enumerate(dentro):
            c['ordem'] = round(ordem(destino) - 0.001 * (len(dentro) - k), 4)


def aplicar(slug: str, arquivo: str) -> None:
    try:
        sel = json.loads(Path(arquivo).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise SystemExit(f'Não consegui ler a seleção {arquivo}: {e}')
    edicao = ler(slug)
    ws = palavras(slug)
    mantidas = validar(sel.get('manter') or [], ws)
    pos = {p['id'] for p in ws}
    duvidas = []
    for d in sel.get('duvidas') or []:
        if d.get('ini') in pos and d.get('fim') in pos:
            duvidas.append({'ini': d['ini'], 'fim': d['fim'], 'motivo': str(d.get('motivo') or '').strip()})
        else:
            print(f'Aviso: dúvida com ID que não existe, ignorada: {d}', file=sys.stderr)
    # os parâmetros que o projeto já tem (um projeto do 18 traz os dele); senão, os padrões
    guardados = (edicao.get('cortes') or {}).get('parametros') or {}
    parametros = {k: float(guardados.get(k, v)) for k, v in PARAMETROS.items()}
    fica = mantidas_por_indice(ws, mantidas)
    clipes = montar_clipes(ws, fica, silencios(slug), edicao['fontes'][0]['duracao'], **parametros)
    mover = sel.get('mover') or []
    mover_clipes(clipes, mover, ws)
    edicao['cortes'] = {'mantidas': mantidas, 'duvidas': duvidas, 'parametros': parametros} | ({'mover': mover} if mover else {})
    edicao.setdefault('timeline', {})['V1'] = clipes
    gravar(slug, edicao)
    print(resumo(edicao, ws, fica))
    for d in duvidas:
        print(f'\nDúvida {d["ini"]}..{d["fim"]}: {d["motivo"]}')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'texto':
        print(linhas(palavras(sys.argv[2]), silencios(sys.argv[2])))
    elif len(sys.argv) >= 4 and sys.argv[1] == 'aplicar':
        aplicar(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
