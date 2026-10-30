"""As cópias de exportação do banco: tudo o que a página de render toca ganha um H.264 8 bits 4:2:0, inclusive motions e
prints sobrepostos (sem a cópia, a página toca o original, e um codec que o Chromium não tem vira um plano preto, sem erro)."""
import json
import subprocess

import render
from base import ffmpeg


def item(banco, bid, **campos):
    pasta = banco / bid
    pasta.mkdir(parents=True)
    # MPEG-4 Part 2: o Chromium não toca, como o HEVC, e o ffmpeg de qualquer máquina grava
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=s=64x64:r=24:d=0.2', '-c:v', 'mpeg4', str(pasta / 'original.mp4'))
    (pasta / 'item.json').write_text(json.dumps({'id': bid, 'tipo': 'video', 'arquivo': 'original.mp4', **campos}))
    return pasta


def formato(arq):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,pix_fmt', '-of', 'csv=p=0', str(arq)],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def test_todo_lugar_que_toca_no_navegador_ganha_a_copia(tmp_path, monkeypatch):
    monkeypatch.setattr(render, 'BIBLIOTECA', tmp_path)
    banco = tmp_path / 'banco'
    ids = {k: f'{i:010x}' for i, k in enumerate(('insert', 'motion', 'pai', 'campo', 'print', 'solto'), 1)}
    pastas = {k: item(banco, ids[k]) for k in ids}
    (banco / 'aaaaaaaaaa').mkdir()  # um trecho: a cópia é a do pai
    (banco / 'aaaaaaaaaa' / 'item.json').write_text(json.dumps({'id': 'aaaaaaaaaa', 'pai': ids['pai'], 'inicio': 0, 'fim': 0.1}))
    edicao = {'inserts': {'pedidos': [{'midias': [{'banco': ids['insert']}]}]},
              'direcao': {'itens': [{'camada': 'elemento', 'banco': ids['print']}, {'camada': 'plano'}]},
              'motions': {'p1': {'tipo': 'video', 'banco': ids['motion']}, 'p2': {'tipo': 'video', 'banco': 'aaaaaaaaaa'},
                          'p3': {'tipo': 'preset', 'valores': {'capa': ids['campo'], 'texto': 'bbbbbbbbbb não existe no banco'}}}}
    antes = {k: (p / 'original.mp4').read_bytes() for k, p in pastas.items()}

    assert render.copias_do_banco(edicao) == 5
    for k in ('insert', 'motion', 'pai', 'campo', 'print'):
        assert formato(pastas[k] / 'exportacao.mp4') == 'h264,yuv420p'
    assert not (pastas['solto'] / 'exportacao.mp4').exists()  # o que o projeto não usa fica sem cópia
    assert all((p / 'original.mp4').read_bytes() == antes[k] for k, p in pastas.items())  # o original nunca muda
    assert render.copias_do_banco(edicao) == 0  # só uma vez
