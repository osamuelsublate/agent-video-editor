"""A montagem do vídeo (do 18: backend/app/exportacao.py, SPEC §13): o ator e o áudio saem do bruto original pelo ffmpeg
(cortes, recorte 9:16, fade curto em cada emenda) e a camada dos inserts é a própria página de render, fotografada quadro
a quadro por navegadores escondidos (`render_quadros.py`). Tudo se junta numa passada só do ffmpeg (`comando_final`),
montada por camadas, uma função por camada. A cola (ler a página, fotografar, rodar) fica em `ferramentas/render.py`."""
import math
from pathlib import Path

from . import audio as audio_mod
from . import legenda as legenda_mod
from . import look as look_mod
from . import sons
from . import transicoes as transicoes_mod

NAVEGADORES = 8  # navegadores fotografando em paralelo
FADE = 0.015  # s de fade do áudio em cada emenda, contra estalos


def dur_saida(c: dict) -> float:
    """Quanto um clipe da V1 dura no vídeo final (acelerado por `vel`). Do 18: backend/app/projeto.py."""
    return (c['fim'] - c['inicio']) / c.get('vel', 1)


JANELA = {'y0': 0.72, 'escala': 0.55, 'raio': 0.07}  # o ator no "insert atrás" (igual a presets/divisao.ts; raio em fração da largura do ator encolhido)


ZOOM_LENTO = {'por_segundo': 0.03, 'maximo': 0.15}  # os presets do Full ator (iguais a `ator/movimento.ts`)
ZOOM_SECO = 0.18


def _movimentos(movimentos: list[dict], w: int, h: int, entrada: str, saida: str) -> str:
    """O movimento de câmera no ator nos planos de Full ator (`__render.movimentos`: ini, fim, tipo, cx, cy): a escala no
    tempo (o lento sai e chega andando: metade linear, metade suavizada; o seco salta de uma vez) e o recorte que deixa o
    centro do rosto parado. A mesma conta de `escalaDoMovimento` na prévia."""
    z, cx, cy = [], [], []
    for m in movimentos:
        a, b = float(m['ini']), float(m['fim'])
        if b - a < 0.02:
            continue
        dentro = f'between(t,{a:.4f},{b:.4f})'
        if m['tipo'] == 'zoom_seco':
            z.append(f'{dentro}*{ZOOM_SECO}')
        else:
            amp = min(ZOOM_LENTO['por_segundo'] * (b - a), ZOOM_LENTO['maximo'])
            u = f'clip((t-{a:.4f})/{b - a:.4f},0,1)'
            z.append(f'{dentro}*{amp:.4f}*(0.5*{u}+0.5*{u}*{u}*(3-2*{u}))')
        cx.append(f'{dentro}*({float(m.get("cx", 0.5)):.4f}-0.5)')
        cy.append(f'{dentro}*({float(m.get("cy", 0.4)):.4f}-0.5)')
    if not z:
        return f'[{entrada}]null[{saida}]'
    zt, xt, yt = '+'.join(z), '+'.join(cx), '+'.join(cy)
    return (f"[{entrada}]scale=w='trunc(iw*(1+{zt})/2)*2':h='trunc(ih*(1+{zt})/2)*2':eval=frame:flags=bicubic,"
            f"crop={w}:{h}:x='(iw-ow)*(0.5+{xt})':y='(ih-oh)*(0.5+{yt})',setsar=1[{saida}]")


def acelerar(vel: float) -> tuple[str, str]:
    """Os filtros de um clipe acelerado: o `setpts` do vídeo e o `atempo` do áudio (com a vírgula; vazio a 1×)."""
    if abs(vel - 1) < 1e-6:
        return 'setpts=PTS-STARTPTS', ''
    return f'setpts=(PTS-STARTPTS)/{vel:.4f}', f'atempo={vel:.4f},'


