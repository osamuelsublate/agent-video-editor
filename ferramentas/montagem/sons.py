"""Sons de apoio no render (do 18: backend/app/sons.py, SPEC §8.6): a biblioteca do time de audiovisual (cliques, pops,
whooshes, risers, digitação), cortada, compactada e no mesmo volume percebido, em `biblioteca/sons/`. A página de render
entrega os eventos (`__render.sons`: os momentos de som dos presets, dos motions e das transições) e o render os mistura
com a voz, cada um no seu instante."""
import re
import subprocess
from pathlib import Path

from base import BIBLIOTECA

RAIZ = BIBLIOTECA / 'sons'
# o ganho de cada intensidade sobre o som normalizado (pico de energia a -18 dBFS), para uma voz no nível das
# referências (`VOZ_REF`): Baixo fica ~16 dB e Médio ~10 dB abaixo da voz (medido nas referências: os sons de apoio
# do time ficam de 14 a 20 dB abaixo dela). Num vídeo com a voz mais baixa, tudo desce junto (`fator_da_voz`).
INTENSIDADES = {'baixo': 0.25, 'medio': 0.5}
VOZ_REF = -14.0  # dBFS: o nível da fala (percentil 90 da energia em janelas de 50 ms) nas referências
_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,60}')


def arquivo(sid: str) -> Path:
    if not _ID.fullmatch(sid or ''):
        raise FileNotFoundError(sid)
    p = RAIZ / f'{sid}.m4a'
    if not p.exists():
        raise FileNotFoundError(sid)
    return p


def midia(caminho: str) -> Path:
    """O áudio de uma mídia do banco que toca no vídeo (um insert com som): só dentro da biblioteca."""
    p = Path(caminho).resolve()
    if not p.is_file() or BIBLIOTECA.resolve() not in p.parents:
        raise FileNotFoundError(caminho)
    return p


def _validos(eventos: list[dict]) -> list[tuple]:
    """Os eventos que tocam: (arquivo, t, ganho, desde, dur, vel); os de som ou mídia que não existem ficam de fora."""
    validos = []
    for e in eventos:
        try:
            validos.append((midia(e['arquivo']) if e.get('arquivo') else arquivo(e['som']), max(float(e['t']), 0.0), float(e.get('ganho', INTENSIDADES['baixo'])),
                            max(float(e.get('desde', 0)), 0.0), e.get('dur'), min(max(float(e.get('vel') or 1), 0.5), 2.0)))
        except (FileNotFoundError, KeyError, TypeError, ValueError):
            continue
    return validos


def _corte(desde: float, dur, vel: float) -> str:
    """O pedaço do arquivo que toca: de `desde`, `dur` s (no tempo do arquivo), na velocidade `vel` (o tom acompanha, como
    no navegador), com um fade no fim (no máximo metade do som). O relógio volta a zero logo depois do corte."""
    fade = min(0.12, float(dur) / 2) if dur else 0
    corte = f'atrim=start={desde:.4f}' + (f':duration={float(dur) * vel:.4f}' if dur else '') + ',asetpts=PTS-STARTPTS'
    if abs(vel - 1) > 0.001:
        corte += f',asetrate={48000 * vel:.2f},aresample=48000'
    if dur:
        corte += f',afade=t=out:st={float(dur) - fade:.3f}:d={fade:.3f}'
    return corte


