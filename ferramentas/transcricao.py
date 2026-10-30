"""A transcrição e o áudio que ela usa (do 18: midia.extrair_audio, midia.silencios).

Importado pelo preparar.py e pelo calibragem.py. Só biblioteca padrão no topo (o httpx, de quem chama, só dentro do
`_pedir`): o calibragem é importado pelo servidor, que roda sem dependências.
"""
import base64
import io
import re
import subprocess
import sys
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import env, ffmpeg  # noqa: E402

URL = 'https://openrouter.ai/api/v1/audio/transcriptions'
MODELO = 'elevenlabs/scribe-v2'
BLOCO = 480  # s por pedido: 8 min de WAV mono 16 kHz são cerca de 20 MB em base64 (o limite é 25 MB)
JANELA = 120  # s: o silêncio do corte é procurado nos últimos 2 min do bloco
SOBRA = 10  # s que dois blocos ouvem em comum quando não há silêncio onde cortar
TOLERANCIA = 1  # s: a mesma palavra nos dois blocos não fica mais longe que isso
PARALELO = 4
ESPERAS = (2, 4, 8, 16)  # s entre as tentativas
SEM_CREDITO = 'Sem crédito no OpenRouter. Adicione créditos e tente de novo.'  # a frase do gemini.py; a Calibragem a reconhece


def extrair_audio(video: Path, destino: Path) -> None:
    """Do 18: midia.extrair_audio. WAV mono 16 kHz, preservando o atraso inicial do áudio (first_pts=0)."""
    ffmpeg('-i', str(video), '-vn', '-af', 'aresample=16000:async=1:first_pts=0', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(destino))


