# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Encaixe: o corpo (um Reels aprovado) seguido de um CTA (outro projeto, gravado para entrar depois dele), num vídeo só,
com uma transição destacada no ponto da emenda (a luz colorida, TRA-04, ou o brilho branco). Usa os finais em 4K de
cada um (`render.py <slug> --final`) e não mexe neles.

    uv run ferramentas/encaixar.py <corpo> <cta> <saida.mp4> [--transicao luz-colorida|brilho-branco]

Antes de montar, confere se os dois lados casam: a sonoridade (LUFS) dos últimos 4 s do corpo e dos primeiros 4 s do CTA
e a luminância/saturação do último quadro do corpo e do primeiro do CTA. Uma diferença grande (o susto na troca) é avisada.
O áudio do CTA já continua a trilha do corpo (`audio.continua` no edicao.json dele); aqui só se emendam as duas partes e
entra o som da transição.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, pasta  # noqa: E402
from montagem import sons, transicoes  # noqa: E402

FPS = 24
JANELA = 4.0  # s de cada lado para comparar o áudio
LIMITE_DB = 2.0  # diferença de sonoridade que vira aviso
LIMITE_LUMA = 12  # diferença de luminância média (0–255) que vira aviso


def final_de(slug: str) -> Path:
    """O final mais recente do projeto (render.py --final)."""
    fs = sorted((pasta(slug) / 'final').glob('*.mp4'), key=lambda p: p.stat().st_mtime)
    if not fs:
        raise SystemExit(f'{slug} ainda não tem final: rode `uv run ferramentas/render.py {slug} --final`.')
    return fs[-1]


def sonda(arq: Path) -> dict:
    s = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,codec_type',
                                   '-of', 'json', str(arq)], capture_output=True, text=True, check=True).stdout)
    v = next(x for x in s['streams'] if x['codec_type'] == 'video')
    return {'dur': float(s['format']['duration']), 'w': v['width'], 'h': v['height']}


def lufs(arq: Path, ini: float, dur: float) -> float:
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-ss', f'{ini:.3f}', '-t', f'{dur:.3f}', '-i', str(arq),
                        '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True)
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', r.stderr)
    return float(m[-1]) if m else float('nan')


def cor(arq: Path, t: float) -> tuple[float, float]:
    """Luminância e saturação médias de um quadro (signalstats)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-ss', f'{max(t, 0):.3f}', '-i', str(arq), '-frames:v', '1',
                        '-vf', 'scale=270:-2,signalstats,metadata=print', '-f', 'null', '-'], capture_output=True, text=True)
    def valor(k):
        m = re.search(rf'lavfi\.signalstats\.{k}=([\d.]+)', r.stderr)
        return float(m.group(1)) if m else float('nan')
    return valor('YAVG'), valor('SATAVG')


def conferir(corpo: Path, cta: Path, dc: float) -> list[str]:
    avisos = []
    a, b = lufs(corpo, dc - JANELA, JANELA), lufs(cta, 0, JANELA)
    print(f'  áudio: fim do corpo {a:.1f} LUFS · começo do CTA {b:.1f} LUFS (Δ {abs(a - b):.1f} dB)')
    if abs(a - b) > LIMITE_DB:
        avisos.append(f'o volume muda {abs(a - b):.1f} dB na emenda')
    (ya, sa), (yb, sb) = cor(corpo, dc - 0.1), cor(cta, 0.05)
    print(f'  cor: último quadro do corpo luma {ya:.0f} sat {sa:.0f} · primeiro do CTA luma {yb:.0f} sat {sb:.0f}')
    if abs(ya - yb) > LIMITE_LUMA:
        avisos.append(f'a luminância muda {abs(ya - yb):.0f} na emenda (look diferente?)')
    return avisos


def encaixar(corpo_slug: str, cta_slug: str, saida: Path, transicao: str) -> None:
    if saida.exists():
        raise SystemExit(f'{saida} já existe: escolha outro nome (nunca sobrescrevemos vídeo).')
    corpo, cta = final_de(corpo_slug), final_de(cta_slug)
    a, b = sonda(corpo), sonda(cta)
    if (a['w'], a['h']) != (b['w'], b['h']):
        raise SystemExit(f'Os finais têm tamanhos diferentes ({a["w"]}×{a["h"]} e {b["w"]}×{b["h"]}).')
    print(f'Corpo: {corpo.name} ({a["dur"]:.2f} s) · CTA: {cta.name} ({b["dur"]:.2f} s)')
    avisos = conferir(corpo, cta, a['dur'])
    tr = json.loads((BIBLIOTECA / 'transicoes' / f'{transicao}.json').read_text())
    t = a['dur']
    w, h = a['w'], a['h']
    ent_t, f_t = transicoes.filtros([{**tr['efeito'], 't': t}], 'cat', 'vfim', w, h, 2, FPS)
    f = [f'[0:v][1:v]concat=n=2:v=1:a=0,fps={FPS}[cat]', *f_t]
    entradas = ['-i', str(corpo), '-i', str(cta), *ent_t]
    # o som da transição no ponto da emenda, no nível dos sons de apoio
    som = tr.get('som') or {}
    idx_som = 2 + ent_t.count('-i')
    f.append('[0:a][1:a]concat=n=2:v=0:a=1[acat]')
    if som.get('som'):
        entradas += ['-i', str(sons.arquivo(som['som']))]
        ganho = sons.INTENSIDADES.get(som.get('intensidade', 'medio'), 0.5)
        atraso = int(max(t + float(som.get('atraso') or 0), 0) * 1000)
        f.append(f'[{idx_som}:a]aresample=48000,aformat=channel_layouts=stereo,volume={ganho},adelay={atraso}|{atraso}[asom]')
        f.append('[acat][asom]amix=inputs=2:duration=first:normalize=0[afim]')
    else:
        f.append('[acat]anull[afim]')
    saida.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', *entradas, '-filter_complex', ';'.join(f), '-map', '[vfim]', '-map', '[afim]',
           '-c:v', 'hevc_videotoolbox', '-q:v', '65', '-tag:v', 'hvc1', '-r', str(FPS), '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', '-n', str(saida)]
    subprocess.run(cmd, check=True)
    s = sonda(saida)
    print(f'Pronto: {saida} ({s["w"]}×{s["h"]}, {s["dur"]:.2f} s, emenda em {t:.2f} s com {tr["nome"]})')
    for x in avisos:
        print(f'Aviso: {x}')


def main() -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n\n')[0])
    ap.add_argument('corpo')
    ap.add_argument('cta')
    ap.add_argument('saida', type=Path)
    ap.add_argument('--transicao', default='luz-colorida', choices=['luz-colorida', 'brilho-branco'])
    x = ap.parse_args()
    encaixar(x.corpo, x.cta, x.saida.expanduser(), x.transicao)


if __name__ == '__main__':
    main()
