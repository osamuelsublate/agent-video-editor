# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""As transições entre planos (SPEC §8.8 do 18): a biblioteca com as favoritas de cada par de grupos, e variar.

    uv run ferramentas/transicoes.py listar
    uv run ferramentas/transicoes.py variar <slug>

Cada corte entre planos (o id é o do plano que entra) recebe sozinho a 1ª favorita do seu par de grupos (de onde sai →
para onde vai: Full ator, tela dividida ou tela cheia; biblioteca/transicoes/ordem.json). `variar` deixa o vídeo como os
exemplos do criador: corte seco em ~89% dos cortes e uma favorita com efeito nas trocas de assunto (~1 em 10); o que não
é o padrão do par vai para `edicao.transicoes[plano] = {id, par}`.
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


# a proporção de cortes com efeito nos Reels do criador (a edição dos roteiros de exemplo, 398 planos, 2026-10-28): 89%
# corte seco; o resto, clique, câmera ou luz
EFEITO = 0.11
FIM_DE_FRASE = ('.', '?', '!', '…')
# os sons que o criador não quer (biblioteca/aprendizados/transicoes.md: sem whoosh nem riser): a transição que os usa não
# entra no sorteio do efeito
SONS_FORA = ('whoosh', 'riser')


def com_efeito_ok(ts: dict, tid: str) -> bool:
    som = ((ts.get(tid) or {}).get('som') or {}).get('som') or ''
    return tid != 'corte-seco' and not any(x in som for x in SONS_FORA)


def variar(slug: str) -> None:
    """As transições do vídeo como nos exemplos: corte seco em quase todos os cortes (gravado mesmo onde a 1ª favorita do
    par tem efeito) e uma favorita com efeito em ~1 de cada 10, nas trocas de assunto (o tipo de tela muda e a fala fecha
    uma frase), espaçadas pelo vídeo. Nunca uma com whoosh ou riser."""
    edicao = ler(slug)
    ts, o = biblioteca(), ler_json(PASTA / 'ordem.json', {})
    texto = {w['id']: w['texto'] for w in ler_json(pasta(slug) / 'transcricao.json')['palavras']}
    planos = planos_em_ordem(slug, edicao)
    cortes = list(zip(planos, planos[1:]))
    # onde cabe um efeito: muda o tipo de tela e a fala do plano que sai termina uma frase
    troca = [familia(a['tipo']) != familia(p['tipo']) and texto.get(a.get('palavra_fim'), '').rstrip().endswith(FIM_DE_FRASE)
             for a, p in cortes]
    quantos = round(len(cortes) * EFEITO)
    passo = len(cortes) / quantos if quantos else len(cortes) + 1
    com_efeito, ultimo = set(), -passo
    for k, ok in enumerate(troca):
        efeitos = [t for t in favoritas(o, ts, cortes[k][0]['tipo'], cortes[k][1]['tipo']) if com_efeito_ok(ts, t)]
        if ok and efeitos and k - ultimo >= passo * 0.8 and len(com_efeito) < quantos:
            com_efeito.add(k)
            ultimo = k
    escolhas = dict(edicao.get('transicoes') or {})
    for k, (a, p) in enumerate(cortes):
        par = f"{a['tipo']}>{p['tipo']}"
        rotulo = f"{p['id']:>4}  {a['tipo']} → {p['tipo']}"
        if k in com_efeito:
            tid = random.choice([t for t in favoritas(o, ts, a['tipo'], p['tipo']) if com_efeito_ok(ts, t)])
            print(f'{rotulo}: {nome(ts, tid)} — troca de assunto')
        else:
            tid = 'corte-seco'
            print(f'{rotulo}: corte seco')
        if tid == padrao_do_par(o, ts, a['tipo'], p['tipo']):
            escolhas.pop(p['id'], None)  # o padrão do par: não precisa gravar
        else:
            escolhas[p['id']] = {'id': tid, 'par': par}
    edicao['transicoes'] = escolhas
    gravar(slug, edicao)
    print(f'\n{len(cortes)} cortes, {len(com_efeito)} com efeito; gravado em projetos/{slug}/edicao.json')


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'listar':
        listar()
    elif len(sys.argv) >= 3 and sys.argv[1] == 'variar':
        variar(sys.argv[2])
    else:
        raise SystemExit(__doc__)
