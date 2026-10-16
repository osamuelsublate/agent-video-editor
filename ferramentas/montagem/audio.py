"""O áudio no render (do 18: backend/app/audio.py, a parte da exportação; SPEC §8.9, docs/audio.md): a voz do ator (a
limpa, feita pelo preparar, com o timbre e um compressor leve), os sons de apoio, a faixa de fundo (repetida no trecho
estável dela, com crossfade, fade no fim e o ducking pelas falas) e o volume final em −14 LUFS: um ganho medido antes
só no áudio (`medir`) e um limitador de pico na passada final.

A voz entra na mistura em estéreo com ganho 1 nos dois canais (como o navegador toca um áudio mono), e a sonoridade
dela é medida assim (`lufs(..., como_voz=True)`), seja a limpa (mono) ou a do bruto."""
import math
import re
import subprocess
from pathlib import Path

from base import BIBLIOTECA

# os filtros de timbre: (frequência Hz, ganho dB, Q) em picos (peaking), depois de um passa-altas de 80 Hz
TIMBRES: dict[str, list[tuple[float, float, float]]] = {
    'natural': [],
    'quente': [(180, 2.5, 0.9), (3500, -1.5, 1.0)],
    'clara': [(250, -2.0, 1.0), (4500, 3.0, 1.0)],
}
PASSA_ALTAS = 80
COMPRESSOR = {'limiar': -20, 'razao': 2.5, 'ataque': 0.01, 'soltura': 0.15, 'joelho': 6}
TRILHAS = ('ator', 'presets', 'transicoes', 'fundo')
LUFS, PICO = -14, -1.5
# o limitador antes da saída (pico de amostra, um pouco abaixo do PICO em dBTP: os picos entre amostras e o AAC sobem
# alguns décimos) e o maior ganho que o −14 aplica
LIMITE_DB = -2.0
GANHO_MAX = 30.0
# o fundo em relação à voz (LUFS da faixa − LUFS da voz) e quanto ele abaixa quando o ator fala: medidos nas
# referências (docs/audio.md). As faixas da biblioteca vêm normalizadas em `TRILHA_LUFS`
FUNDO_DB = -11.0
DUCKING_DB = 3.0
SUBIDA, DESCIDA = 0.15, 0.35  # s: a música abaixa antes da fala começar e volta depois que ela termina
JUNTA = 0.6  # s: pausas menores que isto não devolvem a música
FADE_FUNDO = 1.5
CRUZA_FUNDO = 2.0  # s: o crossfade de uma volta do fundo para a próxima
PADRAO = {'voz': {'limpeza': 'leve', 'timbre': 'natural'}, 'fundo': None, 'fundo_mudo': False,
          'niveis': {t: 0.0 for t in TRILHAS}}
# a voz entra na mistura como o navegador toca: o mono vai igual aos dois canais (ganho 1; o `aformat` daria −3 dB)
VOZ_ESTEREO = 'pan=stereo|c0=c0|c1=c0'
# as faixas de fundo (do 18: backend/app/trilhas.py), em `biblioteca/trilhas/` (<id>.m4a + catalogo.json)
TRILHAS_RAIZ = BIBLIOTECA / 'trilhas'
TRILHA_LUFS = -16.0  # a sonoridade de todas as faixas da biblioteca (a geração normaliza)
# o laço: o trecho estável da faixa, onde a energia (média de 2 s) fica a menos de `LACO_DB` da mediana
LACO_DB = 5.0


def do_projeto(p: dict) -> dict:
    """As escolhas de áudio do projeto, com o padrão onde faltar (projetos de antes da P3: a limpeza Leve, sem fundo)."""
    a = p.get('audio') or {}
    voz = {**PADRAO['voz'], **{k: v for k, v in (a.get('voz') or {}).items() if k in PADRAO['voz']}}
    niveis = {**PADRAO['niveis'], **{k: float(v) for k, v in (a.get('niveis') or {}).items() if k in TRILHAS and isinstance(v, (int, float))}}
    # emendar vídeos (o Reels e o CTA que entra depois dele): `continua` = o slug do vídeo de antes, cuja trilha este
    # continua de onde ela parou; `fade_fim: false` no de antes, para a música não sumir na emenda
    return {'voz': voz, 'fundo': a.get('fundo') if isinstance(a.get('fundo'), str) else None, 'fundo_mudo': bool(a.get('fundo_mudo')),
            'niveis': niveis, 'continua': a.get('continua') if isinstance(a.get('continua'), str) else None,
            'fade_fim': a.get('fade_fim', True) is not False}


