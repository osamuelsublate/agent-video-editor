"""A montagem por camadas (do 18: backend/tests/test_exportacao.py, SPEC §13): o comando do ffmpeg montado pelas funções
de cada camada é exatamente o congelado no 18 (`dados/exportacao_comandos.json`, copiado de lá): o porte não mudou nada,
e os ganchos sem nada a desenhar (transições, legenda) não mudam o comando."""
import json
import runpy
import sys
from pathlib import Path

import pytest

import base
from montagem import exportacao, render_quadros, sons

ESPERADO = Path(__file__).parent / 'dados' / 'exportacao_comandos.json'
CODECS = ('DECODIFICA', 'H264_PROXY', 'HEVC_FINAL', 'PRORES_ALFA')


@pytest.fixture
def constantes_de(monkeypatch):
    """Põe em `exportacao` as constantes de codec de uma plataforma (o `base.py` lido como se rodasse nela), para os
    testes valerem em qualquer máquina. Devolve todas as constantes dela."""
    def trocar(plataforma: str) -> dict:
        with monkeypatch.context() as m:
            m.setattr(sys, 'platform', plataforma)
            g = runpy.run_path(base.__file__)
        for nome in CODECS:
            monkeypatch.setattr(exportacao, nome, g[nome])
        return g
    return trocar


def casos(raiz: Path) -> dict[str, tuple[tuple, dict]]:
    """Entradas variadas de `comando_final`: vertical e horizontal, telas divididas (metade e "insert atrás"), máscara,
    clipes de inserts e sons (repetidos, com trecho, duração e velocidade)."""
    bruto, mascara, saida = raiz / 'midia' / 'bruto.mov', raiz / 'midia' / 'mascara.mp4', raiz / 'exports' / 'final.parte.mp4'
    clipes = [{'inicio': 0.2, 'fim': 1.35}, {'inicio': 2.1, 'fim': 4.0}, {'inicio': 5.25, 'fim': 7.5}]
    duracao = sum(c['fim'] - c['inicio'] for c in clipes)
    camadas = [(raiz / 'camadas' / '000.mov', 0.5), (raiz / 'camadas' / '001.mov', 2.25)]
    eventos = [{'som': 'clique', 't': 0.5, 'ganho': 0.25, 'desde': 0}, {'som': 'clique', 't': 2.0, 'ganho': 0.5, 'desde': 0},
               {'som': 'ding', 't': 1.2, 'ganho': 0.3, 'desde': 0.1, 'dur': 0.4, 'vel': 1.25}, {'som': 'nao-existe', 't': 1}]
    metade = [(0.5, 1.4, {'modo': 'metade', 'f': 0.5}), (2.25, 3.0, {'modo': 'metade', 'f': 0.56})]
    atras = [(3.1, 4.2, {'modo': 'atras', 'f': 0.5})]
    return {
        'vertical_simples': ((bruto, clipes, False, 0.5, 1080, 1920, 24, [], [], 'hevc', duracao, saida), {}),
        'horizontal_com_inserts': ((bruto, clipes, True, 0.37, 2160, 3840, 30, metade, camadas, 'h264', duracao, saida), {}),
        'mascara_sem_atras': ((bruto, clipes, False, 0.5, 720, 1280, 60, metade, camadas[:1], 'hevc', duracao, saida), {'mascara': mascara}),
        'atras_mascara_e_sons': ((bruto, clipes, False, 0.5, 1080, 1920, 24, metade + atras, camadas, 'hevc', duracao, saida),
                                 {'mascara': mascara, 'eventos_som': eventos}),
        'atras_sem_mascara': ((bruto, clipes, False, 0.5, 1080, 1920, 24, atras, [], 'h264', duracao, saida), {'eventos_som': eventos[:1]}),
    }


def biblioteca_falsa(raiz: Path) -> None:
    """Só a existência dos arquivos importa para montar o comando."""
    raiz.mkdir(parents=True, exist_ok=True)
    for sid in ('clique', 'ding'):
        (raiz / f'{sid}.m4a').write_bytes(b'')


def comandos(comando_final, raiz: Path) -> dict[str, list[str]]:
    """Os comandos de cada caso, com a pasta temporária trocada por `<raiz>` (para comparar entre execuções)."""
    return {nome: [x.replace(str(raiz), '<raiz>') for x in comando_final(*args, **kw)] for nome, (args, kw) in casos(raiz).items()}


def test_comando_por_camadas_e_identico_ao_de_antes(tmp_path, constantes_de):
    """Congelado com os codecs do Mac."""
    constantes_de('darwin')
    biblioteca_falsa(sons.RAIZ)
    esperado = json.loads(ESPERADO.read_text())
    atual = comandos(exportacao.comando_final, tmp_path)
    assert set(atual) == set(esperado)
    for nome in esperado:
        assert atual[nome] == esperado[nome], nome


