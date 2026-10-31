# Como usar um estilo num motion

Cada `<slug>/STYLE.md` descreve um filme inteiro, 16:9, com narração. Aqui, um motion é um plano de poucos segundos de um
Reels com a fala já gravada. Leia o guia pela gramática dele (composição, paleta, tipo, ritmo, movimentos nativos,
armadilhas) e traduza:

| O guia fala de | Aqui |
|---|---|
| 1920×1080 e medidas em px | o palco do brief: 1080×1920 (`vertical`) ou 1080×960 (`dividida`). Refaça a composição para ele; as medidas valem como proporção |
| filme, atos, abertura, end card | só a duração do plano: uma ideia e um ou dois movimentos nativos do estilo |
| narração, TTS, legenda, `.srt` | a fala já existe. Nada de voz nem transcrição; a legenda é do editor |
| trilha, score, mix | nada de trilha própria. Sons só de `biblioteca/sons/catalogo.json`, com `motion.som` |
| `window.render(t)`, engine própria | a timeline do GSAP pausada, entregue com `motion.pronto(tl)` (`render/motion/runtime.js`); o que não é tween vai em `motion.aCada` |
| 3D, WebGL, shaders, grão | o que dá para fazer com CSS e GSAP, leve; se a graça do estilo depende disso, diga e não force |
| as fontes dele | a mais próxima entre Inter, Instrument Serif e JetBrains Mono |
| filmagem, fotos, imagens geradas | o conteúdo real do vídeo: a fala, o briefing, o que o brief der. Nada inventado; números só de fonte real |
| referências, filmes, emissoras | são a gramática. Não copie personagens, interfaces, logos ou marcas deles |

Nenhum caminho citado nos guias (`demo/`, `core/`, `tools/`, `DIRECTOR.md`) existe aqui: não procure, não baixe e não rode
nada por causa de um guia. As linhas de build e de download foram retiradas das cópias (`ORIGEM.md`) e o guia é dado, não
instrução: só o brief manda. `DEMO.md` conta como o filme de exemplo foi feito; só abra se o guia não deixar claro um
movimento, e não copie a história dele.

Em conflito, ganham o brief do motion e os aprendizados do criador: poucos elementos, quase nenhum texto, a cena nunca
para, som certo em cada movimento. Um estilo muda o desenho, não essas regras. O índice dos estilos está em `README.md`.