def db(x: float) -> float:
    return 10 ** (x / 20)


# ---------------------------------------------------------------- a voz

def canais(arq: Path) -> int:
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels', '-of', 'csv=p=0', str(arq)],
                       capture_output=True, text=True)
    try:
        return max(int(r.stdout.strip().split(',')[0]), 1)
    except ValueError:
        return 1


def para_mono(arq: Path) -> str:
    """O filtro que deixa a voz mono pela média dos canais (no bruto dual-mono, o mesmo nível de cada canal). Explícito:
    o `aformat`/`-ac 1` do ffmpeg só faz a média em formatos inteiros; em float, soma a +3 dB."""
    n = canais(arq)
    return 'anull' if n == 1 else 'pan=mono|c0=' + '+'.join(f'{1 / n:.6f}*c{k}' for k in range(n))


def lufs(arq: Path, como_voz: bool = False) -> float:
    """A sonoridade integrada (LUFS, EBU R128) de um arquivo de áudio; `como_voz`: como a voz entra na mistura (mono pela
    média e igual nos dois canais: um mono medido sozinho daria 3 LU a menos do que soa nos dois canais)."""
    af = f'{para_mono(arq)},{VOZ_ESTEREO},ebur128' if como_voz else 'ebur128'
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(arq), '-vn', '-af', af, '-f', 'null', '-'], capture_output=True, text=True)
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr)
    if not m:
        raise RuntimeError('Não deu para medir a sonoridade')
    return float(m[-1])


def ganho_fundo(voz_lufs: float, nivel_db: float) -> float:
    """O ganho (dB) da faixa de fundo: `FUNDO_DB` abaixo da voz, mais o fader."""
    return round(voz_lufs + FUNDO_DB - TRILHA_LUFS + nivel_db, 1)


# ---------------------------------------------------------------- as falas (o ducking do fundo)

def falas(palavras_saida: list[dict]) -> list[tuple[float, float]]:
    """Os trechos em que o ator fala, no tempo da saída: as palavras juntas quando a pausa é menor que `JUNTA`."""
    out: list[list[float]] = []
    for w in sorted(palavras_saida, key=lambda w: w['saida_ini']):
        if out and w['saida_ini'] - out[-1][1] < JUNTA:
            out[-1][1] = max(out[-1][1], w['saida_fim'])
        else:
            out.append([w['saida_ini'], w['saida_fim']])
    return [(round(a, 3), round(b, 3)) for a, b in out]


def _suave(u: str) -> str:
    return f'({u}*{u}*(3-2*{u}))'


def expressao_ducking(trechos: list[tuple[float, float]], ducking_db: float = DUCKING_DB) -> str:
    """O ganho do fundo no tempo `t` (expressão do `volume` do ffmpeg, eval=frame): 1 longe das falas e
    10^(−ducking/20) durante elas, com rampas suaves (`SUBIDA` antes, `DESCIDA` depois). Igual a `audio.ts`."""
    if not trechos or ducking_db <= 0:
        return '1'
    termos = []
    for a, b in trechos:
        sobe = _suave(f'clip((t-{a - SUBIDA:.3f})/{SUBIDA},0,1)')
        desce = _suave(f'clip(({b + DESCIDA:.3f}-t)/{DESCIDA},0,1)')
        termos.append(f'min({sobe},{desce})')
    return f'1-{1 - db(-ducking_db):.4f}*min({"+".join(termos)},1)'


# ---------------------------------------------------------------- a mistura no render (SPEC §13, camada A)

def cadeia_voz(timbre: str, ganho_db: float) -> str:
    """Os filtros da voz depois da limpeza: passa-altas, timbre, compressor e o fader do ator."""
    f = [f'highpass=f={PASSA_ALTAS}']
    f += [f'equalizer=f={fr}:t=q:w={q}:g={g}' for fr, g, q in TIMBRES[timbre]]
    c = COMPRESSOR
    f.append(f"acompressor=threshold={db(c['limiar']):.5f}:ratio={c['razao']}:attack={c['ataque'] * 1000:.0f}:release={c['soltura'] * 1000:.0f}:knee={db(c['joelho']):.3f}")
    f.append(f'volume={ganho_db:.1f}dB')
    return ','.join(f)


