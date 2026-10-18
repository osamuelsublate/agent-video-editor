# 11 · Aplicar uma revisão

O criador comenta a versão no app e cola aqui o texto do botão "Copiar revisão":

```text
Revisão · <slug> · v2
[0:03,2] "a galera considera" — tira esse motion, prefiro tela dividida com o site
[0:12,0–0:15,4] "esses dois sites" — mostra os dois, um de cada vez
  ↳ print: projetos/<slug>/revisoes/anexos/c2-1.png
[0:20,1] ↪ v1·c4 "o card ficou grande demais" — "e aqui" — ainda grande, metade disso
Geral: legenda um pouco mais baixa
(projetos/<slug>/revisoes/v2.json)
```

## Rodar

```bash
uv run ferramentas/revisao.py ler <slug> [vN]     # cada comentário com id, âncora (palavra) e o plano sob ele
```

**Réplicas (`↪ v1·c4 "…"`)**: no app, a versão anterior aparece numa linha própria ("Anterior") e numa aba do
painel, com a sua resposta a cada comentário; o criador marca o que ficou bom como concluído e responde o que não ficou.
Uma réplica continua aquela conversa: o `revisao.py ler` mostra o que ele pediu antes e o que você respondeu. Se ele
voltou ao assunto, a primeira solução não resolveu: entenda por quê e não a repita.

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
   no comentário e, na versão seguinte, na conversa da aba "Anterior": é por elas que o criador sabe o que foi feito.
   **Seja conciso:** uma frase curta (até ~25 palavras) com o que mudou no vídeo, nas palavras dele ("troquei por tela
   dividida com o site do X"), ou por que não mudou. Sem explicar o processo nem a ferramenta. Responda as réplicas
   do mesmo jeito (o id delas é o desta versão).
5. Entregue como no `10-render.md`: o link, o que mudou em 3–5 linhas.

## Aprendizados: só na conclusão

Não grave aprendizados no meio das revisões: eles saem todos juntos quando o vídeo é aprovado (`14-concluir.md`), lendo
as revisões de todas as versões. Aqui, só cuide de responder bem cada comentário (a resposta diz o que mudou: é o
registro que a conclusão lê). Exceção: se o criador disser explicitamente que algo vale para sempre ("regra geral",
"sempre", "nunca mais"), confirme com ele o texto e grave já, como manda o `14-concluir.md`.

**O look é do criador.** Na revisão, o botão **Look** do app prova LUT, intensidade e vinheta em 3 s do bruto e, ao
aplicar, grava `edicao.look` e renderiza uma versão nova sozinho (sem comentários). Não mude o look de volta: se uma
versão chegou sem comentários e com o look diferente, foi ele.