@pytest.mark.parametrize('transicoes, legenda', [([{'t': 1.0, 'id': 'x'}], {'blocos': [{'texto': 'oi'}]}), ([], None)])
def test_ganchos_sem_nada_a_desenhar_nao_mudam_o_comando(tmp_path, transicoes, legenda):
    """Uma transição sem efeito conhecido e uma legenda sem `arquivo` (`_legenda` só desenha o ASS gravado por
    `legenda.escrever`; os blocos crus não bastam) deixam o comando como sem elas. O que cada camada desenha está nos
    testes dela (test_transicoes, test_legenda)."""
    biblioteca_falsa(sons.RAIZ)
    for args, kw in casos(tmp_path).values():
        assert exportacao.comando_final(*args, **kw, transicoes=transicoes, legenda=legenda) == exportacao.comando_final(*args, **kw)


def test_cada_camada_na_sua_funcao(tmp_path):
    """A ordem do contrato: inserts sobre a base do ator, a pós-montagem termina no formato de saída, o áudio sem sons só
    renomeia a voz."""
    ent, f = exportacao._inserts([(tmp_path / 'a.mov', 1.5)], 2, 'base', 'topo_in')
    assert ent == ['-i', str(tmp_path / 'a.mov')] and f[-1] == '[o0]null[topo_in]' and f[0].startswith('[2:v]setpts')
    assert exportacao._inserts([], 1, 'base', 'topo_in') == ([], ['[base]null[topo_in]'])
    assert exportacao._pos_montagem(None, None, 'topo', 'v', 180, 320, 3) == ([], ['[topo]format=yuv420p[v]'])
    assert exportacao._audio(None, 3, 'ac', 'am', [{'inicio': 0, 'fim': 1}], 1.0) == ([], ['[ac]anull[am]'])


def test_proxy_sem_chip_e_audio_pronto(tmp_path, constantes_de):
    """O proxy decodifica no processador (`hwaccel=False` só tira o `-hwaccel`) e o áudio já misturado pelo render
    (`pronta`, do cache) entra como está, sem refazer a mistura."""
    constantes_de('darwin')
    biblioteca_falsa(sons.RAIZ)
    args, kw = casos(tmp_path)['vertical_simples']
    com, sem = exportacao.comando_final(*args, **kw), exportacao.comando_final(*args, **kw, hwaccel=False)
    assert [x for x in com if x not in ('-hwaccel', 'videotoolbox')] == sem
    wav = tmp_path / 'audio.wav'
    assert exportacao._audio([], 3, 'ac', 'am', [{'inicio': 0, 'fim': 1}], 1.0, {'pronta': wav}) == (
        ['-i', str(wav)], ['[ac]anullsink', '[3:a]anull[am]'])


def test_comandos_do_linux(tmp_path, constantes_de):
    """No Linux: NVENC com -cq (nunca o -q:v do VideoToolbox), CUDA e o ProRes por software com alfa."""
    g = constantes_de('linux')
    biblioteca_falsa(sons.RAIZ)
    atual = comandos(exportacao.comando_final, tmp_path)
    for cmd in atual.values():
        assert '-q:v' not in cmd and not any('videotoolbox' in x for x in cmd)
        assert cmd[cmd.index('-hwaccel') + 1] == 'cuda'
    hevc, h264 = atual['vertical_simples'], atual['atras_sem_mascara']
    i = hevc.index('-c:v')
    assert hevc[i:i + 14] == ['-c:v', 'hevc_nvenc', *g['NVENC'], '-level', '5.1', '-cq', str(g['CQ_FINAL']), '-tag:v', 'hvc1']
    i = h264.index('-c:v')
    assert h264[i:i + 10] == ['-c:v', 'h264_nvenc', *g['NVENC'], '-cq', str(g['CQ_PROXY'])] and 'hvc1' not in h264
    assert g['H264_PLAYER'] == ['-c:v', 'h264_nvenc', '-forced-idr', '1', '-pix_fmt', 'yuv420p']
    assert g['HEVC_ENQUADRAMENTO'] == ['-c:v', 'hevc_nvenc', *g['NVENC'], '-level', '5.1', '-cq', str(g['CQ_ENQUADRAMENTO']), '-tag:v', 'hvc1']
    assert g['PRORES_ALFA'] == ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le']


def test_constantes_do_mac(constantes_de):
    """Os codecs do Mac, como sempre foram (os dos scripts fora do `comando_final`, que o congelado não cobre)."""
    g = constantes_de('darwin')
    assert g['DECODIFICA'] == ['-hwaccel', 'videotoolbox'] and g['H264_PLAYER'] == ['-c:v', 'h264_videotoolbox']
    assert g['HEVC_ENQUADRAMENTO'] == ['-c:v', 'hevc_videotoolbox', '-q:v', '80', '-tag:v', 'hvc1']
    assert g['HEVC_FINAL'] == ['-c:v', 'hevc_videotoolbox', '-q:v', '65', '-tag:v', 'hvc1']
    assert g['PRORES_ALFA'] == ['-c:v', 'prores_videotoolbox', '-profile:v', '4444']


def test_trabalhador_usa_o_prores_do_base():
    """O trabalhador do render (`render_quadros`, que não importa `exportacao`) grava com a mesma constante."""
    assert render_quadros.PRORES_ALFA is base.PRORES_ALFA


def test_curva_do_video_so_no_mac():
    """A curva da Apple clareia o vídeo só no Chrome do Mac; no Linux, a foto do navegador não muda o cinza."""
    assert exportacao.CURVA_VIDEO == (0.9 if base.MAC else 1.0)
