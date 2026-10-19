# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright==1.63.0", "pillow", "numpy"]
# ///
"""O render: o vídeo do projeto com tudo queimado (cortes, 9:16, look, inserts, motions, transições, legenda e áudio).

    uv run ferramentas/render.py <slug>            → projetos/<slug>/versoes/vN/ (proxy.mp4 720×1280 H.264 + os JSONs da revisão)
    uv run ferramentas/render.py <slug> --final    → projetos/<slug>/final/<nome> · <AAAA-MM-DD HHhMM>.mp4 (2160×3840 HEVC) e,
        ao lado, o .md com a transcrição (a fala que ficou no corte)
    uv run ferramentas/render.py <slug> --camadas  → só fotografa a camada dos inserts e motions para o cache (o pré-render:
        rode em segundo plano enquanto a edição segue; o render da entrega espera ele e acha tudo pronto)
    uv run ferramentas/render.py amostra-look <slug> <t> <lut|-> <intensidade> <vinheta> [nitidez]
        → um trecho de 3 s do ator (do bruto, no instante t do vídeo final) com aquele look: o provador da revisão
    uv run ferramentas/render.py previas-motions [--refazer] [<id> …]
        → biblioteca/motions/previas/<id>.mp4: a prévia de cada motion (720×1280, 30 fps quadro a quadro, mudo), o que a aba
        Motions do app toca na grade (a animação ao vivo fica só no modal). Só refaz o que mudou desde a última prévia.

Como a exportação do 18 (SPEC §13; a cola de backend/app/exportacao.py `_gravar`/`_trechos`, reescrita aqui): a página
de render (`render/`, servida por `servidor.servir`) calcula no navegador o que a prévia calcula (`window.__render`) e é
fotografada quadro a quadro por navegadores escondidos (`montagem/render_quadros.py`); o ator e o áudio saem do bruto
pelo ffmpeg (`montagem/exportacao.py`), em trechos de ~20 s guardados no cache e emendados sem recodificar.

O cache (`projetos/<slug>/.cache/`): a foto de cada trecho da camada (`camadas/<chave>.mov`, pela assinatura que a
página dá a ele) e o áudio pronto, com o −14 LUFS (`audio.json` + `audio.wav`). Numa revisão, só os trechos que mudaram
são fotografados de novo e o áudio só é refeito se algo nele mudou.
"""
import fcntl
import hashlib
import json
import math
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import servidor  # noqa: E402
from base import BIBLIOTECA, RAIZ, ffmpeg, gravar_json, inspecionar, ler, ler_json, pasta  # noqa: E402
from montagem import audio, exportacao, legenda, look, render_quadros, sons  # noqa: E402
from montagem.exportacao import dur_saida  # noqa: E402

FPS = 24
PROXY = (720, 1280, 'h264')
FINAL = (2160, 3840, 'hevc')
VELOCIDADE = (1.0, 1.5)
# o código que desenha a camada: se muda, as fotos guardadas não valem mais
CODIGO_CAMADA = [RAIZ / 'render' / x for x in ('index.html', 'pagina.js', 'motion.html')] + [BIBLIOTECA / 'motions' / 'runtime.js']
GUARDA = 3  # o cache da camada guarda os clipes usados nos últimos N renders do projeto


def pagina(slug: str, porta: int) -> str:
    """A página de render. `RENDER_PAGINA` troca por outra, só para testar contra a do 18 (o mesmo `window.__render`):
    RENDER_PAGINA='http://localhost:5173/render/p/{slug}'."""
    return os.environ.get('RENDER_PAGINA', 'http://127.0.0.1:{porta}/render/?projeto={slug}').format(slug=slug, porta=porta)


# ---------------------------------------------------------------- o projeto no tempo do vídeo final

def v1_tocada(edicao: dict) -> list[dict]:
    """Os clipes da V1 em ordem, cada um com a aceleração do ator (`vel`). Do 18: projeto.v1_tocada."""
    try:
        v = round(min(max(float(edicao.get('velocidade') or 1), VELOCIDADE[0]), VELOCIDADE[1]), 3)
    except (TypeError, ValueError):
        v = 1.0
    return [{**c, 'vel': v} for c in sorted((edicao.get('timeline') or {}).get('V1') or [], key=lambda c: c.get('ordem', c['inicio']))]


def duracao_antes(slug: str, avisos: list[str]) -> float:
    """A duração da última versão do vídeo que vem antes deste na emenda (`audio.continua`): onde a trilha dele parou."""
    vs = sorted((int(d.name[1:]) for d in (pasta(slug) / 'versoes').glob('v*') if d.name[1:].isdigit()), reverse=True)
    for v in vs:
        dur = (ler_json(pasta(slug) / 'versoes' / f'v{v}' / 'info.json', {}) or {}).get('duracao')
        if dur:
            return float(dur)
    avisos.append(f'audio.continua: {slug} não tem versão renderizada; a trilha começou do zero.')
    return 0.0


def palavras_na_saida(palavras: list[dict], clipes: list[dict]) -> list[dict]:
    """As palavras que tocam no vídeo final, com início e fim no tempo da saída. Do 18: direcao_projeto.palavras_na_saida."""
    acc, posicoes = 0.0, []
    for c in clipes:
        posicoes.append((c, acc))
        acc += dur_saida(c)
    out = []
    for w in palavras:
        for c, base in posicoes:
            if w['inicio'] < c['fim'] and w['fim'] > c['inicio']:
                v = c.get('vel', 1)
                out.append({**w, 'saida_ini': round(base + (max(w['inicio'], c['inicio']) - c['inicio']) / v, 3),
                            'saida_fim': round(base + (min(w['fim'], c['fim']) - c['inicio']) / v, 3)})
                break
    return sorted(out, key=lambda w: w['saida_ini'])


# ---------------------------------------------------------------- o banco, a página e as fotos

