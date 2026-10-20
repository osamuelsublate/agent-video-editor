# 12 · Vídeo final

O criador aprovou uma versão no app ("Aprovado · <slug> · vN"), **uma saída** ("Aprovado · <slug> · saída <Destino>") ou
por mensagem. Se foi por mensagem, marque a versão como
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
- **Projeto com saídas** (`cortes.py saidas <slug>`): o Aprovar do projeto aprova todas — exporte todas com
  `uv run ferramentas/render.py <slug> --saidas`; "Aprovado · <slug> · saída <Destino>" é só uma: `--saida <id>`. Cada
  uma sai em `final/saidas/<nome> - <destino>.mp4` + `.md`: a falada renderizada em 4K com o final; a de CTA, o final do
  corpo emendado no final do CTA (`encaixar.py`, com a transição destacada; o CTA precisa ter o final exportado); a sem
  final, o corpo com o nome da saída. Exportar de novo substitui o arquivo da saída. É essa pasta que a `publicar` usa.
- Depois, a vN aprovada vira referência da Calibragem (sem Gemini; refazer substitui):

  ```bash
  uv run ferramentas/calibragem.py de-projeto <slug> vN
  ```

  Diga ao criador que o vídeo está na Calibragem do app como "a revisar" (com os comentários das revisões guardados):
  ele confere a direção e marca como revisado. Só aí ela entra nos roteiros de exemplo e ensina a direção.

Tempo esperado: ~1 min por minuto de vídeo com a camada do 4K já no cache; sem ela, a foto da camada em 4K leva ~4 min
a mais por vídeo de 45 s. Por isso, **quando entregar uma versão que pode ser a aprovada** (sem comentários pendentes,
ou o criador falou em exportar), rode em segundo plano `uv run ferramentas/render.py <slug> --camadas --final`: o
`--final` acha a camada pronta e só monta.

Depois, **conclua o vídeo**: `14-concluir.md` (aprendizados com o criador e faxina do banco).
