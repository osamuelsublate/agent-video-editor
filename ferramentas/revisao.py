# /// script
# requires-python = ">=3.11"
# ///
"""A revisão do criador do lado do Claude (o app grava projetos/<slug>/revisoes/vN.json).

    uv run ferramentas/revisao.py ler <slug> [vN]
        a revisão (a da última versão, se não disser) no mesmo texto do "Copiar revisão" do app e, para cada
        comentário, o id, a âncora (palavras), o plano sob ele e os prints anexados (abra com o Read antes de aplicar).
    uv run ferramentas/revisao.py responder <slug> <vN> <id|geral> --status aplicado|respondido|nao_aplicado --resposta "…"
        grava a resposta no comentário (o app mostra embaixo dele); "geral" responde o geral de revisões antigas.
    uv run ferramentas/revisao.py clipes [--refazer]
        recorta das referências os clipes das galerias da biblioteca: presets/clipes/<id>.mp4 (o trecho da 1ª fonte,
        480 px, com som) e transicoes/clipes/<id>.mp4 (1,5 s em volta do corte da 1ª fonte, com som). A referência vem
        de biblioteca/referencias/ (senão, do 18); as externas, de presets/externas/ (senão, do 18).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, RAIZ, ffmpeg, gravar_json, ler_json, pasta  # noqa: E402

DEZOITO = RAIZ.parent / '18-harness-video-editor' / 'dados'
STATUS = ('aplicado', 'respondido', 'nao_aplicado')


def tempo(t: float) -> str:
    """m:ss,d, como o app mostra (0:03,2)."""
    d = int(max(0.0, t or 0) * 10 + 1e-6)
    return f'{d // 600}:{(d % 600) // 10:02d},{d % 10}'


def quando(c: dict) -> str:
    if c.get('geral'):
        return 'Geral'
    return f'{tempo(c["t"])}–{tempo(c["fim"])}' if c.get('fim') is not None else tempo(c['t'])


def ordem(c: dict) -> float:
    """Os comentários gerais (sem tempo) primeiro, depois pelo tempo."""
    return -1 if c.get('geral') else c['t']


def uma_linha(s: str) -> str:
    return ' / '.join(p.strip() for p in s.strip().splitlines() if p.strip())


def tem_conteudo(c: dict) -> bool:
    """Um comentário que conta: com texto ou com print anexado."""
    return bool((c.get('texto') or '').strip() or c.get('anexos'))


def linha_anexos(slug: str, anexos: list[str]) -> str:
    """Os anexos de um comentário, numa linha embaixo dele (o Claude abre cada print com o Read; num vídeo, tira
    quadros com o ffmpeg). "print" quando são só imagens; "anexo" quando há vídeo."""
    rotulo = 'anexo' if any(a.lower().endswith(('.mp4', '.mov', '.webm')) for a in anexos) else 'print'
    return f'  ↳ {rotulo}: {", ".join(f"projetos/{slug}/{a}" for a in anexos)}'


def texto(slug: str, v: int, rev: dict) -> str:
    """O texto do botão "Copiar revisão" (app/revisao.js, `texto()`): mude os dois juntos."""
    linhas = [f'Revisão · {slug} · v{v}']
    for c in sorted((c for c in rev.get('comentarios', []) if tem_conteudo(c)), key=ordem):
        ancora = quando(c)
        fala = f'"{c["fala"]}" — ' if c.get('fala') else ''
        linhas.append(f'[{ancora}] {fala}{uma_linha(c.get("texto") or "") or "(ver o print)"}')
        if c.get('anexos'):
            linhas.append(linha_anexos(slug, c['anexos']))
    if (rev.get('geral') or '').strip() or rev.get('anexos_geral'):  # revisões antigas (o app de agora grava comentários gerais)
        linhas.append(f'Geral: {uma_linha(rev.get("geral") or "") or "(ver o print)"}')
        if rev.get('anexos_geral'):
            linhas.append(linha_anexos(slug, rev['anexos_geral']))
    linhas.append(f'(projetos/{slug}/revisoes/v{v}.json)')
    return '\n'.join(linhas)


def versao_da_revisao(slug: str, v: str | None) -> int:
    if v:
        return int(v.lstrip('v'))
    feitas = sorted(int(p.stem[1:]) for p in (pasta(slug) / 'revisoes').glob('v*.json') if p.stem[1:].isdigit())
    if not feitas:
        raise SystemExit(f'O projeto {slug} ainda não tem revisão (o criador comenta no app).')
    return feitas[-1]


def ler(slug: str, v: str | None) -> None:
    n = versao_da_revisao(slug, v)
    p = pasta(slug)
    rev = ler_json(p / 'revisoes' / f'v{n}.json')
    if rev is None:
        raise SystemExit(f'Não há revisão da v{n} (projetos/{slug}/revisoes/v{n}.json).')
    vdir = p / 'versoes' / f'v{n}'
    palavras = ler_json(vdir / 'palavras.json', []) or []
    planos = ler_json(vdir / 'planos.json', []) or []

    def palavra_em(t: float) -> dict | None:
        return min(palavras, key=lambda w: 0 if w['ini'] <= t < w['fim'] else min(abs(w['ini'] - t), abs(t - w['fim'])), default=None)

    def planos_em(a: float, b: float) -> list[dict]:
        return [q for q in planos if q['ini'] <= b and q['fim'] > a] if b > a else [q for q in planos if q['ini'] <= a < q['fim']]

    print(texto(slug, n, rev))
    estado = 'APROVADA' if rev.get('aprovado') else f'enviada em {rev["enviado_em"]}' if rev.get('enviado_em') else 'ainda não enviada'
    print(f'\nEstado: {estado}. Para cada um: revisao.py responder {slug} v{n} <id> --status … --resposta "…"')
    for c in sorted(rev.get('comentarios', []), key=ordem):
        if not tem_conteudo(c):
            continue
        fim = c.get('fim')
        if c.get('geral'):
            print(f'\n- {c["id"]} · geral (o vídeo todo) · {c.get("status", "pendente")}')
        else:
            w1 = palavra_em(fim) if fim is not None else None
            ancora = f'palavra {c.get("palavra")}' if w1 is None or w1['id'] == c.get('palavra') else f'palavras {c.get("palavra")}–{w1["id"]}'
            ps = ', '.join(f'{q["id"]} {q["tipo"]} ({tempo(q["ini"])}–{tempo(q["fim"])})' for q in planos_em(c['t'], fim if fim is not None else c['t']))
            print(f'\n- {c["id"]} · {quando(c)} · {ancora} · plano {ps or "—"} · {c.get("status", "pendente")}')
        print(f'  {uma_linha(c.get("texto") or "") or "(só o print)"}')
        for a in c.get('anexos') or []:
            print(f'  anexo: projetos/{slug}/{a}{"" if (p / a).is_file() else " (o arquivo sumiu)"}')
        if c.get('resposta'):
            print(f'  ↳ resposta: {c["resposta"]}')
    for a in rev.get('anexos_geral') or []:
        print(f'\n- geral · anexo: projetos/{slug}/{a}')
    g = rev.get('resposta_geral')
    if g:
        print(f'\n- geral · {g.get("status")} ↳ {g.get("resposta") or ""}')


def responder(slug: str, v: str, cid: str, status: str, resposta: str) -> None:
    status = status.replace('não ', 'nao_').replace('nao ', 'nao_')
    if status not in STATUS:
        raise SystemExit(f'Status inválido: {status} (use {", ".join(STATUS)}).')
    n = int(v.lstrip('v'))
    arq = pasta(slug) / 'revisoes' / f'v{n}.json'
    rev = ler_json(arq)
    if rev is None:
        raise SystemExit(f'Não há revisão da v{n} ({arq}).')
    if cid == 'geral':
        rev['resposta_geral'] = {'status': status, 'resposta': resposta}
    else:
        c = next((x for x in rev.get('comentarios', []) if x.get('id') == cid), None)
        if c is None:
            raise SystemExit(f'Comentário {cid} não existe na v{n} (ids: {", ".join(x["id"] for x in rev.get("comentarios", []))}).')
        c['status'], c['resposta'] = status, resposta
    gravar_json(arq, rev)
    print(f'{cid}: {status} · gravado em projetos/{slug}/revisoes/v{n}.json')


def fonte_ref(ref: str) -> Path:
    if ref.startswith('externa:'):
        nome = ref.split(':', 1)[1]
        local = BIBLIOTECA / 'presets' / 'externas' / f'{nome}.mp4'
        return local if local.exists() else DEZOITO / 'presets' / 'externas' / f'{nome}.mp4'
    local = BIBLIOTECA / 'referencias' / ref / 'proxy.mp4'
    return local if local.exists() else DEZOITO / 'referencias' / ref / 'proxy.mp4'


def recortar(origem: Path, destino: Path, ini: float, dur: float, som: bool) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix('.tmp.mp4')
    # `0:a?`: a referência sem áudio (uma externa muda) sai muda, sem erro
    audio = ['-map', '0:a:0?', '-c:a', 'aac', '-b:a', '96k', '-ac', '2'] if som else ['-an']
    ffmpeg('-ss', f'{ini:.3f}', '-i', str(origem), '-t', f'{dur:.3f}', '-map', '0:v:0', '-vf', 'scale=480:-2', '-c:v', 'libx264', '-preset', 'veryfast',
           '-crf', '30', '-g', '12', '-pix_fmt', 'yuv420p', *audio, '-movflags', '+faststart', str(tmp))
    tmp.replace(destino)


def clipes(refazer: bool) -> None:
    feitos = 0
    for arq in sorted((BIBLIOTECA / 'presets').glob('*.json')):
        p = ler_json(arq)
        if arq.name == 'ordem.json' or not p.get('fontes'):
            continue
        destino = BIBLIOTECA / 'presets' / 'clipes' / f'{p["id"]}.mp4'
        f = p['fontes'][0]
        if destino.exists() and not refazer:
            continue
        origem = fonte_ref(f['ref'])
        if not origem.exists():
            print(f'  sem a referência {f["ref"]} para o preset {p["id"]}')
            continue
        recortar(origem, destino, f['inicio'], max(f['fim'] - f['inicio'], 0.3), som=True)
        print(f'preset {p["id"]} ({p["nome"]}): {f["ref"]} {tempo(f["inicio"])}')
        feitos += 1
    pares = ler_json(BIBLIOTECA / 'transicoes' / 'pares.json', {}) or {}
    for arq in sorted((BIBLIOTECA / 'transicoes').glob('*.json')):
        if arq.name in ('ordem.json', 'pares.json'):
            continue
        t = ler_json(arq)
        destino = BIBLIOTECA / 'transicoes' / 'clipes' / f'{t["id"]}.mp4'
        if destino.exists() and not refazer:
            continue
        # o corte seco não tem fonte própria: um corte seco sem som das referências
        f = (t.get('fontes') or [None])[0] or next((c for par in pares.values() for c in par.get('cortes', [])
                                                     if c.get('classe') == 'seco' and not c.get('sons')), None)
        if not f:
            continue
        origem = fonte_ref(f['ref'])
        if not origem.exists():
            print(f'  sem a referência {f["ref"]} para a transição {t["id"]}')
            continue
        ini = max(f['t'] - 1.5, 0)
        recortar(origem, destino, ini, f['t'] + 1.5 - ini, som=True)
        print(f'transição {t["id"]}: {f["ref"]} {tempo(f["t"])}')
        feitos += 1
    print(f'{feitos} clipes feitos.' if feitos else 'Os clipes já existem (use --refazer para refazer).')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('ler')
    a.add_argument('slug')
    a.add_argument('versao', nargs='?')
    a = sub.add_parser('responder')
    a.add_argument('slug')
    a.add_argument('versao')
    a.add_argument('id')
    a.add_argument('--status', required=True)
    a.add_argument('--resposta', default='')
    a = sub.add_parser('clipes')
    a.add_argument('--refazer', action='store_true')
    x = ap.parse_args()
    if x.cmd == 'ler':
        ler(x.slug, x.versao)
    elif x.cmd == 'responder':
        responder(x.slug, x.versao, x.id, x.status, x.resposta)
    else:
        clipes(x.refazer)
