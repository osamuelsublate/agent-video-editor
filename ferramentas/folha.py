# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Folha de contato de um vídeo: um quadro a cada N s, com o tempo escrito em cada um, numa imagem só (para o Claude
conferir um vídeo olhando).

    uv run ferramentas/folha.py <video> [--cada 2] [--colunas 8]

Grava `<nome>_folha.jpg` ao lado do vídeo (no banco e na mídia dos projetos, em /tmp, para não sujar) e imprime o caminho.
"""
import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, PROJETOS, ffmpeg, inspecionar  # noqa: E402

# a primeira fonte que existe: a do Mac, a DejaVu do Linux; sem nenhuma, o ffmpeg escolhe pelo fontconfig. (As de
# render/motion/fonts/ são woff2: o drawtext não lê.)
FONTE = next((f for f in ('/System/Library/Fonts/Supplemental/Arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf') if Path(f).is_file()), None)
LADO = 320  # o lado maior de cada quadro


def destino(video: Path) -> Path:
    v = video.resolve()
    protegido = v.is_relative_to(BIBLIOTECA) or (v.is_relative_to(PROJETOS) and 'midia' in v.relative_to(PROJETOS).parts)
    pasta = Path('/tmp') if protegido else v.parent
    nome = f'{v.parent.name}_{v.stem}_folha.jpg' if protegido else f'{v.stem}_folha.jpg'
    return pasta / nome


def folha(video: Path, cada: float = 2.0, colunas: int = 8) -> Path:
    if not video.is_file():
        raise SystemExit(f'Vídeo não encontrado: {video}')
    info = inspecionar(video)
    if 'largura' not in info:
        raise SystemExit(f'{video} não tem vídeo.')
    n = max(1, math.floor(info['duracao'] / cada + 1e-6) + (1 if info['duracao'] % cada > 0.05 or info['duracao'] < cada else 0))
    colunas = max(1, min(colunas, n))
    linhas = math.ceil(n / colunas)
    texto = r"%{eif\:trunc(t/60)\:d}\:%{eif\:mod(trunc(t)\,60)\:d\:2}\,%{eif\:trunc(mod(t\,1)*10)\:d}"
    filtros = [f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{cada - 0.02})'",
               f"scale='if(gt(iw,ih),{LADO},-2)':'if(gt(iw,ih),-2,{LADO})'",
               f"drawtext={'fontfile=' + FONTE if FONTE else 'font=sans'}:text='{texto}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=5",
               f'tile={colunas}x{linhas}:margin=4:padding=4:color=0x202020']
    saida = destino(video)
    ffmpeg('-i', str(video), '-vf', ','.join(filtros), '-fps_mode', 'vfr', '-frames:v', '1', '-q:v', '3', str(saida))
    return saida


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Folha de contato de um vídeo.')
    ap.add_argument('video')
    ap.add_argument('--cada', type=float, default=2.0, help='segundos entre os quadros (padrão 2)')
    ap.add_argument('--colunas', type=int, default=8)
    a = ap.parse_args()
    print(folha(Path(a.video), a.cada, a.colunas))
