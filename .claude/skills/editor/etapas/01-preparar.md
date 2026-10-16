# 01 · Preparar

Do bruto à matéria-prima: o projeto criado, o vídeo em 9:16, a transcrição palavra a palavra com IDs, os silêncios, o
proxy, o rosto do ator e a voz limpa.

## Rodar

```bash
uv run ferramentas/preparar.py "<caminho do bruto>" --nome "<nome curto do vídeo>" [--briefing "<texto ou arquivo>"]
```

- O nome vira o slug (`projetos/<slug>/`). Use um nome curto do assunto ("Melhor IA design"), não o nome do arquivo.
- Materiais de apoio que o criador citou: copie para `projetos/<slug>/apoio/` logo depois (com `cp -c`).
- Briefing em áudio: transcreva com o próprio preparar num projeto à parte ou com `gemini.py` e use o texto.

## O que ele faz (em paralelo)

- Bruto **horizontal** (16:9): a câmera virtual segue o rosto e gera `midia/bruto_9x16.mp4`, que vira a fonte (suavidade
  Normal). Vertical: passa direto.
- Proxy 720p, `audio.wav`, `silencios.json` (−35 dB, ≥ 0,3 s).
- Transcrição **ElevenLabs Scribe v2** → `transcricao.json` (IDs `w00000…`, tempos no bruto; nada é limpo: repetições e
  tentativas ficam, porque é delas que os cortes decidem). Sem plano B: se falhar, pare e diga o motivo ao criador.
- Rosto do ator (MediaPipe) → `midia/rosto/f1.json` (enquadra o ator na tela dividida e centra o zoom do Full ator).
- Voz limpa Leve (DeepFilterNet) → `midia/voz/f1_leve.wav`; nível da voz (`nivel_voz`, regula os sons).
- `edicao.json` inicial com os padrões: look sem LUT, vinheta Leve, nitidez Leve, velocidade 1×, legenda palavra a palavra,
  limpeza Leve, timbre Natural, sem trilha (você escolhe no Áudio).

## Conferir

- O resumo impresso: duração, medidas, nº de palavras. Uma fala de 2 min tem ~300–400 palavras; muito menos indica
  áudio ruim ou idioma errado.
- Erro: leia a mensagem; não tente contornar trocando de motor sem falar com o criador.

Tempo esperado: < 1 min para 2 min de bruto vertical (mais ~30 s num 16:9).
