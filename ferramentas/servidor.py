"""Servidor local: serve a raiz do repositório (app de revisão, página de render, projetos e biblioteca) com Range
(o player e o Chromium precisam pular no vídeo) e as rotas do app (revisões, calibragem, referências e biblioteca).

    uv run ferramentas/servidor.py [porta]      → http://localhost:8719/app/
Também importado pelo render (`servir(0)` sobe numa porta livre, numa thread). Só biblioteca padrão.

Rotas (JSON; um erro volta como {"erro": "…"}, com 422 numa validação):
- GET /api/lista?pasta=… (nomes numa pasta pública) · GET /api/projetos (o início do app) · GET /api/motions/fonte/<pro|
  rounded|mono> (as SF da Apple, lidas do Mac: o render/motion/fonts.css as pede) · PUT /api/revisao/<slug>/v<N> (a
  revisão inteira; as respostas do Claude no arquivo são mantidas).
- Calibragem (chama ferramentas/calibragem.py): GET|POST /api/referencias (POST: o vídeo cru no corpo, o nome do arquivo
  no cabeçalho X-Nome) · GET /api/referencias/clipes · GET /api/referencias/<id>/revisao · PUT …/<id>/direcao {itens} ·
  PUT …/<id>/status {revisado} · PUT …/<id>/uso {usar} (entra ou sai da Heurística) · PUT …/<id>/nome {nome} · PUT …/<id>/favorito {inicio, fim, favorito} · POST
  …/<id>/reanalisar · POST …/<id>/tentar · DELETE /api/referencias/<id>.
- GET|PUT /api/heuristica?categoria=<id>: as regras da direção da categoria (exemplos/<categoria>/regras.md) e os
  roteiros de exemplo dela, com os tempos dos planos. · GET|PUT /api/categorias {categorias} (as categorias de vídeo:
  Reels, Ad…; uma em uso não sai) · PUT /api/referencias/<id>/categoria {categoria} · PUT /api/projetos/<slug>/categoria
  {categoria} · o POST /api/referencias aceita a categoria no cabeçalho X-Categoria.
- GET /api/aprendizados (as áreas, com os bullets "Do criador") · GET|PUT /api/aprendizados/<área> {texto} (o
  aprendizados/<área>.md) · GET /api/aprendizados/imagens/<nome> (as imagens que os .md mostram).
- GET /api/presets/amostras (o ator e as mídias do banco da simulação dos presets, render/preset.html)
  · PUT /api/presets/<id> {aprovado} · PUT /api/presets/ordem {chave, ids, favoritos} · PUT /api/transicoes/<id> {aprovado}
  · PUT /api/transicoes/ordem {chave, ids, favoritas} · GET|PUT|DELETE /api/banco/<id> ({estado} marca o selo à mão) · GET /api/estados (selos do banco e usos dos motions nos
  vídeos aprovados) · POST /api/limpar-recusados · GET|POST /api/ctas · PUT|DELETE /api/ctas/<id> (os CTAs) · PUT /api/ctas-produtos {produtos} · POST /api/banco (subir: o arquivo cru, nome em X-Nome) ·
  POST /api/banco/<id>/trechos {inicio, fim, nome} · GET /api/banco/<id>/tira · PUT /api/motions/<id>/aprovar.
- Recusar: GET /api/presets/<id>/usos e /api/motions/<id>/usos (os projetos que usam) · POST /api/presets/<id>/recusar
  e /api/motions/<id>/recusar {motivo}: o arquivo vai para _recusados/ (com recusado_em e motivo), o preset sai do
  ordem.json e os inserts que o usavam voltam ao 1º favorito da situação (presets.py escolher).
- GET /api/projetos/<slug>/versoes: cada versão com a data do render, a duração e o estado da revisão dela. · DELETE
  /api/projetos/<slug>: a pasta vai para projetos/_lixeira/<slug>-AAAAMMDD-HHMMSS (nada sai do disco).
- Anexos da revisão: POST /api/revisao/<slug>/v<N>/anexo?comentario=<c3|geral> (a imagem ou o vídeo cru no corpo) →
  {caminho: "revisoes/anexos/c3-1.png"} · DELETE /api/revisao/<slug>/v<N>/anexo?caminho=revisoes/anexos/c3-1.png.
- GET /api/codigos: {tipo: {id: código}} (ferramentas/codigo.py; dá o próximo número aos itens novos).
- O provador de look da revisão: GET /api/projetos/<slug>/look (o look, os LUTs, as vinhetas e se há um render rodando)
  · POST …/look/amostra {t, lut, intensidade, vinheta} → {video} (3 s do ator com aquele look; render.py amostra-look)
  · PUT …/look {lut, intensidade, vinheta}: grava no edicao.json e renderiza a próxima versão em segundo plano.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from base import APRENDIZADOS, BIBLIOTECA, EXEMPLOS, PROJETOS, RAIZ, gravar_json, ler_json, preparar_biblioteca  # noqa: E402

PORTA = 8719
PUBLICOS = ('app', 'render', 'projetos', 'biblioteca')
FONTES_DO_MAC = {'pro': 'SFNS.ttf', 'rounded': 'SFNSRounded.ttf', 'mono': 'SFNSMono.ttf'}  # não vão para o git
AREAS = {'cortes': 'Cortes', 'inserts': 'Inserts', 'enriquecimento': 'Enriquecimento', 'motions': 'Motions', 'elementos': 'Elementos',
         'transicoes': 'Transições', 'audio': 'Áudio', 'legenda': 'Legenda', 'render': 'Render'}
IMAGEM = re.compile(r'^[\w.-]+\.(png|jpe?g|webp|gif)$', re.I)
REFERENCIAS = BIBLIOTECA / 'referencias'
ID = r'([\w.-]+)'
CHAVE_PRESET = re.compile(r'^(dividida|vertical|atras):(1:(pe|deitada)|2|2\+)$')
CHAVE_TRANSICAO = re.compile(r'^familia:(ator|dividida|cheia)>(ator|dividida|cheia)$')
JSON_DO_MOTION = re.compile(r'(<script type="application/json" id="preset">)(.*?)(</script>)', re.DOTALL)


class Erro(Exception):
    """Um erro que vai para o app como {"erro": mensagem}, com o status."""

    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


def versoes(projeto: Path) -> list[int]:
    """As versões entregues (as que já têm o proxy.mp4), em ordem."""
    return sorted(int(v.name[1:]) for v in projeto.glob('versoes/v*') if v.name[1:].isdigit() and (v / 'proxy.mp4').is_file())


def projetos() -> list[dict]:
    """Os projetos com ao menos uma versão, do mais recente para o mais antigo, com o estado da revisão da última."""
    lista = []
    for p in PROJETOS.iterdir() if PROJETOS.is_dir() else []:
        if p.name.startswith(('_', '.')):  # a _lixeira (os apagados) e o que não é projeto
            continue
        vs = versoes(p)
        if not vs:
            continue
        ultima = vs[-1]
        rev = ler_json(p / 'revisoes' / f'v{ultima}.json', {}) or {}
        info = ler_json(p / 'versoes' / f'v{ultima}' / 'info.json', {}) or {}
        estado = 'aprovado' if rev.get('aprovado') else 'enviada' if rev.get('enviado_em') else 'em_revisao'
        ed = ler_json(p / 'edicao.json', {}) or {}
        lista.append({'slug': p.name, 'nome': ed.get('nome') or p.name, 'formato': ed.get('formato') or 'reels',
                      'versoes': vs, 'ultima': ultima, 'duracao': info.get('duracao'), 'estado': estado,
                      'comentarios': len(rev.get('comentarios', [])),
                      'atualizado': (p / 'versoes' / f'v{ultima}' / 'proxy.mp4').stat().st_mtime})
    return sorted(lista, key=lambda x: -x['atualizado'])


def juntar_respostas(nova: dict, atual: dict) -> dict:
    """O app grava a revisão inteira; o que o Claude respondeu no arquivo (status, resposta) nunca é apagado por ela."""
    respondidos = {c.get('id'): c for c in atual.get('comentarios', []) if c.get('resposta') or c.get('status', 'pendente') != 'pendente'}
    for c in nova.get('comentarios', []):
        r = respondidos.get(c.get('id'))
        if r and c.get('status', 'pendente') == 'pendente' and not c.get('resposta'):
            c['status'], c['resposta'] = r.get('status'), r.get('resposta')
    if atual.get('resposta_geral') and not nova.get('resposta_geral'):
        nova['resposta_geral'] = atual['resposta_geral']
    return nova


# ---------------------------------------------------------------- rotas

ROTAS: list[tuple[str, re.Pattern, callable]] = []


def rota(metodo: str, padrao: str):
    def registrar(f):
        ROTAS.append((metodo, re.compile(f'^{padrao}$'), f))
        return f
    return registrar


def calibragem():
    """O módulo da calibragem (importado na hora: ele é escrito à parte e só usa a biblioteca padrão na importação)."""
    try:
        import calibragem as c
    except ImportError as e:
        raise Erro(f'A calibragem ainda não está disponível no servidor ({e}).', 503) from e
    return c


def arquivo_json(pasta: Path, id_: str) -> Path:
    caminho = pasta / f'{id_}.json'
    if not caminho.is_file():
        raise Erro(f'Não encontrei {id_} em {pasta.relative_to(RAIZ)}', 404)
    return caminho


@rota('GET', '/api/projetos')
def _projetos(h, q):
    return projetos()


@rota('GET', '/api/lista')
def _lista(h, q):  # nomes de arquivos de uma pasta pública: ?pasta=biblioteca/presets
    alvo = (RAIZ / q.get('pasta', [''])[0]).resolve()
    if not alvo.is_dir() or not str(alvo).startswith(str(RAIZ)) or alvo.relative_to(RAIZ).parts[:1] not in [(p,) for p in PUBLICOS]:
        raise Erro('pasta inválida')
    return sorted(p.name + ('/' if p.is_dir() else '') for p in alvo.iterdir() if not p.name.startswith('.'))


@rota('PUT', r'/api/revisao/([\w-]+)/v(\d+)')
def _revisao(h, q, slug, v):  # o app grava a revisão inteira
    if not (PROJETOS / slug).is_dir():
        raise Erro('rota inválida', 404)
    destino = PROJETOS / slug / 'revisoes' / f'v{v}.json'
    gravar_json(destino, juntar_respostas(h.corpo(), ler_json(destino, {}) or {}))
    return {'ok': True}


def versoes_detalhe(slug: str) -> list[dict]:
    """Cada versão (da mais nova para a mais antiga): a data do render, a duração e o estado da revisão dela."""
    p = PROJETOS / slug
    out = []
    for v in reversed(versoes(p)):
        info = ler_json(p / 'versoes' / f'v{v}' / 'info.json', {}) or {}
        rev = ler_json(p / 'revisoes' / f'v{v}.json', None)
        cs = [c for c in (rev or {}).get('comentarios', []) if (c.get('texto') or '').strip() or c.get('anexos')]
        tem = bool(cs or ((rev or {}).get('geral') or '').strip())
        estado = 'aprovada' if (rev or {}).get('aprovado') else 'enviada' if (rev or {}).get('enviado_em') else 'em_revisao' if tem else 'sem'
        out.append({'v': v, 'criado_em': info.get('criado_em'), 'duracao': info.get('duracao'), 'estado': estado,
                    'comentarios': len(cs), 'aplicados': sum(1 for c in cs if c.get('status') == 'aplicado')})
    return out


@rota('GET', r'/api/projetos/([\w-]+)/versoes')
def _versoes(h, q, slug):
    if not (PROJETOS / slug).is_dir():
        raise Erro('Projeto não encontrado', 404)
    return versoes_detalhe(slug)


# ---- o provador de look: LUT, intensidade e vinheta do ator (montagem/look.py), testados em 3 s e aplicados num render

def _look():
    from montagem import look  # só biblioteca padrão na importação (numpy e Pillow só na máscara, que roda no render.py)
    return look


def _edicao(slug: str) -> Path:
    arq = PROJETOS / slug / 'edicao.json'
    if slug.startswith(('_', '.')) or not arq.is_file():
        raise Erro('Projeto não encontrado', 404)
    return arq


def _render_rodando(slug: str) -> bool:
    pid = ler_json(PROJETOS / slug / '.cache' / 'render.json', {}) or {}
    if not pid.get('pid'):
        return False
    try:
        os.kill(int(pid['pid']), 0)
        return True
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True


def _look_pedido(c: dict) -> dict:
    look = _look()
    lut = c.get('lut') or None
    if lut is not None and lut not in look.NOMES:
        raise Erro(f'LUT desconhecido: {lut}', 422)
    if c.get('vinheta') not in look.VINHETAS:
        raise Erro('Vinheta desconhecida', 422)
    try:
        k = round(min(max(float(c.get('intensidade', 1)), 0), 1), 2)
    except (TypeError, ValueError):
        raise Erro('Intensidade inválida', 422) from None
    return {'lut': lut, 'intensidade': k, 'vinheta': c['vinheta']}


@rota('GET', r'/api/projetos/([\w-]+)/look')
def _ler_look(h, q, slug):
    look = _look()
    return {'look': look.do_projeto(ler_json(_edicao(slug), {}) or {}), 'luts': look.NOMES, 'vinhetas': list(look.VINHETAS),
            'renderizando': _render_rodando(slug)}


@rota('POST', r'/api/projetos/([\w-]+)/look/amostra')
def _amostra_look(h, q, slug):
    _edicao(slug)
    c = h.corpo()
    lk = _look_pedido(c)
    r = subprocess.run([shutil.which('uv') or 'uv', 'run', '--quiet', str(Path(__file__).parent / 'render.py'), 'amostra-look', slug,
                        f'{float(c.get("t") or 0):.2f}', lk['lut'] or '-', str(lk['intensidade']), lk['vinheta']],
                       cwd=RAIZ, capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise Erro(f'A amostra falhou: {(r.stderr or r.stdout).strip()[-300:]}', 500)
    rel = r.stdout.strip().splitlines()[-1]
    return {'video': f'/{rel}?{int((RAIZ / rel).stat().st_mtime)}'}  # o carimbo: o navegador nunca reaproveita uma amostra velha


@rota('PUT', r'/api/projetos/([\w-]+)/look')
def _aplicar_look(h, q, slug):
    """Grava o look no projeto e renderiza a próxima versão em segundo plano (a camada dos inserts vem do cache: só a
    montagem é refeita). Um render que já está rodando não é duplicado."""
    arq = _edicao(slug)
    lk = _look_pedido(h.corpo())
    if _render_rodando(slug):
        raise Erro('Já há um render deste projeto rodando: espere ele terminar.', 409)
    edicao = ler_json(arq, {})
    edicao['look'] = lk
    gravar_json(arq, edicao)
    cache = PROJETOS / slug / '.cache'
    cache.mkdir(parents=True, exist_ok=True)
    with open(cache / 'render.log', 'w') as log:
        proc = subprocess.Popen([shutil.which('uv') or 'uv', 'run', '--quiet', str(Path(__file__).parent / 'render.py'), slug],
                                cwd=RAIZ, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    threading.Thread(target=proc.wait, daemon=True).start()
    gravar_json(cache / 'render.json', {'pid': proc.pid, 'motivo': 'look'})
    return {'ok': True, 'proxima': (versoes(PROJETOS / slug) or [0])[-1] + 1}


@rota('DELETE', r'/api/projetos/([\w-]+)')
def _apagar_projeto(h, q, slug):
    """Apagar um projeto não apaga nada do disco: a pasta vai para projetos/_lixeira/<slug>-AAAAMMDD-HHMMSS (como no 18),
    de onde dá para recuperar movendo de volta."""
    origem = PROJETOS / slug
    if slug.startswith('_') or not origem.is_dir():
        raise Erro('Projeto não encontrado', 404)
    from datetime import datetime
    destino = PROJETOS / '_lixeira' / f'{slug}-{datetime.now():%Y%m%d-%H%M%S}'
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(origem), str(destino))
    return {'ok': True, 'lixeira': str(destino.relative_to(RAIZ))}


TIPOS_ANEXO = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/gif': '.gif',
               'video/mp4': '.mp4', 'video/quicktime': '.mov', 'video/webm': '.webm'}
ANEXO = r'revisoes/anexos/(c\d+|geral)-\d+\.(png|jpg|webp|gif|mp4|mov|webm)'


@rota('POST', r'/api/revisao/([\w-]+)/v(\d+)/anexo')
def _anexar(h, q, slug, v):
    """Uma imagem ou um vídeo colado, arrastado ou escolhido num comentário:
    projetos/<slug>/revisoes/anexos/<comentário>-<n>.<ext> (n: o próximo livre; a extensão, a do tipo)."""
    cid = q.get('comentario', [''])[0]
    if not (PROJETOS / slug / 'versoes' / f'v{v}').is_dir() or not re.fullmatch(r'c\d+|geral', cid):
        raise Erro('Comentário ou versão inválida', 422)
    ext = TIPOS_ANEXO.get((h.headers.get('Content-Type') or '').split(';')[0].strip())
    if not ext:
        raise Erro('Só imagens (png, jpg, webp, gif) e vídeos (mp4, mov, webm).', 422)
    resta = int(h.headers.get('Content-Length') or 0)
    if not 0 < resta <= 500 << 20:
        raise Erro('O arquivo está vazio ou passou de 500 MB.', 422)
    pasta = PROJETOS / slug / 'revisoes' / 'anexos'
    pasta.mkdir(parents=True, exist_ok=True)
    with TRAVA_ANEXO:  # reserva o nome (o arquivo vazio) antes de receber
        usados = [int(m.group(1)) for a in pasta.glob(f'{cid}-*') if (m := re.fullmatch(rf'{cid}-(\d+)\.\w+', a.name))]
        destino = pasta / f'{cid}-{max(usados, default=0) + 1}{ext}'
        destino.touch()
    try:
        with open(destino, 'wb') as f:
            while resta > 0:
                bloco = h.rfile.read(min(1 << 20, resta))
                if not bloco:
                    break
                f.write(bloco)
                resta -= len(bloco)
        if resta:
            raise Erro('O envio parou no meio.', 400)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return {'caminho': str(destino.relative_to(PROJETOS / slug))}


@rota('DELETE', r'/api/revisao/([\w-]+)/v(\d+)/anexo')
def _tirar_anexo(h, q, slug, v):
    caminho = q.get('caminho', [''])[0]
    if not re.fullmatch(ANEXO, caminho):
        raise Erro('Anexo inválido', 422)
    (PROJETOS / slug / caminho).unlink(missing_ok=True)
    return {'ok': True}


TRAVA_ANEXO = threading.Lock()


# ---- códigos

@rota('GET', '/api/codigos')
def _codigos(h, q):
    import codigo
    return codigo.mapa()


# ---- calibragem e referências

@rota('GET', '/api/referencias')
def _referencias(h, q):
    return calibragem().listar_referencias()


@rota('POST', '/api/referencias')
def _subir_referencia(h, q):
    """O vídeo vem cru no corpo (o nome em X-Nome): vai para um temporário com o nome original e entra na fila."""
    nome = Path(unquote(h.headers.get('X-Nome') or 'video.mp4')).name
    if Path(nome).suffix.lower() not in ('.mp4', '.mov', '.m4v', '.webm'):
        raise Erro(f'{nome}: não é um vídeo (mp4, mov, m4v ou webm).', 422)
    resta = int(h.headers.get('Content-Length') or 0)
    if not resta:
        raise Erro('Arquivo vazio.', 422)
    pasta = Path(tempfile.mkdtemp(prefix='referencia-'))
    try:
        destino = pasta / re.sub(r'[^\w. -]', '_', nome)
        with open(destino, 'wb') as f:
            while resta > 0:
                bloco = h.rfile.read(min(1 << 20, resta))
                if not bloco:
                    break
                f.write(bloco)
                resta -= len(bloco)
        if resta:
            raise Erro('O envio parou no meio.', 400)
        cat = unquote(h.headers.get('X-Categoria') or '') or 'reels'
        return {'id': calibragem().enfileirar_analise(str(destino), Path(nome).stem, cat)}
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@rota('GET', '/api/referencias/clipes')
def _clipes(h, q):
    return calibragem().clipes()


@rota('GET', f'/api/referencias/{ID}/revisao')
def _revisao_referencia(h, q, id_):
    return calibragem().revisao(id_)


@rota('PUT', f'/api/referencias/{ID}/direcao')
def _salvar_direcao(h, q, id_):
    return calibragem().salvar_edicao(id_, h.corpo().get('itens') or [])


@rota('PUT', f'/api/referencias/{ID}/uso')
def _uso(h, q, id_):  # o "Usar / Não usar" do card: ligada, ensina a direção (entra na Heurística da categoria)
    return calibragem().definir_uso(id_, bool(h.corpo().get('usar')))


@rota('PUT', f'/api/referencias/{ID}/status')
def _status(h, q, id_):
    return calibragem().marcar_revisada(id_, bool(h.corpo().get('revisado'))) or {'ok': True}


@rota('PUT', f'/api/referencias/{ID}/nome')
def _renomear(h, q, id_):
    return calibragem().renomear(id_, str(h.corpo().get('nome') or '').strip()[:120]) or {'ok': True}


@rota('PUT', f'/api/referencias/{ID}/categoria')
def _categoria_referencia(h, q, id_):
    return calibragem().definir_categoria(id_, str(h.corpo().get('categoria') or ''))


@rota('PUT', r'/api/projetos/([\w-]+)/categoria')
def _categoria_projeto(h, q, slug):
    calibragem().categoria_projeto(slug, str(h.corpo().get('categoria') or ''))
    return {'ok': True}


@rota('GET', '/api/categorias')
def _categorias(h, q):
    return {'categorias': calibragem().categorias()}


@rota('PUT', '/api/categorias')
def _salvar_categorias(h, q):
    return {'categorias': calibragem().salvar_categorias(h.corpo().get('categorias') or [])}


@rota('PUT', f'/api/referencias/{ID}/favorito')
def _favoritar(h, q, id_):
    c = h.corpo()
    return calibragem().favoritar(id_, float(c['inicio']), float(c['fim']), bool(c.get('favorito'))) or {'ok': True}


@rota('POST', f'/api/referencias/{ID}/reanalisar')
def _reanalisar(h, q, id_):
    return calibragem().reanalisar(id_) or {'ok': True}


@rota('POST', f'/api/referencias/{ID}/tentar')
def _tentar(h, q, id_):
    return calibragem().tentar_de_novo(id_) or {'ok': True}


@rota('DELETE', f'/api/referencias/{ID}')
def _apagar_referencia(h, q, id_):
    return calibragem().apagar(id_) or {'ok': True}


# ---- heurística: as regras (Markdown) e os roteiros de exemplo

def _categoria(q) -> str:
    """A categoria pedida (?categoria=…), entre as cadastradas; sem ela, Reels."""
    cat = q.get('categoria', ['reels'])[0] or 'reels'
    if cat not in {c['id'] for c in calibragem().categorias()}:
        raise Erro(f'Categoria desconhecida: {cat}', 422)
    return cat


def roteiros(cat: str = 'reels') -> list[dict]:
    """Os roteiros de exemplo da categoria (exemplos/<categoria>/roteiros/<ref>.md), linha a linha: a marcação entre [ ]
    e a fala. A linha k é o plano k da direção da referência (os roteiros são escritos dela, um bloco por plano): daí vêm
    o tipo e os tempos."""
    out = []
    for md in sorted((EXEMPLOS / cat / 'roteiros').glob('*.md')):
        base = REFERENCIAS / md.stem
        info = ler_json(base / 'referencia.json', {}) or {}
        itens = (ler_json(base / 'direcao.json', {}) or {}).get('itens') or []
        planos = sorted((i for i in itens if i.get('camada') == 'plano'), key=lambda i: i['inicio'])
        titulo, linhas = md.stem, []
        for s in md.read_text(encoding='utf-8').splitlines():
            s = s.strip()
            if s.startswith('# '):
                titulo = s[2:].strip()
            elif s.startswith('[') and s.endswith(']'):
                linhas.append({'marcacao': s[1:-1], 'fala': ''})
            elif s and linhas:
                linhas[-1]['fala'] = (linhas[-1]['fala'] + ' ' + s.strip('“”"')).strip()
        if len(planos) == len(linhas):
            for linha, p in zip(linhas, planos):
                linha |= {'tipo': p.get('tipo'), 'inicio': p['inicio'], 'fim': p['fim']}
        out.append({'ref': md.stem, 'nome': info.get('nome') or titulo, 'revisado': info.get('status') == 'revisado',
                    'proxy': (base / 'proxy.mp4').is_file(), 'linhas': linhas})
    return out


@rota('GET', '/api/heuristica')
def _heuristica(h, q):
    cat = _categoria(q)
    arq = calibragem().semear_regras(cat)  # sem regras ainda: começa com uma cópia das do Reels
    return {'categoria': cat, 'regras': arq.read_text(encoding='utf-8') if arq.is_file() else '', 'roteiros': roteiros(cat)}


@rota('PUT', '/api/heuristica')
def _salvar_heuristica(h, q):
    regras = h.corpo().get('regras')
    if not isinstance(regras, str) or not regras.strip():
        raise Erro('As regras não podem ficar vazias.', 422)
    if len(regras) > 20000:
        raise Erro('As regras passaram de 20.000 caracteres.', 422)
    arq = EXEMPLOS / _categoria(q) / 'regras.md'
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(regras.rstrip() + '\n', encoding='utf-8')
    return {'ok': True}


# ---- aprendizados: um .md por área (etapas/14-concluir.md)

def do_criador(texto: str) -> int:
    """Os bullets da seção "## Do criador" de um arquivo de aprendizados."""
    secao = re.search(r'^## Do criador\s*$(.*?)(?=^## |\Z)', texto, re.M | re.S)
    return len(re.findall(r'^[-*]\s', secao.group(1), re.M)) if secao else 0


def arquivo_aprendizado(area: str) -> Path:
    if area not in AREAS:
        raise Erro(f'Área desconhecida: {area}', 404)
    return APRENDIZADOS / f'{area}.md'


def imagem_aprendizado(nome: str) -> Path | None:
    """Uma imagem de aprendizados/imagens/ (só o nome, sem subpastas)."""
    arq = APRENDIZADOS / 'imagens' / nome
    return arq if IMAGEM.match(nome) and arq.is_file() else None


@rota('GET', '/api/aprendizados')
def _aprendizados(h, q):
    out = []
    for area, nome in AREAS.items():
        arq = APRENDIZADOS / f'{area}.md'
        out.append({'area': area, 'nome': nome, 'criador': do_criador(arq.read_text(encoding='utf-8')) if arq.is_file() else 0})
    return out


@rota('GET', r'/api/aprendizados/([a-z]+)')
def _aprendizado(h, q, area):
    arq = arquivo_aprendizado(area)
    return {'area': area, 'nome': AREAS[area], 'texto': arq.read_text(encoding='utf-8') if arq.is_file() else ''}


@rota('PUT', r'/api/aprendizados/([a-z]+)')
def _salvar_aprendizado(h, q, area):
    arq = arquivo_aprendizado(area)
    texto = h.corpo().get('texto')
    if not isinstance(texto, str) or not texto.strip():
        raise Erro('O arquivo não pode ficar vazio.', 422)
    if len(texto) > 20000:
        raise Erro('O arquivo passou de 20.000 caracteres.', 422)
    arq.write_text(texto.rstrip() + '\n', encoding='utf-8')
    return {'ok': True, 'criador': do_criador(texto)}


# ---- presets, transições, banco e motions

def gravar_ordem(arq: Path, chave: str, ids, favoritos, campo: str, maximo: int) -> dict:
    """A ordem de uma situação (presets) ou de um par (transições), no formato do 18: {ids, favoritos|favoritas}."""
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise Erro('ids deve ser uma lista de ids', 422)
    ordem = ler_json(arq, {}) or {}
    if ids:
        ordem[chave] = {'ids': ids, campo: max(0, min(int(favoritos or 0), maximo, len(ids)))}
    else:
        ordem.pop(chave, None)  # "Limpar a ordem": volta a uma lista só
    gravar_json(arq, ordem)
    return ordem


@rota('PUT', '/api/presets/ordem')
def _ordem_presets(h, q):
    c = h.corpo()
    if not CHAVE_PRESET.match(str(c.get('chave'))):
        raise Erro(f'Situação inválida: {c.get("chave")}', 422)
    return gravar_ordem(BIBLIOTECA / 'presets' / 'ordem.json', c['chave'], c.get('ids'), c.get('favoritos'), 'favoritos', 3)


@rota('PUT', '/api/transicoes/ordem')
def _ordem_transicoes(h, q):
    c = h.corpo()
    if not CHAVE_TRANSICAO.match(str(c.get('chave'))):
        raise Erro(f'Par inválido: {c.get("chave")}', 422)
    return gravar_ordem(BIBLIOTECA / 'transicoes' / 'ordem.json', c['chave'], c.get('ids'), c.get('favoritas'), 'favoritas', 2)


def aprovar_json(pasta: Path, id_: str, aprovado) -> dict:
    arq = arquivo_json(pasta, id_)
    dados = ler_json(arq)
    dados['aprovado'] = bool(aprovado)
    gravar_json(arq, dados)
    return dados


LUZ: dict[tuple[str, float], int | None] = {}


def luz(img: Path) -> int | None:
    """O brilho médio (0–255) de uma miniatura do banco: a simulação dos presets evita as quase pretas (um site escuro
    parado parece um card vazio) e as quase brancas. Medido uma vez por arquivo (o ffmpeg reduz a imagem a 1 pixel cinza)."""
    if not img.is_file():
        return None
    chave = (str(img), img.stat().st_mtime)
    if chave not in LUZ:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(img), '-vf', 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True)
        LUZ[chave] = r.stdout[0] if r.returncode == 0 and r.stdout else None
    return LUZ[chave]


def amostras_simulacao() -> dict:
    """O que a simulação dos presets (render/preset.html) usa de verdade: o ator — o proxy do bruto do projeto mais
    recente que tem um (de preferência com a pessoa recortada), com o trecho de 8 s em que o rosto aparece melhor (`t0`), o rosto típico nele, já no recorte
    9:16 (como `ator.rostoDoArquivo`), e a pessoa recortada se houver — e os vídeos do banco (os originais) com a
    proporção de cada um."""
    ator = None
    candidatos = []
    for p in PROJETOS.iterdir() if PROJETOS.is_dir() else []:
        ed = ler_json(p / 'edicao.json', {}) or {}
        bruto = next((f for f in ed.get('fontes', []) if f.get('papel') == 'bruto'), None)
        proxy = bruto and p / 'midia' / 'proxy' / f'{bruto["id"]}.mp4'
        if proxy and proxy.is_file():
            recortado = (p / 'midia' / 'recorte' / f'{bruto["id"]}_pessoa.webm').is_file()
            candidatos.append(((recortado, proxy.stat().st_mtime), p, bruto, ed))
    if candidatos:
        # o mais recente já com a pessoa recortada (no "ator embaixo" a cabeça sai da janela, como na exportação com a
        # máscara); sem nenhum, o mais recente
        _, p, bruto, ed = max(candidatos, key=lambda c: c[0])
        proxy = p / 'midia' / 'proxy' / f'{bruto["id"]}.mp4'
        rosto = ler_json(p / 'midia' / 'rosto' / f'{bruto["id"]}.json', {}) or {}
        am = rosto.get('amostras') or []
        janela = int(8 * (rosto.get('por_segundo') or 6))
        # o trecho de 8 s (a partir de 1 s) com mais amostras confiáveis
        t0, melhor = 1.0, -1
        for i in range(0, max(len(am) - janela, 0), max(janela // 4, 1)):
            boas = sum(1 for a in am[i:i + janela] if a.get('conf', 0) > 0.5)
            if am[i]['t'] >= 1 and boas > melhor:
                t0, melhor = am[i]['t'], boas
        trecho = [a for a in am if t0 <= a['t'] < t0 + 8 and a.get('conf', 0) > 0] or am
        med = lambda k: sorted(a[k] for a in trecho)[len(trecho) // 2]  # noqa: E731
        r = {k: med(k) for k in ('cx', 'cy', 'w', 'h')} if trecho else None
        L, A = rosto.get('largura') or bruto.get('largura') or 0, rosto.get('altura') or bruto.get('altura') or 0
        x = (ed.get('enquadramento') or {}).get('x', 0.5)
        rw = A * 9 / 16 / L if L > A > 0 else 1  # bruto deitado: o rosto vai para o recorte 9:16 em `x`
        if r and rw < 1:
            r = {**r, 'cx': (r['cx'] - (1 - rw) * x) / rw, 'w': r['w'] / rw}
        pessoa = p / 'midia' / 'recorte' / f'{bruto["id"]}_pessoa.webm'  # o recorte da pessoa: a cabeça sai da janela
        ator = {'projeto': p.name, 'video': f'/projetos/{p.name}/midia/proxy/{bruto["id"]}.mp4', 't0': t0, 'rosto': r, 'deitado': rw < 1, 'x': x,
                'poster': '/api/presets/ator.jpg', 'arquivo': str(proxy),
                'pessoa': f'/projetos/{p.name}/midia/recorte/{pessoa.name}' if pessoa.is_file() else None}
    midias = []
    for d in sorted((BIBLIOTECA / 'banco').iterdir()) if (BIBLIOTECA / 'banco').is_dir() else []:
        i = ler_json(d / 'item.json', {}) or {}
        # (fora as capturas que pegaram a tela de espera do Cloudflare: "Um momento…", toda branca)
        if i.get('tipo') != 'video' or i.get('pai') or not i.get('largura') or not i.get('altura') or re.match(r'(um momento|just a moment)', i.get('nome') or '', re.I):
            continue
        video = i.get('proxy') or i.get('arquivo')
        if video and (d / video).is_file():
            midias.append({'id': d.name, 'video': f'/biblioteca/banco/{d.name}/{video}', 'imagem': f'/biblioteca/banco/{d.name}/miniatura.jpg',
                           'aspecto': round(i['largura'] / i['altura'], 4), 'duracao': i.get('duracao') or 0, 'luz': luz(d / 'miniatura.jpg')})
    return {'ator': ator, 'midias': midias}


@rota('GET', '/api/presets/amostras')
def _amostras(h, q):
    a = amostras_simulacao()
    if a['ator']:
        a['ator'].pop('arquivo')
    return a


def poster_do_ator() -> Path | None:
    """Um quadro do ator da simulação (1 s depois de `t0`), para a miniatura parada não precisar abrir o vídeo (a página
    Presets tem uma simulação por card). Feito uma vez por proxy, numa pasta temporária."""
    ator = amostras_simulacao()['ator']
    if not ator:
        return None
    proxy = Path(ator['arquivo'])
    chave = hashlib.md5(f'{proxy}|{proxy.stat().st_mtime}|{ator["t0"]}'.encode()).hexdigest()[:12]
    destino = Path(tempfile.gettempdir()) / f'editor19-ator-{chave}.jpg'
    with TRAVA_POSTER:  # os cards pedem todos juntos
        if not destino.is_file():
            from base import ffmpeg
            ffmpeg('-ss', f'{ator["t0"] + 1:.3f}', '-i', str(proxy), '-frames:v', '1', '-vf', 'scale=360:-2', '-q:v', '4', str(destino))
    return destino


TRAVA_POSTER = threading.Lock()


@rota('PUT', f'/api/presets/{ID}')
def _aprovar_preset(h, q, id_):
    return aprovar_json(BIBLIOTECA / 'presets', id_, h.corpo().get('aprovado'))


@rota('PUT', f'/api/transicoes/{ID}')
def _aprovar_transicao(h, q, id_):
    return aprovar_json(BIBLIOTECA / 'transicoes', id_, h.corpo().get('aprovado'))


def _banco():
    import banco
    return banco


def ler_midia(b, id_: str) -> dict:
    try:
        return b.ler_item(id_)
    except SystemExit as e:
        raise Erro(str(e), 404) from e


@rota('GET', r'/api/banco/(\w+)')
def _midia(h, q, id_):
    b = _banco()
    item, usos = ler_midia(b, id_), b.usos()
    trechos = sorted((t for t in b.todos() if t.get('pai') == id_), key=lambda t: t.get('inicio', 0))
    return {'item': item, 'usos': usos.get(id_, []), 'trechos': [{**t, 'usos': usos.get(t['id'], [])} for t in trechos]}


@rota('POST', '/api/banco')
def _subir_midia(h, q):
    """O criador sobe uma mídia pelo app: o arquivo cru no corpo (o nome em X-Nome). Nasce Aprovada (`do_criador`) e o
    Gemini a descreve em segundo plano."""
    b = _banco()
    nome = Path(unquote(h.headers.get('X-Nome') or 'midia.mp4')).name
    if Path(nome).suffix.lower() not in b.EXT_VIDEO + b.EXT_IMAGEM:
        raise Erro(f'{nome}: use MP4, MOV, WebM, PNG, JPG ou WebP.', 422)
    resta = int(h.headers.get('Content-Length') or 0)
    if not resta:
        raise Erro('Arquivo vazio.', 422)
    pasta = Path(tempfile.mkdtemp(prefix='banco-'))
    try:
        destino = pasta / re.sub(r'[^\w. -]', '_', nome)
        with open(destino, 'wb') as f:
            while resta > 0:
                bloco = h.rfile.read(min(1 << 20, resta))
                if not bloco:
                    break
                f.write(bloco)
                resta -= len(bloco)
        if resta:
            raise Erro('O envio parou no meio.', 400)
        try:
            item = b.adicionar(destino, nome=Path(nome).stem, fonte='upload', mover=True)
        except SystemExit as e:
            raise Erro(str(e), 422) from e
        item['do_criador'] = True
        b.salvar_item(item)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)

    def descrever():
        try:
            b.descrever(item['id'])
        except (Exception, SystemExit) as e:  # sem a descrição, a mídia fica como subiu
            print(f'descrever {item["id"]}: {e}', file=sys.stderr)
    threading.Thread(target=descrever, daemon=True).start()
    return {'item': item}


@rota('POST', r'/api/banco/(\w+)/trechos')
def _criar_trecho(h, q, id_):
    b, c = _banco(), h.corpo()
    ler_midia(b, id_)
    try:
        return {'item': b.criar_trecho(id_, c.get('inicio', 0), c.get('fim', 0), c.get('nome'))}
    except SystemExit as e:
        raise Erro(str(e), 422) from e


@rota('GET', r'/api/banco/(\w+)/tira')
def _tira(h, q, id_):
    b = _banco()
    ler_midia(b, id_)
    b.tira(id_)
    return {'url': f'/biblioteca/banco/{id_}/tira.jpg'}


def _ctas():
    import ctas
    return ctas


@rota('GET', '/api/ctas')
def _lista_ctas(h, q):
    c = _ctas()
    return {'ctas': c.todos(), 'categorias': c.categorias(), 'produtos': c.produtos()}


@rota('PUT', '/api/ctas-produtos')
def _produtos_cta(h, q):
    return {'produtos': _ctas().salvar_produtos(h.corpo().get('produtos') or [])}


@rota('POST', '/api/ctas')
def _subir_cta(h, q):
    """Um vídeo editado (o arquivo cru no corpo, nome em X-Nome; categoria opcional em X-Categoria)."""
    c = _ctas()
    nome = Path(unquote(h.headers.get('X-Nome') or 'cta.mp4')).name
    resta = int(h.headers.get('Content-Length') or 0)
    if not resta:
        raise Erro('Arquivo vazio.', 422)
    pasta = Path(tempfile.mkdtemp(prefix='cta-'))
    try:
        destino = pasta / re.sub(r'[^\w. -]', '_', nome)
        with open(destino, 'wb') as f:
            while resta > 0:
                bloco = h.rfile.read(min(1 << 20, resta))
                if not bloco:
                    break
                f.write(bloco)
                resta -= len(bloco)
        if resta:
            raise Erro('O envio parou no meio.', 400)
        try:
            return {'cta': c.adicionar(destino, Path(nome).stem, unquote(h.headers.get('X-Categoria') or '') or None, mover=True)}
        except SystemExit as e:
            raise Erro(str(e), 422) from e
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@rota('GET', r'/api/ctas/(\w+)/tira')
def _tira_cta(h, q, id_):
    try:
        _ctas().tira(id_)
    except SystemExit as e:
        raise Erro(str(e), 404) from e
    return {'url': f'/biblioteca/ctas/{id_}/tira.jpg'}


@rota('PUT', r'/api/ctas/(\w+)')
def _editar_cta(h, q, id_):
    try:
        return {'cta': _ctas().editar(id_, h.corpo())}
    except SystemExit as e:
        raise Erro(str(e), 422) from e


@rota('DELETE', r'/api/ctas/(\w+)')
def _apagar_cta(h, q, id_):
    try:
        _ctas().apagar(id_)
    except SystemExit as e:
        raise Erro(str(e), 404) from e
    return {}


@rota('GET', '/api/estados')
def _estados(h, q):
    """Os selos do banco (usado · aprovado · recusado, com os usos nos vídeos aprovados) e os usos aprovados dos motions."""
    b = _banco()
    _, motions, _ = b.usos_aprovados()
    return {'midias': b.estados(), 'motions': motions}


@rota('POST', '/api/limpar-recusados')
def _limpar_recusados(h, q):
    return {'levados': _banco().limpar_recusados()}


@rota('PUT', r'/api/banco/(\w+)')
def _editar_midia(h, q, id_):
    b = _banco()
    ler_midia(b, id_)
    c, item = h.corpo(), ler_json(b.pasta_item(id_) / 'item.json')
    if 'nome' in c:
        if not str(c['nome']).strip():
            raise Erro('O nome não pode ficar vazio.', 422)
        item['nome'] = str(c['nome']).strip()[:200]
    if 'descricao' in c and not item.get('pai'):
        item['descricao'] = str(c['descricao'] or '').strip()
    if 'palavras' in c and not item.get('pai'):
        item['palavras'] = [str(p).strip() for p in c['palavras'] or [] if str(p).strip()][:30]
    if item.get('pai') and ('inicio' in c or 'fim' in c):  # o intervalo de um trecho
        try:
            t = b.editar_trecho(id_, c.get('inicio', item['inicio']), c.get('fim', item['fim']))
        except SystemExit as e:
            raise Erro(str(e), 422) from e
        item['inicio'], item['fim'] = t['inicio'], t['fim']  # o nome e o selo, se vieram, ficam no `item`
    if 'estado' in c:  # o selo à mão: aprovado, recusado ou None (volta ao automático)
        if c['estado'] in ('aprovado', 'recusado'):
            item['estado'] = c['estado']
        else:
            item.pop('estado', None)
    b.salvar_item(item)
    return {'item': b.ler_item(id_)}


@rota('DELETE', r'/api/banco/(\w+)')
def _apagar_midia(h, q, id_):
    b = _banco()
    ler_midia(b, id_)
    try:
        return {'apagados': b.apagar(id_)}
    except SystemExit as e:  # está em uso num projeto
        raise Erro(str(e), 409) from e


@rota('PUT', r'/api/motions/([\w-]+)/aprovar')
def _aprovar_motion(h, q, id_):
    """Tira o "a_revisar" do JSON do topo do preset (só aquele JSON é reescrito; o resto do arquivo fica igual)."""
    arq = BIBLIOTECA / 'motions' / 'presets' / f'{id_}.html'
    if not arq.is_file():
        raise Erro(f'Motion não encontrado: {id_}', 404)
    html = arq.read_text(encoding='utf-8')
    m = JSON_DO_MOTION.search(html)
    if not m:
        raise Erro(f'{arq.name} não tem o JSON do preset no topo.', 422)
    dados = json.loads(m.group(2))
    dados.pop('a_revisar', None)
    arq.write_text(html[:m.start(2)] + json.dumps(dados, ensure_ascii=False) + html[m.end(2):], encoding='utf-8')
    return dados


# ---- recusar (os presets e motions que o Claude sugeriu; ou descartar um aprovado)

def usos_preset(id_: str) -> dict[str, list[str]]:
    """{projeto: [planos]} dos inserts que usam o preset."""
    out = {}
    for arq in sorted(PROJETOS.glob('*/edicao.json')):
        planos = [x.get('plano') for x in ((ler_json(arq, {}) or {}).get('inserts') or {}).get('pedidos') or []
                  if (x.get('enriquecimento') or {}).get('preset') == id_]
        if planos:
            out[arq.parent.name] = planos
    return out


def usos_motion(id_: str) -> dict[str, list[str]]:
    out = {}
    for arq in sorted(PROJETOS.glob('*/edicao.json')):
        planos = [k for k, m in ((ler_json(arq, {}) or {}).get('motions') or {}).items() if m.get('preset') == id_]
        if planos:
            out[arq.parent.name] = planos
    return out


def agora_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec='seconds')


@rota('GET', f'/api/presets/{ID}/usos')
def _usos_preset(h, q, id_):
    arquivo_json(BIBLIOTECA / 'presets', id_)
    return usos_preset(id_)


@rota('POST', f'/api/presets/{ID}/recusar')
def _recusar_preset(h, q, id_):
    """Move o preset para presets/_recusados/<id>.json (com recusado_em e o motivo, que o Claude lê antes de sugerir
    outro), tira-o de todas as situações do ordem.json e devolve os inserts que o usavam ao 1º favorito da situação."""
    import contextlib
    import io
    pasta = BIBLIOTECA / 'presets'
    arq = arquivo_json(pasta, id_)
    if id_ == 'ordem':
        raise Erro('ordem.json não é um preset', 422)
    motivo = str(h.corpo().get('motivo') or '').strip()[:1000]
    dados = ler_json(arq) | {'recusado_em': agora_iso(), **({'motivo': motivo} if motivo else {})}
    gravar_json(pasta / '_recusados' / f'{id_}.json', dados)
    arq.unlink()
    ordem = ler_json(pasta / 'ordem.json', {}) or {}
    for chave, o in list(ordem.items()):
        ids = o.get('ids') or []
        if id_ in ids:
            k = ids.index(id_)
            o['ids'] = [x for x in ids if x != id_]
            if k < o.get('favoritos', 0):
                o['favoritos'] -= 1
            if not o['ids']:
                ordem.pop(chave)
    gravar_json(pasta / 'ordem.json', ordem)
    usos = usos_preset(id_)
    trocas = {}
    if usos:
        import presets as P
        from base import gravar, ler
        for slug in usos:
            ed = ler(slug)
            for x in (ed.get('inserts') or {}).get('pedidos') or []:
                if (x.get('enriquecimento') or {}).get('preset') == id_:
                    x['enriquecimento'].pop('preset')
            gravar(slug, ed)
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                P.escolher(slug)
            trocas[slug] = [l for l in saida.getvalue().splitlines() if '—' in l or 'nenhum preset' in l]
    return {'ok': True, 'usos': usos, 'trocas': trocas}


@rota('GET', r'/api/motions/([\w-]+)/usos')
def _usos_motion(h, q, id_):
    if not (BIBLIOTECA / 'motions' / 'presets' / f'{id_}.html').is_file():
        raise Erro(f'Motion não encontrado: {id_}', 404)
    return usos_motion(id_)


@rota('POST', r'/api/motions/([\w-]+)/recusar')
def _recusar_motion(h, q, id_):
    """Move o motion para motions/presets/_recusados/<id>.html, com recusado_em e o motivo no JSON do topo."""
    arq = BIBLIOTECA / 'motions' / 'presets' / f'{id_}.html'
    if not arq.is_file():
        raise Erro(f'Motion não encontrado: {id_}', 404)
    motivo = str(h.corpo().get('motivo') or '').strip()[:1000]
    html = arq.read_text(encoding='utf-8')
    m = JSON_DO_MOTION.search(html)
    if m:
        dados = json.loads(m.group(2)) | {'recusado_em': agora_iso(), **({'motivo': motivo} if motivo else {})}
        html = html[:m.start(2)] + json.dumps(dados, ensure_ascii=False) + html[m.end(2):]
    destino = BIBLIOTECA / 'motions' / 'presets' / '_recusados' / arq.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding='utf-8')
    arq.unlink()
    return {'ok': True, 'usos': usos_motion(id_)}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(RAIZ), **k)

    def log_message(self, format, *args):  # noqa: A002 — silencioso: o render faz milhares de pedidos
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def _json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def corpo(self) -> dict:
        try:
            return json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        except ValueError as e:
            raise Erro('JSON inválido no corpo') from e

    def _api(self, metodo: str) -> bool:
        """Responde se a rota é da API (True); senão, deixa para os arquivos estáticos."""
        url = urlparse(self.path)
        for m, padrao, f in ROTAS:
            achou = padrao.match(url.path)
            if achou and m == metodo:
                break
        else:
            if url.path.startswith('/api/'):
                self._json({'erro': 'rota inválida'}, 404)
                return True
            return False
        try:
            self._json(f(self, parse_qs(url.query), *achou.groups()))
        except Erro as e:
            self._json({'erro': str(e)}, e.status)
        except ValueError as e:  # a validação da calibragem: a mensagem é para o criador ler
            self._json({'erro': str(e)}, 422)
        except (FileNotFoundError, KeyError) as e:
            self._json({'erro': f'Não encontrado: {e}'}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001 — o app mostra a mensagem em vez de ficar sem resposta
            self._json({'erro': f'{type(e).__name__}: {e}'}, 500)
        return True

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/':
            self.send_response(HTTPStatus.FOUND)
            self.send_header('Location', '/app/')
            self.end_headers()
            return
        if url.path.startswith('/api/motions/fonte/'):
            fonte = Path('/System/Library/Fonts') / FONTES_DO_MAC.get(url.path.rsplit('/', 1)[1], '-')
            if not fonte.is_file():
                return self.send_error(404)
            corpo = fonte.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'font/ttf')
            self.send_header('Content-Length', str(len(corpo)))
            self.end_headers()
            return self.wfile.write(corpo)
        if url.path == '/api/presets/ator.jpg' or url.path.startswith('/api/aprendizados/imagens/'):
            arq = poster_do_ator() if url.path == '/api/presets/ator.jpg' else imagem_aprendizado(unquote(url.path[26:]))
            if not arq:
                return self.send_error(404)
            corpo = arq.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(str(arq)))
            self.send_header('Content-Length', str(len(corpo)))
            self.end_headers()
            return self.wfile.write(corpo)
        if self._api('GET'):
            return
        partes = Path(url.path).parts
        if len(partes) < 2 or partes[1] not in PUBLICOS:
            return self.send_error(404)
        if 'Range' in self.headers:
            return self._range()
        super().do_GET()

    def do_PUT(self):
        self._api('PUT') or self._json({'erro': 'rota inválida'}, 404)

    def do_POST(self):
        self._api('POST') or self._json({'erro': 'rota inválida'}, 404)

    def do_DELETE(self):
        self._api('DELETE') or self._json({'erro': 'rota inválida'}, 404)

    def _range(self):
        caminho = Path(self.translate_path(self.path))
        if not caminho.is_file():
            return self.send_error(404)
        tamanho = caminho.stat().st_size
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers['Range'])
        ini = int(m.group(1)) if m and m.group(1) else 0
        fim = int(m.group(2)) if m and m.group(2) else tamanho - 1
        if m and not m.group(1) and m.group(2):  # bytes=-N: os últimos N
            ini, fim = max(tamanho - int(m.group(2)), 0), tamanho - 1
        fim = min(fim, tamanho - 1)
        if ini > fim:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header('Content-Range', f'bytes */{tamanho}')
            return self.end_headers()
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header('Content-Type', self.guess_type(str(caminho)))
        self.send_header('Content-Range', f'bytes {ini}-{fim}/{tamanho}')
        self.send_header('Content-Length', str(fim - ini + 1))
        self.end_headers()
        with open(caminho, 'rb') as f:
            f.seek(ini)
            resta = fim - ini + 1
            try:
                while resta > 0:
                    bloco = f.read(min(1 << 20, resta))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    resta -= len(bloco)
            except (BrokenPipeError, ConnectionResetError):
                pass


Handler.extensions_map |= {'.mjs': 'text/javascript', '.webm': 'video/webm', '.m4a': 'audio/mp4', '.cube': 'text/plain'}


def servir(porta: int = 0) -> ThreadingHTTPServer:
    """Sobe o servidor numa thread (porta 0 = livre) e devolve-o; a porta fica em `.server_address[1]`."""
    srv = ThreadingHTTPServer(('127.0.0.1', porta), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == '__main__':
    preparar_biblioteca()  # uma instalação nova: a biblioteca inicial e a pasta dos projetos
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORTA', PORTA))
    print(f'Editor: http://localhost:{porta}/app/')
    ThreadingHTTPServer(('127.0.0.1', porta), Handler).serve_forever()
