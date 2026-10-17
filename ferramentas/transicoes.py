# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""As transições entre planos (SPEC §8.8 do 18): a biblioteca com as favoritas de cada par de grupos, e variar.

    uv run ferramentas/transicoes.py listar
    uv run ferramentas/transicoes.py variar <slug>

Cada corte entre planos (o id é o do plano que entra) recebe sozinho a 1ª favorita do seu par de grupos (de onde sai →
para onde vai: Full ator, tela dividida ou tela cheia; biblioteca/transicoes/ordem.json). `variar` é o "★ Variar
favoritas" do 18 (frontend/src/transicoes/transicoes.ts: sortearTransicoes 'favoritas'): cada corte fica com uma das 2
favoritas do par, meio a meio; a 1ª é o padrão e não é gravada (o corte volta ao padrão), a outra vai para
`edicao.transicoes[plano] = {id, par}`.
"""
import bisect
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, gravar, ler, ler_json, pasta  # noqa: E402
from direcao import saida_do  # noqa: E402

PASTA = BIBLIOTECA / 'transicoes'
GRUPOS = {'ator': 'Full ator', 'dividida': 'Tela dividida', 'cheia': 'Tela cheia'}


def biblioteca() -> dict[str, dict]:
    return {t['id']: t for a in sorted(PASTA.glob('*.json')) if a.stem not in ('ordem', 'pares') and (t := ler_json(a))}


def familia(categoria: str) -> str:
    """O grupo de uma categoria de plano, a unidade das favoritas (do 18: transicoes.familia)."""
    if categoria.startswith('full_ator'):
        return 'ator'
    if categoria.startswith('tela_dividida') or categoria == 'comentario_insert_ator':
        return 'dividida'
    return 'cheia'


def ordem_do_par(o: dict, de: str, para: str) -> dict | None:
    """A ordem que vale para um par: a do grupo; sem ela, a do par exato (antiga)."""
    return o.get(f'familia:{familia(de)}>{familia(para)}') or o.get(f'{de}>{para}')


def favoritas(o: dict, ts: dict, de: str, para: str) -> list[str]:
    x = ordem_do_par(o, de, para) or {}
    return [t for t in x.get('ids', [])[:x.get('favoritas', 0)] if t in ts]


def padrao_do_par(o: dict, ts: dict, de: str, para: str) -> str:
    """A transição que um corte recebe sozinho: a 1ª favorita do par (um par com ordem e sem favorita fica seco)."""
    x = ordem_do_par(o, de, para)
    tid = x['ids'][0] if x and x.get('favoritas') and x.get('ids') else None
    return tid if tid in ts else 'corte-seco'


def planos_em_ordem(slug: str, edicao: dict) -> list[dict]:
    """Os planos da direção que aparecem no vídeo (algumas palavras deles ficaram), na ordem da fala."""
    ordem = {w['id']: k for k, w in enumerate(ler_json(pasta(slug) / 'transcricao.json')['palavras'])}
    saida = saida_do(slug, edicao)
    toca = {w['id']: w['saida_ini'] for w in saida}  # um trecho movido toca fora da ordem da fala
    ficaram = sorted(ordem[w['id']] for w in saida)
    out = []
    for p in (edicao.get('direcao') or {}).get('itens') or []:
        if p['camada'] != 'plano':
            continue
        # a 1ª palavra do plano que ficou no vídeo (sem nenhuma, o plano é órfão e não tem corte)
        i = bisect.bisect_left(ficaram, ordem.get(p['palavra_ini'], -1))
        if i < len(ficaram) and ficaram[i] <= ordem.get(p['palavra_fim'], -1):
            out.append((ficaram[i], p))
    ids = {k: w for w, k in ordem.items()}
    return [p for _, p in sorted(out, key=lambda x: toca[ids[x[0]]])]


def nome(ts: dict, tid: str) -> str:
    return f"{tid} ({ts[tid]['nome']})" if tid in ts else tid


def listar() -> None:
    ts, o = biblioteca(), ler_json(PASTA / 'ordem.json', {})
    print('Transições:')
    for t in ts.values():
        som = (t.get('som') or {}).get('som') or 'sem som'
        print(f"  {t['id']:<16} {t['nome']:<22} efeito: {t['efeito']['tipo']:<7} som: {som}{'' if t.get('aprovado') else '  (não aprovada)'}")
    print('\nAs 2 favoritas de cada par de grupos (a 1ª é o padrão de todo corte do par):')
    for de, nde in GRUPOS.items():
        for para, npara in GRUPOS.items():
            x = o.get(f'familia:{de}>{para}') or {}
            fav = [nome(ts, t) for t in x.get('ids', [])[:x.get('favoritas', 0)]]
            print(f"  {nde} → {npara}: {', '.join(fav) if fav else 'sem favoritas (corte seco)'}")


def variar(slug: str) -> None:
    edicao = ler(slug)
    ts, o = biblioteca(), ler_json(PASTA / 'ordem.json', {})
    escolhas = dict(edicao.get('transicoes') or {})
    planos = planos_em_ordem(slug, edicao)
    for a, p in zip(planos, planos[1:]):
        par = f"{a['tipo']}>{p['tipo']}"
        favs = favoritas(o, ts, a['tipo'], p['tipo'])
        padrao = padrao_do_par(o, ts, a['tipo'], p['tipo'])
        tid = random.choice(favs) if favs else None
        rotulo = f"{p['id']:>4}  {a['tipo']} → {p['tipo']}"
        if tid and tid != padrao:
            escolhas[p['id']] = {'id': tid, 'par': par}
            print(f'{rotulo}: {nome(ts, tid)} — {favs.index(tid) + 1}ª favorita')
        else:
            escolhas.pop(p['id'], None)
            print(f"{rotulo}: {nome(ts, padrao)} — {'1ª favorita, o padrão' if favs else 'sem favoritas, o padrão'} (não grava)")
    edicao['transicoes'] = escolhas
    gravar(slug, edicao)
    print(f'\n{len(planos) - 1} cortes; gravado em projetos/{slug}/edicao.json')


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'listar':
        listar()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'variar':
        variar(sys.argv[2])
    else:
        raise SystemExit(__doc__)