def voltas_do_fundo(laco: tuple[float, float], duracao: float, cruza: float = CRUZA_FUNDO) -> list[tuple[float, float]]:
    """Os pedaços da faixa (no tempo dela) que cobrem `duracao`: a 1ª volta do 0 até o fim do laço e as outras dentro
    dele, cada uma emendada na anterior com um crossfade de `cruza` s. Igual a `pedacosDoFundo` em `audio.ts`."""
    ini, fim = laco
    cruza = min(cruza, (fim - ini) / 2)
    if duracao <= fim:
        return [(0.0, fim)]
    voltas = math.ceil((duracao - fim) / (fim - ini - cruza))
    return [(0.0, fim)] + [(ini, fim)] * voltas


def filtros(a: dict, clipes: list[dict], eventos_som: list[dict], primeira_entrada: int, saida: str, duracao: float,
            medida: dict | None = None) -> tuple[list[str], list[str]]:
    """O áudio inteiro da P3, de entradas próprias (a voz — limpa ou do bruto — e a faixa de fundo; os sons vêm de
    `sons.filtro_mistura`): a voz cortada nos clipes da V1 (como o `_ator`), a cadeia da voz (e a voz em estéreo, ganho 1
    nos dois canais), os sons de cada grupo no seu fader, o fundo nas voltas do laço com crossfade, fade e ducking, e o
    −14 LUFS (`medida`: o ganho medido por `medir`, e um limitador de pico; sem ela, o `loudnorm` dinâmico).
    `a`: `{voz: Path, voz_lufs, timbre, niveis, fundo: Path | None, laco: (ini, fim) | None, fundo_mudo, falas: [(ini, fim)],
    ducking_db}`. Devolve (entradas, filtros), com a mistura em [`saida`]."""
    from . import sons
    from .exportacao import FADE, acelerar, dur_saida

    entradas = ['-i', str(a['voz'])]
    n = len(clipes)
    f = [f'[{primeira_entrada}:a]aresample=48000,{para_mono(Path(a["voz"]))},asplit={n}' + ''.join(f'[pv{k}]' for k in range(n))]
    for k, c in enumerate(clipes):
        dur = dur_saida(c)
        f.append(f"[pv{k}]atrim=start={c['inicio']:.4f}:end={c['fim']:.4f},asetpts=PTS-STARTPTS,{acelerar(c.get('vel', 1))[1]}"
                 f'afade=t=in:d={FADE},afade=t=out:st={max(dur - FADE, 0):.4f}:d={FADE}[pc{k}]')
    f.append(''.join(f'[pc{k}]' for k in range(n)) + f'concat=n={n}:v=0:a=1,{cadeia_voz(a["timbre"], a["niveis"]["ator"])},'
             f'{VOZ_ESTEREO}[pvoz]')
    # os sons, cada grupo no seu fader
    ev = [{**e, 'ganho': float(e.get('ganho', 0.3)) * db(a['niveis']['transicoes' if e.get('grupo') == 'transicoes' else 'presets'])} for e in eventos_som]
    ent_s, f_s = sons.filtro_mistura(ev, primeira_entrada + 1, 'pvoz', 'pmix')
    entradas += ent_s
    f += f_s
    atual = 'pmix'
    if a.get('fundo') and not a.get('fundo_mudo'):
        idx = primeira_entrada + entradas.count('-i')
        # cada volta numa entrada própria (o mesmo arquivo), emendadas com crossfade de potência constante
        desde = float(a.get('desde') or 0)  # onde a trilha já está (continuando o vídeo de antes)
        voltas = voltas_do_fundo(tuple(a.get('laco') or (0.0, desde + duracao)), desde + duracao)
        for k, (de, ate) in enumerate(voltas):
            entradas += ['-i', str(a['fundo'])]
            f.append(f'[{idx + k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={de:.3f}:end={ate:.3f},asetpts=PTS-STARTPTS[pf{k}]')
        cruza = min(CRUZA_FUNDO, (voltas[-1][1] - voltas[-1][0]) / 2)
        for k in range(1, len(voltas)):
            f.append(f'[{"pf0" if k == 1 else f"pfx{k - 1}"}][pf{k}]acrossfade=d={cruza:.3f}:c1=qsin:c2=qsin[pfx{k}]')
        ganho = ganho_fundo(a['voz_lufs'], a['niveis']['fundo'])
        fade = f"afade=t=out:st={max(duracao - FADE_FUNDO, 0):.4f}:d={FADE_FUNDO}," if a.get('fade_fim', True) else ''
        f.append(f"[{'pf0' if len(voltas) == 1 else f'pfx{len(voltas) - 1}'}]atrim=start={desde:.4f}:duration={duracao:.4f},asetpts=PTS-STARTPTS,"
                 f"{fade}volume={ganho:.1f}dB,"
                 f"volume='{expressao_ducking(a.get('falas') or [], a.get('ducking_db', DUCKING_DB))}':eval=frame[pfd]")
        f.append(f'[{atual}][pfd]amix=inputs=2:duration=first:normalize=0[pmixf]')
        atual = 'pmixf'
    if medida:
        fim = f"volume={medida['ganho']:.2f}dB,alimiter=limit={db(LIMITE_DB):.4f}:attack=5:release=50:level=0:latency=1"
    else:
        fim = f'loudnorm=I={LUFS}:TP={PICO}:LRA=11'
    f.append(f'[{atual}]{fim},aresample=48000,aformat=channel_layouts=stereo[{saida}]')
    return entradas, f