def copias_do_banco(edicao: dict) -> int:
    """A cópia de exportação de cada vídeo do banco usado (o original, ou o pai de um trecho): a resolução original com
    quadro-chave a cada 6 quadros, para a busca quadro a quadro ser rápida; refeita se o original mudou. Do 18:
    banco.arquivo_para_exportar. Devolve quantas fez."""
    feitas = 0
    usados = {m['banco'] for x in (edicao.get('inserts') or {}).get('pedidos', []) for m in x.get('midias', []) if m.get('banco')}
    for base in sorted({(ler_json(BIBLIOTECA / 'banco' / b / 'item.json') or {}).get('pai') or b for b in usados}):
        pasta_item = BIBLIOTECA / 'banco' / base
        item = ler_json(pasta_item / 'item.json')
        if not item or item.get('tipo') != 'video' or not (pasta_item / item['arquivo']).exists():
            continue  # imagem (vai a original) ou mídia apagada do banco: a página mostra o que houver
        original, pronto = pasta_item / item['arquivo'], pasta_item / 'exportacao.mp4'
        if pronto.exists() and pronto.stat().st_mtime >= original.stat().st_mtime:
            continue
        tmp = pasta_item / 'exportacao.tmp.mp4'
        ffmpeg('-i', str(original), '-map', '0:v:0', '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-c:v', 'libx264', '-preset', 'veryfast',
               '-crf', '14', '-g', '6', '-keyint_min', '6', '-pix_fmt', 'yuv420p', '-an', '-movflags', '+faststart', str(tmp))
        tmp.replace(pronto)
        feitas += 1
    return feitas