def silencios(audio: Path, db: float = -35, minimo: float = 0.3) -> list[dict]:
    """Do 18: midia.silencios. Silêncios reais (silencedetect); o que vai até o fim do arquivo não tem fim e fica de fora."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(audio), '-af', f'silencedetect=n={db}dB:d={minimo}',
                        '-f', 'null', '-'], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-300:])
    inicios = [max(float(x), 0) for x in re.findall(r'silence_start: (-?[\d.]+)', r.stderr)]
    fins = re.findall(r'silence_end: ([\d.]+) \| silence_duration: ([\d.]+)', r.stderr)
    return [{'inicio': round(s, 3), 'fim': float(e), 'dur': float(d)} for s, (e, d) in zip(inicios, fins)]


def _blocos(duracao: float, pausas: list[dict]) -> list[tuple[float, float]]:
    """Os trechos (início, fim) de cada pedido. Corta no maior silêncio dos últimos minutos do bloco; sem silêncio, no limite,
    e o bloco seguinte recomeça SOBRA segundos antes (os dois ouvem a mesma fala, e a emenda escolhe a palavra: _emendar)."""
    blocos, inicio = [], 0.0
    while duracao - inicio > BLOCO:
        limite = inicio + BLOCO
        meios = [(p['dur'], (p['inicio'] + p['fim']) / 2) for p in pausas]
        meios = [m for m in meios if limite - JANELA <= m[1] <= limite]
        fim = max(meios)[1] if meios else limite
        blocos.append((inicio, fim))
        inicio = fim if meios else limite - SOBRA
    blocos.append((inicio, duracao))
    return blocos


def _pedir(wav: bytes, chave: str) -> dict:
    """Um pedido ao OpenRouter, com novas tentativas em 429, 502 e erro de rede. Sem crédito (402) não adianta repetir."""
    import httpx

    corpo = {'model': MODELO, 'input_audio': {'data': base64.b64encode(wav).decode(), 'format': 'wav'},
             'response_format': 'verbose_json', 'timestamp_granularities': ['word'], 'language': 'pt',
             'provider': {'options': {'elevenlabs': {'tag_audio_events': False, 'diarize': False}}}}
    for espera in (*ESPERAS, None):
        try:
            r = httpx.post(URL, headers={'Authorization': f'Bearer {chave}'}, json=corpo, timeout=300)
        except httpx.HTTPError as e:
            falha = f'sem resposta do OpenRouter: {e.__class__.__name__}'
        else:
            try:
                dados = r.json()
            except ValueError:
                dados = None
            erro = dados.get('error') if isinstance(dados, dict) else None
            if r.status_code < 400 and not erro:
                if not isinstance(dados, dict):
                    raise RuntimeError('OpenRouter devolveu uma resposta fora do formato (não é JSON)')
                return dados
            # o erro pode vir com status 200, no corpo; a frase dele, se houver, em vez do JSON inteiro
            info = erro if isinstance(erro, dict) else {}
            codigo = r.status_code if r.status_code >= 400 else info.get('code') or r.status_code
            if codigo == 402:
                raise RuntimeError(SEM_CREDITO)
            falha = f'OpenRouter respondeu {codigo}: ' + str(info.get('message') or erro or r.text)[:200].replace(chave, '***')
            if codigo not in (429, 502):
                raise RuntimeError(falha)
            if espera is not None:
                try:  # o 429 pode dizer quanto esperar
                    espera = max(espera, min(float(r.headers.get('retry-after', 0)), 60))
                except ValueError:
                    pass
        if espera is None:
            raise RuntimeError(falha)
        time.sleep(espera)


def _sem_eventos(palavras: list[dict]) -> list[dict]:
    """Tira os eventos sonoros que escaparem de tag_audio_events: "(risos)", "[música]" ou "(risos altos)", em várias palavras.
    Sem o fechamento por perto, ou com número dentro ("(2023)"), é fala e fica."""
    saida, i = [], 0
    while i < len(palavras):
        fim = None
        if palavras[i]['word'].strip()[:1] in ('(', '['):
            fim = next((j for j in range(i, min(i + 5, len(palavras))) if re.search(r'[)\]]\W*$', palavras[j]['word'].strip())), None)
            if fim is not None and re.search(r'\d', ' '.join(w['word'] for w in palavras[i:fim + 1])):
                fim = None
        if fim is None:
            saida.append(palavras[i])
            i += 1
        else:
            i = fim + 1
    return saida


def _palavras(dados: dict, deslocamento: float) -> list[dict]:
    """A resposta de um bloco vira as palavras no tempo do áudio inteiro. Resposta sem as palavras é erro, nunca fala a menos."""
    palavras, texto = dados.get('words'), dados.get('text') or ''
    if not isinstance(palavras, list) or (not palavras and re.sub(r'\([^)]*\)|\[[^\]]*\]', '', texto).strip()):
        raise RuntimeError('OpenRouter devolveu uma resposta sem as palavras e seus tempos')
    try:
        return [{'texto': w['word'].strip(), 'inicio': round(deslocamento + float(w['start']), 3), 'fim': round(deslocamento + float(w['end']), 3)}
                for w in _sem_eventos(palavras) if w['word'].strip()]
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise RuntimeError(f'OpenRouter devolveu uma palavra fora do formato ({e.__class__.__name__})') from e


def _emendar(a: list[dict], b: list[dict], inicio: float, fim: float) -> list[dict]:
    """Junta dois blocos que ouviram o mesmo trecho [inicio, fim]. As bordas podem ter palavra partida, e o meio não: a emenda é
    a palavra igual nos dois (texto e tempo) mais perto do meio; fica o `a` até ela e o `b` dali em diante, sem perder nem repetir.
    Se nenhuma coincide (os dois ouviram diferente), o tempo decide cada palavra pelo seu meio."""
    def chave(w):
        return re.sub(r'\W', '', w['texto']).casefold()
    za = [i for i, w in enumerate(a) if w['inicio'] >= inicio]
    zb = [i for i, w in enumerate(b) if w['inicio'] < fim]
    meio = (inicio + fim) / 2
    pares = []
    for bloco in SequenceMatcher(None, [chave(a[i]) for i in za], [chave(b[i]) for i in zb], autojunk=False).get_matching_blocks():
        for k in range(bloco.size):
            i, j = za[bloco.a + k], zb[bloco.b + k]
            if abs(a[i]['inicio'] - b[j]['inicio']) <= TOLERANCIA:
                pares.append((abs(a[i]['inicio'] - meio), i, j))
    if pares:
        _, i, j = min(pares)
        return a[:i] + b[j:]
    return [w for w in a if (w['inicio'] + w['fim']) / 2 < meio] + [w for w in b if (w['inicio'] + w['fim']) / 2 >= meio]


def transcrever(audio: Path) -> list[dict]:
    """ElevenLabs Scribe v2 pelo OpenRouter (manda o áudio da voz a um terceiro), em português, com o tempo de cada palavra no
    áudio inteiro; nada é limpo (repetições e retomadas ficam: são o que os cortes decidem). Áudio longo vai em blocos, em
    paralelo; a falha de um bloco falha a transcrição inteira."""
    chave = env('OPENROUTER_API_KEY')
    with wave.open(str(audio), 'rb') as w:
        taxa, quadros = w.getframerate(), w.getnframes()
    if not quadros:
        return []
    duracao = quadros / taxa
    blocos = _blocos(duracao, silencios(audio) if duracao > BLOCO else [])

    def um_bloco(trecho: tuple[float, float]) -> list[dict]:
        a, b = round(trecho[0] * taxa), round(trecho[1] * taxa)
        saida = io.BytesIO()
        with wave.open(str(audio), 'rb') as w, wave.open(saida, 'wb') as s:
            s.setparams(w.getparams())
            w.setpos(a)
            s.writeframes(w.readframes(b - a))
        return _palavras(_pedir(saida.getvalue(), chave), a / taxa)

    ex = ThreadPoolExecutor(PARALELO)
    try:
        tarefas = [ex.submit(um_bloco, b) for b in blocos]
        for t in as_completed(tarefas):
            t.result()  # o primeiro erro para tudo: o que ainda não começou nem é pedido
    finally:
        ex.shutdown(wait=True, cancel_futures=True)

    palavras = tarefas[0].result()  # a ordem é a dos blocos, não a das respostas
    for i in range(1, len(blocos)):
        inicio, fim = blocos[i][0], blocos[i - 1][1]
        palavras = _emendar(palavras, tarefas[i].result(), inicio, fim) if inicio < fim else palavras + tarefas[i].result()
    return [{'id': f'w{i:05d}', **w} for i, w in enumerate(palavras)]  # os IDs só depois de juntar