def _ator(clipes: list[dict], horizontal: bool, enquadramento_x: float, w: int, h: int, fps: int,
          divisoes: list[tuple[float, float, dict]], duracao: float, mascara: bool, com_look: bool = False,
          movimentos: list[dict] | None = None) -> tuple[list[str], list[str]]:
    """Os filtros do ator e do áudio (entrada 0 = bruto; 1 = a máscara da pessoa, se houver): cada clipe da V1 vira um
    par vídeo + áudio (o áudio com fade curto nas pontas) e o concat mantém os dois juntos em cada emenda; depois, recorte
    9:16, escala, fps de saída (o ator repete quadros, sem interpolar) e o ator descendo para a parte de baixo nas telas
    divididas (metade de `f` da altura). Devolve os filtros de baixo (saídas [base] e [ac]) e os de cima, aplicados depois
    dos inserts sobre [topo_in] → [topo]: o ator na janela do "insert atrás" e a pessoa recortada saindo da área dele.
    `com_look`: o ator escalado sai em [ator_cru] e o look (`look.filtros`, ligado em `comando_final`) faz o [ator].
    `movimentos`: os presets do Full ator (zoom no ator, antes do look: a vinheta não aproxima junto)."""
    n = len(clipes)
    # a geometria do ator (P5, `ator/ator.ts`): quando a página de render a manda, o ator é posto por ela
    geometria = any(d.get('ator') for _, _, d in divisoes)
    if geometria:
        usa_mascara = mascara and any((d.get('ator') or {}).get('modo') in ('janela', 'recortado') for _, _, d in divisoes)
    else:
        usa_mascara = mascara and any(d['modo'] == 'atras' for _, _, d in divisoes)  # a cabeça sai por cima só no "ator embaixo"
    partes = [f'[0:v]split={n}' + ''.join(f'[v{k}]' for k in range(n)), f'[0:a]asplit={n}' + ''.join(f'[a{k}]' for k in range(n))]
    if usa_mascara:
        partes.append(f'[1:v]split={n}' + ''.join(f'[m{k}]' for k in range(n)))
    videos, audios, masc = '', '', ''
    acc = 0.0  # o começo do clipe no vídeo final
    for k, c in enumerate(clipes):
        ini, fim = c['inicio'], c['fim']
        dur, vel = dur_saida(c), c.get('vel', 1)
        # acelerado (`vel`, a aceleração do ator): o vídeo com os tempos divididos e o áudio no atempo (mantém o tom)
        setpts, atempo = acelerar(vel)
        # o vídeo do clipe ocupa exatamente os quadros do vídeo final que começam dentro dele (a ≤ t < b, a regra de
        # `quadros` e das camadas de cima), cada um com o quadro do bruto daquele instante. Antes, o clipe saía com os
        # quadros inteiros do bruto (23,976/s) e o concat cobria a sobra repetindo o último quadro do clipe anterior: um
        # quadro "perdido" do ator na pose de antes logo depois de cada corte (mvi-0717 v5 c1–c3)
        q0, q1 = math.ceil(acc * fps - 1e-9), math.ceil((acc + dur) * fps - 1e-9)
        ini_v = ini + (q0 / fps - acc) * vel
        # `desde_v` (o proxy por trechos, num trecho que começa no meio do clipe): o vídeo cortado de onde o clipe inteiro
        # começa, pulando os quadros de antes do trecho; o `fps` ancora a grade no 1º quadro do bruto depois do corte, e
        # cortado no começo do trecho ela saía até 1 quadro fora da do vídeo inteiro
        ini_v, pular = c.get('desde_v') or (ini_v, 0)
        no_grid = f'{setpts},fps={fps},tpad=stop_mode=clone:stop_duration=0.5,trim=start_frame={pular}:end_frame={pular + q1 - q0},setpts=PTS-STARTPTS'
        # o vídeo vai 1 quadro além do fim: o último quadro do clipe pega o quadro do bruto mais próximo do seu instante,
        # que às vezes cai logo depois do `fim` (bruto a 23,976/s); cortado no `fim`, ele virava uma cópia do anterior
        # (um quadro repetido antes de cada corte, mvi-0719 v1). O quadro a mais é a continuação da mesma tomada
        fim_v = fim + vel / fps
        partes.append(f'[v{k}]trim=start={ini_v:.4f}:end={fim_v:.4f},{no_grid}[cv{k}]')
        partes.append(f'[a{k}]atrim=start={ini:.4f}:end={fim:.4f},asetpts=PTS-STARTPTS,{atempo}'
                      f'afade=t=in:d={FADE},afade=t=out:st={max(dur - FADE, 0):.4f}:d={FADE}[ca{k}]')
        videos += f'[cv{k}]'
        audios += f'[ca{k}]'
        if usa_mascara:
            partes.append(f'[m{k}]trim=start={ini_v:.4f}:end={fim_v:.4f},{no_grid}[cm{k}]')
            masc += f'[cm{k}]'
        acc += dur
    # o vídeo e o áudio emendados cada um por si: o vídeo em quadros exatos do vídeo final, o áudio no tempo exato
    partes.append(f'{videos}concat=n={n}:v=1:a=0[vc]')
    partes.append(f'{audios}concat=n={n}:v=0:a=1[ac]')
    recorte = f"crop=w=trunc(ih*9/16/2)*2:h=ih:x=(iw-ow)*{enquadramento_x:.4f}," if horizontal else ''
    rotulo = 'ator_cru' if com_look else 'ator'
    partes.append(f'[vc]{recorte}scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},setsar=1,fps={fps}[{'ator_mv' if movimentos else rotulo}]')
    if movimentos:
        partes.append(_movimentos(movimentos, w, h, 'ator_mv', rotulo))
    if geometria:
        if usa_mascara:
            partes.append(f'{masc}concat=n={n}:v=1:a=0,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray,fps={fps}[masc]')
        topo = _ator_na_geometria(partes, divisoes, w, h, fps, duracao, usa_mascara)
        return partes, topo
    quando = lambda ts: '+'.join(f'between(t,{a:.4f},{b - 0.5 / fps:.4f})' for a, b in ts) or '0'  # noqa: E731
    metades = [(a, b, d['f']) for a, b, d in divisoes if d['modo'] == 'metade']
    atras = [(a, b) for a, b, d in divisoes if d['modo'] == 'atras']
    # o ator desce metade da fração do insert (o centro do quadro vai para o meio da parte de baixo)
    desce = '+'.join(f'between(t,{a:.4f},{b - 0.5 / fps:.4f})*{f / 2:.5f}*H' for a, b, f in metades) or '0'
    usos = 1 + (1 if atras else 0) + (1 if usa_mascara else 0)
    partes.append(f'[ator]split={usos}[ator0]' + ('[ator1]' if atras else '') + ('[ator2]' if usa_mascara else ''))
    partes.append(f'color=c=black:s={w}x{h}:r={fps}:d={duracao:.4f}[tela]')
    partes.append(f"[tela][ator0]overlay=x=0:y='{desce}':eval=frame:shortest=1[base]")
    topo: list[str] = []
    atual = 'topo_in'
    jw, jh = round(w * JANELA['escala'] / 2) * 2, round(h * JANELA['escala'] / 2) * 2
    jx, jy_ator = (w - jw) // 2, h - jh  # o ator encolhido, apoiado embaixo e centrado
    corte = round(h * JANELA['y0']) - jy_ator  # a janela começa aqui, dentro do ator encolhido
    if atras:
        r = round(jw * JANELA['raio'])
        janela_h = jh - corte
        topo.append(f'[ator1]scale={jw}:{jh},crop={jw}:{janela_h}:0:{corte},format=rgba[jan]')
        topo.append(f"color=c=white:s={jw}x{janela_h}:r={fps},format=gray,geq=lum='255*lte(hypot(max(0,max({r}-X,X-{jw - r})),"
                    f"max(0,max({r}-Y,Y-{janela_h - r}))),{r})'[cantos]")
        topo.append('[jan][cantos]alphamerge[janr]')
        topo.append(f"[{atual}][janr]overlay=x={jx}:y={jy_ator + corte}:enable='{quando([(a, b) for a, b in atras])}'[t1]")
        atual = 't1'
    if usa_mascara:
        partes.append(f'{masc}concat=n={n}:v=1:a=0,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=gray,fps={fps}[masc]')
        partes.append('[ator2][masc]alphamerge[pessoa]')
        fs: list[float] = []
        saidas = len(fs) + (1 if atras else 0)
        topo.append(f'[pessoa]split={saidas}' + ''.join(f'[p{i}]' for i in range(saidas)))
        for i, f in enumerate(fs):
            y = round(f / 2 * h)
            topo.append(f'[p{i}]crop={w}:{y}:0:0[pc{i}]')
            topo.append(f"[{atual}][pc{i}]overlay=x=0:y={y}:enable='{quando([(a, b) for a, b, g in metades if g == f])}'[tp{i}]")
            atual = f'tp{i}'
        if atras:
            topo.append(f'[p{len(fs)}]scale={jw}:{jh},crop={jw}:{corte}:0:0[pj]')
            topo.append(f"[{atual}][pj]overlay=x={jx}:y={jy_ator}:enable='{quando(atras)}'[tpj]")
            atual = 'tpj'
    topo.append(f'[{atual}]null[topo]')
    return partes, topo


