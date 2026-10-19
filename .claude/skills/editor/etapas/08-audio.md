# 08 · Áudio

Quatro trilhas, iguais na prévia e no MP4: a **voz** (limpeza → passa-altas 80 Hz → timbre, `referencia` por padrão → compressor leve), os
**sons dos presets**, os **sons das transições** e o **fundo** (música 11 dB abaixo da voz, abaixando 3 dB enquanto o ator
fala, em laço com crossfade e fade no fim). No final, −14 LUFS (o padrão do Instagram), pico abaixo de −1,5 dBTP.

> **Antes de começar, leia `biblioteca/aprendizados/audio.md` (+ `biblioteca/exemplos/<categoria>/aprendizados/audio.md`)**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## O que você decide (em `edicao.audio`)

- **`fundo`**: o id de uma trilha de `biblioteca/trilhas/catalogo.json`, pelo clima do vídeo (ou `null` = sem fundo):

| id | clima · BPM |
|---|---|
| `lofi-piano` | calmo, focado · 86 |
| `arpejo-suave` | leve, inspirador · 103 |
| `pads-ambiente` | flutuante, reflexivo · 108 |
| `chillhop` | descontraído · 92 |
| `sinos-leves` | otimista, curioso · 118 |
| `cinematico` | pensativo, com tensão leve · 86 |
| `grave-tech` | focado, escuro · 103 |
| `piano-pulsante` | energia · 152 |

  Tutorial/ferramenta → `lofi-piano`, `chillhop` ou `arpejo-suave`; notícia/novidade de IA → `sinos-leves` ou
  `grave-tech`; opinião forte/polêmica → `cinematico`. Varie entre vídeos seguidos.
- **`voz.limpeza`**: `leve` (padrão, já feita no preparar). `media`/`forte` só se o ruído de fundo incomodar (pede
  rodar a limpeza de novo; veja o preparar). `voz.timbre`: `referencia` (padrão: a voz do Reels
  "Image to HTML", o alvo que o criador escolheu — médios-graves cheios, presença em 1,7 kHz, agudos sem realce) ·
  `encorpada` (o equilíbrio das VSLs de referência, com o ar de 8 kHz) · `natural` (sem equalização) · `quente` · `clara`. Se o criador gravar com outro microfone ou outra pessoa falar,
  compare o espectro da voz com o de uma referência aprovada antes de manter o padrão.
- **`niveis`** (dB em volta do nível das referências, −12 a +6): `ator`, `presets`, `transicoes`, `fundo`. Padrão 0.
  Mexa só com motivo (ex.: o criador achou os sons altos → `presets: -3`).

Nada para rodar: o render aplica tudo. Tempo esperado: segundos.
