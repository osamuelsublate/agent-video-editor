"""A legenda no render (do 18: backend/app/legenda.py; SPEC §8.10, docs/legenda.md): o ASS que o libass desenha por cima
de tudo, no fim da montagem. Os blocos (quais palavras, o texto, quando e onde) são montados pela página de render (a
mesma conta da prévia) e chegam em `__render.legenda`; o estilo é o medido nas referências, branca com sombra difusa,
centralizada, na Inter Bold do repositório (a mesma no Mac e no Linux; nada instalado no sistema)."""
from functools import lru_cache
from pathlib import Path

# o tamanho: a altura das maiúsculas medida nas referências (OCR), 39,5 px num 1080×1920. O libass divide o tamanho pela
# altura da fonte (ascendente + descendente: 1,21 em na Inter), então 66 no libass = 54,55 px no Chrome (`ESTILO`)
FONTE = 'Inter'
FONTES = Path(__file__).resolve().parents[2] / 'render' / 'motion' / 'fonts' / 'ass'  # só o TTF: o libass não lê woff2
TAMANHO_ASS = 80 / 1920  # frases de 2–3 palavras: um pouco maior que a palavra solta de antes (66)
SOMBRA_Y = 3 / 1920  # a sombra difusa: um pouco para baixo, borrada
SOMBRA_BLUR = 9 / 1920  # o blur em fração da altura (6 num 1080×1920, conferido lado a lado com a prévia; 12 em 4K)
SOMBRA_ALFA = 0x38  # 0 = opaca, 255 = invisível (ASS)
# o halo: a sombra também ganha um contorno grosso borrado, que escurece em volta das letras (legível em tela branca)
HALO = 7 / 1920
# o contorno fino escuro que deixa a letra legível em qualquer fundo, até em tela branca (sem faixa escura atrás)
CONTORNO = 2.4 / 1920
CONTORNO_ALFA = 0x40
# a palavra ainda não dita fica apagada e acende quando é falada (a 1ª já entra acesa)
APAGADA = 0x70
ACENDE = 0.08  # s
# a placa: um retângulo arredondado escuro e desfocado atrás da frase, que garante a leitura em qualquer fundo
PLACA_ALFA = 0x5C  # ~64% de preto
PLACA_RAIO = 0.42  # em fração da altura da letra
PLACA_FOLGA = (0.55, 0.30)  # em fração do tamanho da letra: dos lados, em cima e embaixo
PLACA_BLUR = 2.5 / 1920


@lru_cache(maxsize=4)
def _fonte(tam: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTES / 'Inter-Bold.ttf'), tam)


def _largura(texto: str, tam: int, espaco: float) -> float:
    """A largura do texto no libass (px), medida na mesma Inter Bold, com o espaço entre as letras."""
    return _fonte(tam).getlength(texto) + espaco * max(len(texto) - 1, 0)


def _placa(cx: float, cy: float, w: float, h: float, r: float) -> str:
    """Um retângulo arredondado no desenho do ASS (\\p1), com o centro em (cx, cy)."""
    x0, y0, x1, y1 = -w / 2, -h / 2, w / 2, h / 2
    k = r * 0.45  # o controle da curva de Bézier que aproxima o quarto de círculo
    return (f'm {x0 + r:.0f} {y0:.0f} l {x1 - r:.0f} {y0:.0f} b {x1 - k:.0f} {y0:.0f} {x1:.0f} {y0 + k:.0f} {x1:.0f} {y0 + r:.0f} '
            f'l {x1:.0f} {y1 - r:.0f} b {x1:.0f} {y1 - k:.0f} {x1 - k:.0f} {y1:.0f} {x1 - r:.0f} {y1:.0f} '
            f'l {x0 + r:.0f} {y1:.0f} b {x0 + k:.0f} {y1:.0f} {x0:.0f} {y1 - k:.0f} {x0:.0f} {y1 - r:.0f} '
            f'l {x0:.0f} {y0 + r:.0f} b {x0:.0f} {y0 + k:.0f} {x0 + k:.0f} {y0:.0f} {x0 + r:.0f} {y0:.0f}')
# o espaço entre as letras: os −0,01em da prévia, em px (`\fsp`) num 1080×1920
ESPACO = -0.55 / 1920


def _tempo(t: float) -> str:
    cs = max(round(t * 100), 0)
    return f'{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}'


def _texto(s: str) -> str:
    """O texto num evento do ASS: sem chaves (abririam um bloco de tags) e com as quebras de linha do formato."""
    return s.replace('\\', '\\\\').replace('{', '(').replace('}', ')').replace('\n', '\\N')