def _par(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _cantos(w: int, h: int, r: int, fps: int, dur: float, rotulo: str) -> str:
    """Uma máscara de cantos redondos (raio `r` px) do tamanho do ator, para o `alphamerge`."""
    return (f"color=c=white:s={w}x{h}:r={fps}:d={dur:.4f},format=gray,"
            f"geq=lum='255*lte(hypot(max(0,max({r}-X,X-{w - r})),max(0,max({r}-Y,Y-{h - r}))),{r})'[{rotulo}]")


def _desde(a: float, fps: int) -> str:
    """Leva um pedaço recortado do ator (começando em 0) de volta ao instante `a` com quadros transparentes antes dele, no
    lugar de só empurrar o tempo (`setpts=PTS+a/TB`): sem quadros até `a`, o overlay esperava o primeiro e guardava na
    fila todos os quadros do ator de 0 até `a` (a memória crescia com o instante do insert, gigabytes num insert tardio).
    `n`: os quadros do ator (um a cada 1/fps desde 0) antes de `a`, então o primeiro do pedaço cai no instante dele."""
    n = math.ceil(a * fps - 1e-6)
    return f'tpad=start={n}:color=black@0' if n > 0 else 'null'


def _ator_na_geometria(partes: list[str], divisoes: list[tuple[float, float, dict]], w: int, h: int, fps: int, duracao: float,
                       usa_mascara: bool) -> list[str]:
    """O ator posto pela geometria de cada trecho dividido (P5; `ator/ator.ts`): `{modo, s, tx, ty, topo?, raio?}` —
    o quadro do ator com o canto de cima à esquerda em (tx, ty) e a escala s, em frações do quadro.
    - `metade` (tela dividida): o ator inteiro, ampliado e deslocado pelo rosto, embaixo dos inserts ([base]);
    - `janela`, `canto`: o ator encolhido por cima dos inserts — a janela (só de `topo` para baixo) ou o quadro inteiro,
      com os cantos redondos; `recortado`: só a pessoa (a máscara). Na janela, a pessoa recortada sai por cima dela.
    Cada trecho por cima é um pedaço recortado do ator (só aqueles quadros são escalados). Acrescenta os filtros de baixo
    em `partes` (saída [base]) e devolve os de cima, de [topo_in] a [topo]."""
    quando = lambda a, b: f'gte(t,{a - 1e-4:.5f})*lt(t,{b - 1e-4:.5f})'  # noqa: E731  (a ≤ t < b, como `quadros`)
    # o ator embaixo (metade): o quadro n (t = n/fps) é do trecho em que ele cai, a ≤ t < b — a mesma regra das camadas de
    # cima (o 1º quadro de um trecho é o ceil(a·fps)). Com o `quando`, um quadro a menos de meio quadro do fim ficava fora
    # dos dois trechos e o ator saía sem o enquadramento (mvi-0717 v2 c6, v3 c1: o rosto some e aparece o notebook)
    na_faixa = lambda a, b: f'gte(t,{a - 1e-4:.5f})*lt(t,{b - 1e-4:.5f})'  # noqa: E731
    metades = [(a, b, d['ator']) for a, b, d in divisoes if (d.get('ator') or {}).get('modo') == 'metade']
    sobre = [(a, b, d['ator']) for a, b, d in divisoes if (d.get('ator') or {}).get('modo') in ('janela', 'canto', 'recortado', 'caixa')]
    # sem a máscara (o recorte do ator não ficou pronto), o recortado vira o ator inteiro num canto
    if not usa_mascara:
        sobre = [(a, b, {**g, 'modo': 'canto', 'raio': g.get('raio') or 0.07} if g['modo'] == 'recortado' else g) for a, b, g in sobre]
    quadros = [(a, b, g) for a, b, g in sobre if g['modo'] in ('janela', 'canto', 'caixa')]
    pessoas = [(a, b, g) for a, b, g in sobre if g['modo'] in ('janela', 'recortado')] if usa_mascara else []
    usos = 1 + len(quadros) + (1 if pessoas else 0)
    partes.append(f'[ator]split={usos}[ator0]' + ''.join(f'[aq{i}]' for i in range(len(quadros))) + ('[ator2]' if pessoas else ''))
    partes.append(f'color=c=black:s={w}x{h}:r={fps}:d={duracao:.4f}[tela]')
    # a tela dividida: escala e posição por trecho (fora dos trechos, o ator como foi gravado)
    escala = '+'.join(f"{na_faixa(a, b)}*{g['s'] - 1:.5f}" for a, b, g in metades if abs(g['s'] - 1) > 1e-4)
    x = '+'.join(f"{na_faixa(a, b)}*{g['tx']:.5f}*W" for a, b, g in metades if abs(g['tx']) > 1e-5) or '0'
    y = '+'.join(f"{na_faixa(a, b)}*{g['ty']:.5f}*H" for a, b, g in metades if abs(g['ty']) > 1e-5) or '0'
    ator0 = 'ator0'
    if escala:
        partes.append(f"[ator0]scale=w='trunc(iw*(1+{escala})/2)*2':h='trunc(ih*(1+{escala})/2)*2':eval=frame[ator0s]")
        ator0 = 'ator0s'
    partes.append(f"[tela][{ator0}]overlay=x='{x}':y='{y}':eval=frame:shortest=1[base]")
    topo: list[str] = []
    atual = 'topo_in'
    for i, (a, b, g) in enumerate(quadros):
        sw, sh = _par(g['s'] * w), _par(g['s'] * h)
        x0, y0 = round(g['tx'] * w), round(g['ty'] * h)
        if g['modo'] == 'caixa':  # um recorte do ator ampliado, na caixa (REF-15·p42)
            c = g['caixa']
            cw, ch = _par(c['w'] * w), _par(c['h'] * h)
            cx, cy = max(0, round((c['x'] - g['tx']) * w)), max(0, round((c['y'] - g['ty']) * h))
            r = max(1, round((g.get('raio') or 0) * cw))
            topo.append(f'[aq{i}]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,scale={sw}:{sh},crop={cw}:{ch}:{min(cx, sw - cw)}:{min(cy, sh - ch)},format=rgba[q{i}]')
            topo.append(_cantos(cw, ch, r, fps, b - a, f'qc{i}'))
            topo.append(f'[q{i}][qc{i}]alphamerge,{_desde(a, fps)}[qr{i}]')
            topo.append(f"[{atual}][qr{i}]overlay=x={round(c['x'] * w)}:y={round(c['y'] * h)}:eof_action=pass:enable='{quando(a, b)}'[tq{i}]")
            atual = f'tq{i}'
            continue
        corte = _par((g.get('topo') or 0) * sh) if g['modo'] == 'janela' else 0
        qh = sh - corte
        r = max(1, round((g.get('raio') or 0) * sw))
        topo.append(f'[aq{i}]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,scale={sw}:{sh},crop={sw}:{qh}:0:{corte},format=rgba[q{i}]')
        topo.append(_cantos(sw, qh, r, fps, b - a, f'qc{i}'))
        topo.append(f'[q{i}][qc{i}]alphamerge,{_desde(a, fps)}[qr{i}]')
        topo.append(f"[{atual}][qr{i}]overlay=x={x0}:y={y0 + corte}:eof_action=pass:enable='{quando(a, b)}'[tq{i}]")
        atual = f'tq{i}'
    if pessoas:
        # o ator e a máscara são cortados no trecho antes de se juntarem: o alphamerge (que espera as duas entradas) só
        # recebe os quadros do trecho, e nada do ator antes dele fica guardado esperando a máscara
        n = len(pessoas)
        partes.append('[ator2]split=' + str(n) + ''.join(f'[pa{i}]' for i in range(n)))
        partes.append('[masc]split=' + str(n) + ''.join(f'[pm{i}]' for i in range(n)))
        for i, (a, b, g) in enumerate(pessoas):
            sw, sh = _par(g['s'] * w), _par(g['s'] * h)
            x0, y0 = round(g['tx'] * w), round(g['ty'] * h)
            # na janela, só a parte de cima (a cabeça e os ombros saindo dela); no recortado, a pessoa inteira
            alto = _par((g.get('topo') or 0) * sh) if g['modo'] == 'janela' else sh
            corte = f'trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS'
            topo.append(f'[pa{i}]{corte}[pat{i}]')
            topo.append(f'[pm{i}]{corte}[pmt{i}]')
            topo.append(f'[pat{i}][pmt{i}]alphamerge,scale={sw}:{sh},crop={sw}:{alto}:0:0,{_desde(a, fps)}[pq{i}]')
            topo.append(f"[{atual}][pq{i}]overlay=x={x0}:y={y0}:eof_action=pass:enable='{quando(a, b)}'[tp{i}]")
            atual = f'tp{i}'
    topo.append(f'[{atual}]null[topo]')
    return topo


def _inserts(camadas: list[tuple[Path, float]], primeira_entrada: int, rotulo_in: str, saida: str) -> tuple[list[str], list[str]]:
    """Camada 2 (SPEC §13): cada clipe da camada dos inserts e motions (ProRes 4444 com transparência, fotografado pelos
    navegadores) sobreposto no seu instante. Devolve (entradas, filtros), de [`rotulo_in`] a [`saida`]."""
    entradas: list[str] = []
    filtros: list[str] = []
    atual = rotulo_in
    for k, (clipe, inicio) in enumerate(camadas):
        entradas += ['-i', str(clipe)]
        filtros.append(f'[{k + primeira_entrada}:v]setpts=PTS-STARTPTS+{inicio:.6f}/TB[c{k}]')
        filtros.append(f'[{atual}][c{k}]overlay=format=auto:eof_action=pass[o{k}]')
        atual = f'o{k}'
    filtros.append(f'[{atual}]null[{saida}]')
    return entradas, filtros


def _transicoes(transicoes: list[dict] | None, rotulo_in: str, w: int, h: int, primeira_entrada: int,
                fps: int = 30) -> tuple[list[str], list[str], str]:
    """Camada 4 (SPEC §13, §8.8): as transições entre planos, sobre o quadro já montado (`transicoes.filtros`: zoom com
    desfoque, brilho e a luz colorida, só nas janelas delas). Recebe `__render.transicoes`. Devolve (entradas, filtros,
    rótulo de saída); sem transições com efeito, nada."""
    if not any(x.get('tipo') in ('luz', 'brilho', 'zoom') for x in transicoes or []):
        return [], [], rotulo_in
    entradas, f = transicoes_mod.filtros(transicoes, rotulo_in, 'tr', w, h, primeira_entrada, fps)
    return entradas, f, 'tr'


def _legenda(legenda: dict | None, rotulo_in: str) -> tuple[list[str], str]:
    """Camada 5 (SPEC §13, §8.10; a P4): a legenda por cima de tudo, um ASS (`legenda.escrever`, dos blocos de
    `__render.legenda`) desenhado pelo libass. `legenda`: `{arquivo: Path}`; sem arquivo, nada. Devolve (filtros,
    rótulo de saída)."""
    if not legenda or not legenda.get('arquivo'):
        return [], rotulo_in
    return [f'[{rotulo_in}]{legenda_mod.filtro(legenda["arquivo"])}[leg]'], 'leg'


def _pos_montagem(transicoes: list[dict] | None, legenda: dict | None, rotulo_in: str, saida: str, w: int, h: int,
                  primeira_entrada: int, fps: int = 30) -> tuple[list[str], list[str]]:
    """O que age sobre o quadro inteiro já montado: as transições e, por cima de tudo, a legenda; no fim, o formato de
    saída. Devolve (entradas, filtros)."""
    entradas, filtros, atual = _transicoes(transicoes, rotulo_in, w, h, primeira_entrada, fps)
    f_leg, atual = _legenda(legenda, atual)
    return entradas, [*filtros, *f_leg, f'[{atual}]format=yuv420p[{saida}]']


def _audio(eventos_som: list[dict] | None, primeira_entrada: int, rotulo_voz: str, saida: str, clipes: list[dict],
           duracao: float, audio: dict | None = None) -> tuple[list[str], list[str]]:
    """Camada A (SPEC §13, §8.6, §8.8, §8.9): sem `audio`, a voz do bruto (já cortada, [`rotulo_voz`]) com os sons
    somados — os de apoio dos presets e os das transições (os dois vêm em `__render.sons`). Com `audio` (a P3,
    `audio.da_exportacao`), a voz vem de uma entrada própria (a limpa, cortada igual) com o timbre, o compressor e os
    faders, o fundo com ducking e o −14 LUFS (`audio.filtros`); a voz do bruto é descartada. Devolve (entradas,
    filtros), com a mistura em [`saida`]. `audio['pronta']`: a mistura já feita (um WAV, do cache do render), só lida."""
    if audio is None:
        return sons.filtro_mistura(eventos_som or [], primeira_entrada, rotulo_voz, saida)
    if audio.get('pronta'):
        return ['-i', str(audio['pronta'])], [f'[{rotulo_voz}]anullsink', f'[{primeira_entrada}:a]anull[{saida}]']
    entradas, filtros = audio_mod.filtros(audio, clipes, eventos_som or [], primeira_entrada, saida, duracao, audio.get('medida'))
    return entradas, [f'[{rotulo_voz}]anullsink', *filtros]


def comando_final(bruto: Path, clipes: list[dict], horizontal: bool, enquadramento_x: float, w: int, h: int, fps: int,
                  divisoes: list[tuple[float, float, dict]], camadas: list[tuple[Path, float]], codec: str, duracao: float,
                  saida: Path, mascara: Path | None = None, eventos_som: list[dict] | None = None,
                  transicoes: list[dict] | None = None, legenda: dict | None = None, look: dict | None = None,
                  mascara_vinheta: Path | None = None, audio: dict | None = None, movimentos: list[dict] | None = None,
                  hwaccel: bool = True) -> list[str]:
    """Uma passada só, montada por camadas na ordem do contrato (SPEC §13; cada área mexe só na sua função): o ator e o
    áudio do bruto, decodificado pelo chip de vídeo (`_ator`); por cima, a camada dos inserts (`_inserts`); por cima
    dela, o ator na janela do "insert atrás" e a pessoa recortada (a parte de cima de `_ator`); depois, sobre o quadro
    montado, as transições e a legenda (`_pos_montagem`); o áudio (`_audio`). Codifica no chip de vídeo (HEVC ou H.264).
    Entradas do ffmpeg, nesta ordem: o bruto, a máscara (se usada), os clipes dos inserts, os sons e a máscara da
    vinheta do look (se houver; lida uma vez e repetida pelo filtro `loop`). O look (LUT + vinheta, `look.py`) vale só
    para o ator, logo depois da escala. `hwaccel`: decodificar o bruto no chip de vídeo (no 4K compensa; num vídeo leve,
    como o proxy 720p, trazer cada quadro do chip de volta custa mais que decodificar no processador)."""
    com_look = look_mod.ativo(look)
    partes, topo = _ator(clipes, horizontal, enquadramento_x, w, h, fps, divisoes, duracao, mascara is not None, com_look, movimentos)
    usa_mascara = any('[1:v]' in x for x in partes)
    base_idx = 2 if usa_mascara else 1
    entradas: list[str] = ['-i', str(mascara)] if usa_mascara else []
    ent_ins, f_ins = _inserts(camadas, base_idx, 'base', 'topo_in')
    ent_som, f_som = _audio(eventos_som, base_idx + len(camadas), 'ac', 'am', clipes, duracao, audio)
    entradas += ent_ins + ent_som
    if com_look:
        idx_vinheta = None
        if mascara_vinheta is not None and look_mod.VINHETAS.get(look.get('vinheta'), 0) > 0:
            idx_vinheta = base_idx + len(camadas) + ent_som.count('-i')
            entradas += ['-i', str(mascara_vinheta)]
        partes += look_mod.filtros(look, 'ator_cru', 'ator', idx_vinheta, h)
    ent_pos, f_pos = _pos_montagem(transicoes, legenda, 'topo', 'v', w, h, 1 + entradas.count('-i'), fps)
    entradas += ent_pos
    partes += f_ins + f_som + topo + f_pos
    cv = ['-c:v', 'hevc_videotoolbox', '-q:v', '65', '-tag:v', 'hvc1'] if codec == 'hevc' else ['-c:v', 'h264_videotoolbox', '-q:v', '65']
    return ['ffmpeg', '-y', '-loglevel', 'error', '-progress', 'pipe:1', '-nostats', *(['-hwaccel', 'videotoolbox'] if hwaccel else []), '-i', str(bruto),
            *entradas, '-filter_complex', ';'.join(partes), '-map', '[v]', '-map', '[am]', *cv, '-pix_fmt', 'yuv420p',
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
            '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-t', f'{duracao:.4f}', '-movflags', '+faststart', str(saida)]


def quadros(t: dict, fps: int) -> range:
    """Os quadros do vídeo final (índices) em que o trecho aparece: os que começam em [ini, fim)."""
    return range(math.ceil(t['ini'] * fps - 1e-9), math.ceil(t['fim'] * fps - 1e-9))


def fotos(t: dict, fps: int) -> list[float]:
    """Os instantes fotografados de um trecho: a grade dele mesmo (ini + j/fps), com fotos para qualquer fase (ceil da
    duração em quadros). O quadro q0 + j do vídeo mostra a foto j: no máximo 1 quadro atrás do instante exato, e a mesma
    foto serve em qualquer instante do vídeo (os cortes movem o trecho; o cache do render reaproveita)."""
    return [t['ini'] + j / fps for j in range(math.ceil(round((t['fim'] - t['ini']) * fps, 6)))]


def pedacos(trechos: list[dict], fps: int, navegadores: int) -> list[list[list[float]]]:
    """Os instantes fotografados de cada trecho (`fotos`), cortados em pedaços para dividir entre os navegadores: pedaços
    pequenos o bastante para todos trabalharem até o fim, grandes o bastante para não perder tempo trocando."""
    por_trecho = [fotos(t, fps) for t in trechos]
    total = sum(map(len, por_trecho))
    tamanho = max(12, min(48, math.ceil(total / (navegadores * 3)) if total else 12))
    return [[ts[i:i + tamanho] for i in range(0, len(ts), tamanho)] for ts in por_trecho if ts]
