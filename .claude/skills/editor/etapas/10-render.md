# 10 · Render e autorrevisão

> **Antes de começar, leia `biblioteca/aprendizados/render.md` e, na autorrevisão, confira o vídeo contra os aprendizados de todas as áreas**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## Render do proxy

```bash
uv run ferramentas/render.py <slug>
```

Gera `projetos/<slug>/versoes/vN/` (N = a próxima): `proxy.mp4` (720p, 24 fps, tudo queimado), uma cópia do
`edicao.json`, `palavras.json` e `planos.json` (no tempo do vídeo final, para o app), `notas.json` (suas dúvidas e as
dos cortes) e `info.json` (tempos e avisos). Leia os avisos impressos (ex.: voz limpa ausente).

Como funciona: a página `render/?projeto=<slug>` desenha a camada dos inserts, motions e elementos; Chromes escondidos a
fotografam quadro a quadro; uma passada só do ffmpeg junta o ator (cortes, 9:16, look, zoom do Full ator, posição na
tela dividida), a camada, as transições, a legenda (ASS) e o áudio (voz limpa, sons, trilha com ducking, −14 LUFS).

## Autorrevisão (1 rodada, antes de entregar)

1. `uv run ferramentas/folha.py projetos/<slug>/versoes/vN/proxy.mp4 --cada 1` e **olhe** a folha: inserts no lugar e
   com a mídia certa, nada vazio ou preto, legenda legível e fora do conteúdo importante, elementos com texto certo,
   abertura forte (gancho visual).
2. `uv run ferramentas/gemini.py projetos/<slug>/versoes/vN/proxy.mp4 "<pergunta>"` com:
   ```text
   Você revisa um Reels editado antes de ir para o criador. Aponte só problemas concretos, com o tempo (m:ss):
   corte brusco ou palavra cortada no meio; insert que não combina com o que está sendo dito; tela preta ou vazia;
   legenda sobre texto importante ou ilegível; som alto demais, estalo ou música cobrindo a voz; repetição de fala.
   Se estiver tudo bem num item, não comente. Máximo 10 itens.
   ```
3. Separe o que é **grave** do que é **ajuste**:
   - **grave** (o criador não deveria ver): fala cortada no meio de uma palavra, tela preta ou vazia, mídia errada ou
     quebrada, um texto na tela errado (nome de ferramenta, número). Corrija e renderize de novo **uma vez**, apagando a
     versão descartada (`versoes/vN/`) para a entregue ser a v1;
   - **ajuste** (gosto, ou uma limitação conhecida, como a legenda sobre o conteúdo de um insert em tela cheia): não
     renderize de novo; vire uma nota em `edicao.notas` ("vi isso, posso trocar por…") e acrescente direto em
     `versoes/vN/notas.json` (mesmo formato, com `ini`/`fim` no tempo do vídeo final), para aparecer no app.
   Sem nada grave, entregue a v1 como saiu do primeiro render.

## Entregar

```bash
uv run ferramentas/servidor.py      # se não estiver no ar (em segundo plano) → http://localhost:8719/app/
```
Diga ao criador, em poucas linhas: o link do app, a duração final, quanto tempo levou, as dúvidas que deixou como nota
e o que não conseguiu (ex.: "o insert do p7 ficou com um print estático: o site exige login").

Tempo esperado (máquina calma, 1 min de vídeo com metade em insert): ~55 s do zero; numa revisão, 15 a 26 s, porque os
trechos de insert/motion que não mudaram vêm do cache (`.cache/camadas/` do projeto) e o áudio também, se não mudou. O
render imprime "N trechos do cache, M para fotografar". Autorrevisão: ~30 s (o Gemini responde em ~16 s).
