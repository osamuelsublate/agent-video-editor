"""A transcrição pelo OpenRouter, com a API simulada: `httpx.post` falso, que lê o WAV do pedido.

O áudio de teste é um relógio: cada amostra guarda o segundo a que pertence. Assim o falso sabe que trecho recebeu, e o
deslocamento de cada bloco é conferido de verdade. A "fala" é uma palavra por segundo, w<segundo>."""
import base64
import io
import json
import struct
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

import httpx
import pytest

import transcricao
from transcricao import BLOCO, SEM_CREDITO, SOBRA, transcrever

TAXA = 100  # o bastante para o relógio; os blocos são por tempo, não por bytes


def _wav(caminho, segundos: int):
    with wave.open(str(caminho), 'wb') as w:
        w.setparams((1, 2, TAXA, 0, 'NONE', 'not compressed'))
        w.writeframes(b''.join(struct.pack('<h', s) * TAXA for s in range(segundos)))
    return caminho


def _trecho(pedido: dict) -> tuple[int, int]:
    """O (segundo inicial, duração em amostras) do WAV que veio no pedido."""
    with wave.open(io.BytesIO(base64.b64decode(pedido['input_audio']['data'])), 'rb') as w:
        quadros = w.readframes(w.getnframes())
        return struct.unpack('<h', quadros[:2])[0], len(quadros) // 2


class Resposta:
    def __init__(self, status=200, corpo=None, headers=None):
        self.status_code, self.corpo, self.headers = status, corpo, headers or {}
        self.text = json.dumps(corpo)

    def json(self):
        if self.corpo is None:
            raise ValueError
        return self.corpo


