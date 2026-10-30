"""A legenda no render (do 18: backend/app/legenda.py; SPEC §8.10, docs/legenda.md): o ASS que o libass desenha por cima
de tudo, no fim da montagem. Os blocos (quais palavras, o texto, quando e onde) são montados pela página de render (a
mesma conta da prévia) e chegam em `__render.legenda`; o estilo é o medido nas referências, branca com sombra difusa,
centralizada, na Inter Bold do repositório (a mesma no Mac e no Linux; nada instalado no sistema)."""
from pathlib import Path

# o tamanho: a altura das maiúsculas medida nas referências (OCR), 39,5 px num 1080×1920. O libass divide o tamanho pela
# altura da fonte (ascendente + descendente: 1,21 em na Inter), então 66 no libass = 54,55 px no Chrome (`ESTILO`)
FONTE = 'Inter'
FONTES = Path(__file__).resolve().parents[2] / 'render' / 'motion' / 'fonts' / 'ass'  # só o TTF: o libass não lê woff2
TAMANHO_ASS = 66 / 1920
SOMBRA_Y = 3 / 1920  # a sombra difusa: um pouco para baixo, borrada
SOMBRA_BLUR = 6 / 1920  # o blur em fração da altura (6 num 1080×1920, conferido lado a lado com a prévia; 12 em 4K)
SOMBRA_ALFA = 0x55  # 0 = opaca, 255 = invisível (ASS)
# o espaço entre as letras: os −0,01em da prévia, em px (`\fsp`) num 1080×1920
ESPACO = -0.55 / 1920


def _tempo(t: float) -> str:
    cs = max(round(t * 100), 0)
    return f'{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}'


def _texto(s: str) -> str:
    """O texto num evento do ASS: sem chaves (abririam um bloco de tags) e com as quebras de linha do formato."""
    return s.replace('\\', '\\\\').replace('{', '(').replace('}', ')').replace('\n', '\\N')


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
Style: Legenda,{FONTE},{tam},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,{round(w * 0.06)},{round(w * 0.06)},0,1
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
        linhas.append(f'Dialogue: 0,{ini},{fim},Sombra,,0,0,0,,{{\\pos({x:.0f},{y + SOMBRA_Y * h:.0f})\\blur{SOMBRA_BLUR * h:.1f}{esp}}}{_texto(texto)}')
        linhas.append(f'Dialogue: 1,{ini},{fim},Legenda,,0,0,0,,{{\\pos({x:.0f},{y:.0f}){esp}}}{_texto(texto)}')
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
