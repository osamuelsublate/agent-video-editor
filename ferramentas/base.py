"""O comum dos scripts: caminhos, o edicao.json de cada projeto, ffmpeg/ffprobe e as chaves do .env.

Importado pelos outros scripts de ferramentas/ (rodados com `uv run ferramentas/<script>.py`). Só biblioteca padrão.
"""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# fora do git: a biblioteca (o que serve a qualquer vídeo; copia-se entre máquinas, por cima) e os projetos de cada um
BIBLIOTECA = RAIZ / 'biblioteca'
PROJETOS = RAIZ / 'projetos'
# na biblioteca, o que o Claude lê para editar: os exemplos da direção (criador.md e uma pasta por categoria de vídeo,
# gerados pela Calibragem) e os aprendizados (um .md por área, as correções do criador)
EXEMPLOS = BIBLIOTECA / 'exemplos'
APRENDIZADOS = BIBLIOTECA / 'aprendizados'
# no git: o que uma biblioteca nova recebe (os aprendizados técnicos e motions de exemplo)
INICIAL = Path(__file__).resolve().parent / 'inicial'


def preparar_biblioteca() -> None:
    """Cria `projetos/` e completa a biblioteca com o que falta dela em `ferramentas/inicial/` (cada pasta ou arquivo de
    primeiro nível que não existe; o que já existe, mesmo vazio, nunca é tocado). O servidor chama ao subir; o preparar,
    ao criar um projeto."""
    import shutil

    PROJETOS.mkdir(parents=True, exist_ok=True)
    BIBLIOTECA.mkdir(parents=True, exist_ok=True)
    for x in sorted(INICIAL.iterdir()) if INICIAL.is_dir() else ():
        alvo = BIBLIOTECA / x.name
        if x.name.startswith('.') or alvo.exists():
            continue
        if x.is_dir():
            shutil.copytree(x, alvo)
        else:
            shutil.copy2(x, alvo)


def pasta(slug: str) -> Path:
    """A pasta de um projeto (`projetos/<slug>/`)."""
    p = PROJETOS / slug
    if not p.is_dir():
        raise SystemExit(f'Projeto não encontrado: {slug} (em {PROJETOS})')
    return p


def ler_json(caminho: Path, padrao=None):
    caminho = Path(caminho)
    if not caminho.exists():
        return padrao
    return json.loads(caminho.read_text(encoding='utf-8'))


def tag_limpa(t) -> str:
    """Uma tag como no Obsidian: sem o #, sem espaços (viram -), níveis com / ("fia/ad-vsl")."""
    return re.sub(r'/+', '/', re.sub(r'\s+', '-', str(t or '').strip().lstrip('#').strip())).strip('/')


def tags_limpas(lista) -> list[str]:
    return list(dict.fromkeys(t for t in (tag_limpa(x) for x in lista or []) if t))[:30]


def renomear_tags(tags: list[str], de: str, para: str) -> list[str]:
    """Troca a tag `de` e as de dentro dela ("fia" leva "fia/reels") por `para`; `para` vazio tira."""
    out = []
    for t in tags or []:
        if t == de or t.startswith(f'{de}/'):
            t = f'{para}{t[len(de):]}' if para else ''
        if t and t not in out:
            out.append(t)
    return out


def gravar_json(caminho: Path, dados) -> None:
    """Grava de uma vez (arquivo temporário + rename): quem lê nunca vê um JSON pela metade."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=caminho.parent, suffix='.tmp', delete=False) as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(f.name, caminho)


def ler(slug: str) -> dict:
    """O edicao.json do projeto (o estado da edição; contrato em .claude/skills/editor/edicao.md)."""
    edicao = ler_json(pasta(slug) / 'edicao.json')
    if edicao is None:
        raise SystemExit(f'O projeto {slug} ainda não tem edicao.json (rode preparar.py).')
    return edicao


def gravar(slug: str, edicao: dict) -> None:
    gravar_json(pasta(slug) / 'edicao.json', edicao)


def ffmpeg(*args: str) -> None:
    """Roda o ffmpeg sem perguntar; se falhar, o erro traz o fim da mensagem dele."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'ffmpeg (código {r.returncode}): {r.stderr.strip()[-600:] or "sem mensagem"}')


def inspecionar(arquivo: Path) -> dict:
    """Duração e medidas como o espectador vê (aplica a rotação do metadado: celular em pé diz 3840×2160 cru)."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(arquivo)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'Não consegui ler {arquivo} (formato não suportado ou arquivo corrompido).')
    dados = json.loads(r.stdout)
    video = next((s for s in dados['streams'] if s['codec_type'] == 'video'), None)
    info = {'duracao': round(float(dados['format'].get('duration', 0)), 3),
            'tem_audio': any(s['codec_type'] == 'audio' for s in dados['streams'])}
    if video:
        w, h = video['width'], video['height']
        rotacao = next((int(d.get('rotation', 0)) for d in video.get('side_data_list', []) if 'rotation' in d), 0)
        if abs(rotacao) % 180 == 90:
            w, h = h, w
        info |= {'largura': w, 'altura': h, 'fps': video.get('avg_frame_rate')}
    return info


def env(nome: str) -> str:
    """Uma chave do .env da raiz (nunca imprima o valor)."""
    if nome not in os.environ and (RAIZ / '.env').exists():
        for linha in (RAIZ / '.env').read_text().splitlines():
            if '=' in linha and not linha.lstrip().startswith('#'):
                k, v = linha.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))
    if not os.environ.get(nome):
        raise SystemExit(f'Falta {nome} no .env da raiz do projeto.')
    return os.environ[nome]
