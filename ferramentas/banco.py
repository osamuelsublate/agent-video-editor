# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Banco de mídias dos inserts e motions, global (`biblioteca/banco/<id>/`: o original, `proxy.mp4`, `miniatura.jpg` e
`item.json` no formato do 18). Do 18: backend/app/banco.py, sem servidor.

    uv run ferramentas/banco.py adicionar <arquivo> [--nome N] [--descricao D] [--palavras "a,b"] [--fonte url|upload|captura] [--projeto slug]
    uv run ferramentas/banco.py buscar <termos…>          nome, descrição e palavras-chave, sem diferenciar acentos
    uv run ferramentas/banco.py trecho <id> <ini> <fim> [--nome N]   um pedaço de um vídeo (sem arquivo próprio)
    uv run ferramentas/banco.py apagar <id…>              apaga mídias que não serviram (recusa se alguma está em uso)
    uv run ferramentas/banco.py listar
    uv run ferramentas/banco.py descrever <id>            o Gemini descreve e sugere palavras-chave

Trechos (do 18): itens com `pai`, `inicio` e `fim`, que tocam o original e herdam dele a descrição, as palavras e o formato.
"""
import argparse
import json
import math
import re
import shutil
import sys
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, PROJETOS, ffmpeg, gravar_json, inspecionar, ler_json, renomear_tags  # noqa: E402

RAIZ = BIBLIOTECA / 'banco'
EXT_VIDEO = ('.mp4', '.mov', '.m4v', '.webm')
EXT_IMAGEM = ('.png', '.jpg', '.jpeg', '.webp')
PROPORCOES = {'16:9': 16 / 9, '16:10': 16 / 10, '4:3': 4 / 3, '1:1': 1.0, '4:5': 4 / 5, '3:4': 3 / 4, '9:16': 9 / 16, 'alto': 9 / 22}
MIN_TRECHO = 0.2
HERDADOS = ('tipo', 'formato', 'largura', 'altura', 'descricao', 'palavras', 'descricao_ia', 'origem', 'ia', 'arquivo', 'proxy', 'cortes')
VERSAO_PROXY = 2  # quadro-chave a cada 12 quadros: a busca no player é imediata

PROMPT_DESCREVER = """Você cataloga mídias (vídeos e imagens) de um banco usado em inserts de vídeos curtos sobre IA, tecnologia e design. Descreva o que aparece nesta mídia para que ela seja achada depois por busca: o site, a ferramenta ou a marca, os textos legíveis que importam e, no vídeo, o que acontece. Concreto e curto. Português."""
ESQUEMA_DESCRICAO = {
    'title': 'DescricaoMidia', 'type': 'object', 'additionalProperties': False, 'required': ['descricao', 'palavras'],
    'properties': {
        'descricao': {'type': 'string', 'description': 'o que aparece, em 1 a 3 frases concretas: site/ferramenta/marca, textos legíveis importantes, o que acontece (no vídeo)'},
        'palavras': {'type': 'array', 'items': {'type': 'string'}, 'description': '3 a 6 palavras-chave curtas, em minúsculas (ex.: "github", "landing page", "claude", "preços")'}}}


# ---------------------------------------------------------------- itens

def pasta_item(bid: str) -> Path:
    if not re.fullmatch(r'[0-9a-f]{10}', bid or ''):
        raise SystemExit(f'Id de mídia inválido: {bid} (10 caracteres hexadecimais)')
    return RAIZ / bid


def existe(bid: str) -> bool:
    return bool(re.fullmatch(r'[0-9a-f]{10}', bid or '')) and (RAIZ / bid / 'item.json').exists()


def formato_de(largura: int | None, altura: int | None) -> str:
    """O formato mais próximo da proporção real da mídia."""
    if not largura or not altura:
        return '16:9'
    r = largura / altura
    return min(PROPORCOES, key=lambda f: abs(math.log(r / PROPORCOES[f])))


def _completar(i: dict) -> dict:
    """Um trecho com o que herda do original e a sua duração."""
    i.setdefault('palavras', [])
    if not i.get('pai'):
        return i
    pai = ler_json(RAIZ / i['pai'] / 'item.json') or {}
    return {**{k: pai.get(k) for k in HERDADOS}, **i, 'duracao': round(i['fim'] - i['inicio'], 3), 'nome_pai': pai.get('nome')}


def ler_item(bid: str) -> dict:
    i = ler_json(pasta_item(bid) / 'item.json')
    if i is None:
        raise SystemExit(f'Mídia não encontrada no banco: {bid}')
    return _completar(i)


def salvar_item(item: dict) -> dict:
    gravar_json(RAIZ / item['id'] / 'item.json', item)
    return item


def todos() -> list[dict]:
    out = []
    for arq in RAIZ.glob('*/item.json'):
        try:
            out.append(json.loads(arq.read_text(encoding='utf-8')))
        except ValueError:
            continue
    return out


def para_busca(t: str) -> str:
    """Só letras e números, minúsculas e sem acentos: "animacao" acha "animação" (do 18: comum.para_busca)."""
    t = re.sub(r'[^\wÀ-ÿ]', '', t.lower())
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')


def usos() -> dict[str, list[str]]:
    """Onde cada mídia está ligada: `projeto/plano` (lendo os edicao.json)."""
    out: dict[str, list[str]] = {}
    for arq in PROJETOS.glob('*/edicao.json'):
        try:
            e = json.loads(arq.read_text(encoding='utf-8'))
        except ValueError:
            continue
        for x in (e.get('inserts') or {}).get('pedidos') or []:
            for m in x.get('midias') or []:
                out.setdefault(m.get('banco'), []).append(f'{arq.parent.name}/{x.get("plano") or x.get("id")}')
        for plano, m in (e.get('motions') or {}).items():
            if m.get('banco'):
                out.setdefault(m['banco'], []).append(f'{arq.parent.name}/{plano} (motion)')
    return out


def versao_aprovada(projeto: Path) -> int | None:
    """A última versão aprovada de um projeto (`revisoes/vN.json` com `aprovado`), ou None."""
    vs = []
    for r in (projeto / 'revisoes').glob('v*.json'):
        m = re.fullmatch(r'v(\d+)\.json', r.name)
        if m and (ler_json(r, {}) or {}).get('aprovado') and (projeto / 'versoes' / f'v{m.group(1)}' / 'edicao.json').exists():
            vs.append(int(m.group(1)))
    return max(vs) if vs else None


def usos_aprovados() -> tuple[dict[str, list[dict]], dict[str, list[dict]], set[str]]:
    """O que entrou nos vídeos aprovados (a última versão aprovada de cada projeto): `{banco_id: [uso]}` das mídias,
    `{preset_do_motion: [uso]}` dos motions e os projetos aprovados. Cada uso: projeto, versão, plano e o instante do plano."""
    midias: dict[str, list[dict]] = {}
    motions: dict[str, list[dict]] = {}
    aprovados: set[str] = set()
    for p in sorted(PROJETOS.iterdir()):
        v = versao_aprovada(p) if p.is_dir() and not p.name.startswith('_') else None
        if v is None:
            continue
        aprovados.add(p.name)
        e = ler_json(p / 'versoes' / f'v{v}' / 'edicao.json', {}) or {}
        pl = ler_json(p / 'versoes' / f'v{v}' / 'planos.json', []) or []
        ini = {x.get('id'): x.get('ini') for x in (pl if isinstance(pl, list) else pl.get('planos', []))}
        quando = (ler_json(p / 'versoes' / f'v{v}' / 'info.json', {}) or {}).get('criado_em')  # para ordenar pelo uso mais recente
        uso = lambda plano: {'projeto': p.name, 'versao': v, 'plano': plano, 't': ini.get(plano), 'quando': quando}  # noqa: E731
        for x in (e.get('inserts') or {}).get('pedidos') or []:
            for m in x.get('midias') or []:
                if m.get('banco'):
                    midias.setdefault(m['banco'], []).append(uso(x.get('plano') or x.get('id')))
        for plano, m in (e.get('motions') or {}).items():
            if m.get('banco'):
                midias.setdefault(m['banco'], []).append(uso(plano))
            if m.get('preset'):
                motions.setdefault(m['preset'], []).append(uso(plano))
    return midias, motions, aprovados


def estados() -> dict[str, dict]:
    """O selo de cada mídia (originais e trechos): `usado` (entrou num vídeo aprovado: ela ou um trecho dela),
    `aprovado` (marcada à mão, ou subida pelo criador no app: `do_criador`), `recusado` (marcada à mão, de um projeto já aprovado e que
    ficou de fora, ou de um projeto que não existe mais) ou None (de um projeto ainda em edição). Com os usos aprovados de cada uma."""
    midias, _, aprovados = usos_aprovados()
    itens = todos()
    por_pai: dict[str, list[dict]] = {}
    for i in itens:
        if i.get('pai'):
            por_pai.setdefault(i['pai'], []).append(i)
    out = {}
    for i in itens:
        us = list(midias.get(i['id'], []))
        if not i.get('pai'):
            us += [u for t in por_pai.get(i['id'], []) for u in midias.get(t['id'], [])]
        if us:
            estado = 'usado'
        elif i.get('estado') in ('aprovado', 'recusado'):
            estado = i['estado']
        elif i.get('do_criador') or (i.get('pai') and existe(i['pai']) and ler_item(i['pai']).get('do_criador')):
            estado = 'aprovado'
        elif (prj := i.get('projeto') or (ler_item(i['pai']).get('projeto') if i.get('pai') and existe(i['pai']) else None)) in aprovados:
            estado = 'recusado'
        elif not prj or not (PROJETOS / prj / 'edicao.json').exists():
            estado = 'recusado'  # o projeto dela não existe mais (foi para a lixeira) ou ela veio sem projeto
        else:
            estado = None
        out[i['id']] = {'estado': estado, 'usos': us}
    return out


def renomear_tag(de: str, para: str) -> int:
    """Troca a tag `de` (e as de dentro dela: "fia" leva "fia/reels") por `para` em todas as mídias; `para` vazio apaga.
    Devolve quantas mídias mudaram."""
    n = 0
    for i in todos():
        tags = i.get('tags') or []
        novas = renomear_tags(tags, de, para)
        if novas != tags:
            if novas:
                i['tags'] = novas
            else:
                i.pop('tags', None)
            salvar_item(i)
            n += 1
    return n


def limpar_recusados() -> list[str]:
    """Leva para a lixeira do banco (`banco/_lixeira/<id>-<data>`) os originais recusados, com os trechos: nunca o que o
    criador subiu, nem o que algum projeto ainda usa. Devolve os ids levados."""
    est, em_uso = estados(), usos()
    lixeira = RAIZ / '_lixeira'
    levados = []
    for i in todos():
        if i.get('pai') or est.get(i['id'], {}).get('estado') != 'recusado' or i.get('do_criador'):
            continue
        ids = [i['id']] + [t['id'] for t in todos() if t.get('pai') == i['id']]
        if any(em_uso.get(x) for x in ids):
            continue
        lixeira.mkdir(exist_ok=True)
        carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')
        for x in ids:
            shutil.move(str(pasta_item(x)), str(lixeira / f'{x}-{carimbo}'))
        levados += ids
    return levados


def apagar(bid: str) -> list[str]:
    """Apaga uma mídia que não serviu (e os trechos dela). Recusa se algum projeto a usa. Devolve os ids apagados."""
    ids = [bid] + [i['id'] for i in todos() if i.get('pai') == bid]
    em_uso = {u for i in ids for u in usos().get(i, [])}
    if em_uso:
        raise SystemExit(f'{bid} está em uso ({", ".join(sorted(em_uso))}): tire dos inserts antes de apagar.')
    for i in ids:
        shutil.rmtree(pasta_item(i), ignore_errors=True)
    return ids


def listar_banco(busca: str = '') -> list[dict]:
    """Os originais, os mais novos primeiro, cada um com os seus trechos; `busca` procura no nome, na descrição e nas
    palavras-chave (do original ou de um trecho), sem diferenciar acentos (do 18: banco.listar_banco)."""
    termos = [para_busca(t) for t in busca.split() if para_busca(t)]
    originais, trechos = [], {}
    for i in todos():
        if i.get('pai'):
            trechos.setdefault(i['pai'], []).append(i)
        else:
            i.setdefault('palavras', [])
            originais.append(i)
    itens = []
    for i in originais:
        filhos = [{**{k: i.get(k) for k in HERDADOS}, **t, 'duracao': round(t['fim'] - t['inicio'], 3), 'nome_pai': i.get('nome')}
                  for t in sorted(trechos.get(i['id'], []), key=lambda t: t['inicio'])]
        if termos:
            texto = ' '.join(para_busca(x) for x in ' '.join([i.get('nome') or '', i.get('descricao') or '', ' '.join(i['palavras']),
                                                              *(t.get('nome') or '' for t in filhos)]).split())
            if not all(t in texto for t in termos):
                continue
        itens.append({**i, 'trechos': filhos})
    return sorted(itens, key=lambda i: i.get('criado_em') or '', reverse=True)


# ---------------------------------------------------------------- adicionar

def fazer_proxy(origem: Path, destino: Path) -> None:
    """A versão leve para tocar (lado maior até 1280), com quadros-chave curtos (do 18: banco._fazer_proxy)."""
    ffmpeg('-i', str(origem), '-vf', "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '23', '-preset', 'veryfast', '-g', '12', '-keyint_min', '12',
           '-sc_threshold', '0', '-tune', 'fastdecode', '-c:a', 'aac', '-movflags', '+faststart', str(destino))


def adicionar(arquivo: Path, nome: str | None = None, descricao: str = '', palavras: list[str] = (), fonte: str = 'upload',
              projeto: str | None = None, origem: dict | None = None, mover: bool = False) -> dict:
    """Guarda um arquivo no banco (copiado; `mover` para temporários) e prepara a versão leve e a miniatura. `fonte`: a URL
    de onde veio, ou "upload"/"captura". `origem`: o registro do 18 (ex.: captura de site), quando há."""
    arquivo = Path(arquivo)
    if not arquivo.is_file():
        raise SystemExit(f'Arquivo não encontrado: {arquivo}')
    ext = arquivo.suffix.lower()
    if ext not in EXT_VIDEO + EXT_IMAGEM:
        raise SystemExit(f'Formato não aceito ({ext or "sem extensão"}): use MP4, MOV, WebM, PNG, JPG ou WebP')
    bid = uuid.uuid4().hex[:10]
    pasta = RAIZ / bid
    pasta.mkdir(parents=True)
    alvo = pasta / f'original{ext}'
    (shutil.move if mover else shutil.copy2)(str(arquivo), alvo)
    tipo = 'video' if ext in EXT_VIDEO else 'imagem'
    try:
        info = inspecionar(alvo)
        if tipo == 'video':
            fazer_proxy(alvo, pasta / 'proxy.mp4')
            ffmpeg('-ss', str(min(1.0, (info.get('duracao') or 0) / 2)), '-i', str(pasta / 'proxy.mp4'), '-frames:v', '1',
                   '-vf', 'scale=-2:360', '-q:v', '4', str(pasta / 'miniatura.jpg'))
        else:
            ffmpeg('-i', str(alvo), '-vf', "scale='min(640,iw)':-2,crop=iw:'min(ih,iw*2)':0:0", '-q:v', '4', str(pasta / 'miniatura.jpg'))
    except Exception:
        shutil.rmtree(pasta, ignore_errors=True)
        raise
    if origem is None:
        origem = {'tipo': 'upload', 'nome_original': arquivo.name} if not fonte.startswith('http') else {'tipo': 'web', 'url': fonte}
    return salvar_item({
        'id': bid, 'nome': (nome or arquivo.stem).strip()[:200], 'descricao': descricao.strip()[:2000],
        'palavras': list(dict.fromkeys(p.strip().lower()[:40] for p in palavras if p.strip()))[:30],
        'tipo': tipo, 'arquivo': alvo.name, 'proxy': 'proxy.mp4' if tipo == 'video' else None, 'proxy_v': VERSAO_PROXY,
        'largura': info.get('largura'), 'altura': info.get('altura'), 'duracao': (info.get('duracao') or 0.0) if tipo == 'video' else 0.0,
        'formato': formato_de(info.get('largura'), info.get('altura')), 'origem': origem, 'fonte': fonte, 'projeto': projeto,
        'criado_em': datetime.now().isoformat(timespec='seconds'), 'ia': {'status': 'pendente', 'erro': None}})


def criar_trecho(pai: str, inicio: float, fim: float, nome: str | None = None) -> dict:
    """Um trecho de um vídeo do banco (sem arquivo próprio: toca o original). Do 18: banco.criar_trecho."""
    original = ler_item(pai)
    if original.get('pai') or original['tipo'] != 'video':
        raise SystemExit('Só vídeos originais têm trechos')
    ini, fim = round(max(float(inicio), 0.0), 3), round(min(float(fim), original['duracao']), 3)
    if fim - ini < MIN_TRECHO:
        raise SystemExit(f'Trecho curto demais (mínimo {MIN_TRECHO} s; o vídeo tem {original["duracao"]} s)')
    n = sum(1 for i in todos() if i.get('pai') == pai) + 1
    tid = uuid.uuid4().hex[:10]
    (RAIZ / tid).mkdir(parents=True)
    salvar_item({'id': tid, 'pai': pai, 'inicio': ini, 'fim': fim, 'nome': (nome or '').strip()[:200] or f'{original["nome"]} · trecho {n}',
                 'criado_em': datetime.now().isoformat(timespec='milliseconds')})
    ffmpeg('-ss', f'{(ini + fim) / 2:.3f}', '-i', str(RAIZ / pai / (original.get('proxy') or original['arquivo'])), '-frames:v', '1',
           '-vf', 'scale=-2:360', '-q:v', '4', str(RAIZ / tid / 'miniatura.jpg'))
    return ler_item(tid)


def editar_trecho(tid: str, inicio: float, fim: float) -> dict:
    """Muda o intervalo de um trecho (e refaz a miniatura no meio dele)."""
    t = ler_item(tid)
    if not t.get('pai'):
        raise SystemExit(f'{tid} não é um trecho')
    original = ler_item(t['pai'])
    ini, fim = round(max(float(inicio), 0.0), 3), round(min(float(fim), original['duracao']), 3)
    if fim - ini < MIN_TRECHO:
        raise SystemExit(f'Trecho curto demais (mínimo {MIN_TRECHO} s)')
    t.update(inicio=ini, fim=fim)
    salvar_item(t)
    ffmpeg('-ss', f'{(ini + fim) / 2:.3f}', '-i', str(RAIZ / t['pai'] / (original.get('proxy') or original['arquivo'])), '-frames:v', '1',
           '-vf', 'scale=-2:360', '-q:v', '4', str(RAIZ / tid / 'miniatura.jpg'))
    return ler_item(tid)


def tira(bid: str) -> Path:
    """A tira de quadros de um vídeo (24 quadros de 90 px numa linha), o fundo da linha do tempo dos trechos. Feita uma
    vez e guardada em `tira.jpg` (do 18: banco.tira)."""
    item = ler_item(bid)
    alvo = RAIZ / bid / 'tira.jpg'
    if not alvo.exists():
        dur = max(item.get('duracao') or 1.0, 0.1)
        ffmpeg('-i', str(RAIZ / bid / (item.get('proxy') or item['arquivo'])), '-vf', f'fps={24 / dur:.6f},scale=-2:90,tile=24x1',
               '-frames:v', '1', '-q:v', '5', str(alvo))
    return alvo


# ---------------------------------------------------------------- descrição pelo Gemini

def descrever(bid: str) -> dict:
    """O Gemini descreve a mídia e sugere palavras-chave; o que já foi escrito à mão fica (do 18: banco.descrever)."""
    import gemini

    item = ler_item(bid)
    if item.get('pai'):
        raise SystemExit('Trechos herdam a descrição do original: descreva o original ' + item['pai'])
    pasta = RAIZ / bid
    tocar = pasta / (item.get('proxy') or item['arquivo'])
    if item['tipo'] == 'video':
        leve = pasta / 'analise.mp4'
        if not leve.exists():
            ffmpeg('-i', str(tocar), '-t', '120', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '32', '-preset', 'veryfast',
                   '-vf', "fps=2,scale='if(gt(iw,ih),min(640,iw),-2)':'if(gt(iw,ih),-2,min(640,ih))'", str(leve))
        preparado = (item.get('duracao') or 0) >= gemini.MIN_VIDEO  # curto: o gemini.py manda o quadro do meio
        arquivo = leve if preparado else tocar
    else:
        leve = pasta / 'analise.jpg'
        if not leve.exists():
            ffmpeg('-i', str(tocar), '-vf', "scale='min(1024,iw)':-2,crop=iw:'min(ih,4000)':0:0", '-q:v', '4', str(leve))
        arquivo, preparado = leve, True
    try:
        r = gemini.perguntar([arquivo], f"Mídia: {item['nome']} ({item['tipo']})", sistema=PROMPT_DESCREVER,
                             esquema=ESQUEMA_DESCRICAO, preparados=preparado, max_tokens=1500)
    except SystemExit as e:
        salvar_item({**ler_json(pasta / 'item.json'), 'ia': {'status': 'erro', 'erro': str(e)[:300]}})
        raise
    item = ler_json(pasta / 'item.json')
    descricao = str(r.get('descricao') or '').strip()
    palavras = list(dict.fromkeys([*item.get('palavras', []), *(str(p).strip().lower() for p in r.get('palavras') or [] if str(p).strip())]))[:30]
    return salvar_item({**item, 'descricao': item.get('descricao') or descricao, 'palavras': palavras, 'descricao_ia': descricao,
                        'ia': {'status': 'pronto', 'erro': None}})


# ---------------------------------------------------------------- saída

def num(x: float, casas: int = 1) -> str:
    return f'{x:.{casas}f}'.replace('.', ',')


SELO = {'usado': '★ usado em vídeo aprovado', 'aprovado': '✓ aprovado', 'recusado': '✗ recusado'}


def linha(i: dict, onde: dict[str, list[str]], est: dict | None = None) -> str:
    dur = f'{num(i.get("duracao") or 0)} s' if i.get('tipo') == 'video' else '—'
    desc = ' '.join((i.get('descricao') or '').split())
    desc = desc[:90] + '…' if len(desc) > 90 else desc
    usado = f'  [em {", ".join(onde[i["id"]])}]' if onde.get(i['id']) else ''
    selo = f'  ({SELO[e]})' if (e := (est or {}).get(i['id'], {}).get('estado')) else ''
    return f'{i["id"]}  {i.get("tipo", "?"):<6} {i.get("formato", "?"):<5} {dur:>7}  {i.get("nome")}{" — " + desc if desc else ""}{usado}{selo}'


def mostrar(itens: list[dict]) -> None:
    if not itens:
        print('Nada no banco com esses termos.')
        return
    onde, est = usos(), estados()
    for i in itens:
        print(linha(i, onde, est))
        for t in i.get('trechos') or []:
            u = f'  [em {", ".join(onde[t["id"]])}]' if onde.get(t['id']) else ''
            e = est.get(t['id'], {}).get('estado')
            print(f'  └ {t["id"]}  trecho {num(t["inicio"], 2)}–{num(t["fim"], 2)} s ({num(t["duracao"])} s)  {t.get("nome")}{u}{f"  ({SELO[e]})" if e else ""}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Banco de mídias (biblioteca/banco/).', usage=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('adicionar')
    a.add_argument('arquivo')
    a.add_argument('--nome')
    a.add_argument('--descricao', default='')
    a.add_argument('--palavras', default='')
    a.add_argument('--fonte', default='upload')
    a.add_argument('--projeto')
    b = sub.add_parser('buscar')
    b.add_argument('termos', nargs='+')
    t = sub.add_parser('trecho')
    t.add_argument('id')
    t.add_argument('ini', type=float)
    t.add_argument('fim', type=float)
    t.add_argument('--nome')
    sub.add_parser('listar')
    d = sub.add_parser('descrever')
    d.add_argument('id')
    x = sub.add_parser('apagar')
    x.add_argument('ids', nargs='+')
    args = ap.parse_args()
    if args.cmd == 'adicionar':
        item = adicionar(Path(args.arquivo), args.nome, args.descricao, args.palavras.split(','), args.fonte, args.projeto)
        print(item['id'])
    elif args.cmd == 'buscar':
        mostrar(listar_banco(' '.join(args.termos)))
    elif args.cmd == 'trecho':
        item = criar_trecho(args.id, args.ini, args.fim, args.nome)
        print(f'{item["id"]}  trecho {num(item["inicio"], 2)}–{num(item["fim"], 2)} s de {args.id}  {item["nome"]}')
    elif args.cmd == 'listar':
        mostrar(listar_banco())
    elif args.cmd == 'apagar':
        for bid in args.ids:
            print('apagado:', ' '.join(apagar(bid)))
    elif args.cmd == 'descrever':
        item = descrever(args.id)
        print(f'{item["id"]}  {item["nome"]}\nDescrição (IA): {item["descricao_ia"]}\nPalavras-chave: {", ".join(item["palavras"])}')
