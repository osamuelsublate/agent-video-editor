# /// script
# requires-python = ">=3.12"
# dependencies = ["mediapipe", "opencv-python", "numpy"]
# ///
"""O recorte do ator (do 18: backend/app/recorte_ator.py): a silhueta da pessoa quadro a quadro, para a cabeça e os ombros
passarem por cima do insert quando o ator fica pequeno no "ator embaixo" (o modo janela, com a cabeça saindo por cima,
e o recortado). Roda sobre o proxy do bruto (a mesma linha do tempo) com a segmentação de pessoa do macOS (Vision,
qualidade alta, `recorte_vision.swift`: limpa no cabelo); sem o `swiftc`, com o segmentador de selfie do MediaPipe, local
(o de antes, que vazava em volta da cabeça).

    uv run ferramentas/recorte.py <slug>

Sai em `projetos/<slug>/midia/recorte/<bruto>_mascara.mp4` (cinza, branco = pessoa, borda macia), que o render usa
sozinho quando existe.
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, ler, pasta  # noqa: E402

MODELO = BIBLIOTECA / 'modelos' / 'selfie_segmenter.tflite'
URL = 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite'


VISION = Path(__file__).parent / 'recorte_vision.swift'


def segmentar_vision(video: Path, destino: Path) -> bool:
    """A máscara pelo Vision (compilado uma vez em `biblioteca/modelos/recorte_vision`), suavizada no tempo, com borda macia
    Devolve False sem o `swiftc` (o MediaPipe entra no lugar)."""
    import shutil
    if not shutil.which('swiftc'):
        return False
    binario = BIBLIOTECA / 'modelos' / 'recorte_vision'
    if not binario.exists() or binario.stat().st_mtime < VISION.stat().st_mtime:
        binario.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['swiftc', '-O', str(VISION), '-o', str(binario)], check=True, capture_output=True)
    import json
    v = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate',
                                   '-of', 'json', str(video)], capture_output=True, text=True, check=True).stdout)['streams'][0]
    w, h, fps = v['width'], v['height'], v['r_frame_rate']
    destino.parent.mkdir(parents=True, exist_ok=True)
    gerar = subprocess.Popen([str(binario), str(video)], stdout=subprocess.PIPE)
    filtro = "tmix=frames=2:weights='1 1',gblur=sigma=1.2"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{w}x{h}', '-r', fps, '-i', '-',
                        '-vf', filtro, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'veryfast', str(destino)],
                       stdin=gerar.stdout)
    gerar.stdout.close()
    if gerar.wait() or r.returncode:
        raise SystemExit('a máscara pelo Vision falhou')
    return True


def segmentar(video: Path, destino: Path) -> None:
    """A máscara quadro a quadro: a confiança do segmentador suavizada no tempo (sem tremer), uma rampa estreita em volta
    de 0,5 (borda definida) e um desfoque leve (a borda macia que mistura com o insert). Do 18, igual."""
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions, vision

    if not MODELO.exists():
        MODELO.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, MODELO)
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    opcoes = vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(MODELO)),
                                          running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    sai = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{w}x{h}', '-r', f'{fps}',
                            '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'veryfast', str(destino)],
                           stdin=subprocess.PIPE)
    anterior = None
    with vision.ImageSegmenter.create_from_options(opcoes) as seg:
        k = 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            conf = seg.segment_for_video(img, int(k * 1000 / fps)).confidence_masks[0].numpy_view()
            m = cv2.resize(conf, (w, h), interpolation=cv2.INTER_LINEAR)
            anterior = m if anterior is None else 0.6 * m + 0.4 * anterior
            a = np.clip((anterior - 0.35) / 0.3, 0, 1)
            a = cv2.GaussianBlur(a, (0, 0), 2.5)
            sai.stdin.write((a * 255).astype(np.uint8).tobytes())
            k += 1
            if k % 240 == 0:
                print(f'      {k}/{total} quadros', flush=True)
    sai.stdin.close()
    if sai.wait():
        raise SystemExit('ffmpeg (máscara) falhou')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    slug = sys.argv[1]
    e = ler(slug)
    fonte = next(f for f in e['fontes'] if f.get('papel', 'bruto') == 'bruto')
    proxy = pasta(slug) / (fonte.get('proxy') or f'midia/proxy/{fonte["id"]}.mp4')
    destino = pasta(slug) / 'midia' / 'recorte' / f'{fonte["id"]}_mascara.mp4'
    print(f'Recorte do ator de {slug}: {proxy.name} → {destino.relative_to(pasta(slug))}', flush=True)
    if not segmentar_vision(proxy, destino):
        segmentar(proxy, destino)
    print('Pronto.')
