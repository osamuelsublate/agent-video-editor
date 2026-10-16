# 14 · Concluir um vídeo: aprendizados e faxina do banco

Depois do vídeo aprovado e exportado (`12-final.md`), feche o ciclo em três passos. É aqui que a skill aprende: o que o
criador corrigiu num vídeo não pode se repetir no próximo.

## 1. Aprendizados (com o criador)

1. **Junte o que aconteceu no vídeo:** `uv run ferramentas/revisao.py ler <slug> vN`, para cada versão revisada (as
   revisões ficam em `projetos/<slug>/revisoes/v*.json`, com as suas respostas e os anexos); o que ele respondeu no chat às suas
   dúvidas; e o que você mesmo teve de corrigir na autorrevisão.
2. **Extraia os aprendizados.** Para cada comentário, pergunte: isso vale para os próximos vídeos ou só para este?
   - Correção pontual ("aqui prefiro o outro site") **não** é aprendizado.
   - Um gosto que pode se repetir ("lettering demais", "esse tipo de motion fica poluído", "música alta") é.
   - Um **defeito** técnico (palavra cortada no meio, captura com tela branca, som estourado) é aprendizado **e** pede
     correção na ferramenta, se der: corrija o script e anote "corrigido em <script>".
   - Antes, leia o `biblioteca/aprendizados/<área>.md`: se o aprendizado já existe, reforce (some a origem nova) em vez de repetir.
3. **Mostre ao criador antes de gravar**, numa lista curta por área:
   ```text
   Aprendizados do PRJ-03 (v3 aprovada):
   inserts · [gosto] prefira gravação de tela rolando a print parado quando a fala cita um site  (c2, c5)
   elementos · [gosto] no máximo 1 lettering a cada ~10 s; nunca dois seguidos  (c4)
   cortes · [defeito] o "m" de "mas" vazou na emenda do ✂3 → borda ajustada; regra: …  (autorrevisão)
   Confirma? Pode cortar, mudar o texto ou acrescentar.
   ```
   Grave só o que ele confirmar, com o texto que ele aprovar.
4. **Grave** cada aprendizado no arquivo da área (abaixo), no formato:
   ```markdown
   - **[gosto]** Prefira gravação de tela rolando a print parado quando a fala cita um site.
     _PRJ-03·v2 c2, PRJ-05·v1 c1 · 2026-10-14_ · ![exemplo](imagens/prj03-c2.png)
   ```
   - **Só para uma categoria de vídeo?** Se a correção só vale para a categoria deste vídeo (ex.: um VSL pede um ritmo
     que o Reels não pede), marque o item com `[só <Categoria>]`, pelo nome dela (`calibragem.py categorias`):
     `- **[gosto]** [só VSL] Deixe o preço na tela até o fim do plano.` Sem a marca, vale para todas. Na dúvida,
     pergunte ao criador ao mostrar a lista.
   - Um print ajuda quando o texto sozinho é ambíguo ("poluído", "card grande demais"): copie o anexo do comentário
     (`projetos/<slug>/revisoes/anexos/…`) ou um quadro do vídeo (ffmpeg) para `biblioteca/aprendizados/imagens/<prj>-<cN>.png`
     e mostre-o no bullet (um "certo" e um "errado" lado a lado é o melhor exemplo).
   - Aprendizados de **direção** (que plano, quando, abertura, ritmo, lettering como decisão de roteiro) vão para as
     **Regras do criador** em `biblioteca/exemplos/<categoria>/regras.md` (o criador também as edita na página Heurística do app), não para
     esta pasta.
   - Preset, transição, motion ou trilha que o criador não quer mais: tire das favoritas/recomendados (`ordem.json`) ou
     recuse (página Presets/Motions do app) — e anote o porquê no arquivo da área.

| Área | Arquivo | Lido em |
|---|---|---|
| Cortes | `biblioteca/aprendizados/cortes.md` | `02-cortes.md` |
| Direção | `biblioteca/exemplos/<categoria>/regras.md` (Regras do criador) | `03-direcao.md` |
| Inserts (busca, captura de tela, escolha da mídia) | `biblioteca/aprendizados/inserts.md` | `04-inserts.md` e o prompt dos subagentes |
| Enriquecimento (presets, Full ator, fundo) | `biblioteca/aprendizados/enriquecimento.md` | `05-enriquecimento.md` |
| Motions | `biblioteca/aprendizados/motions.md` | `06-…` e o prompt do subagente de motion |
| Elementos (lettering, ManyChat, caixinha, print) | `biblioteca/aprendizados/elementos.md` | `06-…` e `03-direcao.md` |
| Transições | `biblioteca/aprendizados/transicoes.md` | `07-transicoes.md` |
| Áudio | `biblioteca/aprendizados/audio.md` | `08-audio.md` |
| Legenda | `biblioteca/aprendizados/legenda.md` | `09-legenda.md` |
| Render e autorrevisão | `biblioteca/aprendizados/render.md` | `10-render.md` |

## 2. Faxina do banco

1. Liste o que entrou no banco por causa deste vídeo: `uv run ferramentas/banco.py listar` (cada item mostra o projeto
   de origem e onde é usado).
2. **Não apague.** Com o vídeo aprovado, os selos do banco se resolvem sozinhos (`banco.estados`, a partir da versão
   aprovada): o que entrou no vídeo vira **Usado em vídeo** (com o chip do projeto e do plano), e o que você trouxe para
   este projeto e ficou de fora vira **Recusado**. As recusadas só saem quando o criador clica em "Limpar recusados" no
   Banco do app (vão para `biblioteca/banco/_lixeira/`, recuperável); antes disso ele pode promover qualquer uma a
   **Aprovado** (boa, mesmo sem uso). Os motions usados no vídeo ganham o mesmo selo de uso.
3. **Melhore a descrição** das que ficaram, para servirem de novo: nome claro, descrição do que aparece e do que ela
   ilustrou ("home da Anthropic, título serifado em fundo creme; usada como exemplo de 'clichê de site de IA'"),
   palavras-chave pelos assuntos em que ela serve (edite o `item.json`, ou `banco.py descrever <id>` para a IA sugerir e
   depois corrija). Se só um pedaço do vídeo é bom, crie o trecho (`banco.py trecho`).

## 3. Consolidar (a cada 5 vídeos aprovados)

Os arquivos de `aprendizados/` são lidos em toda edição: precisam ficar curtos. A cada 5 vídeos aprovados (conte os
`prj-*` em `biblioteca/referencias/`), releia cada arquivo: junte bullets que dizem a mesma coisa (somando as
origens), tire os defeitos que já viraram correção no código, e os gostos que o criador desmentiu depois. Mostre ao
criador o antes e o depois de cada arquivo em poucas linhas e grave com o "ok" dele.

## No fim

Diga ao criador, em 3 linhas: quantos aprendizados entraram e em quais áreas, quantas mídias saíram do banco e quantas
ganharam descrição melhor, e que a referência do vídeo está na Calibragem esperando a revisão dele.
