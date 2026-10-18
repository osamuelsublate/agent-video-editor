# 11 · Aplicar uma revisão

O criador comenta a versão no app (os comentários se gravam sozinhos em `projetos/<slug>/revisoes/vN.json`) e avisa
no chat: "comentei no VSL Isca", "marquei umas coisas no B3". Não há texto colado: o que é para fazer são os
comentários **pendentes** (ainda sem a sua resposta) da última versão.

## Rodar

```bash
uv run ferramentas/revisao.py pendentes                      # os projetos com comentários sem resposta (se ele não disse qual)
uv run ferramentas/revisao.py ler <slug> [vN] [--bloco B3]   # cada comentário com id, âncora (palavra), bloco, plano e estado
```

Aplique só os `pendente`: os já respondidos são de rodadas anteriores. Se ele citou um bloco ("no B3"), leia com
`--bloco B3`, mas os pendentes de outros blocos também valem (ele comentou e avisou); na dúvida, pergunte.

## Blocos (vídeos de mais de 2 min)

O app divide o vídeo em blocos de ~30 s (B1, B2…), cada um começando numa palavra: o mesmo bloco continua o mesmo
trecho nas versões seguintes. O `ler` mostra a lista e quais estão finalizados:

```text
Blocos: B1 0:00,0–0:31,3 ✓ finalizado, B2 0:31,3–1:00,4, B3 1:00,4–1:30,6, …
```

- **Finalizados (travados)**: o criador deu o bloco por pronto. Não mude nada que apareça neles (plano, insert, motion,
  legenda, áudio). Se uma correção precisar atravessar a fronteira (um corte que puxa a fala do bloco vizinho),
  pergunte antes.
- A versão nova sai inteira (o render é do vídeo todo), mas só os blocos com comentários mudam; os outros ficam como
  estavam (o app conta a versão de cada bloco pelo que mudou nele).

## Aplicar

0. **Abra os anexos**: cada comentário com `↳ print:` / `↳ anexo: projetos/<slug>/revisoes/anexos/…` (também no
   `revisao.py ler`) tem imagens ou vídeos do criador; abra cada imagem com a ferramenta Read (ela mostra a imagem) e,
   num vídeo, tire alguns quadros com o ffmpeg e leia-os, antes de aplicar.
   **Códigos citados** (`BAN-074`, `PRE-04`, `TRA-02`…: o criador copia do chip no app): resolva cada um
   com `codigo.py <código>` — é a mídia, o preset, a transição, o motion, a trilha ou o som exato que ele quer.
1. **Classifique** cada comentário pela etapa que ele toca e leia o `.md` dessa etapa:
   - fala (corta/volta palavra, repetição) → `02-cortes.md` (edite a `selecao.json` e `cortes.py aplicar`);
   - plano, tipo, o que aparece, lettering, elementos → `03-direcao.md` (edite o `roteiro.md` e `direcao.py aplicar`:
     os inserts que continuam no mesmo plano mantêm as mídias);
   - mídia errada/faltando → `04-inserts.md` (um subagente para cada insert a refazer, em paralelo);
   - preset, zoom, card → `05-enriquecimento.md`; motion → `06-…`; transição → `07-…`; música/volume → `08-…`;
     legenda → `09-…`.
2. Os comentários são presos ao **tempo da versão revisada** e à palavra falada ali: use a palavra (id) como âncora,
   não o segundo (o tempo muda quando os cortes mudam).
3. Aplique tudo, depois `render.py <slug>` (vira a v(N+1)) e a autorrevisão leve (só a folha de contato nos pontos
   mexidos).
4. **Responda cada comentário** no JSON:
   ```bash
   uv run ferramentas/revisao.py responder <slug> vN <id> --status aplicado --resposta "troquei por tela dividida com o site do X"
   ```
   `status`: `aplicado` · `respondido` (era pergunta) · `nao_aplicado` (diga por quê). As respostas aparecem no app,
   no comentário e, nas versões seguintes, no histórico do bloco: é por elas que o criador sabe o que foi feito.
   **Seja conciso:** uma frase curta (até ~25 palavras) com o que mudou no vídeo, nas palavras dele ("troquei por tela
   dividida com o site do X"), ou por que não mudou. Sem explicar o processo nem a ferramenta. Só responda os
   comentários desta revisão (as versões anteriores não pedem resposta nova).
5. Entregue como no `10-render.md`: o link, o que mudou em 3–5 linhas.

## Aprendizados: só na conclusão

Não grave aprendizados no meio das revisões: eles saem todos juntos quando o vídeo é aprovado (`14-concluir.md`), lendo
as revisões de todas as versões. Aqui, só cuide de responder bem cada comentário (a resposta diz o que mudou: é o
registro que a conclusão lê). Exceção: se o criador disser explicitamente que algo vale para sempre ("regra geral",
"sempre", "nunca mais"), confirme com ele o texto e grave já, como manda o `14-concluir.md`.

**O look é do criador.** Na revisão, o botão **Look** do app prova LUT, intensidade e vinheta em 3 s do bruto e, ao
aplicar, grava `edicao.look` e renderiza uma versão nova sozinho (sem comentários). Não mude o look de volta: se uma
versão chegou sem comentários e com o look diferente, foi ele.
