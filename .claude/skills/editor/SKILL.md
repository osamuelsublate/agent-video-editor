---
name: editor
description: Edita Reels (9:16) de ponta a ponta a partir de um vídeo bruto — transcrição, cortes, enquadramento, look, direção visual, inserts (banco, captura de site, web), presets, motions, elementos, transições, áudio e legenda — e entrega um proxy para revisão no app local; depois aplica as revisões coladas pelo criador e exporta o final. Use quando o usuário mandar um vídeo para editar ("edita esse vídeo", "/editor <caminho>"), colar uma revisão ("Revisão · <slug> · vN"), aprovar ("Aprovado · <slug> · vN") ou pedir para ver/organizar a biblioteca (banco de inserts, presets, transições, motions, trilhas).
---

# Editor de Reels

Você é o editor de vídeo do criador. Ele manda o bruto (e às vezes um briefing); você edita tudo sozinho, sem parar
para perguntar, e entrega uma versão para ele revisar no app. As decisões editoriais (o que cortar, o que mostrar,
quais inserts, qual preset) são suas, no estilo do criador (`biblioteca/exemplos/`, da categoria do vídeo). Os scripts de `ferramentas/` preparam,
validam, calculam tempos e renderizam.

Antes de cada etapa, leia **só** o `.md` dela em `etapas/` (não carregue todos de uma vez). O estado do projeto está
em `projetos/<slug>/edicao.json` (contrato em `edicao.md`). Todos os scripts: `uv run ferramentas/<script>.py …`, da
raiz do repositório.

## Fluxo 1 — Vídeo novo: do bruto à v1 (sem parar)

Marque a hora de início; a meta é a **v1 em menos de 10 min** para 2 min de bruto. Registre o tempo de cada etapa. O
que segura o relógio (medido): a busca de inserts (~3 min em grupos), um motion novo (~7 min) e a fotografia da camada
de inserts e motions no render (até ~5 min sem cache). Por isso: o motion novo fica fora do caminho da v1, e a camada é
fotografada em segundo plano (o pré-render) enquanto a edição segue.

1. **Preparar** (`etapas/01-preparar.md`): cria o projeto, transcreve, proxy, rosto, voz limpa.
2. **Cortes** (`etapas/02-cortes.md`): você escolhe as palavras que ficam.
3. **Direção** (`etapas/03-direcao.md`): você escreve o roteiro dirigido.
4. **Em paralelo**, num só turno:
   - **Motions** (`etapas/06-motions-e-elementos.md`): na v1, só presets que já existem (ou um vídeo do banco). Se a
     direção pediu algo que nenhum preset faz, o motion novo vai num subagente (opus, `inserts.py motion-brief` +
     `Leia <arquivo> e siga.`) **fora do caminho da v1**: o plano entra na v1 com o preset mais próximo e o novo só
     substitui se ficar pronto antes do render; senão, entra na v2 (diga na entrega);
   - **Inserts** (`etapas/04-inserts.md`): `inserts.py briefs` e um subagente por arquivo (grupos de 3, sonnet), com
     `Leia <arquivo> e siga.`; nunca escreva os briefs à mão;
   - enquanto eles trabalham, você faz **Áudio** (`etapas/08-audio.md`), **Legenda** (`etapas/09-legenda.md`) e
     **Transições** (`etapas/07-transicoes.md`).
5. **Enriquecimento e pré-render, a cada leva** (`etapas/05-enriquecimento.md`): quando um subagente volta,
   `inserts.py juntar`, os presets desses inserts e, em segundo plano, `uv run ferramentas/render.py <slug> --camadas`
   (o pré-render fotografa a camada do que já está pronto; se um já está rodando, ele sai sem fazer nada e o próximo
   pega o resto). Os motions de preset entram já no 1º pré-render.
6. **Render e autorrevisão** (`etapas/10-render.md`): o render da entrega espera o pré-render e acha a camada quase
   toda no cache (só fotografa o que mudou depois); uma rodada de conferência; entrega.

Briefing: se vier, leia antes dos cortes; ele vale para cortes, direção e inserts. Materiais de apoio citados vão para
`projetos/<slug>/apoio/` e são a primeira fonte dos inserts.

## Fluxo 2 — Revisão colada ("Revisão · <slug> · vN", ou "… · vN · bloco B3")

Leia `etapas/11-revisao.md`. Aplique cada comentário do texto colado (com "bloco B3", só os daquele bloco; os
"Travados" não se mexem), renderize a v(N+1) e responda cada um no JSON da revisão, numa frase curta (a resposta diz
o que mudou: é o registro de onde saem os aprendizados na conclusão).

## Fluxo 3 — Aprovado ("Aprovado · <slug> · vN")

Leia `etapas/12-final.md` e exporte o final em 4K; a versão aprovada vai para a Calibragem. Depois **conclua o vídeo**
(`etapas/14-concluir.md`): junte os aprendizados das revisões por área, mostre ao criador e grave só o que ele
confirmar; faça a faxina do banco (apague o que você baixou e não foi usado, melhore a descrição do resto).

## Fluxo 4 — Biblioteca

O criador vê a biblioteca no app (aba Biblioteca) e organiza com você pelo chat. Onde mora cada coisa
(`biblioteca/`): `banco/` (mídias dos inserts; `banco.py`), `presets/` (receitas de enriquecimento + `ordem.json` com as
favoritas por situação; `presets.py listar`), `transicoes/` (+ `ordem.json`, favoritas por par; `transicoes.py listar`),
`motions/presets/*.html`, `trilhas/catalogo.json`, `sons/catalogo.json`, `luts/`. Mudar um preset ou uma transição vale
para os próximos renders de todos os vídeos que os usam. Nada é aprovado sem o criador dizer. Preset novo a partir de
um trecho de referência: `etapas/13-presets-novos.md`.

## Sempre

- **Aprenda com o passado:** antes de cada etapa, leia o `biblioteca/aprendizados/<área>.md` dela (a etapa diz qual);
  os itens marcados `[só <Categoria>]` valem só para os vídeos daquela categoria (pule os de outra). São as
  correções do criador em vídeos anteriores, com exemplos em `biblioteca/aprendizados/imagens/`: não as repita. Subagentes também.
- **Paralelize** o que não depende do resto (subagentes em segundo plano para inserts e motions; comandos independentes
  no mesmo turno). Não espere à toa: enquanto um subagente busca, faça outra etapa.
- **Códigos**: quando o criador citar um código (`PRE-07`, `BAN-012.2`, `REF-03·p7`, `PRJ-02·v3`…), resolva com
  `uv run ferramentas/codigo.py <código>` antes de agir.
- **Guarde o porquê** de cada plano (`porque` no edicao.json): o criador vai perguntar.
- **Dúvidas** que mudam o sentido vão para o chat, na entrega (o tempo e a fala de cada uma). Nada de notas no app:
  o criador não lê.
- **Não reescreva a fala.** Cortes escolhem palavras existentes; legenda só corrige grafia.
- Os originais nunca são alterados. As chaves do `.env` nunca aparecem.
- Ao entregar, diga em poucas linhas: o link do app, a duração final, o tempo total, as dúvidas (com o tempo de cada uma) e o que não
  conseguiu (ex.: insert sem mídia real).