def _acendendo(texto: str, tempos: list | None, ini: float) -> str:
    """O texto com cada palavra acendendo quando é dita: começa apagada (`APAGADA`) e vai ao branco em `ACENDE` s, no
    tempo dela dentro do bloco. Sem os tempos (um texto à mão) ou com outra contagem de palavras, o texto todo aceso."""
    palavras = texto.split(' ')
    if not tempos or len(tempos) != len(palavras) or len(palavras) < 2:
        return _texto(texto)
    partes = []
    for k, (p, t) in enumerate(zip(palavras, tempos)):
        ms = max(round((float(t) - ini) * 1000), 0)
        if k == 0 or ms == 0:
            partes.append(f'{{\\1a&H00&\\3a&H{CONTORNO_ALFA:02X}&}}{_texto(p)}')
        else:
            partes.append(f'{{\\1a&H{APAGADA:02X}&\\3a&HC0&\\t({ms},{ms + round(ACENDE * 1000)},\\1a&H00&\\3a&H{CONTORNO_ALFA:02X}&)}}{_texto(p)}')
    return ' '.join(partes)


def ass(blocos: list[dict], w: int, h: int) -> str:
    """O ASS dos blocos (`{ini, fim, texto, y}`, no tempo do vídeo final; `y`: o centro do texto, fração da altura).
    Cada bloco são dois eventos: a sombra (o texto em preto, borrado e um pouco abaixo) e o texto branco por cima."""
    tam = round(TAMANHO_ASS * h)
    esp = f'\\fsp{ESPACO * h:.2f}'  # no evento: o Spacing negativo do estilo o libass ignora
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes
Kerning: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,{FONTE},{tam},&H00FFFFFF,&H00FFFFFF,&H{CONTORNO_ALFA:02X}000000,&H00000000,-1,0,0,0,100,100,0,0,1,{CONTORNO * h:.2f},0,5,{round(w * 0.06)},{round(w * 0.06)},0,1
Style: Placa,{FONTE},{tam},&H{PLACA_ALFA:02X}000000,&H{PLACA_ALFA:02X}000000,&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Sombra,{FONTE},{tam},&H{SOMBRA_ALFA:02X}000000,&H{SOMBRA_ALFA:02X}000000,&H{SOMBRA_ALFA:02X}000000,&HFF000000,-1,0,0,0,100,100,0,0,1,0,0,5,{round(w * 0.06)},{round(w * 0.06)},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = []
    for b in blocos:
        texto = str(b.get('texto') or '').strip()
        if not texto or float(b['fim']) <= float(b['ini']):
            continue
        x, y = w / 2, float(b['y']) * h
        ini, fim = _tempo(float(b['ini'])), _tempo(float(b['fim']))
        larg = min(_largura(texto, tam, ESPACO * h), w * 0.88)
        cap = tam * 0.75  # a altura útil da letra (maiúsculas e ascendentes)
        pw, ph = larg + 2 * PLACA_FOLGA[0] * tam, cap + 2 * PLACA_FOLGA[1] * tam
        linhas.append(f'Dialogue: 0,{ini},{fim},Placa,,0,0,0,,{{\\an7\\pos({x:.0f},{y + tam * 0.04:.0f})\\blur{PLACA_BLUR * h:.1f}\\p1}}{_placa(0, 0, pw, ph, PLACA_RAIO * ph)}{{\\p0}}')
        linhas.append(f'Dialogue: 1,{ini},{fim},Sombra,,0,0,0,,{{\\pos({x:.0f},{y + SOMBRA_Y * h:.0f})\\bord{HALO * h:.1f}\\blur{SOMBRA_BLUR * h:.1f}{esp}}}{_texto(texto)}')
        linhas.append(f'Dialogue: 2,{ini},{fim},Legenda,,0,0,0,,{{\\pos({x:.0f},{y:.0f}){esp}}}{_acendendo(texto, b.get("tempos"), float(b["ini"]))}')
    return cab + '\n'.join(linhas) + '\n'


def escrever(legenda: dict | None, w: int, h: int, destino: Path) -> Path | None:
    """Grava o ASS de `__render.legenda` (`{blocos}`) em `destino`; sem blocos (ou desligada), nada."""
    blocos = (legenda or {}).get('blocos') or []
    if not blocos:
        return None
    destino.write_text(ass(blocos, w, h), encoding='utf-8')
    return destino


def _escapar(arquivo: Path) -> str:
    caminho = str(arquivo)
    for nivel in ("\\':", "\\'[],;"):
        for c in nivel:
            caminho = caminho.replace(c, '\\' + c)
    return caminho


def filtro(arquivo: Path) -> str:
    """O filtro do ffmpeg que desenha o ASS. O caminho vem do nome da exportação (texto do criador: espaços, apóstrofo,
    vírgula…), escapado nos dois níveis do ffmpeg, sem aspas (dentro delas um apóstrofo não tem escape): primeiro o
    valor da opção (`\\ ' :`), depois o grafo de filtros (`\\ ' [ ] , ;`). `fontsdir` traz a fonte, com o mesmo escape
    (a pasta do repositório também pode ter espaços)."""
    return f'ass=filename={_escapar(arquivo)}:fontsdir={_escapar(FONTES)}'