def ler_pagina(url: str) -> dict:
    """O que a página de render calcula (`window.__render`, no tempo do vídeo final): os inserts e motions (`trechos`), os
    sons, as transições, os blocos da legenda, os movimentos do Full ator e, para a revisão, as palavras e os planos
    (null se a página não os tiver). Do 18: exportacao._trechos."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chromium')
        try:
            pg = render_quadros.abrir_render(browser, url)
            return pg.evaluate("""async () => {
                const r = window.__render
                const ler = async (f) => (typeof f === 'function' ? await f() : f ?? null)
                return { duracao: r.duracao, trechos: r.trechos, sons: r.sons ? await r.sons() : [], transicoes: await ler(r.transicoes),
                         legenda: await ler(r.legenda), movimentos: await ler(r.movimentos), palavras: await ler(r.palavras),
                         planos: await ler(r.planos) }
            }""")
        finally:
            browser.close()


def fotografar(url: str, trechos: list[dict], w: int, h: int, tmp: Path, navegadores: int) -> list[Path]:
    """A camada dos inserts: as fotos de cada trecho (`exportacao.fotos`, na grade do próprio trecho) em pedaços,
    fotografadas em paralelo (cada navegador grava os seus pedaços em clipes ProRes 4444 com transparência); depois, um
    clipe por trecho, os pedaços emendados sem recodificar. Devolve os clipes, na ordem dos trechos."""
    grupos = exportacao.pedacos(trechos, FPS, navegadores)
    total = sum(len(x) for g in grupos for x in g)
    if not total:
        return []
    tarefas = [(ts, FPS, w, h, str(tmp / f'{i:03d}_{j:03d}.mov')) for i, g in enumerate(grupos) for j, ts in enumerate(g)]
    print(f'      {total} quadros em {len(tarefas)} pedaços, {min(navegadores, len(tarefas))} navegadores', flush=True)
    pool = multiprocessing.get_context('spawn').Pool(min(navegadores, len(tarefas)), initializer=render_quadros.iniciar,
                                                      initargs=(url, w, h))
    try:
        feitos, marca = 0, 0.25
        for n in pool.imap_unordered(render_quadros.pedaco, tarefas):
            feitos += n
            if feitos / total >= marca:
                print(f'      {feitos}/{total} quadros', flush=True)
                marca = math.floor(feitos / total * 4 + 1) / 4
        pool.close()
        pool.join()
    finally:
        pool.terminate()
    camadas = []
    for i, g in enumerate(grupos):
        lista = tmp / f'{i:03d}.txt'
        lista.write_text(''.join(f"file '{i:03d}_{j:03d}.mov'\n" for j in range(len(g))))
        clipe = tmp / f'{i:03d}.mov'
        ffmpeg('-f', 'concat', '-safe', '0', '-i', str(lista), '-c', 'copy', str(clipe))
        camadas.append(clipe)
    return camadas


def _hash(*partes: str | bytes) -> str:
    h = hashlib.sha256()
    for x in partes:
        h.update(x if isinstance(x, bytes) else x.encode())
        h.update(b'\0')
    return h.hexdigest()[:32]


def _hash_arquivo(arq: Path) -> str:
    return _hash(arq.read_bytes()) if arq.is_file() else 'ausente'


def chave_do_trecho(t: dict, w: int, h: int, codigo: str) -> str:
    """A chave das fotos de um trecho: a assinatura da página (o que ele desenha, nos tempos relativos ao começo dele), o
    código da camada, o HTML dos presets de motion que ele usa, o tamanho, o fps e quantas fotos. Sem a fase do 1º quadro:
    as fotos são na grade do próprio trecho (`exportacao.fotos`), então com tudo igual servem em qualquer instante."""
    presets = sorted({m['preset'] for m in json.loads(t['assinatura']).get('motions') or [] if m.get('preset')})
    return _hash(t['assinatura'], codigo, *(_hash_arquivo(BIBLIOTECA / 'motions' / 'presets' / f'{x}.html') for x in presets),
                 f'{w}x{h}', str(FPS), str(len(exportacao.fotos(t, FPS))))


def camada(url: str, trechos: list[dict], w: int, h: int, cache: Path, tmp: Path) -> tuple[list[tuple[Path, float]], list[str] | None]:
    """A camada dos inserts com o cache: o clipe de cada trecho fica em `cache/<chave>.mov` e só os que faltam são
    fotografados. O `_inserts` põe o clipe no 1º quadro do trecho (`q0 / FPS`, contado agora): serve onde o trecho cair.
    O clipe tem fotos para qualquer fase; se o trecho agora pega um quadro a menos, vai uma cópia sem a última (sem
    recodificar), senão ela cobriria o 1º quadro do que vem depois. Uma página sem `assinatura` (a do 18, por
    `RENDER_PAGINA`) fotografa tudo, sem guardar. Devolve os clipes com o instante de cada um e as chaves usadas (None sem
    o cache)."""
    itens = [(t, qs) for t in trechos if (qs := exportacao.quadros(t, FPS))]
    com_cache = all(t.get('assinatura') for t in trechos)
    if com_cache:
        codigo = _hash(*(_hash_arquivo(a) for a in CODIGO_CAMADA))
        chaves = [chave_do_trecho(t, w, h, codigo) for t, _ in itens]
    else:
        cache, chaves = tmp / 'camadas', [f'{k:03d}' for k in range(len(itens))]
    cache.mkdir(parents=True, exist_ok=True)
    faltam = {k: t for (t, _), k in zip(itens, chaves) if not (cache / f'{k}.mov').exists()}
    print(f'      {len(itens) - len(faltam)} trechos do cache, {len(faltam)} para fotografar', flush=True)
    for k, clipe in zip(faltam, fotografar(url, list(faltam.values()), w, h, tmp, exportacao.NAVEGADORES)):
        clipe.replace(cache / f'{k}.mov')
    camadas = []
    for i, ((t, qs), k) in enumerate(zip(itens, chaves)):
        clipe = cache / f'{k}.mov'
        if len(qs) < len(exportacao.fotos(t, FPS)):
            clipe, curto = tmp / f'curto_{i:03d}.mov', clipe
            ffmpeg('-i', str(curto), '-map', '0:v', '-c', 'copy', '-frames:v', str(len(qs)), str(clipe))
        camadas.append((clipe, qs.start / FPS))
    return camadas, chaves if com_cache else None


def limpar_camadas(cache: Path, chaves: list[str], extensao: str = '.mov') -> None:
    """Depois de um render: guarda as chaves dele e apaga do cache os clipes que nenhum dos últimos `GUARDA` usou."""
    registro = cache / 'usos.json'
    usos = ([*(ler_json(registro) or []), chaves])[-GUARDA:]
    gravar_json(registro, usos)
    vivos = {k for u in usos for k in u}
    for clipe in cache.glob(f'*{extensao}'):
        if clipe.stem not in vivos:
            clipe.unlink(missing_ok=True)


# ---------------------------------------------------------------- o áudio

def som(p: Path, edicao: dict, fonte: dict, clipes: list[dict], transcricao: list[dict], avisos: list[str]) -> dict:
    """O que o áudio precisa (`audio.filtros`): a voz da escolha (`midia/voz/<fonte>_<limpeza>.wav`, feita pelo preparar;
    se faltar, a do bruto com um aviso, como no 18), a sonoridade dela, o fundo e o laço, e as falas para o ducking.
    Do 18: audio.da_exportacao."""
    a = audio.do_projeto(edicao)
    limpeza = a['voz']['limpeza']
    voz = p / 'midia' / 'voz' / f"{fonte['id']}_{limpeza}.wav"
    if limpeza != 'sem' and not voz.exists():
        avisos.append(f'Falta a voz limpa ({voz.relative_to(p)}): o vídeo saiu com a voz do bruto.')
        limpeza = 'sem'
    if limpeza == 'sem':
        voz = p / fonte['arquivo']
    voz_lufs = ((edicao.get('audio') or {}).get('voz_lufs') or {}).get(f"{fonte['id']}_{limpeza}")
    if voz_lufs is None:
        voz_lufs = round(audio.lufs(voz, como_voz=True), 1)
    fundo = audio.arquivo_trilha(a['fundo'])
    if a['fundo'] and not fundo:
        avisos.append(f"A faixa de fundo {a['fundo']} não está em biblioteca/trilhas/: o vídeo saiu sem fundo.")
    laco = audio.laco(fundo) if fundo else None
    # a trilha entra já no trecho cheio do laço, sem a introdução baixa (o criador sentiu falta da música no começo)
    return {'voz': voz, 'voz_lufs': voz_lufs, 'timbre': a['voz']['timbre'], 'niveis': a['niveis'], 'fundo': fundo,
            'laco': laco, 'fundo_mudo': a['fundo_mudo'], 'fade_fim': a['fade_fim'],
            'desde': (laco[0] if laco else 0.0) + (duracao_antes(a['continua'], avisos) if a['continua'] else 0.0),
            'falas': audio.falas(palavras_na_saida(transcricao, clipes)), 'ducking_db': audio.DUCKING_DB, 'limpeza': limpeza}


def falas_extras(p: Path, edicao: dict, transicao: list[dict], clipes: list[dict]) -> list[dict]:
    """As falas gravadas à parte (`audio.extras`: `arquivo` do projeto, presa ao fim de uma `palavra` + `depois` s, `ganho`):
    entram por cima da voz no fader do ator, já tratadas (ex.: o fim alternativo de uma versão sem ManyChat)."""
    saida = {w['id']: w for w in palavras_na_saida(transicao, clipes)}
    out = []
    for x in (edicao.get('audio') or {}).get('extras') or []:
        w, arq = saida.get(x.get('palavra')), p / x.get('arquivo', '')
        if not w or not arq.is_file():
            continue
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(arq)],
                                   capture_output=True, text=True).stdout or 0)
        out.append({'arquivo': str(arq), 't': w['saida_fim'] + float(x.get('depois', 0)), 'desde': 0.0, 'dur': dur,
                    'ganho': float(x.get('ganho', 1.0)), 'grupo': 'voz'})
    return out


def sons_das_midias(edicao: dict, planos: list[dict]) -> list[dict]:
    """O áudio próprio dos inserts com `som: true` (ex.: a demo do produto falando): a 1ª mídia toca do começo do plano
    até o fim dele, no ganho `som_ganho` (padrão 1, o nível do arquivo). Um trecho toca o original a partir do início dele."""
    tempo = {p.get('id'): p for p in planos}
    out = []
    for q in (edicao.get('inserts') or {}).get('pedidos') or []:
        pl = tempo.get(q.get('plano'))
        if not q.get('som') or not pl or not q.get('midias'):
            continue
        item = ler_json(BIBLIOTECA / 'banco' / q['midias'][0]['banco'] / 'item.json', {}) or {}
        dono = ler_json(BIBLIOTECA / 'banco' / item['pai'] / 'item.json', {}) if item.get('pai') else item
        if not dono or not dono.get('arquivo'):
            continue
        arq = BIBLIOTECA / 'banco' / (item.get('pai') or item['id']) / dono['arquivo']
        out.append({'arquivo': str(arq), 't': float(pl['ini']), 'desde': float(item.get('inicio') or 0),
                    'dur': float(pl['fim']) - float(pl['ini']), 'ganho': float(q.get('som_ganho', 1.0)), 'grupo': 'midia'})
    return out


def mistura(p: Path, a: dict, clipes: list[dict], eventos: list[dict], duracao: float) -> tuple[dict, Path]:
    """O áudio pronto: a mistura numa passada só, o ganho do −14 LUFS medido sobre ela (`audio.medir`) e aplicado, num WAV
    em float (as mesmas amostras que a passada final faria: ela só codifica). Guardados em `.cache/audio.json` e
    `.cache/audio.wav` com a chave do que entra no áudio: o próprio grafo dele (a V1, a voz, os sons, o fundo, os níveis e
    o ducking) e o tamanho e a data de cada arquivo de entrada. Sem nada mudado no áudio, nem mede nem mistura de novo."""
    entradas, f = audio.filtros(a, clipes, eventos, 0, 'pfim', duracao, {'ganho': 0})
    arquivos = [Path(x) for x in entradas if x != '-i']
    chave = _hash(*entradas, *f, f'{duracao:.4f}', *(f'{x.stat().st_size}@{x.stat().st_mtime_ns}' for x in arquivos))
    guardada, wav = ler_json(p / '.cache' / 'audio.json') or {}, p / '.cache' / 'audio.wav'
    if guardada.get('chave') == chave and wav.exists():
        return guardada['medida'], wav
    (p / '.cache' / 'audio.json').unlink(missing_ok=True)  # a chave velha nunca fica apontando para um WAV novo
    # uma passada do grafo inteiro (sem o ganho final); a medida e o ganho só leem esse WAV (as mesmas amostras em float)
    # os sons somados numa faixa à parte (`sons.faixa`): um filtro por som no grafo era o grosso do tempo do áudio
    cru, parte, faixa = wav.with_suffix('.cru.wav'), wav.with_suffix('.parte.wav'), wav.with_suffix('.sons.wav')
    try:
        sons.faixa(audio.com_faders(a, eventos), duracao, faixa)
        entradas, f = audio.filtros(a, clipes, eventos, 0, 'pfim', duracao, {'cru': True}, faixa)
        ffmpeg(*entradas, '-filter_complex', ';'.join(f), '-map', '[pfim]', '-t', f'{duracao:.4f}', '-c:a', 'pcm_f32le', str(cru))
        m = audio.medir(a, clipes, eventos, duracao, cru)
        ffmpeg('-i', str(cru), '-af', f"{audio.final(m['ganho'])},aresample=48000,aformat=channel_layouts=stereo", '-c:a', 'pcm_f32le', str(parte))
    finally:
        cru.unlink(missing_ok=True)
        faixa.unlink(missing_ok=True)
    parte.replace(wav)
    gravar_json(p / '.cache' / 'audio.json', {'chave': chave, 'medida': m})
    return m, wav


# ---------------------------------------------------------------- a montagem por trechos

TRECHO = 20.0  # s: o tamanho mínimo de cada trecho da montagem
JUNTOS = 4  # trechos montados ao mesmo tempo


def fronteiras(clipes: list[dict], trechos: list[dict], transicoes: list[dict] | None, legenda: dict | None, n: int) -> list[int]:
    """Onde a montagem do proxy se divide (quadros do vídeo final, de 0 a `n`): a cada `TRECHO` s, nunca no meio de um
    insert ou motion nem de uma transição (com 2 quadros de folga); de preferência num corte e fora de um bloco de
    legenda. Cada fronteira é o 1º quadro do trecho seguinte."""
    proibido = set()
    for t in trechos:
        qs = exportacao.quadros(t, FPS)
        proibido.update(range(qs.start + 1, qs.stop))
    for x in transicoes or []:
        q0 = math.floor((x['t'] - x['antes']) * FPS)
        proibido.update(range(q0 - 2, math.ceil((x['t'] + x['depois']) * FPS) + 3))
    na_legenda = set()
    for b in (legenda or {}).get('blocos') or []:
        na_legenda.update(range(math.ceil(b['ini'] * FPS) + 1, math.ceil(b['fim'] * FPS)))
    acc, cortes = 0.0, set()
    for c in clipes:
        cortes.add(math.ceil(acc * FPS - 1e-9))
        acc += dur_saida(c)
    passo = round(TRECHO * FPS)
    out, q = [0], 0
    while n - q > passo * 1.5:
        janela = range(q + passo, min(q + 2 * passo, n - passo // 2))
        livres = [x for x in janela if x not in proibido]
        escolha = (next((x for x in livres if x in cortes and x not in na_legenda), None)
                   or next((x for x in livres if x not in na_legenda), None) or next(iter(livres), None))
        if escolha is None:  # nada livre: o trecho cresce até achar
            escolha = next((x for x in range(q + 2 * passo, n) if x not in proibido), None)
            if escolha is None:
                break
        out.append(escolha)
        q = escolha
    return [*out, n]


def fatia(clipes: list[dict], a: float, b: float) -> list[dict]:
    """Os clipes da V1 que tocam em [a, b) do vídeo final, recortados nesse intervalo (os tempos do bruto)."""
    acc, out = 0.0, []
    for c in clipes:
        d, v = dur_saida(c), c.get('vel', 1)
        x0, x1 = max(acc, a), min(acc + d, b)
        if x1 - x0 > 1e-6:
            pedaco = {**c, 'inicio': c['inicio'] + (x0 - acc) * v, 'fim': c['inicio'] + (x1 - acc) * v}
            if acc < a:  # começa no meio do clipe: o vídeo na grade do clipe inteiro (`desde_v` em `exportacao._ator`)
                q0 = math.ceil(acc * FPS - 1e-9)
                pedaco['desde_v'] = (c['inicio'] + (q0 / FPS - acc) * v, round(a * FPS) - q0)
            out.append(pedaco)
        acc += d
    # um último pedaço menor que um quadro (sem quadro nenhum do trecho) não entra: o concat do ator não aceita vazio
    while out and math.ceil((b - a - dur_saida(out[-1])) * FPS - 1e-9) >= math.ceil((b - a) * FPS - 1e-9):
        out.pop()
    return out


def _impressao(cmd: list[str], tmp: Path, nomes: dict[str, str]) -> str:
    """A chave de um trecho montado: o comando do ffmpeg com cada arquivo de entrada trocado pelo que ele é (os do tmp
    pelo conteúdo; os outros pelo tamanho e a data) e os caminhos de `nomes` (a saída, a legenda, o silêncio: os nomes
    mudam com o índice do trecho) pelo apelido dado."""
    partes = []
    for i, x in enumerate(cmd):
        if i and cmd[i - 1] == '-i' and x not in nomes:
            arq = Path(x)
            x = _hash_arquivo(arq) if arq.is_relative_to(tmp) else f'{x}@{arq.stat().st_size}@{arq.stat().st_mtime_ns}'
        for de, para in nomes.items():
            x = x.replace(de, para)
        partes.append(x)
    return _hash(*partes)


def montar_por_trechos(video: Path, clipes: list[dict], horizontal: bool, enq_x: float, w: int, h: int, codec: str, duracao: float,
                       trechos: list[dict], camadas: list[tuple[Path, float]], divisoes: list, r: dict, lk: dict, vinheta: Path | None,
                       mascara: Path | None, a: dict, destino: Path, hwaccel: bool, cache: Path, tmp: Path) -> list[str]:
    """A montagem (proxy ou final) em trechos de ~`TRECHO` s (`fronteiras`), cada um com o mesmo `comando_final` do vídeo
    inteiro, só com o que cai nele (no tempo dele), guardado em `cache/<chave>.mp4`: numa revisão, só os trechos em que
    algo mudou são montados de novo (e `JUNTOS` por vez). Depois, emendados sem recodificar, com o áudio pronto por
    cima. O bruto é lido a partir de pouco antes do 1º clipe do trecho (`-ss`), não do começo. Devolve as chaves."""
    n = math.ceil(duracao * FPS - 1e-9)
    com_quadros = [t for t in trechos if exportacao.quadros(t, FPS)]  # na ordem de `camadas`
    qs = fronteiras(clipes, trechos, r.get('transicoes'), r.get('legenda'), n)
    mudo = tmp / 'mudo.wav'  # o áudio de cada trecho é descartado (vai o pronto, inteiro): um silêncio curto no lugar
    ffmpeg('-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', '0.1', str(mudo))
    tarefas = []
    for i, (qa, qb) in enumerate(zip(qs, qs[1:])):
        ta, tb = qa / FPS, min(qb / FPS, duracao)
        seg = fatia(clipes, ta, tb)
        ss = max(min(min(c['inicio'], (c.get('desde_v') or (c['inicio'],))[0]) for c in seg) - 2, 0.0)
        seg = [{**c, 'inicio': c['inicio'] - ss, 'fim': c['fim'] - ss,
                **({'desde_v': (c['desde_v'][0] - ss, c['desde_v'][1])} if c.get('desde_v') else {})} for c in seg]
        cam = [(clipe, ini - ta) for (clipe, ini), t in zip(camadas, com_quadros)
               if qa <= exportacao.quadros(t, FPS).start and exportacao.quadros(t, FPS).stop <= qb]
        div = [(max(x0 - ta, 0.0), min(x1, tb) - ta, d) for x0, x1, d in divisoes if x0 < tb and x1 > ta]
        trans = [{**x, 't': x['t'] - ta} for x in r.get('transicoes') or [] if x['t'] + x['depois'] > ta and x['t'] - x['antes'] < tb]
        mov = [{**m, 'ini': m['ini'] - ta, 'fim': m['fim'] - ta} for m in r.get('movimentos') or [] if m['ini'] < tb and m['fim'] > ta]
        blocos = [{**b, 'ini': max(b['ini'] - ta, 0.0), 'fim': min(b['fim'], tb) - ta}
                  for b in (r.get('legenda') or {}).get('blocos') or [] if b['ini'] < tb and b['fim'] > ta]
        arq_leg = legenda.escrever({'blocos': blocos}, w, h, tmp / f'legenda_{i:03d}.ass')
        saida = tmp / f'trecho_{i:03d}.mp4'
        cmd = exportacao.comando_final(video, seg, horizontal, enq_x, w, h, FPS, div, cam, codec, tb - ta, saida, mascara, None, trans,
                                       {'arquivo': arq_leg} if arq_leg else None, lk, vinheta, {'pronta': mudo}, mov, hwaccel=hwaccel)
        # o trecho sai sem áudio: o AAC abre com 1024 amostras de atraso e o concat empurraria o vídeo junto (21 ms)
        k = cmd.index('-filter_complex')
        cmd[k + 1] += ';[am]anullsink'
        cmd = [x for i, x in enumerate(cmd) if x not in ('-progress', 'pipe:1') and x != '[am]' and not (x == '-map' and cmd[i + 1] == '[am]')]
        for arq in (video, mascara):  # o bruto e a máscara lidos a partir de `ss`
            if arq is not None and str(arq) in cmd:
                k = cmd.index(str(arq))
                cmd[k - 1:k - 1] = ['-ss', f'{ss:.3f}']
        nomes = {str(saida): '<saida>', str(mudo): '<mudo>', **({str(arq_leg): '<legenda>'} if arq_leg else {})}
        chave = _hash(_impressao(cmd, tmp, nomes), _hash_arquivo(arq_leg) if arq_leg else '')
        tarefas.append((chave, cmd, saida))
    cache.mkdir(parents=True, exist_ok=True)
    faltam = [(k, cmd, s) for k, cmd, s in tarefas if not (cache / f'{k}.mp4').exists()]
    print(f'      {len(tarefas)} trechos: {len(tarefas) - len(faltam)} do cache, {len(faltam)} para montar', flush=True)

    def montar(t: tuple[str, list[str], Path]) -> None:
        k, cmd, s = t
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f'ffmpeg falhou num trecho: {res.stderr[-600:]}')
        s.replace(cache / f'{k}.mp4')

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(JUNTOS) as pool:
        for j, _ in enumerate(pool.map(montar, faltam), 1):
            if j == len(faltam) or j % max(1, len(faltam) // 4) == 0:
                print(f'      {j}/{len(faltam)} montados', flush=True)
    lista = tmp / 'trechos.txt'
    lista.write_text(''.join(f"file '{cache / f'{k}.mp4'}'\n" for k, _, _ in tarefas))
    # a cor declarada por inteiro (BT.709 na matriz, nas primárias e na curva): o encoder do chip de vídeo só grava a
    # matriz, e um conversor que não acha as outras duas chuta outro padrão (no vturb, a pele saiu laranja)
    cor = f"{'hevc' if codec == 'hevc' else 'h264'}_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0"
    ffmpeg('-f', 'concat', '-safe', '0', '-i', str(lista), '-i', str(a['pronta']), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-bsf:v', cor,
           '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
           *(['-tag:v', 'hvc1'] if codec == 'hevc' else []), '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-t', f'{duracao:.4f}',
           '-movflags', '+faststart', str(destino))
    return [k for k, _, _ in tarefas]


# ---------------------------------------------------------------- o render

def _nome_livre(destino: Path) -> Path:
    k = 2
    alvo = destino
    while alvo.exists():
        alvo = destino.with_name(f'{destino.stem} ({k}){destino.suffix}')
        k += 1
    return alvo


def render(slug: str, final: bool = False) -> Path:
    t_ini = time.time()
    p = pasta(slug)
    edicao = ler(slug)
    clipes = v1_tocada(edicao)
    if not clipes:
        raise SystemExit(f'O projeto {slug} ainda não tem cortes (timeline.V1 vazia).')
    fonte = next(f for f in edicao['fontes'] if f['papel'] == 'bruto')
    duracao = sum(dur_saida(c) for c in clipes)
    w, h, codec = FINAL if final else PROXY
    horizontal = (fonte.get('largura') or 0) > (fonte.get('altura') or 0)
    transcricao = (ler_json(p / 'transcricao.json') or {}).get('palavras', [])
    fases: dict[str, float] = {}
    avisos: list[str] = []
    marca = [time.time()]

    def fase(nome: str) -> None:
        fases[nome] = round(time.time() - marca[0], 1)
        print(f'      {fases[nome]:.1f} s', flush=True)
        marca[0] = time.time()

    if final:
        nome = re.sub(r'\s+', ' ', re.sub(r'[/\\:*?"<>|\n\r\t]+', ' ', edicao.get('nome') or slug)).strip().strip('.')[:120]
        destino = _nome_livre(p / 'final' / f'{nome} · {datetime.now():%Y-%m-%d %Hh%M}.mp4')
        pasta_versao = None
        versao = None
    else:
        versao = 1 + max([int(m.group(1)) for x in (p / 'versoes').glob('v*') if (m := re.fullmatch(r'v(\d+)', x.name))], default=0)
        pasta_versao = p / 'versoes' / f'.v{versao}.parte'  # vira vN no fim: o app nunca vê uma versão pela metade
        shutil.rmtree(pasta_versao, ignore_errors=True)
        pasta_versao.mkdir(parents=True)
        destino = pasta_versao / 'proxy.mp4'
        # o aviso do app ("Claude trabalhando"): agora é o render da versão nova (sem aviso antes, sem os blocos)
        aviso_app = p / 'revisoes' / 'trabalhando.json'
        if (p / 'revisoes').is_dir():
            gravar_json(aviso_app, {'blocos': [], 'desde': datetime.now().isoformat(timespec='seconds'), **(ler_json(aviso_app, {}) or {}),
                                    'fase': 'renderizando', 'para': versao})
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='.render-', dir=p))
    srv = servidor.servir(0)
    print(f'Render de {slug}: {"final 2160×3840 HEVC" if final else f"proxy v{versao} 720×1280 H.264"}, {duracao:.1f} s de vídeo', flush=True)
    try:
        print('[1/5] Banco: cópias de exportação dos vídeos', flush=True)
        n = copias_do_banco(edicao)
        if n:
            print(f'      {n} feita(s)', flush=True)
        fase('banco')

        url = pagina(slug, srv.server_address[1])
        print(f'[2/5] Página de render: {url}', flush=True)
        r = ler_pagina(url)
        if r.get('duracao') is not None and abs(float(r['duracao']) - duracao) > 0.05:
            avisos.append(f"A página diz {float(r['duracao']):.2f} s de vídeo e a V1 dá {duracao:.2f} s.")
        trechos = r['trechos'] or []
        print(f"      {len(trechos)} trechos de insert/motion, {len(r['sons'] or [])} sons, {len(r['transicoes'] or [])} transições, "
              f"{len((r['legenda'] or {}).get('blocos') or [])} blocos de legenda", flush=True)
        fase('pagina')

        print('[3/5] Fotos da camada dos inserts', flush=True)
        cache = p / '.cache' / 'camadas'
        with _cadeado_camadas(p, esperar=True):  # um pré-render rodando: espera ele e usa o que ele fotografou
            camadas, chaves = camada(url, trechos, w, h, cache, tmp)
        fase('fotos')

        print('[4/5] Áudio: a voz, o fundo e o −14 LUFS', flush=True)
        nivel = edicao.get('nivel_voz') or {}
        db_voz = nivel.get('db') if nivel.get('fonte') == fonte['id'] else sons.nivel_da_voz(p / fonte['arquivo'])
        fator = sons.fator_da_voz(db_voz)  # os sons na mesma relação com a voz deste vídeo que nas referências
        eventos = [{**ev, 'ganho': float(ev.get('ganho', sons.INTENSIDADES['baixo'])) * fator} for ev in r['sons'] or []]
        eventos += sons_das_midias(edicao, r.get('planos') or [])
        extras = falas_extras(p, edicao, transcricao, clipes)
        eventos += extras
        a = som(p, edicao, fonte, clipes, transcricao, avisos)
        a['falas'] = sorted([*a['falas'], *((e['t'], e['t'] + e['dur']) for e in extras)])  # o fundo abaixa também nelas
        a['medida'], a['pronta'] = mistura(p, a, clipes, eventos, duracao)
        print(f"      voz {a['limpeza']}, fundo {(edicao.get('audio') or {}).get('fundo') or '—'}, ganho {a['medida']['ganho']:+.1f} dB → "
              f"{a['medida']['i']:.1f} LUFS, pico {a['medida']['pico']} dBFS", flush=True)
        fase('audio')

        print(f'[5/5] Montagem (ffmpeg, por trechos de ~{TRECHO:.0f} s)', flush=True)
        divisoes = [(t['ini'], t['fim'], t.get('divisao') or {'modo': 'metade', 'f': 0.5}) for t in trechos if t['dividida']]
        mascara = p / 'midia' / 'recorte' / f"{fonte['id']}_mascara.mp4"
        lk = look.do_projeto(edicao)
        vinheta = look.mascara_vinheta(w, h, look.VINHETAS[lk['vinheta']], tmp / 'vinheta.png') if look.ativo(lk) else None
        parte = destino.with_name(destino.stem + '.parte.mp4')
        # no proxy, o ator sai do proxy 720p (a mesma linha do tempo do bruto): decodificar e escalar o 4K pesava mais que tudo
        video = p / fonte['arquivo']
        if not final and not horizontal and fonte.get('proxy') and (p / fonte['proxy']).exists():
            video = p / fonte['proxy']  # leve: decodificado no processador (`hwaccel` abaixo)
        # por trechos guardados, no proxy e no final: numa revisão, só o que mudou é montado de novo (e 4 por vez)
        montados = p / '.cache' / 'trechos'
        usados = montar_por_trechos(video, clipes, horizontal, (edicao.get('enquadramento') or {}).get('x', 0.5), w, h, codec, duracao,
                                    trechos, camadas, divisoes, r, lk, vinheta, mascara if mascara.exists() else None, a, parte,
                                    video == p / fonte['arquivo'], montados, tmp)
        parte.replace(destino)
        fase('montagem')
        limpar_camadas(montados, usados, '.mp4')
        if chaves is not None:
            limpar_camadas(cache, chaves)
    except BaseException:
        if pasta_versao:
            shutil.rmtree(pasta_versao, ignore_errors=True)
        else:
            destino.with_name(destino.stem + '.parte.mp4').unlink(missing_ok=True)
        raise
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    fases['total'] = round(time.time() - t_ini, 1)
    duracao_real = inspecionar(destino)['duracao']
    if final:  # ao lado do vídeo, a transcrição dele (a fala que ficou no corte), como as saídas do encaixar
        import encaixar
        md = destino.with_suffix('.md')
        md.write_text(f"# {edicao.get('nome') or slug}\n\n`{destino.name}` · {int(duracao_real // 60)}:{int(duracao_real % 60):02d}\n\n"
                      f"{encaixar.paragrafos([w['texto'] for w in palavras_na_saida(transcricao, clipes)])}\n", encoding='utf-8')
        print(f'Transcrição: {md}')
    if not final:
        gravar_json(pasta_versao / 'edicao.json', edicao)
        for campo in ('palavras', 'planos'):
            if r.get(campo) is None:
                avisos.append(f'A página não entregou __render.{campo}: {campo}.json ficou de fora.')
            else:
                gravar_json(pasta_versao / f'{campo}.json', r[campo])
        gravar_json(pasta_versao / 'info.json', {'versao': versao, 'duracao': duracao_real, 'criado_em': datetime.now().isoformat(timespec='seconds'),
                                                 'fases': fases, 'avisos': avisos})
        final_dir = p / 'versoes' / f'v{versao}'
        pasta_versao.replace(final_dir)
        (p / 'revisoes' / 'trabalhando.json').unlink(missing_ok=True)  # a versão chegou: o app tira o aviso
        destino = final_dir / 'proxy.mp4'
    for x in avisos:
        print(f'Aviso: {x}')
    print(f'Pronto: {destino}')
    print(f'Duração {duracao_real:.2f} s · ' + ' · '.join(f'{k} {v:.1f} s' for k, v in fases.items()))
    return destino


@contextmanager
def _cadeado_camadas(p: Path, esperar: bool):
    """Um só fotografando a camada de um projeto por vez (o pré-render e o render da entrega dividem o cache). Sem
    `esperar`, sai com False se já há outro."""
    arq = p / '.cache' / 'camadas.trava'
    arq.parent.mkdir(parents=True, exist_ok=True)
    with open(arq, 'w') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if esperar else fcntl.LOCK_NB))
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def pre_render(slug: str) -> None:
    """O pré-render: fotografa para o cache (`.cache/camadas/`) os trechos de insert e motion do estado de agora, sem
    áudio, montagem nem versão. Rodado em segundo plano a cada leva de inserts que fica pronta, o render da entrega acha
    a camada quase toda feita (só o que mudou depois é fotografado de novo). Já há um rodando: sai sem fazer nada."""
    t0 = time.time()
    p = pasta(slug)
    edicao = ler(slug)
    if not v1_tocada(edicao):
        raise SystemExit(f'O projeto {slug} ainda não tem cortes.')
    w, h, _ = PROXY
    with _cadeado_camadas(p, esperar=False) as livre:
        if not livre:
            print('Já há um pré-render deste projeto rodando: nada a fazer (o próximo pega o que mudou).')
            return
        tmp = Path(tempfile.mkdtemp(prefix='.prerender-', dir=p))
        srv = servidor.servir(0)
        try:
            copias_do_banco(edicao)
            url = pagina(slug, srv.server_address[1])
            trechos = ler_pagina(url)['trechos'] or []
            camada(url, trechos, w, h, p / '.cache' / 'camadas', tmp)
        finally:
            srv.shutdown()
            shutil.rmtree(tmp, ignore_errors=True)
    print(f'Pré-render de {slug}: {len(trechos)} trechos no cache em {time.time() - t0:.0f} s')


AMOSTRA = 3.0  # s do provador de look


def amostra_look(slug: str, t: float, lk: dict) -> Path:
    """O provador de look da revisão: um trecho de 3 s do ator, tirado do bruto no instante `t` do vídeo final (sem
    inserts nem legenda: o look só vale no ator), recortado em 9:16 como no render e com o LUT, a intensidade e a
    vinheta dados. Guardado em `.cache/look/` pelo look e pelo instante (pedir de novo é instantâneo). Devolve o arquivo."""
    p = pasta(slug)
    edicao = ler(slug)
    clipes = v1_tocada(edicao)
    if not clipes:
        raise SystemExit('O projeto ainda não tem cortes.')
    lk = {**look.PADRAO, **lk}
    if lk.get('lut') and lk['lut'] not in look.NOMES:
        raise SystemExit(f'LUT desconhecido: {lk["lut"]}')
    if lk['vinheta'] not in look.VINHETAS:
        raise SystemExit(f'Vinheta desconhecida: {lk["vinheta"]}')
    if lk.get('nitidez', 'sem') not in look.NITIDEZ:
        raise SystemExit(f'Nitidez desconhecida: {lk["nitidez"]}')
    acc, src = 0.0, clipes[0]['inicio']
    for c in clipes:  # o instante do bruto que toca em t (a amostra segue o bruto dali: para ver a cor, basta)
        d = dur_saida(c)
        if t < acc + d:
            src = c['inicio'] + max(t - acc, 0) * c.get('vel', 1)
            break
        acc += d
    else:
        src = clipes[-1]['inicio']
    chave = hashlib.sha1(json.dumps([round(src, 2), lk], sort_keys=True).encode()).hexdigest()[:16]
    destino = p / '.cache' / 'look' / f'{chave}.mp4'
    if destino.exists():
        return destino
    fonte = next(f for f in edicao['fontes'] if f['papel'] == 'bruto')
    w, h = PROXY[:2]
    horizontal = (fonte.get('largura') or 0) > (fonte.get('altura') or 0)
    x = (edicao.get('enquadramento') or {}).get('x', 0.5)
    recorte = f'crop=w=trunc(ih*9/16/2)*2:h=ih:x=(iw-ow)*{x:.4f},' if horizontal else ''
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        entradas = ['-ss', f'{src:.3f}', '-t', f'{AMOSTRA}', '-i', str(p / fonte['arquivo'])]
        mascara = None
        if look.VINHETAS[lk['vinheta']] > 0:
            entradas += ['-i', str(look.mascara_vinheta(w, h, look.VINHETAS[lk['vinheta']], Path(tmp) / 'vinheta.png'))]
            mascara = 1
        grafo = [f'[0:v]{recorte}scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={FPS}[ator_cru]']
        grafo += look.filtros(lk, 'ator_cru', 'lk', mascara, h) if look.ativo(lk) else ['[ator_cru]null[lk]']
        grafo.append('[lk]format=yuv420p[saida]')
        parcial = destino.with_suffix(f'.{os.getpid()}.tmp.mp4')  # duas amostras iguais pedidas juntas não se atropelam
        ffmpeg(*entradas, '-filter_complex', ';'.join(grafo), '-map', '[saida]', '-an', '-c:v', 'libx264', '-preset', 'veryfast',
               '-crf', '20', '-movflags', '+faststart', str(parcial))
        parcial.replace(destino)
    return destino


def _previa_motion(args: tuple[str, float, str, int]) -> str:
    """Uma prévia (num processo à parte): a página do motion com o tempo nas mãos daqui, fotografada quadro a quadro."""
    from playwright.sync_api import sync_playwright
    mid, dur, destino, porta = args
    mp4 = Path(destino)
    FPS = 30
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chromium')
        try:
            pg = browser.new_page(viewport={'width': 360, 'height': 640}, device_scale_factor=2)
            pg.goto(f'http://127.0.0.1:{porta}/render/motion.html?preset={mid}&formato=vertical&tocar=1', wait_until='load', timeout=60_000)
            pg.wait_for_function('() => !!window.__ir', timeout=30_000)
            # o tempo passa a ser daqui: o loop da galeria fica sem efeito e o vídeo do fundo para
            pg.evaluate("""() => { window.__irDeVerdade = window.__ir; window.__ir = () => Promise.resolve()
                                   for (const v of document.querySelectorAll('#fundo video')) v.pause() }""")
            pg.wait_for_timeout(300)  # as fontes
            tmp = mp4.with_suffix('.parte.mp4')
            proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                                     '-an', '-c:v', 'libx264', '-crf', '24', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                                     '-movflags', '+faststart', str(tmp)], stdin=subprocess.PIPE)
            try:
                for k in range(int(round((dur + 0.6) * FPS))):
                    pg.evaluate("""async (t) => {
                        await window.__irDeVerdade(t)
                        for (const v of document.querySelectorAll('#fundo video'))
                            if (v.duration) { v.currentTime = t % v.duration; await new Promise((r) => v.addEventListener('seeked', r, { once: true })) }
                        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
                    }""", min(k / FPS, dur))
                    proc.stdin.write(pg.screenshot(type='jpeg', quality=90))
            finally:
                proc.stdin.close()
                proc.wait()
            if proc.returncode:
                tmp.unlink(missing_ok=True)
                return f'{mid}: o ffmpeg falhou'
            tmp.replace(mp4)
            return f'{mid}: {dur:.1f} s'
        finally:
            browser.close()


def previas_motions(refazer: bool = False, ids: list[str] | None = None) -> None:
    """Grava a prévia de cada motion, quadro a quadro (30 fps, liso por mais pesado que o motion seja): a página dele com
    o fundo (render/motion.html?tocar=1), com o tempo nas mãos daqui (window.__ir(t) e o vídeo do fundo no mesmo instante),
    fotografada em 720×1280. A duração do motion e mais 0,6 s parado no fim (o loop da galeria). Só refaz um motion se o
    .html dele é mais novo que a prévia."""
    from playwright.sync_api import sync_playwright
    origem = BIBLIOTECA / 'motions' / 'presets'
    destino = BIBLIOTECA / 'motions' / 'previas'
    destino.mkdir(parents=True, exist_ok=True)
    fila = []
    for arq in sorted(origem.glob('*.html')):
        mp4 = destino / f'{arq.stem}.mp4'
        if ids and arq.stem not in ids:
            continue
        if not refazer and mp4.exists() and mp4.stat().st_mtime >= arq.stat().st_mtime:
            continue
        m = re.search(r'<script[^>]*id=["\']preset["\'][^>]*>(.*?)</script>', arq.read_text(encoding='utf-8'), re.S)
        try:
            dur = float(json.loads(m.group(1)).get('duracao') or 4) if m else 4.0
        except (ValueError, TypeError):
            dur = 4.0
        fila.append((arq.stem, min(max(dur, 1.0), 15.0), mp4))
    if not fila:
        print('As prévias estão em dia (use --refazer para refazer).')
        return
    srv = servidor.servir(0)
    porta = srv.server_address[1]
    try:
        # 4 navegadores ao mesmo tempo, um motion em cada (fotografar quadro a quadro é lento: uns 4,5 quadros por segundo)
        with multiprocessing.get_context('spawn').Pool(min(4, len(fila))) as pool:
            for linha in pool.imap_unordered(_previa_motion, [(mid, dur, str(mp4), porta) for mid, dur, mp4 in fila]):
                print(linha, flush=True)
    finally:
        srv.shutdown()
    print(f'{len(fila)} prévia(s) em biblioteca/motions/previas/.')


if __name__ == '__main__':
    if sys.argv[1:2] == ['previas-motions']:
        previas_motions('--refazer' in sys.argv, [a for a in sys.argv[2:] if not a.startswith('--')])
        sys.exit(0)
    if sys.argv[1:2] == ['amostra-look']:
        _, _, slug, t, lut, intensidade, vinheta, *nit = sys.argv
        print(amostra_look(slug, float(t), {'lut': None if lut == '-' else lut, 'intensidade': float(intensidade), 'vinheta': vinheta,
                                            'nitidez': nit[0] if nit else 'sem'}).relative_to(RAIZ))
        sys.exit(0)
    args = [a for a in sys.argv[1:] if a not in ('--final', '--camadas')]
    if len(args) != 1:
        raise SystemExit(__doc__)
    if '--camadas' in sys.argv[1:]:
        pre_render(args[0])
    else:
        render(args[0], final='--final' in sys.argv[1:])
