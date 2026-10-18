# agent-video-editor

Um editor de Reels por linguagem natural: o **Claude Code é o editor**. Você manda o vídeo bruto (e, se quiser, um
briefing) e ele entrega a edição completa — cortes, 9:16, look, direção visual, inserts reais, motions, transições,
áudio e legenda. Você revisa num app local estilo frame.io, comenta no ponto exato do vídeo e avisa no
chat: ele aplica e renderiza a próxima versão.

![O app de revisão](docs/revisao.jpg)

## Como funciona

Tudo mora numa skill do Claude Code, em [`.claude/skills/editor/`](.claude/skills/editor/SKILL.md):

1. **Vídeo novo → v1, sem parar:** preparar (transcrição palavra a palavra, proxy, rosto, voz limpa) → cortes →
   direção (o roteiro dirigido, plano a plano) → inserts, motions, áudio, legenda e transições em paralelo →
   enriquecimento → render e autorrevisão.
2. **Revisão:** você comenta no app (nos vídeos longos, por blocos de ~30 s, que se finalizam um a um) e avisa no
   chat; os comentários pendentes viram a v(N+1), com uma resposta curta em cada um.
3. **Aprovado:** exporta o final e conclui o vídeo — as correções viram aprendizados (só os que você confirmar), lidos
   antes de cada etapa nos próximos vídeos.

Cada vídeo tem uma **categoria** (📱 Reels, 💰 Ad, 📺 VSL, 🎥 YouTube, 📚 Aula; outras no painel Categorias do app), e
cada categoria tem a sua Calibragem e a sua Heurística: a direção de um vídeo aprende com os vídeos da categoria dele.

As decisões editoriais são do Claude, guiadas pelos exemplos do criador; os scripts validam, calculam tempos e
renderizam. Tudo fica preso às palavras da transcrição (IDs), nunca a segundos — o contrato está em
[`edicao.md`](.claude/skills/editor/edicao.md).

## Estrutura

| Pasta | O que tem |
|---|---|
| `.claude/skills/editor/` | `SKILL.md` (os fluxos) e `etapas/` (um .md por etapa) |
| `ferramentas/` | um script por etapa (`uv run ferramentas/<script>.py`, dependências no próprio arquivo); `inicial/`, a biblioteca de uma instalação nova |
| `render/` | a página que desenha inserts, motions e legenda para o render, com o runtime dos motions, fontes e fundos |
| `app/` | o app de revisão (HTML + JS puro) |
| `biblioteca/` | o que é do criador (fora do git): exemplos da direção por categoria, aprendizados, presets, transições, sons, trilhas, LUTs, motions, banco de mídias, referências (os CTAs são projetos da categoria CTA) |
| `projetos/` | um vídeo por pasta (fora do git) |

### A biblioteca e os projetos

`biblioteca/` e `projetos/` ficam fora do git: um `git pull` nunca mexe nelas. Para levar a biblioteca para outra
máquina, **copie a pasta inteira por cima da de lá** (com o servidor parado): a de lá é substituída, e o que só existia
nela se perde. Sem biblioteca, o servidor cria uma inicial (`ferramentas/inicial/`: os aprendizados técnicos e dois
motions de exemplo). Os projetos são de cada um e não vão junto.

## Rodar

Precisa de [uv](https://docs.astral.sh/uv/), ffmpeg e o [Claude Code](https://claude.com/claude-code). As chaves ficam
num `.env` na raiz (nunca vão para o git):

```bash
OPENROUTER_API_KEY=...
ELEVENLABS_API_KEY=...
```

O app de revisão:

```bash
uv run ferramentas/servidor.py   # http://localhost:8719/app/
```

E no Claude Code, dentro da pasta: *"edite este vídeo: /caminho/do/bruto.mp4"*.