def faixa(eventos: list[dict], duracao: float, destino: Path) -> Path:
    """Os sons numa faixa só (WAV estéreo em float, 48 kHz, da duração do vídeo): cada pedaço tocado (`_corte`) sai uma
    vez do ffmpeg e é somado no instante de cada uso, no ganho dele (o instante em ms, como o `adelay`). A mesma soma do
    `amix` de `filtro_mistura`, sem o ffmpeg gerar silêncio do começo do vídeo até cada som (219 sons: ~55 s → poucos)."""
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    validos = _validos(eventos)

    def decodificar(k: tuple) -> np.ndarray:
        arq, desde, dur, vel = k
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(arq), '-vn', '-af', f'aresample=48000,aformat=channel_layouts=stereo,{_corte(desde, dur, vel)}',
                            '-f', 'f32le', '-ac', '2', '-ar', '48000', '-'], capture_output=True)
        if r.returncode:
            raise RuntimeError(f'ffmpeg (som {arq.name}) falhou: {r.stderr[-300:]}')
        return np.frombuffer(r.stdout, np.float32).reshape(-1, 2)

    chaves = list(dict.fromkeys((v[0], v[3], v[4], v[5]) for v in validos))
    with ThreadPoolExecutor(8) as pool:
        pedacos = dict(zip(chaves, pool.map(decodificar, chaves)))
    n = round(duracao * 48000)
    soma = np.zeros((n, 2), np.float32)
    for arq, t, ganho, desde, dur, vel in validos:
        x = pedacos[(arq, desde, dur, vel)]
        a = round(t * 1000) * 48
        b = min(n, a + len(x))
        if b > a:
            soma[a:b] += x[:b - a] * np.float32(ganho)
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', '-', '-c:a', 'pcm_f32le', str(destino)],
                       input=soma.tobytes(), capture_output=True)
    if r.returncode:
        raise RuntimeError(f'ffmpeg (faixa dos sons) falhou: {r.stderr[-300:]}')
    return destino


def filtro_mistura(eventos: list[dict], primeira_entrada: int, rotulo_voz: str, saida: str) -> tuple[list[str], list[str]]:
    """As entradas e os filtros do ffmpeg que põem os sons por cima da voz: cada evento (`som`, `t` no vídeo final,
    `ganho`, `desde`: de onde tocar dentro do arquivo, `dur` opcional) vira um atraso + volume, e tudo soma com a voz
    (sem normalizar: a voz fica como estava). Devolve (entradas, filtros); sem eventos, só renomeia a voz. Num vídeo
    com muitos sons, `faixa` faz a mesma soma muito mais rápido."""
    validos = _validos(eventos)
    if not validos:
        return [], [f'[{rotulo_voz}]anull[{saida}]']
    # um arquivo de entrada por som (dividido entre os usos): um vídeo com muitos cliques não abre centenas de arquivos
    arquivos = list(dict.fromkeys(v[0] for v in validos))
    entradas = [x for a in arquivos for x in ('-i', str(a))]
    usos = {a: [v for v in validos if v[0] == a] for a in arquivos}
    filtros = [f'[{rotulo_voz}]aresample=48000,aformat=channel_layouts=stereo[voz]']
    rotulos = []
    for i, a in enumerate(arquivos):
        n = len(usos[a])
        filtros.append(f'[{primeira_entrada + i}:a]aresample=48000,aformat=channel_layouts=stereo,asplit={n}' + ''.join(f'[f{i}_{j}]' for j in range(n)))
        for j, (_, t, ganho, desde, dur, vel) in enumerate(usos[a]):
            ms = round(t * 1000)
            filtros.append(f'[f{i}_{j}]{_corte(desde, dur, vel)},volume={ganho:.3f},adelay={ms}|{ms}[s{i}_{j}]')
            rotulos.append(f'[s{i}_{j}]')
    filtros.append(f'[voz]{"".join(rotulos)}amix=inputs={len(rotulos) + 1}:duration=first:normalize=0[{saida}]')
    return entradas, filtros


def nivel_da_voz(arq: Path, ate: float = 180) -> float:
    """O nível da fala de um vídeo (dBFS): o percentil 90 da energia em janelas de 50 ms, nos primeiros `ate` s."""
    import numpy as np
    r = subprocess.run(['ffmpeg', '-v', 'error', '-t', str(ate), '-i', str(arq), '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                       capture_output=True)
    x = np.frombuffer(r.stdout, np.float32).astype(np.float64)
    n = len(x) // 800
    if not n:
        return VOZ_REF
    e = np.sqrt((x[: n * 800].reshape(n, 800) ** 2).mean(axis=1))
    return round(float(20 * np.log10(np.percentile(e, 90) + 1e-9)), 2)


def fator_da_voz(nivel: float | None) -> float:
    """Quanto os sons sobem ou descem para ficar na mesma relação com a voz deste vídeo que nas referências."""
    return 1.0 if nivel is None else round(min(max(10 ** ((nivel - VOZ_REF) / 20), 0.1), 3.0), 4)
