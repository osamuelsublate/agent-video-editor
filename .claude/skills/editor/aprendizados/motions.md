# Aprendizados · Motions

O que já foi aprendido nesta área, vídeo a vídeo (como gravar: `etapas/14-concluir.md`). Leia antes de trabalhar nela
e não repita estes erros. **[gosto]** = preferência confirmada pelo criador · **[defeito]** = erro técnico.

## Do criador

- **[gosto] Identidade visual.** Fundo escuro: cards de vidro do design system da Asimov (fundo branco a 5%, borda
  branca a 10%, desfoque de 12 px), tipografia Inter fina, uma única cor de acento e o fundo oficial da marca (a
  chuva da Asimov, `chuva`). Fundo claro: objetos e ícones reais (arquivos, pastas, apps) sobre fundo liso. Nunca
  cards sólidos chapados nem fonte pesada. _mvi-0717 · 2026-10-12_
- **[gosto] Mostrar, não escrever.** Poucos elementos e quase nenhum texto: se o motion precisa de uma frase para ser
  entendido, ele não está mostrando a ideia. _mvi-0717 · 2026-10-12_
- **[gosto] Movimento suave e vivo.** Tudo com ease (entrada curta, chegada longa), nunca linear; a cena nunca congela
  — depois da entrada, algo continua se movendo devagar até o corte. _mvi-0717 · 2026-10-12_

## Técnicos (do editor)

- **[técnica] O design system vem do original.** Cores, vidro, fontes e fundos saem dos arquivos do design system do
  criador (CSS, fontes, gravações), nunca recriados de cabeça. Se não achar o original, pergunte ao criador antes de
  aproximar. _mvi-0717 · 2026-10-12_
- **[técnica] Números de verdade.** Todo número na tela vem de fonte real (documentação, anúncio). Se for
  ilustrativo, avise o criador numa nota. _mvi-0717 · 2026-10-12_
- **[técnica] O meio da tela é da legenda.** Num motion de tela cheia com texto no centro (um Lettering "Nível 1"), a
  legenda cai em cima: esconda a legenda das palavras desse plano (`legenda.ajustes` com `""`) e confira no proxy.
  Motion novo de tela cheia deixa livre a faixa do meio (~45–55% da altura). _do 18 · 3-niveis-de-sites-com-ia · 2026-10-14_
- **[técnica] O motion novo primeiro.** É a tarefa mais longa (~7 min): dispare o subagente logo depois da direção,
  antes dos inserts, senão é ele que segura a entrega. _do 18 · 2026-10-14_
