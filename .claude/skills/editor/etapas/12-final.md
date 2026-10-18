# 12 · Vídeo final

O criador aprovou uma versão no app ("Aprovado · <slug> · vN") ou por mensagem. Se foi por mensagem, marque a versão como
aprovada no app, igual ao botão: `aprovado: true` em `projetos/<slug>/revisoes/vN.json` (crie o arquivo com
`{"projeto", "versao", "aprovado": true, "enviado_em": null, "comentarios": []}` se não existir). Os selos "Usado em
vídeo" do banco e dos motions saem da versão aprovada.

```bash
uv run ferramentas/render.py <slug> --final
```

- Usa o `edicao.json` atual. Se ele mudou depois da vN aprovada (confira com `versoes/vN/edicao.json`), avise e pergunte
  antes: o aprovado é a vN.
- Sai em `projetos/<slug>/final/<nome> · <data>.mp4`: 2160×3840 (4K), HEVC, 24 fps, AAC 320 kbps, −14 LUFS. **Sempre
  junto, na mesma pasta, `<nome> · <data>.md`: a transcrição do vídeo** (a fala que ficou no corte, em parágrafos, com
  a grafia corrigida), que o criador usa para a legenda do post e o Obsidian. O render grava os dois; confira que o
  `.md` saiu e entregue os dois caminhos. As saídas com CTA (`encaixar.py`) também saem com o `.md` ao lado.
- Entregue com o caminho e `open -R "<arquivo>"` (abre o Finder no arquivo).
- Depois, a vN aprovada vira referência da Calibragem (sem Gemini; refazer substitui):

  ```bash
  uv run ferramentas/calibragem.py de-projeto <slug> vN
  ```

  Diga ao criador que o vídeo está na Calibragem do app como "a revisar" (com os comentários das revisões guardados):
  ele confere a direção e marca como revisado. Só aí ela entra nos roteiros de exemplo e ensina a direção.

Tempo esperado: ~1 min por minuto de vídeo.

Depois, **conclua o vídeo**: `14-concluir.md` (aprendizados com o criador e faxina do banco).
