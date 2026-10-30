"""Traz um projeto do 18-harness-video-editor para projetos/<slug>/ (para testar o render e a revisão com um caso real).

    uv run ferramentas/importar18.py <id-no-18> [slug-aqui]

Lê o 18 sem mexer nele. A mídia é clonada (clone do APFS ou reflink: não ocupa espaço novo). O edicao.json é o subconjunto do
projeto.json do 18 descrito em .claude/skills/editor/edicao.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import PROJETOS, clonar as clonar_arquivo, gravar_json, ler_json  # noqa: E402

DEZOITO = Path(__file__).resolve().parents[2] / '18-harness-video-editor' / 'dados' / 'projetos'
CAMPOS = ['id', 'nome', 'criado_em', 'formato', 'saida', 'fontes', 'enquadramento', 'look', 'velocidade', 'nivel_voz',
          'motions', 'transicoes', 'audio', 'legenda']


def clonar(de: Path, para: Path) -> None:
    if de.is_file() and not para.exists():
        para.parent.mkdir(parents=True, exist_ok=True)
        clonar_arquivo(de, para)


def importar(origem: str, slug: str) -> Path:
    o, d = DEZOITO / origem, PROJETOS / slug
    p = ler_json(o / 'projeto.json')
    if p is None:
        raise SystemExit(f'Não achei {o}/projeto.json')
    for rel in ['audio.wav', 'silencios.json', *[str(f.relative_to(o)) for f in (o / 'midia').rglob('*') if f.is_file()]]:
        clonar(o / rel, d / rel)
    ativa = p.get('transcricao_ativa') or 'elevenlabs'
    gravar_json(d / 'transcricao.json', {'motor': ativa, 'palavras': (ler_json(o / 'transcricoes' / f'{ativa}.json') or {})['palavras']})
    ed = {k: p[k] for k in CAMPOS if k in p}
    ed['id'] = slug
    ed['timeline'] = {'V1': p['timeline']['V1']}
    ed['cortes'] = {k: p['cortes'][k] for k in ('mantidas', 'duvidas', 'parametros') if k in p.get('cortes', {})}
    dr = p.get('direcao', {})
    ed['direcao'] = {'roteiro': dr.get('roteiro', ''), 'itens': dr.get('itens', [])}
    ins = p.get('inserts', {})
    ed['inserts'] = {'pedidos': ins.get('pedidos', []), 'fundo': ins.get('fundo'), 'ator_planos': ins.get('ator_planos', {})}
    gravar_json(d / 'edicao.json', ed)
    return d


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    destino = importar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
    print(f'Importado em {destino}')