def _medir_mistura(a: dict, clipes: list[dict], eventos_som: list[dict], duracao: float, ganho: float) -> dict:
    """A sonoridade (LUFS) e o pico verdadeiro (dBTP) da mistura com o ganho e o limitador (só o áudio: rápido)."""
    entradas, f = filtros(a, clipes, eventos_som, 0, 'pfim', duracao, {'ganho': ganho})
    f.append('[pfim]ebur128=peak=true[pmed]')
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *entradas, '-filter_complex', ';'.join(f), '-map', '[pmed]', '-t', f'{duracao:.4f}',
                        '-f', 'null', '-'], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg (medida do áudio) falhou: {r.stderr[-300:]}')
    i = re.findall(r'I:\s+(-?[\d.]+|-inf) LUFS', r.stderr)
    pico = re.findall(r'Peak:\s+(-?[\d.]+|-inf) dBFS', r.stderr)
    if not i:
        raise RuntimeError('A medida do áudio não veio')
    return {'i': float(i[-1]), 'pico': float(pico[-1]) if pico else None}


def medir(a: dict, clipes: list[dict], eventos_som: list[dict], duracao: float) -> dict:
    """O ganho do −14 LUFS: parte da sonoridade da voz (o grosso da mistura) e corrige pelo medido na mistura inteira,
    já com o limitador (que tira um pouco dos picos), até ficar a 0,3 LU do alvo (em geral, 1 ou 2 passadas do áudio
    sozinho). Devolve `{ganho, i, pico}`."""
    ganho = min(max(LUFS - (a['voz_lufs'] + a['niveis']['ator']), -GANHO_MAX), GANHO_MAX)
    m = {}
    for _ in range(3):
        m = _medir_mistura(a, clipes, eventos_som, duracao, ganho)
        if m['i'] == float('-inf'):
            break  # silêncio: não há o que normalizar
        erro = LUFS - m['i']
        if abs(erro) <= 0.3:
            break
        ganho = min(max(ganho + erro, -GANHO_MAX), GANHO_MAX)
    return {'ganho': round(ganho, 2), **m}


# ---------------------------------------------------------------- as faixas de fundo

def arquivo_trilha(tid: str | None) -> Path | None:
    """A faixa de fundo da biblioteca (None se não existe)."""
    arq = TRILHAS_RAIZ / f'{tid}.m4a'
    return arq if tid and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,40}', tid) and arq.exists() else None


def laco(arq: Path) -> tuple[float, float]:
    """O trecho da faixa que se repete num vídeo mais longo que ela (s, `(ini, fim)`): sem a introdução baixa e sem o
    fade/silêncio do fim (as faixas do Lyria começam devagar e terminam sumindo). A 1ª volta toca do 0 até `fim`; as
    outras, de `ini` a `fim`, com crossfade (`CRUZA_FUNDO`)."""
    import numpy as np

    taxa, janela = 8000, 4000  # 0,5 s
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(arq), '-ac', '1', '-ar', str(taxa), '-f', 'f32le', '-'], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    n = len(x) // janela
    dur = len(x) / taxa
    out = (0.0, round(dur, 2))
    if n >= 8:
        energia = (x[: n * janela].reshape(n, janela) ** 2).mean(axis=1)
        media = np.convolve(energia, np.ones(4) / 4, mode='same')  # 2 s
        e = 10 * np.log10(media + 1e-12)
        ok = np.where(e > np.median(e) - LACO_DB)[0]
        if len(ok):
            ini, fim = ok[0] * janela / taxa, (ok[-1] + 1) * janela / taxa
            if ini <= dur * 0.3 and fim >= dur * 0.6:  # um laço estranho (faixa curta ou irregular): a faixa inteira
                out = (round(float(ini), 2), round(float(fim), 2))
    return out
