(() => {
  // src/curvas.ts
  var solvers = /* @__PURE__ */ new Map();
  function bezier(x1, y1, x2, y2) {
    const chave = `${x1},${y1},${x2},${y2}`;
    let f = solvers.get(chave);
    if (!f) solvers.set(chave, f = montar(x1, y1, x2, y2));
    return f;
  }
  var limite01 = (v) => Math.max(0, Math.min(1, v));
  function montar(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const x = (s) => ((ax * s + bx) * s + cx) * s;
    const dx = (s) => (3 * ax * s + 2 * bx) * s + cx;
    const y = (s) => ((ay * s + by) * s + cy) * s;
    return (t) => {
      if (t <= 0) return 0;
      if (t >= 1) return 1;
      let s = t;
      for (let i = 0; i < 8; i++) {
        const d = dx(s);
        if (Math.abs(d) < 1e-6) break;
        s -= (x(s) - t) / d;
      }
      s = Math.min(1, Math.max(0, s));
      for (let i = 0, a = 0, b = 1; i < 20 && Math.abs(x(s) - t) > 1e-5; i++) {
        if (x(s) < t) a = s;
        else b = s;
        s = (a + b) / 2;
      }
      return y(s);
    };
  }

  // src/presets.ts
  var limite = limite01;
  var NEUTRO = { dx: 0, dy: 0, escala: 1, altura: 1, rot: 0, rx: 0, ry: 0, opacidade: 1, desfoque: 0 };
  function noTempo(r, dur) {
    const k = Math.min(1, dur / Math.max(r.duracao_ref, 0.01));
    if (k >= 0.999) return r;
    const mov = (m, f) => m && f < 0.999 ? {
      ...m,
      duracao: m.duracao * f,
      atraso: Object.fromEntries(Object.entries(m.atraso ?? {}).map(([p, v]) => [p, v * f])),
      dur: Object.fromEntries(Object.entries(m.dur ?? {}).map(([p, v]) => [p, v * f]))
    } : m;
    return {
      ...r,
      cards: r.cards.map((c) => {
        const sai = c.sai_antes_do_fim * k;
        const vida = Math.max(c.fim_frac != null ? c.fim_frac * dur : dur - sai, 0.05) - c.inicio_frac * dur;
        const soma = (c.entrada?.duracao ?? 0) + (c.saida?.duracao ?? 0);
        const f = soma > vida ? vida / soma : 1;
        return { ...c, sai_antes_do_fim: sai, entrada: mov(c.entrada, f), saida: mov(c.saida, f) };
      })
    };
  }
  function comRepouso(c, rep) {
    const novo = { ...c.repouso, ...rep };
    const s = c.saida;
    if (!s || s.para.escala <= 1.05 || novo.w === c.repouso.w && novo.h === c.repouso.h) return { ...c, repouso: novo };
    const kx = novo.w / Math.max(c.repouso.w, 0.01);
    const ky = novo.h / Math.max(c.repouso.h, 0.01);
    return { ...c, repouso: novo, saida: { ...s, para: { ...s.para, dx: s.para.dx * kx, dy: s.para.dy * ky } } };
  }
  function janela(c, dur) {
    const ini = c.inicio_frac * dur;
    const fim = Math.max(c.fim_frac != null ? Math.min(c.fim_frac * dur + (c.fim_mais ?? 0), dur) : dur - c.sai_antes_do_fim, ini + 0.05);
    return { ini, fim };
  }
  function progresso(m, k, t) {
    const atraso = m.atraso?.[k] ?? 0;
    const d = m.dur?.[k] ?? m.duracao - atraso;
    const curva = m.curvas[k] ?? m.curvas.pos ?? [0.16, 1, 0.3, 1];
    return bezier(...curva)(limite((t - atraso) / Math.max(d, 0.01)));
  }
  var mistura = (a, b, p) => a + (b - a) * p;
  function estadoCard(c, rel, dur) {
    const { ini, fim } = janela(c, dur);
    if (rel < ini || rel > fim) return null;
    let e = { ...NEUTRO };
    if (c.entrada && rel < ini + c.entrada.duracao) {
      const t = rel - ini;
      const de = c.entrada.de;
      const pp = progresso(c.entrada, "pos", t);
      const pr = progresso(c.entrada, "rot", t);
      e = {
        dx: mistura(de.dx, 0, pp),
        dy: mistura(de.dy, 0, pp),
        escala: mistura(de.escala, 1, progresso(c.entrada, "escala", t)),
        altura: mistura(de.altura ?? 1, 1, progresso(c.entrada, "escala", t)),
        rot: mistura(de.rot, 0, pr),
        rx: mistura(de.rx, 0, pr),
        ry: mistura(de.ry, 0, pr),
        opacidade: limite(mistura(de.opacidade, 1, progresso(c.entrada, "opacidade", t))),
        desfoque: Math.max(0, mistura(de.desfoque, 0, progresso(c.entrada, "desfoque", t)))
      };
    }
    if (c.saida && rel > fim - c.saida.duracao) {
      const t = rel - (fim - c.saida.duracao);
      const pa = c.saida.para;
      const pp = progresso(c.saida, "pos", t);
      const pr = progresso(c.saida, "rot", t);
      e = {
        dx: e.dx + mistura(0, pa.dx, pp),
        dy: e.dy + mistura(0, pa.dy, pp),
        escala: e.escala * mistura(1, pa.escala, progresso(c.saida, "escala", t)),
        altura: (e.altura ?? 1) * mistura(1, pa.altura ?? 1, progresso(c.saida, "escala", t)),
        rot: e.rot + mistura(0, pa.rot, pr),
        rx: e.rx + mistura(0, pa.rx, pr),
        ry: e.ry + mistura(0, pa.ry, pr),
        opacidade: e.opacidade * limite(mistura(1, pa.opacidade, progresso(c.saida, "opacidade", t))),
        desfoque: e.desfoque + Math.max(0, mistura(0, pa.desfoque, progresso(c.saida, "desfoque", t)))
      };
    }
    const z = c.continuo;
    if (z) {
      const t = rel - ini;
      e = { ...e, escala: e.escala * Math.pow(1 + z.escala, t), dx: e.dx + z.dx * t, dy: e.dy + z.dy * t, rot: e.rot + (z.rot ?? 0) * t };
    }
    return e;
  }
  function zoomMidia(c, rel, dur) {
    const z = c.zoom;
    if (!z) return 1;
    const t = rel - janela(c, dur).ini - z.inicio;
    return mistura(1, z.escala, bezier(...z.curva)(limite(t / Math.max(z.duracao, 0.01))));
  }
  function cantosNoTempo(qs, f) {
    if (qs.length === 1 || f <= qs[0].f) return qs[0].q;
    if (f >= qs[qs.length - 1].f) return qs[qs.length - 1].q;
    let i = 0;
    while (qs[i + 1].f < f) i++;
    const a = qs[Math.max(i - 1, 0)], b = qs[i], c = qs[i + 1], d = qs[Math.min(i + 2, qs.length - 1)];
    const t = (f - b.f) / Math.max(c.f - b.f, 1e-6);
    const cr = (p0, p1, p2, p3) => 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
    return b.q.map((_, k) => [cr(a.q[k][0], b.q[k][0], c.q[k][0], d.q[k][0]), cr(a.q[k][1], b.q[k][1], c.q[k][1], d.q[k][1])]);
  }
  function matrizDosCantos(w, h, q2) {
    const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = q2;
    const dx1 = x1 - x2, dx2 = x3 - x2, dy1 = y1 - y2, dy2 = y3 - y2;
    const sx = x0 - x1 + x2 - x3, sy = y0 - y1 + y2 - y3;
    const den = dx1 * dy2 - dx2 * dy1;
    const g = (sx * dy2 - dx2 * sy) / den, hh = (dx1 * sy - sx * dy1) / den;
    const a = x1 - x0 + g * x1, b = x3 - x0 + hh * x3, c = x0;
    const d = y1 - y0 + g * y1, e = y3 - y0 + hh * y3, f = y0;
    const m = [a / w, d / w, 0, g / w, b / h, e / h, 0, hh / h, 0, 0, 1, 0, c, f, 0, 1];
    return `matrix3d(${m.map((v) => +v.toFixed(8)).join(",")})`;
  }
  var nMidias = (r) => Math.max(...r.cards.map((c, k) => (c.midia ?? k) + 1));
  function paraMidias(r, n) {
    if (!r.repete && n >= 1 && n < nMidias(r)) return { ...r, cards: r.cards.map((c, k) => ({ ...c, midia: (c.midia ?? k) % n })) };
    if (!r.repete || n < 1) return r;
    const fixos = r.cards.slice(0, -1);
    const molde = r.cards[r.cards.length - 1];
    const seq = r.cards.some((c) => c.fim_frac != null && c.fim_frac < 1);
    const fimDe = (_c, k) => k === n - 1 ? 1 : (k + 1) / n;
    const mais = (c, k) => k < n - 1 && c.saida ? c.saida.duracao : 0;
    const ultimoSai = (k) => k < n - 1 || !!r.sai_ultimo;
    const comoMedida = n === r.cards.length;
    const cards2 = fixos.map((c, k) => seq && !comoMedida ? { ...c, fim_frac: fimDe(c, k), fim_mais: mais(c, k), saida: ultimoSai(k) ? c.saida : null } : c);
    for (let k = fixos.length; k < n; k++)
      cards2.push({
        ...molde,
        midia: k,
        inicio_frac: k === 0 || comoMedida ? molde.inicio_frac : k / n,
        fim_frac: seq ? fimDe(molde, k) : molde.fim_frac,
        fim_mais: seq ? mais(molde, k) : molde.fim_mais,
        saida: seq && !ultimoSai(k) ? null : molde.saida,
        repouso: { ...molde.repouso, z: molde.repouso.z + k }
      });
    return { ...r, cards: n < fixos.length ? cards2.slice(0, n) : cards2 };
  }
  function paraFormato(r, formato) {
    if (r.formato === formato) return r;
    const k = formato === "dividida" ? 2 : 0.5;
    const y = (v) => formato === "dividida" ? (v - 25) * 2 : v / 2 + 25;
    const mov = (m) => {
      if (!m) return m;
      const chave = "de" in m ? "de" : "para";
      const e = m[chave];
      return { ...m, [chave]: { ...e, dy: e.dy * k } };
    };
    return {
      ...r,
      formato,
      cards: r.cards.map((c) => ({
        ...c,
        repouso: { ...c.repouso, cy: y(c.repouso.cy), h: c.repouso.h * k },
        entrada: mov(c.entrada),
        saida: mov(c.saida),
        continuo: c.continuo ? { ...c.continuo, dy: c.continuo.dy * k } : c.continuo
      }))
    };
  }
  var noFormato = (p, formato, n) => {
    const r = n ? paraMidias(p.receita, n) : p.receita;
    const q2 = r === p.receita ? p : { ...p, receita: r };
    return q2.formato === formato || formato !== "vertical" && formato !== "dividida" ? q2 : { ...q2, receita: paraFormato(q2.receita, formato), adaptado: true };
  };

  // src/ajustes.ts
  var escalaTempo = (m, k) => m ? {
    ...m,
    duracao: m.duracao * k,
    atraso: Object.fromEntries(Object.entries(m.atraso ?? {}).map(([p, v]) => [p, v * k])),
    dur: Object.fromEntries(Object.entries(m.dur ?? {}).map(([p, v]) => [p, v * k]))
  } : m;
  var cards = (r, f) => ({ ...r, cards: r.cards.map(f) });
  var estado = (m) => "de" in m ? m.de : m.para;
  var comEstado = (m, e) => "de" in m ? { ...m, de: { ...m.de, ...e } } : { ...m, para: { ...m.para, ...e } };
  var cheio = (c) => c.repouso.w >= 99 && c.repouso.h >= 99;
  var deslizaTransbordando = (c) => c.repouso.w > 100 && Math.abs(c.saida?.para.dx ?? 0) >= 5 && (c.saida?.para.escala ?? 1) <= 1.05;
  var AJUSTES = [
    {
      id: "entrada",
      nome: "Entrada",
      opcoes: ["Lenta", "Normal", "R\xE1pida"],
      fase: "antes",
      aplicar: (r, i) => cards(r, (c) => ({ ...c, entrada: escalaTempo(c.entrada, i === 0 ? 1.4 : 0.7) }))
    },
    {
      id: "saida",
      nome: "Sa\xEDda",
      opcoes: ["Lenta", "Normal", "R\xE1pida"],
      fase: "antes",
      aplicar: (r, i) => cards(r, (c) => ({ ...c, saida: escalaTempo(c.saida, i === 0 ? 1.4 : 0.7) }))
    },
    {
      // num card que transborda e desliza (o "Cresce e desliza"): até onde ele anda — pouco, como na referência, ou até a
      // outra borda do card chegar à borda da tela
      id: "deslize",
      nome: "At\xE9 onde desliza",
      opcoes: ["Pouco", "Como na refer\xEAncia", "At\xE9 a borda"],
      fase: "antes",
      aplicar: (r, i) => cards(r, (c) => deslizaTransbordando(c) ? { ...c, deslize: i === 0 ? 12 : 1e3 } : c)
    },
    {
      id: "zoom",
      nome: "Zoom",
      opcoes: ["Menos", "Normal", "Mais"],
      fase: "antes",
      aplicar: (r, i) => {
        const k = i === 0 ? 0.6 : 1.5;
        return cards(r, (c) => ({
          ...c,
          zoom: c.zoom ? { ...c.zoom, escala: 1 + (c.zoom.escala - 1) * k } : c.zoom,
          saida: c.saida && estado(c.saida).escala > 1.05 ? comEstado(c.saida, { escala: 1 + (estado(c.saida).escala - 1) * k }) : c.saida
        }));
      }
    },
    {
      id: "zona",
      nome: "Mergulha em",
      opcoes: ["Topo \xE0 esquerda", "Topo", "Topo \xE0 direita", "Esquerda", "Centro", "Direita", "Base \xE0 esquerda", "Base", "Base \xE0 direita"],
      fase: "depois",
      // depois de o card ganhar o tamanho da mídia: o ponto é sobre o card final,
      grade: true,
      // a zona para onde o zoom de saída (o mergulho) vai: o ponto da imagem que fica parado enquanto o card cresce
      padrao: (r) => {
        const c = r.cards.find((x) => x.saida && estado(x.saida).escala > 1.05);
        if (!c?.saida) return 4;
        const e = estado(c.saida);
        const px = 0.5 - e.dx / ((e.escala - 1) * c.repouso.w);
        const py = 0.5 - e.dy / ((e.escala - 1) * c.repouso.h);
        const q2 = (v) => v < 0.36 ? 0 : v > 0.64 ? 2 : 1;
        return q2(py) * 3 + q2(px);
      },
      aplicar: (r, i) => {
        const px = [0.2, 0.5, 0.8][i % 3];
        const py = [0.2, 0.5, 0.8][Math.floor(i / 3)];
        return cards(r, (c) => {
          if (!c.saida || estado(c.saida).escala <= 1.05) return c;
          const s = estado(c.saida).escala;
          return { ...c, saida: comEstado(c.saida, { dx: -(s - 1) * (px - 0.5) * c.repouso.w, dy: -(s - 1) * (py - 0.5) * c.repouso.h }) };
        });
      }
    },
    {
      id: "forma",
      nome: "Forma",
      opcoes: ["Card", "Tela toda"],
      fase: "antes",
      padrao: (r) => r.cards.every(cheio) ? 1 : 0,
      // tela toda: a mídia ocupa a área (na tela cheia, só as em pé; ver receitaParaInsert); card: centrado, com cantos e sombra
      aplicar: (r, i) => cards(r, (c) => comRepouso(c, i === 1 ? { cx: 50, cy: 50, w: 100, h: 100, raio: 0, sombra: false } : { cx: 50, cy: 50, w: 88, h: 70, raio: 2.2, sombra: true }))
    },
    {
      id: "camera",
      nome: "Zoom lento",
      opcoes: ["Parado", "Leve", "Mais"],
      fase: "antes",
      padrao: (r) => r.cards.some((c) => c.continuo && (c.continuo.escala || c.continuo.dx || c.continuo.dy)) ? 1 : 0,
      // um zoom in linear e contínuo, a partir do centro de cada card (a câmera da composição inteira)
      aplicar: (r, i) => cards(r, (c) => {
        if (i === 0) return { ...c, continuo: null };
        const z = 0.015 * (i === 2 ? 2 : 1);
        return { ...c, continuo: { escala: z, dx: z * (c.repouso.cx - 50), dy: z * (c.repouso.cy - 50), rot: 0 } };
      })
    },
    {
      id: "desfoque",
      nome: "Desfoque na entrada",
      opcoes: ["Sem", "Normal", "Mais"],
      fase: "antes",
      aplicar: (r, i) => cards(r, (c) => ({ ...c, entrada: c.entrada ? comEstado(c.entrada, { desfoque: i === 0 ? 0 : Math.max(estado(c.entrada).desfoque * 1.8, 12) }) : c.entrada }))
    },
    {
      id: "tamanho",
      nome: "Tamanho do card",
      opcoes: ["Menor", "Normal", "Maior"],
      fase: "depois",
      aplicar: (r, i) => {
        const k = i === 0 ? 0.86 : 1.12;
        return cards(r, (c) => c.repouso.w >= 99 && c.repouso.h >= 99 ? c : comRepouso(c, { w: c.repouso.w * k, h: c.repouso.h * k }));
      }
    },
    {
      id: "som",
      nome: "Som",
      opcoes: ["Sem", "Baixo", "M\xE9dio"],
      fase: "antes",
      // os sons do preset (SPEC §8.6): neste insert, sem som, ou todos mais baixos ou mais altos
      padrao: (r) => {
        const ss = (r.sons ?? []).filter((s) => s.som);
        return !ss.length ? 0 : ss.every((s) => s.intensidade === "medio") ? 2 : 1;
      },
      aplicar: (r, i) => ({ ...r, sons: (r.sons ?? []).map((s) => i === 0 ? { ...s, som: null } : { ...s, intensidade: i === 1 ? "baixo" : "medio" }) })
    },
    {
      id: "proximo",
      nome: "Quando o pr\xF3ximo entra",
      opcoes: ["Antes", "Normal", "Depois"],
      fase: "depois",
      // numa sequência, o anterior sai quando o próximo entra (termina na fração em que ele começa): a saída vai junto, para
      // não ficar um vão vazio (Depois) nem o próximo por cima do anterior parado (Antes)
      aplicar: (r, i) => {
        const k = i === 0 ? 0.75 : 1.25;
        const novo = (j) => j === 0 ? r.cards[0].inicio_frac : Math.min(r.cards[j].inicio_frac * k, 0.9);
        return cards(r, (c, j) => {
          const prox = r.cards[j + 1];
          const passa = prox && c.fim_frac != null && Math.abs(c.fim_frac - prox.inicio_frac) < 0.02;
          return { ...c, inicio_frac: novo(j), ...passa ? { fim_frac: novo(j + 1) } : {} };
        });
      }
    }
  ];
  function ajustesEfetivos(p, ajustes, aspectos) {
    if (!p?.tela_toda_em_pe || ajustes?.forma || !aspectos.length || !aspectos.every((a) => a < 0.8)) return ajustes;
    return { ...ajustes ?? {}, forma: "Tela toda" };
  }
  var padraoDe = (a, r) => a.padrao ? a.padrao(r) : 1;
  function livres(r, ajustes) {
    const y = Number(ajustes.y ?? 0);
    const k = Number(ajustes.largura ?? 1);
    if (!y && k === 1) return r;
    return cards(r, (c) => cheio(c) ? c : comRepouso(c, { cy: c.repouso.cy + y, w: c.repouso.w * k, h: c.repouso.h * k }));
  }
  function comAjustes(r, ajustes, fase) {
    if (!ajustes) return r;
    if (fase === "depois") r = livres(r, ajustes);
    return AJUSTES.filter((a) => a.fase === fase && ajustes[a.id] != null).reduce((rr, a) => {
      const i = a.opcoes.indexOf(ajustes[a.id]);
      return i >= 0 && i !== padraoDe(a, rr) ? a.aplicar(rr, i) : rr;
    }, r);
  }

  // src/ator.ts
  var PADRAO_MODO = {
    janela: { x: 0.5, y: 1 - 0.55 / 2, escala: 0.55 },
    recortado: { x: 0.5, y: 1 - 0.62 / 2, escala: 0.62 },
    canto: { x: 1 - 0.34 / 2 - 0.04, y: 1 - 0.34 / 2 - 0.035, escala: 0.34 }
  };
  var TOPO_JANELA = (0.72 - 0.45) / 0.55;
  var RAIO = 0.07;
  var REGRA = { olhos: 0.4, folga: 0.06, rosto: 0.3, zoomMax: 1.6 };
  var ZOOM = { min: 1 / REGRA.zoomMax, max: REGRA.zoomMax };
  var limite2 = (v, a, b) => Math.min(Math.max(v, a), b);
  function enquadrar(f, r) {
    if (!r || r.h <= 0) return { s: 1, tx: 0, ty: f / 2 };
    const area = 1 - f;
    const s = limite2(REGRA.rosto * area / r.h, 1, REGRA.zoomMax);
    const olhos = r.cy - 0.15 * r.h;
    const tx = limite2(0.5 - s * r.cx, 1 - s, 0);
    let ty = f + REGRA.olhos * area - s * olhos;
    ty = Math.max(ty, f + REGRA.folga * area - s * (r.cy - 0.6 * r.h));
    return { s, tx, ty: limite2(ty, 1 - s, f) };
  }
  function metadeSemDeslocamento(d, aj, rosto) {
    const auto = enquadrar(d.f, rosto);
    const s = limite2(auto.s * (aj?.zoom ?? 1), 1, REGRA.zoomMax);
    const cx = 0.5;
    const cy = d.f + (1 - d.f) / 2;
    return { auto, s, tx: cx - (cx - auto.tx) * s / auto.s, ty: cy - (cy - auto.ty) * s / auto.s };
  }
  function geometriaDoAtor(d, aj, rosto) {
    if (!d) return null;
    if (d.modo === "metade") {
      const m = metadeSemDeslocamento(d, aj, rosto);
      return { modo: "metade", s: m.s, tx: limite2(m.tx + (aj?.dx ?? 0), 1 - m.s, 0), ty: limite2(m.ty + (aj?.dy ?? 0), 1 - m.s, d.f) };
    }
    const modo = aj?.modo ?? "janela";
    const p = PADRAO_MODO[modo];
    const s = aj?.escala ?? p.escala;
    const xAuto = modo !== "canto" && rosto ? limite2(0.5 - s * (rosto.cx - 0.5), s / 2, 1 - s / 2) : p.x;
    const x = aj?.x ?? xAuto;
    const y = aj?.y ?? (modo === "canto" ? p.y : 1 - s / 2);
    return { modo, s, tx: x - s / 2, ty: y - s / 2, topo: modo === "janela" ? TOPO_JANELA : void 0, raio: modo === "recortado" ? void 0 : RAIO };
  }

  // src/divisao.ts
  var JANELA = { escala: 0.55, y0: 72, raio: 7 };
  var TOPO_CABECA = 100 - JANELA.escala * 100 + JANELA.escala * 10;
  var MARGEM = 0.06;
  var W_H = 9 / 16;
  var telaTodaPermitida = (formato, atras, aspectos) => formato === "dividida" && !atras ? aspectos.some((a) => a >= 0.8) : aspectos.some((a) => a < 0.8);
  var tipoDoPreset = (p) => p?.divisao_tipo ?? (p && p.receita.cards.every((c) => c.repouso.w >= 99 && c.repouso.h >= 99) ? "area" : "card");
  function divisaoDe(x, banco, presets) {
    if (x.formato !== "dividida") return null;
    const preset = x.enriquecimento?.preset ? presets?.find((p) => p.id === x.enriquecimento?.preset) : null;
    const forma = ajustesEfetivos(preset, x.enriquecimento?.ajustes, aspectosDe(x.midias, banco))?.forma;
    const atras = x.enriquecimento?.divisao === "atras";
    const aspectos = aspectosDe(x.midias, banco);
    let base = forma === "Tela toda" ? "area" : forma === "Card" ? "card" : preset ? tipoDoPreset(preset) : "card";
    if (base === "area" && !telaTodaPermitida("dividida", atras, aspectos)) base = "card";
    const tipo = atras ? "atras" : base;
    if (tipo === "atras" && base === "area") return { modo: "atras", tipo, f: 1 };
    const i = x.midias[0] && banco?.get(x.midias[0].banco);
    const a = i?.largura && i?.altura ? i.largura / i.altura : 16 / 9;
    const varios = !!preset && (preset.receita.repete || preset.receita.cards.length > 1);
    if (varios && tipo !== "area") return { modo: tipo === "atras" ? "atras" : "metade", tipo, f: tipo === "atras" ? JANELA.y0 / 100 : 0.56 };
    if (tipo === "area") return { modo: "metade", tipo, f: a < 1 ? 0.5 : Math.min(Math.max(W_H / a, 0.28), 0.5625) };
    const livre = tipo === "atras" ? JANELA.y0 / 100 : 0.62;
    let cw = 0.9;
    let ch = cw * W_H / a;
    if (ch > livre - 2 * MARGEM) {
      ch = livre - 2 * MARGEM;
      cw = ch * a / W_H;
    }
    const f = tipo === "atras" ? livre : Math.min(Math.max(ch + 2 * MARGEM, 0.4), livre);
    return { modo: tipo === "atras" ? "atras" : "metade", tipo, f, card: { w: cw * 100, h: ch / f * 100 } };
  }
  function receitaParaInsert(r, d, aspectos, formato) {
    const areaAsp = formato === "dividida" ? W_H / (d?.f ?? 0.5) : W_H;
    const cards2 = r.cards.map((c, k) => {
      if (c.quadros?.length) return c;
      const cheio2 = c.repouso.w >= 99 && c.repouso.h >= 99;
      const a0 = aspectos[c.midia ?? k] ?? aspectos[0];
      const cabe = a0 ? formato === "dividida" && d?.modo !== "atras" ? a0 >= 0.8 : a0 < 0.8 : true;
      if (cheio2 && !cabe && a0) {
        let w2 = 90;
        let h2 = w2 * areaAsp / a0;
        if (h2 > 90) {
          h2 = 90;
          w2 = h2 * a0 / areaAsp;
        }
        return { ...comRepouso(c, { cx: 50, cy: 50, w: w2, h: h2, raio: c.repouso.raio || 2.2, sombra: true }), ajuste: "cover" };
      }
      if (cheio2) {
        const z = c.continuo;
        const continuo2 = !z ? z : z.escala < 0 ? { ...z, escala: -z.escala, dx: 0, dy: -z.escala * 100 / 2 } : { ...z, dy: z.dy || z.escala * 100 / 2 };
        const cc = comRepouso(c, { cx: 50, cy: 50, w: 100, h: 100 });
        return { ...cc, ajuste: "topo", continuo: continuo2, saida: saidaCobrindo(cc.saida) };
      }
      if (d?.card && r.cards.length === 1) return { ...comRepouso(c, { cx: 50, cy: 50, w: d.card.w, h: d.card.h }), ajuste: "cover" };
      const a = aspectos[c.midia ?? k] ?? aspectos[0];
      if (!a) return c;
      const emPe = a < 0.9 && c.repouso.w > c.repouso.h;
      const atras = d?.modo === "atras";
      const desliza = deslizeTransbordando(c, a, areaAsp, atras);
      if (desliza) return desliza;
      const bw = atras ? 96 : Math.min(c.repouso.w, 96);
      const bh = emPe ? Math.max(Math.min(c.repouso.h, 96), 84) : Math.min(c.repouso.h, 96);
      let w = bw;
      let h = w * areaAsp / a;
      if (h > bh) {
        h = bh;
        w = h * a / areaAsp;
      }
      const empilhado = r.cards.length > 1 && !r.repete && Math.abs(c.repouso.cy - 50) > 10;
      const junto = empilhado ? Math.sign(50 - c.repouso.cy) * Math.max(0, c.repouso.h - h) / 2 : 0;
      const cy = emPe ? 50 : atras ? Math.max(h / 2 + 3, 44) : c.repouso.cy + junto;
      const folga = emPe ? Math.max(0, 98 - h) / Math.max(1, 98 - Math.min(c.repouso.h, 96)) : 1;
      const continuo = c.continuo && folga < 1 ? { ...c.continuo, dy: c.continuo.dy * folga } : c.continuo;
      const visivel = [Math.max(c.repouso.cx - c.repouso.w / 2, 0), Math.min(c.repouso.cx + c.repouso.w / 2, 100)];
      const meio = Math.min(Math.max((visivel[0] + visivel[1]) / 2, w / 2 + 2), 98 - w / 2);
      const cx = atras || emPe ? 50 : c.repouso.w > 96 ? meio : c.repouso.cx;
      return { ...comRepouso(c, { w, h, cy, cx }), continuo, ajuste: "cover" };
    });
    return { ...r, cards: cards2 };
  }
  var DESLIZE = 23;
  function deslizeTransbordando(c, a, areaAsp, atras) {
    const dx = c.saida?.para.dx ?? 0;
    if (atras || c.repouso.w <= 100 || Math.abs(dx) < 5 || (c.saida?.para.escala ?? 1) > 1.05) return null;
    let w = c.repouso.w;
    let h = w * areaAsp / a;
    const hMax = Math.min(c.repouso.h, 96);
    if (h > hMax) {
      h = hMax;
      w = h * a / areaAsp;
    }
    if (w <= 100) return null;
    const esq = dx < 0;
    const borda = esq ? c.repouso.cx - c.repouso.w / 2 : c.repouso.cx + c.repouso.w / 2;
    const cx = esq ? borda + w / 2 : borda - w / 2;
    const sobra = esq ? cx + w / 2 - 100 : -(cx - w / 2);
    const deslize = (esq ? -1 : 1) * Math.max(Math.min(c.deslize ?? DESLIZE, sobra), 0);
    const e = c.entrada;
    const entrada = e && e.de.escala < 0.98 ? { ...e, de: { ...e.de, dx: (esq ? -1 : 1) * (w / 2) * (1 - e.de.escala) } } : e;
    return { ...c, repouso: { ...c.repouso, w, h, cx }, entrada, saida: c.saida && { ...c.saida, para: { ...c.saida.para, dx: deslize } }, ajuste: "cover" };
  }
  function saidaCobrindo(s) {
    if (!s || s.para.opacidade < 0.99) return s;
    const { dx, dy, escala } = s.para;
    if (escala > 1.05) {
      const m = 50 * (escala - 1);
      return { ...s, para: { ...s.para, dx: Math.min(Math.max(dx, -m), m), dy: Math.min(Math.max(dy, -m), m) } };
    }
    const d = Math.max(Math.abs(dx), Math.abs(dy));
    if (escala < 0.999 || d < 0.5 || d > 25) return s;
    const comoPos = (o) => {
      const resto = Object.fromEntries(Object.entries(o ?? {}).filter(([k]) => k !== "escala"));
      return o?.pos != null ? { ...resto, escala: o.pos } : resto;
    };
    return { ...s, para: { ...s.para, escala: Math.max(escala, 1 + 2 * d / 100) }, curvas: comoPos(s.curvas), atraso: comoPos(s.atraso), dur: comoPos(s.dur) };
  }
  var aspectosDe = (midias, banco) => midias.map((m) => {
    const i = banco?.get(m.banco);
    return i?.largura && i?.altura ? i.largura / i.altura : 16 / 9;
  });
  var areaDoInsert = (d) => !d ? { inset: 0 } : { left: 0, right: 0, top: 0, height: `${d.f * 100}%` };

  // src/sons.ts
  var INTENSIDADES = { baixo: 0.25, medio: 0.5 };
  function eventoNoTempo(s, quando, cat, dur, abrange) {
    const info = s.som ? cat.sons.find((x) => x.id === s.som) : null;
    if (!info) return null;
    const ganho = cat.intensidades[s.intensidade] ?? 0.3;
    if (abrange && abrange > 0.05) {
      const golpe = quando + s.atraso;
      const vel = Math.min(Math.max(info.ataque / abrange, VEL[0]), VEL[1]);
      let t2 = golpe - Math.min(info.ataque / vel, abrange);
      let desde = Math.max(info.ataque - abrange * vel, 0);
      if (t2 < 0) {
        desde -= t2 * vel;
        t2 = 0;
      }
      const rabo = (info.duracao - info.ataque) / vel;
      const corte = rabo > RABO ? { dur: +(golpe - t2 + RABO).toFixed(4) } : {};
      return { t: t2, som: info.id, ganho, desde, ...corte, ...Math.abs(vel - 1) > 0.01 ? { vel: +vel.toFixed(4) } : {} };
    }
    const t = quando + s.atraso - (dur ? 0 : info.ataque);
    return { t: Math.max(t, 0), som: info.id, ganho, desde: Math.max(-t, 0), ...dur ? { dur } : {} };
  }
  var RABO = 0.15;
  var VEL = [0.65, 1.6];
  function paradoAos(curva, alvo = 0.95) {
    if (!curva) return 1;
    const f = bezier(...curva);
    for (let k = 1; k <= 100; k++) if (f(k / 100) >= alvo) return k / 100;
    return 1;
  }
  function eventosDaReceita(receita, dur, cat) {
    if (!cat || !receita.sons?.length) return [];
    const r = noTempo(receita, dur);
    const cards2 = r.cards.map((c) => ({ c, ...janela(c, dur) })).sort((a, b) => a.ini - b.ini);
    const quando = { entrada: [], troca: [], saida: [], mergulho: [], zoom: [] };
    const temMergulho = (r.sons ?? []).some((s) => s.momento === "mergulho");
    cards2.forEach(({ c, ini, fim }, k) => {
      quando.entrada.push([ini + (c.entrada?.atraso?.pos ?? 0)]);
      if (k > 0 && ini > cards2[0].ini + 0.02) quando.troca.push([ini]);
      if (c.saida) {
        if (c.saida.para.escala > 1.05 && temMergulho) {
          const atraso = c.saida.atraso?.escala ?? 0;
          const d = c.saida.dur?.escala ?? c.saida.duracao - atraso;
          const visto = d * paradoAos(c.saida.curvas.escala ?? c.saida.curvas.pos);
          quando.mergulho.push([fim - c.saida.duracao + atraso + visto, visto]);
        } else quando.saida.push([fim - c.saida.duracao]);
      }
      if (c.zoom) {
        const visto = c.zoom.duracao * paradoAos(c.zoom.curva);
        quando.zoom.push([ini + c.zoom.inicio + visto, visto]);
      }
    });
    const out = [];
    for (const s of r.sons ?? [])
      for (const [q2, abrange] of quando[s.momento] ?? []) {
        const e = eventoNoTempo(s, q2, cat, void 0, abrange);
        if (e && e.t < dur && !out.some((o) => o.som === e.som && Math.abs(o.t - e.t) < 0.04)) out.push(e);
      }
    return out.sort((a, b) => a.t - b.t);
  }

  // src/inserts.ts
  var ESTILO_SIMPLES = { vertical: { layout: "card" }, dividida: { layout: "metade" } };
  var SURGIR = { curva: [0.16, 1, 0.3, 1], duracao: 0.75, escala: 94 };
  function corteSimples(n, rel, dur) {
    const parte = dur / Math.max(n, 1);
    const k = Math.max(Math.min(Math.floor(rel / parte), n - 1), 0);
    return n === 2 ? { k, ini: k * parte, durM: parte } : { k, ini: 0, durM: dur };
  }
  function estiloSimples(rel, durM) {
    const d = Math.min(SURGIR.duracao, durM);
    const p = bezier(...SURGIR.curva)(limite01(rel / Math.max(d, 0.01)));
    const s0 = SURGIR.escala / 100;
    return { transform: `scale(${s0 + (1 - s0) * p})`, opacity: limite01(p) };
  }

  // src/desenho.ts
  var guardados = /* @__PURE__ */ new WeakMap();
  var estilos = /* @__PURE__ */ new WeakMap();
  var CHAVE = "k";
  function desenhar(pai, filhos) {
    let mapa = guardados.get(pai);
    if (!mapa) guardados.set(pai, mapa = /* @__PURE__ */ new Map());
    const vs = filhos.filter((v) => !!v);
    const els = vs.map((v) => {
      const tag = (v.tag ?? "div").toUpperCase();
      let el = mapa.get(v.chave);
      if (!el || el.tagName !== tag) {
        el = document.createElement(tag);
        el.dataset[CHAVE] = v.chave;
        mapa.set(v.chave, el);
        v.criar?.(el);
      }
      return el;
    });
    const ficam = new Set(els);
    for (const el of [...pai.children]) if (!ficam.has(el)) el.remove();
    vs.forEach((v, i) => {
      const el = els[i];
      if (pai.children[i] !== el) pai.insertBefore(el, pai.children[i] ?? null);
      if (el.className !== (v.classe ?? "")) el.className = v.classe ?? "";
      for (const [k, valor] of Object.entries(v.atributos ?? {})) if (el.getAttribute(k) !== valor) el.setAttribute(k, valor);
      aplicarEstilo(el, v.estilo ?? {});
      if (v.texto != null) {
        if (el.textContent !== v.texto) el.textContent = v.texto;
      } else desenhar(el, v.filhos ?? []);
      v.depois?.(el);
    });
  }
  function aplicarEstilo(el, novo) {
    const antes = estilos.get(el) ?? {};
    const s = el.style;
    for (const k of Object.keys(antes)) if (novo[k] == null) s[k] = "";
    for (const [k, v] of Object.entries(novo)) if (v != null && antes[k] !== v) s[k] = String(v);
    estilos.set(el, novo);
  }
  var relogio = 0;
  var FUNDOS = [
    { id: "verde_claro", nome: "Verde claro", claro: true, amostra: "linear-gradient(180deg,#dfe8e1 0%,#a9c6b3 55%,#6f9c84 100%)" },
    { id: "papel", nome: "Papel", claro: true, amostra: "radial-gradient(120% 90% at 50% 40%,#f1ecdd 0%,#e4dcc7 70%,#d6ccb3 100%)" },
    { id: "nevoa", nome: "N\xE9voa azul", claro: true, amostra: "linear-gradient(180deg,#d9d6e2 0%,#a9b2c7 45%,#8a97ad 75%,#c8ccd8 100%)" },
    { id: "chuva", nome: "Chuva", claro: false, amostra: "radial-gradient(90% 70% at 50% 40%,#0c3b35 0%,#06201c 55%,#050505 100%)" },
    { id: "gradiente", nome: "Gradiente escuro", claro: false, amostra: "radial-gradient(85% 70% at 50% 45%,#24423b 0%,#13201d 60%,#0b1412 100%)" }
  ];
  function chuvaNoRelogio(v) {
    if (!v.duration) return;
    v.pause();
    const alvo = relogio % v.duration;
    if (Math.abs(v.currentTime - alvo) > 1e-3) v.currentTime = alvo;
  }
  function fundo(id, chave = "fundo") {
    const f = FUNDOS.find((x) => x.id === id) ?? FUNDOS[4];
    return {
      chave,
      classe: "absolute inset-0 overflow-hidden",
      estilo: { background: f.id === "chuva" ? "#050505" : f.amostra },
      filhos: [
        f.id === "chuva" && {
          chave: "chuva",
          tag: "video",
          classe: "absolute inset-0 size-full object-cover",
          atributos: { src: "/render/fundos/aura/chuva.mp4", preload: "auto" },
          criar: (el) => {
            const v = el;
            v.muted = v.loop = v.playsInline = true;
            v.addEventListener("loadedmetadata", () => chuvaNoRelogio(v));
          },
          depois: (el) => chuvaNoRelogio(el)
        },
        // névoa: manchas desfocadas, como no fundo de referência
        f.id === "nevoa" && {
          chave: "n1",
          classe: "absolute rounded-full",
          estilo: { top: "-10%", left: "-20%", height: "55%", width: "90%", background: "#eae6f0", opacity: 0.7, filter: "blur(64px)" }
        },
        f.id === "nevoa" && {
          chave: "n2",
          classe: "absolute rounded-full",
          estilo: { top: "40%", right: "-25%", height: "45%", width: "80%", background: "#6f7f99", opacity: 0.5, filter: "blur(64px)" }
        }
      ]
    };
  }
  function videoNoTempo(m, item, rel, topo) {
    const alvo = Math.min((item.inicio ?? 0) + rel, item.fim ?? Infinity);
    return {
      chave: `m:${m.id}`,
      tag: "video",
      classe: `size-full object-cover${topo ? " object-top" : ""}`,
      atributos: { src: item.url, preload: "auto" },
      criar: (el) => {
        const v = el;
        v.muted = v.playsInline = true;
      },
      depois: (el) => {
        const v = el;
        const fim = Math.min(item.fim ?? Infinity, Number.isFinite(v.duration) ? v.duration : Infinity);
        const destino = Math.min((Math.floor(Math.min(alvo, fim) * 24 + 1e-6) + 0.5) / 24, fim - 1e-3);
        if (Math.abs(v.currentTime - destino) > 1e-3) {
          v.dataset.quadro = "0";
          v.requestVideoFrameCallback?.(() => v.dataset.quadro = "1");
          v.currentTime = destino;
        }
        if (!v.paused) v.pause();
      }
    };
  }
  function midia(m, banco, rel, topo) {
    if (!m) return null;
    const item = banco.get(m.banco);
    if (item?.tipo === "video") return videoNoTempo(m, item, rel, topo);
    return {
      chave: `m:${m.id}`,
      tag: "img",
      classe: `size-full object-cover${topo ? " object-top" : ""}`,
      atributos: { src: item?.url ?? "", alt: "" }
    };
  }
  var SOMBRA = "sombra-card";
  function cenaPreset(p) {
    const r = noTempo(p.receita, p.dur);
    const cards2 = r.cards.map((c, k) => {
      const e = estadoCard(c, p.rel, p.dur);
      if (!e || e.opacidade <= 1e-3) return null;
      const rep = c.repouso;
      const ini = janela(c, p.dur).ini;
      const conteudo = () => p.midia(c.midia ?? k, Math.max(p.rel - ini, 0), c.ajuste === "topo");
      if (c.quadros?.length) {
        const tam = p.caixa;
        if (!tam) return null;
        const { fim } = janela(c, p.dur);
        const q2 = cantosNoTempo(c.quadros, (p.rel - ini) / Math.max(fim - ini, 0.01)).map(([x, y]) => [x / 100 * tam[0], y / 100 * tam[1]]);
        const w = rep.w / 100 * tam[0], h = rep.h / 100 * tam[1];
        return {
          chave: `c${k}`,
          classe: "absolute top-0 left-0 origin-top-left",
          estilo: { width: `${w}px`, height: `${h}px`, zIndex: rep.z, opacity: e.opacidade, transform: matrizDosCantos(w, h, q2), filter: rep.desfoque ? `blur(${(rep.desfoque / 10.8).toFixed(3)}cqw)` : void 0 },
          filhos: [{ chave: "moldura", classe: "size-full overflow-hidden", estilo: { borderRadius: `${rep.raio * rep.w / 100}cqw` }, filhos: [conteudo()] }]
        };
      }
      const giro3d = rep.rx + e.rx || rep.ry + e.ry ? `perspective(138.9cqw) rotateX(${rep.rx + e.rx}deg) rotateY(${rep.ry + e.ry}deg) ` : "";
      return {
        chave: `c${k}`,
        classe: "absolute",
        estilo: {
          left: `${rep.cx - rep.w / 2}%`,
          top: `${rep.cy - rep.h * (e.altura ?? 1) / 2}%`,
          width: `${rep.w}%`,
          height: `${rep.h * (e.altura ?? 1)}%`,
          zIndex: rep.z,
          opacity: e.opacidade,
          transform: `translate(${e.dx}cqw, ${e.dy}cqh) ${giro3d}rotate(${rep.rot + e.rot}deg) scale(${e.escala})`,
          filter: e.desfoque + (rep.desfoque ?? 0) > 0.05 ? `blur(${((e.desfoque + (rep.desfoque ?? 0)) / 10.8).toFixed(3)}cqw)` : void 0
        },
        filhos: [
          {
            chave: "moldura",
            classe: `size-full overflow-hidden${rep.sombra ? ` ${SOMBRA}` : ""}${c.ajuste === "contain" ? " bg-black" : ""}`,
            estilo: { borderRadius: `${rep.raio * rep.w / 100}cqw` },
            filhos: [
              c.zoom ? { chave: "zoom", classe: "size-full", estilo: { transform: `scale(${zoomMidia(c, p.rel, p.dur)})`, transformOrigin: `${c.zoom.ox}% ${c.zoom.oy}%` }, filhos: [conteudo()] } : conteudo()
            ]
          }
        ]
      };
    });
    return {
      chave: "cena",
      classe: `pointer-events-none absolute isolate overflow-hidden ${p.classe ?? ""}${r.fundo === "nenhum" && !p.semFundo ? " bg-black" : ""}`,
      estilo: { containerType: "size" },
      // `semFundo`: quem usa já desenha o fundo, maior que a cena (o "ator embaixo": a tela toda)
      filhos: [r.fundo === "proprio" && !p.semFundo && fundo(p.fundo), ...cards2]
    };
  }
  function insertNoLugar(p) {
    const { pedido, banco, divisao } = p;
    const area = areaDoInsert(divisao);
    const n = pedido.midias.length;
    const dur = Math.max(pedido.t.fim - pedido.t.inicio, 0.01);
    const rel = Math.max(p.tempo - pedido.t.inicio, 0);
    if (!n) return [];
    const atras = divisao?.modo === "atras" && { chave: "atras", classe: "pointer-events-none absolute inset-0", filhos: [fundo(p.fundo)] };
    if (p.receita)
      return [
        atras,
        {
          chave: "area",
          classe: "pointer-events-none absolute",
          estilo: area,
          filhos: [
            cenaPreset({
              receita: p.receita,
              rel,
              dur,
              fundo: p.fundo,
              classe: "inset-0",
              semFundo: divisao?.modo === "atras",
              caixa: p.caixa,
              midia: (k2, relM, topo) => midia(pedido.midias[k2], banco, relM, topo)
            })
          ]
        }
      ].filter(Boolean);
    const emCard = ESTILO_SIMPLES[pedido.formato].layout === "card";
    const { k, ini, durM } = corteSimples(n, rel, dur);
    const anim = estiloSimples(rel - ini, durM);
    return [
      atras,
      {
        chave: "area",
        classe: `pointer-events-none absolute overflow-hidden${emCard ? "" : " bg-black"}`,
        estilo: area,
        filhos: [
          emCard && fundo(p.fundo),
          {
            chave: `moldura${k}`,
            classe: `absolute ${emCard ? "inset-8p" : "inset-0"}`,
            estilo: anim,
            filhos: [{ chave: "card", classe: `size-full overflow-hidden${emCard ? ` ${SOMBRA} rounded-18` : ""}`, filhos: [midia(pedido.midias[k], banco, rel - ini)] }]
          }
        ]
      }
    ].filter(Boolean);
  }

  // src/preset.ts
  var q = new URLSearchParams(location.search);
  var PAUSA = 0.4;
  var ASPECTO = { pe: 9 / 16, "1:1": 1, "4:3": 4 / 3, "16:9": 16 / 9 };
  var json = (url) => fetch(url).then((r) => r.ok ? r.json() : Promise.reject(new Error(`${url}: ${r.status}`)));
  var esperar = (ms) => new Promise((r) => setTimeout(r, ms));
  function aspectosDe2(prop, n) {
    return Array.from(
      { length: n },
      (_, k) => n === 1 ? ASPECTO[prop] ?? 16 / 9 : prop === "pe" ? 9 / 16 : prop === "deitada" ? k % 2 ? 4 / 3 : 16 / 9 : k % 2 ? 16 / 9 : 9 / 16
    );
  }
  function aspectosDaReferencia(r, n) {
    const area = r.formato === "vertical" ? 9 / 16 : 9 / 8;
    const cards2 = paraMidias(r, n).cards;
    return Array.from({ length: n }, (_, k) => {
      const c = cards2.find((x, j) => (x.midia ?? j) === k) ?? cards2[0];
      return Math.min(Math.max(c.repouso.w / Math.max(c.repouso.h, 1) * area, 0.4), 2.4);
    });
  }
  function escolherMidias(todas, aspectos, semente) {
    const claras = todas.filter((m) => m.luz == null || m.luz >= 40 && m.luz <= 250);
    const am = claras.length >= 3 ? claras : todas;
    const familia = (a) => a < 0.8 ? 0 : a < 1.5 ? 1 : 2;
    let s = 0;
    for (const ch of semente) s = s * 31 + ch.charCodeAt(0) >>> 0;
    return aspectos.map((a, k) => {
      const f = familia(a);
      const l = am.filter((m) => familia(m.aspecto) === f);
      const outras = l.length ? l : am.filter((m) => familia(m.aspecto) === (f === 1 ? 2 : f === 2 ? 1 : 0));
      const lista = outras.length ? outras : am;
      return lista.length ? lista[(s + k) % lista.length] : null;
    });
  }
  function instanteParado(cards2, dur) {
    const vidas = cards2.map((c) => janela(c, dur));
    const repousos = cards2.map((c, k) => [vidas[k].ini + (c.entrada?.duracao ?? 0), vidas[k].fim - (c.saida?.duracao ?? 0)]).filter(([a, b]) => b - a > 0.05);
    let t = dur / 2;
    if (repousos.length) {
      const parados = (x) => repousos.filter(([a, b]) => x >= a - 1e-6 && x <= b + 1e-6).length;
      let n = -1;
      for (const [a, b] of repousos) {
        const x = Math.min(a + 0.1, (a + b) / 2);
        const k = parados(x);
        if (k > n || k === n && x < t) [t, n] = [x, k];
      }
    } else if (vidas.length) {
      const j = vidas.reduce((m, v) => v.fim - v.ini > m.fim - m.ini ? v : m);
      t = (j.ini + j.fim) / 2;
    }
    return +Math.min(Math.max(t, 0), dur - 0.05).toFixed(3);
  }
  function estiloDoQuadro(g) {
    if (!g) return {};
    const base = { transform: `translate(${g.tx * 100}%, ${g.ty * 100}%) scale(${g.s})`, transformOrigin: "0 0" };
    const cantos = `round ${(g.raio ?? 0) * 100}% / ${(g.raio ?? 0) * 100 * 9 / 16}%`;
    if (g.modo === "metade" || g.modo === "recortado") return base;
    if (g.modo === "canto") return { ...base, clipPath: `inset(0 ${cantos})` };
    return { ...base, clipPath: `inset(${(g.topo ?? 0) * 100}% 0 0 0 ${cantos})` };
  }
  function estiloDaPessoa(g) {
    if (g?.modo !== "janela") return null;
    return { transform: `translate(${g.tx * 100}%, ${g.ty * 100}%) scale(${g.s})`, transformOrigin: "0 0", clipPath: `inset(0 0 ${(1 - (g.topo ?? 0)) * 100}% 0)` };
  }
  var buffers = /* @__PURE__ */ new Map();
  var audio = null;
  var soando = /* @__PURE__ */ new Set();
  function buffer(id, c) {
    if (!buffers.has(id))
      buffers.set(
        id,
        fetch(`/biblioteca/sons/${encodeURIComponent(id)}.m4a`).then((r) => r.ok ? r.arrayBuffer() : Promise.reject()).then((b) => c.decodeAudioData(b)).catch(() => null)
      );
    return buffers.get(id);
  }
  async function tocarEvento(e, atrasado, relogio2, log) {
    const c = audio;
    if (!c) return;
    const t0 = performance.now();
    const b = await buffer(e.som, c);
    if (!b || c !== audio) return;
    if (c.state === "suspended") await c.resume().catch(() => {
    });
    atrasado += (performance.now() - t0) / 1e3;
    const vel = e.vel ?? 1;
    const desde = e.desde + Math.max(atrasado, 0) * vel;
    if (desde >= b.duration || e.dur != null && atrasado >= e.dur) return;
    const f = c.createBufferSource();
    f.buffer = b;
    f.playbackRate.value = vel;
    const g = c.createGain();
    g.gain.value = e.ganho;
    if (e.dur != null) {
      const fim = c.currentTime + e.dur - atrasado;
      g.gain.setValueAtTime(e.ganho, Math.max(fim - Math.min(0.12, e.dur / 2), c.currentTime));
      g.gain.linearRampToValueAtTime(0, fim);
    }
    f.connect(g).connect(c.destination);
    f.start(c.currentTime, desde, e.dur != null ? (e.dur - atrasado) * vel : void 0);
    soando.add(f);
    f.onended = () => soando.delete(f);
    log.push({ som: e.som, t: +e.t.toFixed(3), relogio: +relogio2.toFixed(3), ganho: e.ganho, audio: c.state });
  }
  function calarSons() {
    for (const f of soando)
      try {
        f.stop();
      } catch {
      }
    soando.clear();
  }
  async function iniciar() {
    document.documentElement.style.zoom = String(window.innerWidth / 540);
    window.addEventListener("resize", () => document.documentElement.style.zoom = String(window.innerWidth / 540));
    const raiz = document.getElementById("quadro");
    const id = q.get("preset") ?? "";
    const [preset, am, sons] = await Promise.all([
      window.__preset ? Promise.resolve(window.__preset) : json(`/biblioteca/presets/${encodeURIComponent(id)}.json`),
      json("/api/presets/amostras").catch(() => ({ ator: null, midias: [] })),
      json("/biblioteca/sons/catalogo.json").catch(() => [])
    ]);
    const catalogo = { sons, intensidades: INTENSIDADES };
    const original = !q.get("tela") || q.get("tela") === "original";
    const tela = original ? preset.formato === "vertical" ? "vertical" : "dividida" : q.get("tela");
    const formato = tela === "vertical" ? "vertical" : "dividida";
    const nRef = preset.receita.repete ? Math.max(preset.receita.cards.length, 2) : nMidias(preset.receita);
    const n = Math.max(1, Number(q.get("n")) || nRef);
    const aspectos = original && !q.get("prop") ? aspectosDaReferencia(preset.receita, n) : aspectosDe2(q.get("prop") ?? (n === 1 ? "16:9" : "deitada"), n);
    const fonte = preset.fontes?.[0];
    const durRef = fonte ? fonte.fim - fonte.inicio : preset.receita.duracao_ref;
    const dur = Number(q.get("dur")) || (original ? durRef : Math.max(durRef, n > 1 ? 1.8 * n : 2.5));
    const escolhidas = escolherMidias(am.midias, aspectos, preset.id);
    const item = (k, vivo) => {
      const m = escolhidas[k];
      return { id: `sim${k}`, tipo: vivo && m ? "video" : "imagem", largura: Math.round(aspectos[k] * 1e3), altura: 1e3, duracao: m?.duracao ?? 3, arquivo: "", url: (vivo ? m?.video : m?.imagem) ?? "" };
    };
    const bancoDe = (vivo) => new Map(aspectos.map((_, k) => [`sim${k}`, item(k, vivo)]));
    const pedido = {
      id: "sim",
      plano: "sim",
      tipo: formato === "vertical" ? "insert_tela_cheia" : "tela_dividida_insert",
      formato,
      descricao: "",
      texto: null,
      fala: "",
      inicio: 0,
      duracao: dur,
      midias: aspectos.map((_, k) => ({ id: `sim${k}`, banco: `sim${k}` })),
      enriquecimento: { preset: preset.id, divisao: tela === "atras" ? "atras" : void 0 },
      t: { inicio: 0, fim: dur }
    };
    const banco0 = bancoDe(false);
    const ajEf = ajustesEfetivos(preset, void 0, aspectos);
    const divisao = divisaoDe(pedido, banco0, [preset]);
    const base = noFormato(preset, formato, n).receita;
    const receita = comAjustes(receitaParaInsert(comAjustes(base, ajEf, "antes"), divisao, aspectos, formato), ajEf, "depois");
    const noT = noTempo(receita, dur);
    const geometria = geometriaDoAtor(divisao, null, am.ator?.rosto ?? null);
    const eventos = eventosDaReceita(receita, dur, catalogo);
    const tParado = Number(q.get("t")) || instanteParado(noT.cards, dur);
    const t0 = am.ator?.t0 ?? 0;
    for (const e of eventos) void buffer(e.som, new OfflineAudioContext(1, 1, 48e3));
    let atorVideo = null;
    const estiloPessoa = tela === "atras" && am.ator?.pessoa ? estiloDaPessoa(geometria) : null;
    const pessoa = (mostrar) => estiloPessoa && {
      chave: "pessoa",
      tag: "video",
      classe: "absolute inset-0 size-full object-cover pointer-events-none",
      estilo: { ...estiloPessoa, zIndex: 6, display: mostrar ? void 0 : "none" },
      criar: (el) => {
        const v = el;
        v.muted = v.playsInline = true;
        v.preload = "auto";
        v.src = am.ator.pessoa;
      },
      depois: (el) => {
        const v = el;
        const a = atorVideo;
        if (!a) return;
        const alvo = a.preload === "none" ? t0 + 1 : a.currentTime;
        if (Math.abs(v.currentTime - alvo) > 0.08) v.currentTime = alvo;
        if (a.paused !== v.paused) void (a.paused ? v.pause() : v.play().catch(() => {
        }));
      }
    };
    const ator = (g, atras) => ({
      chave: "ator",
      classe: "absolute inset-0 pointer-events-none",
      estilo: { ...estiloDoQuadro(g), zIndex: atras ? 5 : void 0 },
      filhos: [
        am.ator && {
          chave: "video",
          tag: "video",
          classe: "size-full object-cover",
          estilo: am.ator.deitado ? { objectPosition: `${am.ator.x * 100}% 50%` } : {},
          criar: (el) => {
            const v = atorVideo = el;
            v.muted = v.playsInline = true;
            v.preload = "none";
            if (am.ator.poster) v.poster = am.ator.poster;
            v.src = am.ator.video;
          }
        }
      ]
    });
    const aoVivo = (v, t, k = -1) => {
      const kk = /^c\d+$/.test(v.chave) ? Number(v.chave.slice(1)) : k;
      if (v.tag === "video" && v.chave.startsWith("m:") && kk >= 0) {
        const rel = Math.max(t - janela(noT.cards[kk], dur).ini, 0);
        return {
          ...v,
          depois: (el) => {
            const m = el;
            const fim = Number.isFinite(m.duration) ? m.duration - 0.05 : Infinity;
            const alvo = Math.min(rel, fim);
            if (Math.abs(m.currentTime - alvo) > 0.25) m.currentTime = alvo;
            if (rel >= fim) m.pause();
            else if (m.paused && tocando) void m.play().catch(() => {
            });
          }
        };
      }
      return v.filhos ? { ...v, filhos: v.filhos.map((f) => f && aoVivo(f, t, kk)) } : v;
    };
    const quadro = (t, vivo) => {
      const dentro = t >= 0 && t <= dur;
      const banco = vivo ? bancoDe(true) : banco0;
      const camada = (caixa) => {
        const ins = dentro ? insertNoLugar({ pedido, banco, tempo: t, fundo: "gradiente", receita, divisao, caixa }) : [];
        return [fundo("gradiente", "fundo0"), ator(dentro ? geometria : null, dentro && tela === "atras"), pessoa(dentro), ...vivo ? ins.map((v) => aoVivo(v, t)) : ins];
      };
      desenhar(raiz, camada(null));
      if (dentro && receita.cards.some((c) => c.quadros?.length)) {
        const cena = raiz.querySelector('[data-k="cena"]');
        if (cena) desenhar(raiz, camada([cena.clientWidth, cena.clientHeight]));
      }
    };
    let tocando = false;
    let externo = null;
    let comSom = q.get("som") === "1";
    let anterior = -1;
    let inicioPerf = 0;
    let raf = 0;
    const log = [];
    const relogio2 = () => {
      if (externo) return externo();
      const a = atorVideo;
      if (a && !a.error && a.readyState >= 1) return a.currentTime - t0;
      return (performance.now() - inicioPerf) / 1e3;
    };
    const recomecar = () => {
      if (atorVideo) atorVideo.currentTime = t0;
      inicioPerf = performance.now();
      anterior = -1;
      calarSons();
    };
    const passo = () => {
      if (!tocando) return;
      let t = relogio2();
      if (!externo && t > dur + PAUSA) {
        recomecar();
        t = 0;
      }
      if (t < anterior - 0.1) {
        anterior = -1;
        calarSons();
      }
      const a = atorVideo;
      if (a && externo) {
        if (Math.abs(a.currentTime - (t0 + t)) > 0.3) a.currentTime = t0 + Math.max(t, 0);
        if (a.paused) void a.play().catch(() => {
        });
      }
      quadro(t, true);
      if (comSom && audio) {
        for (const e of eventos) if (e.t > anterior && e.t <= t) void tocarEvento(e, t - e.t, t, log);
      }
      anterior = Math.max(anterior, t);
      raf = requestAnimationFrame(passo);
    };
    const tocar = (op = {}) => {
      cancelAnimationFrame(raf);
      tocando = true;
      externo = op.relogio ?? null;
      if (op.som != null) comSom = op.som;
      if (op.audio) audio = op.audio;
      if (comSom) {
        audio ??= new AudioContext();
        if (audio.state === "suspended") void audio.resume().catch(() => {
        });
      }
      if (atorVideo) atorVideo.preload = "auto";
      recomecar();
      if (atorVideo) void atorVideo.play().catch(() => {
      });
      raf = requestAnimationFrame(passo);
    };
    const pararDe = (t) => {
      cancelAnimationFrame(raf);
      tocando = false;
      externo = null;
      calarSons();
      for (const v of document.querySelectorAll("video")) v.pause();
      if (atorVideo && atorVideo.preload !== "none") atorVideo.currentTime = t0 + Math.min(Math.max(t, 0), dur);
      quadro(t, false);
    };
    const prontoVideos = async () => {
      const limite3 = Date.now() + 8e3;
      const ok = () => [...document.querySelectorAll("video")].every((v) => v.error || v.preload === "none" || v.readyState >= 2 && !v.seeking);
      while (!ok() && Date.now() < limite3) await esperar(20);
      await Promise.all([...document.images].map((i) => i.complete ? null : i.decode().catch(() => {
      })));
    };
    pararDe(tParado);
    Object.assign(window.__sim, {
      tocar,
      parar: () => pararDe(tParado),
      som: (ligado) => {
        comSom = ligado;
        if (!ligado) calarSons();
        else if (tocando) {
          audio ??= new AudioContext();
          void audio.resume().catch(() => {
          });
        }
      },
      ir: async (t) => {
        pararDe(t);
        await prontoVideos();
      },
      log,
      info: { preset: preset.id, tela, formato, n, aspectos, dur, tParado, divisao, geometria, eventos, midias: escolhidas.map((m) => m?.id ?? null), ator: am.ator }
    });
    window.addEventListener("message", (e) => {
      const d = e.data;
      if (d?.sim === "tocar") tocar({ som: d.ligado });
      else if (d?.sim === "parar") pararDe(tParado);
      else if (d?.sim === "som") window.__sim.som(!!d.ligado);
    });
    await prontoVideos();
    if (q.get("tocar") === "1") tocar();
  }
  var pronto;
  var falhou;
  window.__sim = {
    pronto: new Promise((ok, erro) => (pronto = ok, falhou = erro)),
    tocar: () => {
    },
    parar: () => {
    },
    som: () => {
    },
    ir: async () => {
    },
    info: {},
    log: []
  };
  void window.__sim.pronto.catch(() => {
  });
  iniciar().then(
    () => pronto(),
    (e) => {
      console.error(e);
      document.title = `erro: ${e.message}`;
      document.getElementById("quadro").innerHTML = `<p style="padding:24px;color:#faf7ee;font:14px Manrope,sans-serif">${String(e.message)}</p>`;
      falhou(e);
    }
  );
})();