def _fala(pedido):
    """A fala do trecho recebido: tempos relativos ao bloco, como a API devolve."""
    a, n = _trecho(pedido)
    return Resposta(corpo={'text': 'x', 'words': [{'word': f'w{s} ', 'start': s - a + 0.25, 'end': s - a + 0.75, 'confidence': 0.9}
                                                  for s in range(a, a + n // TAXA)]})


@pytest.fixture
def api(monkeypatch):
    """Instala o httpx.post falso; devolve a lista de pedidos. `api.responder` troca o que ele faz."""
    class Api(list):
        responder = staticmethod(_fala)
    falsa = Api()
    trava = threading.Lock()

    def post(url, headers, json, timeout):
        with trava:
            falsa.append(json)
            falsa.url, falsa.headers = url, headers
        return falsa.responder(json)
    monkeypatch.setattr(httpx, 'post', post)
    monkeypatch.setattr(transcricao, 'env', lambda nome: 'sk-teste-segredo')
    monkeypatch.setattr(transcricao, 'silencios', lambda audio: [])
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    return falsa


def _textos(palavras):
    return [p['texto'] for p in palavras]


def test_formato_da_resposta(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(corpo={'text': 'rápido: é', 'words': [
        {'word': ' rápido: ', 'start': 39.98, 'end': 40.3456, 'confidence': 0.99}, {'word': '  ', 'start': 41, 'end': 41.1},
        {'word': 'é', 'start': 41.2, 'end': 41.5}]}))
    assert transcrever(_wav(tmp_path / 'a.wav', 60)) == [
        {'id': 'w00000', 'texto': 'rápido:', 'inicio': 39.98, 'fim': 40.346},
        {'id': 'w00001', 'texto': 'é', 'inicio': 41.2, 'fim': 41.5}]
    pedido = api[0]
    assert len(api) == 1 and _trecho(pedido) == (0, 60 * TAXA)  # áudio curto: um pedido só, sem cortar
    assert api.url == 'https://openrouter.ai/api/v1/audio/transcriptions'
    assert api.headers['Authorization'] == 'Bearer sk-teste-segredo'
    assert pedido['model'] == 'elevenlabs/scribe-v2' and pedido['language'] == 'pt' and pedido['input_audio']['format'] == 'wav'
    assert pedido['timestamp_granularities'] == ['word'] and pedido['response_format'] == 'verbose_json'
    assert pedido['provider']['options']['elevenlabs'] == {'tag_audio_events': False, 'diarize': False}


def test_repeticoes_ficam(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(corpo={'text': 'a a a', 'words': [
        {'word': 'gastando', 'start': 1, 'end': 2}, {'word': 'gastando', 'start': 2, 'end': 3}, {'word': 'é', 'start': 3, 'end': 4}]}))
    assert _textos(transcrever(_wav(tmp_path / 'a.wav', 10))) == ['gastando', 'gastando', 'é']


def test_audio_sem_fala(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(corpo={'text': '', 'words': []}))
    assert transcrever(_wav(tmp_path / 'a.wav', 10)) == []


def test_audio_vazio_nem_pede(api, tmp_path):
    assert transcrever(_wav(tmp_path / 'a.wav', 0)) == [] and not api


def test_silencio_no_corte_desloca_o_tempo_e_numera_em_sequencia(api, tmp_path, monkeypatch):
    monkeypatch.setattr(transcricao, 'silencios', lambda a: [
        {'inicio': 100, 'fim': 110, 'dur': 10},  # cedo demais: fora da janela
        {'inicio': 400.0, 'fim': 402.0, 'dur': 2}, {'inicio': 450.0, 'fim': 450.5, 'dur': 0.5},  # o maior da janela ganha
        {'inicio': 500, 'fim': 501, 'dur': 1}])  # passa do limite
    palavras = transcrever(_wav(tmp_path / 'a.wav', 600))
    assert sorted(_trecho(p)[0] for p in api) == [0, 401]
    assert [p['id'] for p in palavras] == [f'w{i:05d}' for i in range(len(palavras))]
    assert all(p['inicio'] == int(p['texto'][1:]) + 0.25 for p in palavras)  # o tempo no áudio inteiro
    assert _textos(palavras) == [f'w{s}' for s in range(600)]


def test_sem_silencio_corta_no_limite_sem_perder_nem_repetir(api, tmp_path):
    n = BLOCO * 2 + 100
    palavras = transcrever(_wav(tmp_path / 'a.wav', n))
    assert sorted(_trecho(p)[0] for p in api) == [0, BLOCO - SOBRA, 2 * (BLOCO - SOBRA)]
    assert max(_trecho(p)[1] for p in api) <= BLOCO * TAXA  # nenhum pedido passa do limite
    assert _textos(palavras) == [f'w{s}' for s in range(n)]
    assert [p['id'] for p in palavras] == [f'w{i:05d}' for i in range(n)]


def test_emenda_com_palavra_partida_na_borda(api, tmp_path):
    """Os dois blocos erram na borda do que ouviram; a emenda no meio do trecho comum não aproveita o erro."""
    def responder(p):
        r = _fala(p)
        palavras = r.corpo['words']
        if _trecho(p)[0] == 0:
            palavras[-1]['word'] = 'partida-no-fim'
        else:
            palavras[0]['word'] = 'partida-no-inicio'
        return r
    api.responder = staticmethod(responder)
    n = BLOCO + 60
    assert _textos(transcrever(_wav(tmp_path / 'a.wav', n))) == [f'w{s}' for s in range(n)]


def test_emenda_sem_palavra_igual_decide_pelo_tempo(api, tmp_path):
    """Sem coincidência no trecho comum, cada um fica com a sua metade: nada some nem repete."""
    def responder(p):
        a, n = _trecho(p)
        return Resposta(corpo={'text': 'x', 'words': [{'word': f'{"a" if a == 0 else "b"}{s}', 'start': s - a + .25, 'end': s - a + .75}
                                                      for s in range(a, a + n // TAXA)]})
    api.responder = staticmethod(responder)
    n = BLOCO + 60
    palavras = transcrever(_wav(tmp_path / 'a.wav', n))
    assert [int(p['texto'][1:]) for p in palavras] == list(range(n))
    meio = BLOCO - SOBRA / 2
    assert all(p['texto'][0] == ('a' if int(p['texto'][1:]) + .5 < meio else 'b') for p in palavras)


def test_ordem_com_respostas_fora_de_ordem(api, tmp_path):
    """O primeiro bloco só responde depois que o último respondeu."""
    ultimo = threading.Event()
    simultaneos, trava = [0, 0], threading.Lock()

    def responder(p):
        with trava:
            simultaneos[0] += 1
            simultaneos[1] = max(simultaneos)
        a = _trecho(p)[0]
        if a == 0:
            assert ultimo.wait(5)
        elif a == 3 * (BLOCO - SOBRA):
            ultimo.set()
        with trava:
            simultaneos[0] -= 1
        return _fala(p)
    api.responder = staticmethod(responder)
    n = 3 * (BLOCO - SOBRA) + 100
    assert _textos(transcrever(_wav(tmp_path / 'a.wav', n))) == [f'w{s}' for s in range(n)]
    assert 1 < simultaneos[1] <= 4


def test_429_e_502_repetem_com_espera(api, tmp_path, monkeypatch):
    esperas = []
    monkeypatch.setattr(time, 'sleep', esperas.append)
    respostas = iter([Resposta(429, {'error': {'code': 429, 'message': 'devagar'}}, {'retry-after': '7'}),
                      Resposta(502, {'error': {'code': 502, 'message': 'provedor'}})])
    api.responder = staticmethod(lambda p: next(respostas, None) or _fala(p))
    assert len(transcrever(_wav(tmp_path / 'a.wav', 5))) == 5
    assert len(api) == 3 and esperas == [7, 4]


def test_erro_de_rede_repete(api, tmp_path):
    falhas = iter([httpx.ConnectError('caiu')])

    def responder(p):
        for e in falhas:
            raise e
        return _fala(p)
    api.responder = staticmethod(responder)
    assert len(transcrever(_wav(tmp_path / 'a.wav', 5))) == 5 and len(api) == 2


def test_429_insistente_desiste_citando_openrouter(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(429, {'error': {'code': 429, 'message': 'devagar'}}))
    with pytest.raises(RuntimeError, match='OpenRouter respondeu 429: devagar'):
        transcrever(_wav(tmp_path / 'a.wav', 5))
    assert len(api) == 5


def test_rede_insistente_desiste_citando_openrouter(api, tmp_path):
    def responder(p):
        raise httpx.ReadTimeout('demorou')
    api.responder = staticmethod(responder)
    with pytest.raises(RuntimeError, match='sem resposta do OpenRouter: ReadTimeout'):
        transcrever(_wav(tmp_path / 'a.wav', 5))


def test_402_vira_sem_credito_sem_repetir(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(402, {'error': {'code': 402, 'message': 'Insufficient credits'}}))
    with pytest.raises(RuntimeError) as e:
        transcrever(_wav(tmp_path / 'a.wav', 5))
    assert str(e.value) == SEM_CREDITO and len(api) == 1


def test_402_no_corpo_de_um_200(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(200, {'error': {'code': 402, 'message': 'Insufficient credits'}}))
    with pytest.raises(RuntimeError) as e:
        transcrever(_wav(tmp_path / 'a.wav', 5))
    assert str(e.value) == SEM_CREDITO


def test_401_nao_repete_e_nao_vaza_a_chave(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(401, {'error': {'code': 401, 'message': 'chave sk-teste-segredo inválida'}}))
    with pytest.raises(RuntimeError) as e:
        transcrever(_wav(tmp_path / 'a.wav', 5))
    assert 'OpenRouter respondeu 401' in str(e.value) and 'sk-teste-segredo' not in str(e.value) and len(api) == 1


def test_bloco_que_falha_falha_tudo(api, tmp_path):
    def responder(p):
        if _trecho(p)[0] == BLOCO - SOBRA:
            return Resposta(400, {'error': {'code': 400, 'message': 'recusado'}})
        return _fala(p)
    api.responder = staticmethod(responder)
    with pytest.raises(RuntimeError, match='OpenRouter respondeu 400: recusado'):
        transcrever(_wav(tmp_path / 'a.wav', BLOCO * 3))


@pytest.mark.parametrize('corpo', [{'text': 'tinha fala', 'words': []}, {'text': 'tinha fala'}, {},
                                   {'text': 'x', 'words': [{'word': 'sem tempo'}]}, {'text': 'x', 'words': [{'word': 'a', 'start': None, 'end': 1}]}])
def test_resposta_sem_palavras_e_erro_nao_buraco(api, tmp_path, corpo):
    api.responder = staticmethod(lambda p: Resposta(corpo=corpo))
    with pytest.raises(RuntimeError, match='OpenRouter'):
        transcrever(_wav(tmp_path / 'a.wav', 5))


def test_resposta_que_nao_e_json(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(200, None))
    with pytest.raises(RuntimeError, match='OpenRouter'):
        transcrever(_wav(tmp_path / 'a.wav', 5))


@pytest.mark.parametrize('entra, sai', [
    (['oi', '(risos)', 'tudo'], ['oi', 'tudo']),
    (['oi', '[música]', 'tudo'], ['oi', 'tudo']),
    (['oi', '(risos).', 'tudo'], ['oi', 'tudo']),
    (['oi', '(risos', 'altos)', 'tudo'], ['oi', 'tudo']),
    (['oi', '(2023)', 'tudo'], ['oi', '(2023)', 'tudo']),  # número é fala
    (['oi', '(aberto', 'a', 'b', 'c', 'd', 'e', 'f)', 'g'], ['oi', '(aberto', 'a', 'b', 'c', 'd', 'e', 'f)', 'g']),  # longe demais
    (['palavra(s)', 'fica'], ['palavra(s)', 'fica']),
])
def test_eventos_saem_e_fala_fica(api, tmp_path, entra, sai):
    api.responder = staticmethod(lambda p: Resposta(corpo={'text': ' '.join(entra), 'words': [
        {'word': w, 'start': i, 'end': i + .5} for i, w in enumerate(entra)]}))
    palavras = transcrever(_wav(tmp_path / 'a.wav', 10))
    assert _textos(palavras) == sai and [p['id'] for p in palavras] == [f'w{i:05d}' for i in range(len(sai))]


def test_so_evento_sem_palavras_e_audio_sem_fala(api, tmp_path):
    api.responder = staticmethod(lambda p: Resposta(corpo={'text': '(risos)', 'words': []}))
    assert transcrever(_wav(tmp_path / 'a.wav', 5)) == []


def test_calibragem_mostra_sem_credito_quando_a_transcricao_falha(monkeypatch, tmp_path):
    """O passo de transcrição, com 402 na API falsa, deixa na referência a mesma mensagem da análise."""
    import calibragem

    guardado = {'status': 'na_fila', 'nome': 'x', 'analise': {}}

    def atualizar(id, f):
        f(guardado)
        return guardado
    monkeypatch.setattr(calibragem.signal, 'signal', lambda *a: None)  # o analisar troca o SIGTERM do processo
    monkeypatch.setattr(calibragem, 'atualizar', atualizar)
    monkeypatch.setattr(calibragem, 'pasta', lambda id: tmp_path)
    monkeypatch.setattr(calibragem, '_trava', lambda nome: threading.Lock())
    monkeypatch.setattr(calibragem, 'ler', lambda id: guardado)
    monkeypatch.setattr(calibragem, '_passo', lambda *a, **k: None)
    monkeypatch.setattr(calibragem, 'PASSOS', ['transcricao'])
    monkeypatch.setattr(calibragem, '_gravar', lambda *a, **k: None)
    monkeypatch.setattr(calibragem, '_video', lambda base: base / 'v.mp4')
    monkeypatch.setattr(transcricao, 'extrair_audio', lambda v, d: _wav(d, 5))
    monkeypatch.setattr(transcricao, 'silencios', lambda a: [])
    monkeypatch.setattr(transcricao, 'env', lambda nome: 'sk-teste-segredo')
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: Resposta(402, {'error': {'code': 402, 'message': 'Insufficient credits'}}))

    assert calibragem.analisar('r1') is False
    assert guardado['status'] == 'erro' and guardado['erro'] == calibragem.SEM_CREDITO


def test_servidor_importa_sem_httpx():
    """O servidor roda sem dependências: o módulo só pode pedir o httpx dentro das funções."""
    codigo = "import sys; sys.modules['httpx'] = None; import transcricao; print('ok')"
    r = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, cwd=Path(transcricao.__file__).parent)
    assert r.stdout.strip() == 'ok', r.stderr
