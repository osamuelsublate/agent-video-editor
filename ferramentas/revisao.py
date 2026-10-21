# /// script
# requires-python = ">=3.11"
# ///
"""A revisão do criador do lado do Claude (o app grava projetos/<slug>/revisoes/vN.json).

    uv run ferramentas/revisao.py pendentes
        os projetos com comentários ainda sem resposta, em qualquer versão (o criador avisa no chat que comentou no app).
    uv run ferramentas/revisao.py ler <slug> [vN] [--bloco B3]
        a revisão (a da última versão, se não disser) no mesmo texto do "Copiar revisão" do app e, para cada
        comentário, o id, a âncora (palavras), o bloco, o plano sob ele e os prints anexados (abra com o Read antes de
        aplicar). Com --bloco, só os daquele bloco. Sem a versão: as versões que têm pendentes (todas, se mais de uma).
    uv run ferramentas/revisao.py responder <slug> <vN> <id|geral> --status aplicado|respondido|nao_aplicado --resposta "…"
        grava a resposta no comentário (o app mostra embaixo dele); "geral" responde o geral de revisões antigas.
    uv run ferramentas/revisao.py pronto <slug>
        tira o aviso de "Claude trabalhando" do app (o `ler` o põe nos blocos dos pendentes; a versão nova o tira
        sozinha). Use quando terminar uma revisão sem render novo (só respostas).
    uv run ferramentas/revisao.py historico <slug>
        todas as revisões do projeto, versão a versão (cada comentário com o bloco e a sua resposta) e os blocos que
        voltaram a ser comentados. É o que a conclusão (14-concluir.md) lê.
    uv run ferramentas/revisao.py encerrar <slug> [--confirmar] [--mesmo-assim]
        o fim do projeto, depois dos exports e dos aprendizados (14-concluir.md): fica só a última versão (a de todos os
        blocos), as revisões, a mídia original e o final/; saem as versões anteriores e o .cache (um render novo refaz).
        Sem --confirmar, só mostra o que sairia e quanto libera. Recusa se a última versão não está aprovada, se há um
        render dele rodando ou uma saída aprovada sem export (--mesmo-assim passa por cima dos dois últimos).
    uv run ferramentas/revisao.py clipes [--refazer]
        recorta das referências os clipes das galerias da biblioteca: presets/clipes/<id>.mp4 (o trecho da 1ª fonte,
        480 px, com som) e transicoes/clipes/<id>.mp4 (1,5 s em volta do corte da 1ª fonte, com som). A referência vem
        de biblioteca/referencias/ (senão, do 18); as externas, de presets/externas/ (senão, do 18).
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import BIBLIOTECA, PROJETOS, RAIZ, ffmpeg, gravar_json, ler_json, pasta, renders_rodando, tamanho  # noqa: E402

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


def curto(s: str, n: int = 60) -> str:
    t = uma_linha(s or '')
    return f'{t[:n - 1]}…' if len(t) > n else t


def versoes_com_revisao(slug: str) -> list[int]:
    return sorted(int(p.stem[1:]) for p in (pasta(slug) / 'revisoes').glob('v*.json') if p.stem[1:].isdigit())


def blocos(slug: str, n: int, rev: dict) -> list[dict]:
    """Os blocos (~30 s) da vN como o app os mostra: os do arquivo dela ou, sem eles, os da última versão anterior que
    tem (o app herda igual). Cada bloco começa numa palavra (id da transcrição) e vai até o começo do próximo; aqui
    ganha `ini`/`fim` nesta versão. Vídeos curtos não têm blocos ([])."""
    defs = rev.get('blocos') or []
    if not defs:
        for x in reversed([x for x in versoes_com_revisao(slug) if x < n]):
            defs = (ler_json(pasta(slug) / 'revisoes' / f'v{x}.json', {}) or {}).get('blocos') or []
            if defs:
                break
    if not defs:
        return []
    vdir = pasta(slug) / 'versoes' / f'v{n}'
    palavras = ler_json(vdir / 'palavras.json', []) or []
    palavras = palavras if isinstance(palavras, list) else palavras.get('palavras', [])
    dur = (ler_json(vdir / 'info.json', {}) or {}).get('duracao') or (palavras[-1]['fim'] if palavras else 0)

    def inicio(pid: str) -> float:
        w = next((w for w in palavras if w['id'] == pid), None) or next((w for w in sorted(palavras, key=lambda w: w['id']) if w['id'] > pid), None)
        return w['ini'] if w else dur

    out = sorted(({**d, 'ini': 0.0 if k == 0 else inicio(d['palavra'])} for k, d in enumerate(defs)), key=lambda b: b['ini'])
    for k, b in enumerate(out):
        b['fim'] = out[k + 1]['ini'] if k + 1 < len(out) else dur
    return [b for b in out if b['fim'] - b['ini'] > 0.05]


def saidas_do(slug: str) -> dict:
    """As saídas do projeto (corpo + final), por id: o comentário feito no final de uma é sobre o final dela."""
    return {x['id']: x for x in (ler_json(pasta(slug) / 'edicao.json', {}) or {}).get('saidas') or [] if isinstance(x, dict) and x.get('final')}


def onde_na_saida(sx: dict | None) -> str:
    """O rótulo de um comentário feito no final de uma saída: o final falado (palavras do bruto, com a direção dele) ou o
    CTA à parte (outro projeto: o comentário se aplica nele)."""
    if not sx:
        return 'Final (saída que não existe mais)'
    f = sx['final']
    alvo = f'CTA {f["cta"]} — aplique no projeto do CTA' if f['tipo'] == 'cta' else 'final falado' if f['tipo'] == 'falado' else 'sem final'
    return f'Final da saída {sx["destino"]} ({alvo})'


def bloco_em(bs: list[dict], t: float | None) -> dict | None:
    if t is None or not bs:
        return None
    return next((b for b in bs if b['ini'] <= t < b['fim']), bs[-1])


def texto(slug: str, v: int, rev: dict, bloco: str | None = None) -> str:
    """A revisão em texto (o cabeçalho do `ler`): os comentários com o tempo, a fala e os prints; com `bloco`, só os
    que caem nele; no fim, os blocos travados."""
    bs = blocos(slug, v, rev)
    b = next((x for x in bs if x['id'] == bloco), None) if bloco else None
    if bloco and not b:
        raise SystemExit(f'Não há o bloco {bloco} na v{v} (blocos: {", ".join(x["id"] for x in bs) or "nenhum"}).')
    linhas = [f'Revisão · {slug} · v{v}' + (f' · bloco {b["id"]} ({tempo(b["ini"])}–{tempo(b["fim"])})' if b else '')]
    cs = [c for c in rev.get('comentarios', []) if tem_conteudo(c) and (not b or (not c.get('geral') and bloco_em(bs, c['t']) is b))]
    sxs = saidas_do(slug)
    for c in sorted(cs, key=ordem):
        fala = f'"{c["fala"]}" — ' if c.get('fala') else ''
        da_saida = f'(saída {sxs.get(c["saida"], {}).get("destino", c["saida"])}) ' if c.get('saida') else ''
        linhas.append(f'[{quando(c)}] {da_saida}{fala}{uma_linha(c.get("texto") or "") or "(ver o print)"}')
        if c.get('anexos'):
            linhas.append(linha_anexos(slug, c['anexos']))
    if not b and ((rev.get('geral') or '').strip() or rev.get('anexos_geral')):  # revisões antigas (o app de agora grava comentários gerais)
        linhas.append(f'Geral: {uma_linha(rev.get("geral") or "") or "(ver o print)"}')
        if rev.get('anexos_geral'):
            linhas.append(linha_anexos(slug, rev['anexos_geral']))
    travados = [x for x in bs if x.get('aprovado')]
    if travados:
        linhas.append('Travados (finalizados, não mexa): ' + ', '.join(f'{x["id"]} {tempo(x["ini"])}–{tempo(x["fim"])}' for x in travados))
    linhas.append(f'(projetos/{slug}/revisoes/v{v}.json)')
    return '\n'.join(linhas)


def versao_da_revisao(slug: str, v: str | None) -> int:
    if v:
        return int(v.lstrip('v'))
    feitas = versoes_com_revisao(slug)
    if not feitas:
        raise SystemExit(f'O projeto {slug} ainda não tem revisão (o criador comenta no app).')
    return feitas[-1]


def ler(slug: str, v: str | None, bloco: str | None = None) -> None:
    n = versao_da_revisao(slug, v)
    p = pasta(slug)
    rev = ler_json(p / 'revisoes' / f'v{n}.json')
    if rev is None:
        raise SystemExit(f'Não há revisão da v{n} (projetos/{slug}/revisoes/v{n}.json).')
    vdir = p / 'versoes' / f'v{n}'
    palavras = ler_json(vdir / 'palavras.json', []) or []
    planos = ler_json(vdir / 'planos.json', []) or []
    bs = blocos(slug, n, rev)

    def palavra_em(t: float) -> dict | None:
        return min(palavras, key=lambda w: 0 if w['ini'] <= t < w['fim'] else min(abs(w['ini'] - t), abs(t - w['fim'])), default=None)

    def planos_em(a: float, b: float) -> list[dict]:
        return [q for q in planos if q['ini'] <= b and q['fim'] > a] if b > a else [q for q in planos if q['ini'] <= a < q['fim']]

    print(texto(slug, n, rev, bloco))
    estado = 'APROVADA' if rev.get('aprovado') else f'enviada em {rev["enviado_em"]}' if rev.get('enviado_em') else 'ainda não enviada'
    pend = [c for c in rev.get('comentarios', []) if tem_conteudo(c) and c.get('status', 'pendente') == 'pendente']
    n_pend = len(pend)
    # qualquer versão com pendentes (o criador comenta a que está vendo, que nem sempre é a última): os blocos se somam.
    # Também numa versão aprovada: comentar depois de aprovar é pedir mais uma mudança, e o app tem de mostrar o loader
    if pend:
        trabalhando(slug, n, bs, pend)  # o app mostra o loader sobre esses blocos até a versão nova
    print(f'\nEstado: {estado} · {n_pend} pendente(s), os que você ainda não respondeu: aplique só esses. '
          f'Para cada um: revisao.py responder {slug} v{n} <id> --status … --resposta "…"')
    if bs:
        print('Blocos: ' + ', '.join(f'{b["id"]} {tempo(b["ini"])}–{tempo(b["fim"])}{" ✓ finalizado" if b.get("aprovado") else ""}' for b in bs))
    for c in sorted(rev.get('comentarios', []), key=ordem):
        if not tem_conteudo(c):
            continue
        b = None if c.get('saida') else bloco_em(bs, None if c.get('geral') else c['t'])
        if bloco and (not b or b['id'] != bloco) and not (bloco == 'Final' and c.get('saida')):
            continue
        fim = c.get('fim')
        if c.get('geral'):
            print(f'\n- {c["id"]} · geral (o vídeo todo) · {c.get("status", "pendente")}')
        else:
            w1 = palavra_em(fim) if fim is not None else None
            ancora = f'palavra {c.get("palavra")}' if w1 is None or w1['id'] == c.get('palavra') else f'palavras {c.get("palavra")}–{w1["id"]}'
            ps = ', '.join(f'{q["id"]} {q["tipo"]} ({tempo(q["ini"])}–{tempo(q["fim"])})' for q in planos_em(c['t'], fim if fim is not None else c['t']))
            nome_bloco = f' · {onde_na_saida(saidas_do(slug).get(c["saida"]))}' if c.get('saida') else f' · {b["id"]}' if b else ''
            print(f'\n- {c["id"]} · {quando(c)}{nome_bloco} · {ancora} · plano {ps or "—"} · {c.get("status", "pendente")}')
        print(f'  {uma_linha(c.get("texto") or "") or "(só o print)"}')
        for a in c.get('anexos') or []:
            print(f'  anexo: projetos/{slug}/{a}{"" if (p / a).is_file() else " (o arquivo sumiu)"}')
        if c.get('resposta'):
            print(f'  ↳ resposta: {c["resposta"]}')
    if not bloco:
        for a in rev.get('anexos_geral') or []:
            print(f'\n- geral · anexo: projetos/{slug}/{a}')
        g = rev.get('resposta_geral')
        if g:
            print(f'\n- geral · {g.get("status")} ↳ {g.get("resposta") or ""}')


def versoes_pendentes(slug: str) -> list[tuple[int, int]]:
    """As versões com comentários sem resposta e quantos: o criador comenta na versão que está vendo, que nem sempre é a
    última (com os blocos, ele revisa um bloco numa versão enquanto outro já foi refeito)."""
    out = []
    for n in versoes_com_revisao(slug):
        rev = ler_json(pasta(slug) / 'revisoes' / f'v{n}.json', {}) or {}
        k = sum(1 for c in rev.get('comentarios', []) if tem_conteudo(c) and c.get('status', 'pendente') == 'pendente')
        if k:
            out.append((n, k))
    return out


def pendentes() -> None:
    """Os projetos com comentários sem resposta (em qualquer versão): é por onde começar quando o criador avisa no chat
    que comentou no app. Os aprovados também entram: comentar depois de aprovar é pedir mais uma mudança."""
    achou = False
    for proj in sorted((x for x in PROJETOS.iterdir() if x.is_dir() and not x.name.startswith(('_', '.'))), key=lambda x: x.name):
        if not versoes_com_revisao(proj.name):
            continue
        pend = versoes_pendentes(proj.name)
        if pend:
            achou = True
            nome = (ler_json(proj / 'edicao.json', {}) or {}).get('nome') or proj.name
            print(f'{proj.name} · {", ".join(f"v{n}: {k}" for n, k in pend)} pendente(s) · {nome}')
    if not achou:
        print('Nenhum comentário pendente.')


def trabalhando(slug: str, n: int, bs: list[dict], pend: list[dict]) -> None:
    """O aviso para o app: o Claude está aplicando os pendentes destes blocos (`revisoes/trabalhando.json`, lido a cada
    4 s; o render da versão nova o apaga)."""
    arq = pasta(slug) / 'revisoes' / 'trabalhando.json'
    antes = ler_json(arq, {}) or {}
    blocos_pend = {('Final' if c.get('saida') else b['id']) for c in pend if c.get('saida') or (b := bloco_em(bs, None if c.get('geral') else c['t']))} | set(antes.get('blocos') or [])
    gravar_json(arq, {
        'versoes': sorted(set(antes.get('versoes') or []) | {n}), 'blocos': sorted(blocos_pend, key=lambda x: (not x[1:].isdigit(), int(x[1:]) if x[1:].isdigit() else 0)),
        'geral': bool(antes.get('geral')) or not bs or any(c.get('geral') for c in pend),
        'fase': 'aplicando', 'desde': antes.get('desde') or datetime.now().isoformat(timespec='seconds')})


def pronto(slug: str) -> None:
    (pasta(slug) / 'revisoes' / 'trabalhando.json').unlink(missing_ok=True)
    print('O aviso de "Claude trabalhando" saiu do app.')


def historico(slug: str) -> None:
    """Todas as revisões do projeto, versão a versão: cada comentário (com o bloco, se o vídeo tem) e a sua resposta;
    no fim, os blocos que voltaram a ser comentados em mais de uma versão (onde a correção não pegou de primeira)."""
    vs = versoes_com_revisao(slug)
    if not vs:
        raise SystemExit(f'O projeto {slug} ainda não tem revisão.')
    voltas: dict[str, list[int]] = {}
    for n in vs:
        rev = ler_json(pasta(slug) / 'revisoes' / f'v{n}.json', {}) or {}
        cs = [c for c in rev.get('comentarios', []) if tem_conteudo(c)]
        if not cs:
            continue
        bs = blocos(slug, n, rev)
        print(f'\n## v{n}{" · APROVADA" if rev.get("aprovado") else ""}')
        for c in sorted(cs, key=ordem):
            b = bloco_em(bs, None if c.get('geral') else c['t'])
            if b:
                voltas.setdefault(b['id'], [])
                if n not in voltas[b['id']]:
                    voltas[b['id']].append(n)
            nome_bloco = f' · {b["id"]}' if b else ''
            print(f'\n- v{n}·{c["id"]} [{quando(c)}{nome_bloco}] {curto(c.get("texto"), 200) or "(só o print)"}')
            print(f'  Claude ({c.get("status", "pendente")}): {c.get("resposta") or "(sem resposta)"}')
    repetidos = {k: v for k, v in voltas.items() if len(v) > 1}
    if repetidos:
        print('\nBlocos comentados em mais de uma versão (a correção não pegou de primeira): '
              + ', '.join(f'{k} ({", ".join(f"v{x}" for x in v)})' for k, v in sorted(repetidos.items(), key=lambda kv: int(kv[0][1:]))))


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
    rev['mexido_em'] = datetime.now().isoformat(timespec='seconds')  # a data do card: o Claude respondeu
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


def encerrar(slug: str, confirmar: bool = False, mesmo_assim: bool = False) -> None:
    """Encerra o projeto: apaga as versões anteriores à última e o .cache (ver o docstring do módulo)."""
    import shutil
    p = pasta(slug)
    vs = sorted(int(d.name[1:]) for d in (p / 'versoes').glob('v*') if d.name[1:].isdigit())
    if not vs:
        raise SystemExit(f'{slug} não tem versões.')
    ultima = vs[-1]
    edicao = ler_json(p / 'edicao.json', {}) or {}
    rev = ler_json(p / 'revisoes' / f'v{ultima}.json', {}) or {}
    if not rev.get('aprovado'):
        raise SystemExit(f'{slug}: a v{ultima} não está aprovada. Encerre só depois de aprovar e exportar.')
    avisos = []
    if slug in renders_rodando():
        avisos.append('há um render deste projeto rodando agora')
    falta = [x['destino'] for x in edicao.get('saidas') or [] if isinstance(x, dict) and x.get('final') and x.get('aprovado') and not x.get('exportado')]
    if falta:
        avisos.append(f'saídas aprovadas ainda sem export: {", ".join(falta)}')
    alvos = [p / 'versoes' / f'v{v}' for v in vs[:-1]] + sorted((p / 'versoes').glob('.v*.parte')) + sorted(p.glob('.render-*'))
    if (p / '.cache').is_dir():
        alvos.append(p / '.cache')
    total = sum(tamanho(a) for a in alvos)
    print(f'Encerrar {slug}: fica a v{ultima} (a última de todos os blocos), as revisões, a mídia original e o final/.')
    for a in alvos:
        print(f'  sai {a.relative_to(p)}  {tamanho(a) / 1e9:.2f} GB')
    print(f'Libera {total / 1e9:.1f} GB.' if alvos else 'Nada a apagar: já está encerrado.')
    for x in avisos:
        print(f'Atenção: {x}.')
    if not confirmar or not alvos:
        if alvos:
            print(f'Nada apagado. Para encerrar: uv run ferramentas/revisao.py encerrar {slug} --confirmar')
        return
    if avisos and not mesmo_assim:
        raise SystemExit('Não encerrei por causa da atenção acima (resolva, ou --mesmo-assim se o criador mandar).')
    for a in alvos:
        shutil.rmtree(a, ignore_errors=True)
    edicao['encerrado_em'] = datetime.now().isoformat(timespec='seconds')
    gravar_json(p / 'edicao.json', edicao)
    print(f'Encerrado: {total / 1e9:.1f} GB liberados.')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('ler')
    a.add_argument('slug')
    a.add_argument('versao', nargs='?')
    a.add_argument('--bloco')
    a = sub.add_parser('responder')
    a.add_argument('slug')
    a.add_argument('versao')
    a.add_argument('id')
    a.add_argument('--status', required=True)
    a.add_argument('--resposta', default='')
    sub.add_parser('pendentes')
    a = sub.add_parser('pronto')
    a.add_argument('slug')
    a = sub.add_parser('historico')
    a.add_argument('slug')
    a = sub.add_parser('encerrar')
    a.add_argument('slug')
    a.add_argument('--confirmar', action='store_true')
    a.add_argument('--mesmo-assim', action='store_true')
    a = sub.add_parser('clipes')
    a.add_argument('--refazer', action='store_true')
    x = ap.parse_args()
    if x.cmd == 'ler':
        pend = [] if x.versao else versoes_pendentes(x.slug)
        if len(pend) > 1:  # sem dizer a versão: os pendentes de todas (ele comentou em mais de uma)
            print(f'Pendentes em {len(pend)} versões: {", ".join(f"v{n}" for n, _ in pend)}. Todos vão para a versão nova.')
            for n, _ in pend:
                print(f'\n{"=" * 30} v{n} {"=" * 30}')
                ler(x.slug, f'v{n}', x.bloco)
        else:
            ler(x.slug, x.versao or (f'v{pend[0][0]}' if pend else None), x.bloco)
    elif x.cmd == 'responder':
        responder(x.slug, x.versao, x.id, x.status, x.resposta)
    elif x.cmd == 'pendentes':
        pendentes()
    elif x.cmd == 'pronto':
        pronto(x.slug)
    elif x.cmd == 'historico':
        historico(x.slug)
    elif x.cmd == 'encerrar':
        encerrar(x.slug, x.confirmar, x.mesmo_assim)
    else:
        clipes(x.refazer)
