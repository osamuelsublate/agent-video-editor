# Aprendizados · Inserts (busca, captura de tela, escolha da mídia)

O que já foi aprendido nesta área, vídeo a vídeo (como gravar: `etapas/14-concluir.md`). Leia antes de trabalhar nela
e não repita estes erros. **[gosto]** = preferência confirmada pelo criador · **[defeito]** = erro técnico.

## Do criador

## Técnicos (do editor)

- **[técnica] Conferir o trecho inteiro.** Antes de entregar, olhe começo, meio e fim do trecho usado: nada de troca
  de cena, câmera indo para outra coisa, sobreposição do vídeo original (cronômetro, marca d'água, legenda) ou borda do
  fundo aparecendo. _mvi-0717 · 2026-10-12_
- **[técnica] Resolução sobrando.** Baixe sempre a maior resolução disponível e nunca amplie além do que a fonte
  tem. Julgue a nitidez no vídeo final em 4K, em tamanho real — a prévia de 720p esconde o borrado. Se a melhor fonte
  ainda fica borrada, grave a sua própria: rode a ferramenta de verdade (ex.: uma sessão real do terminal) e
  renderize em alta resolução. _mvi-0717 · 2026-10-12_
- **[técnica] O detalhe citado aparece grande.** Se a fala cita um detalhe (uma data, um preço, um número), o insert
  termina nesse detalhe, ampliado e legível. _mvi-0717 · 2026-10-12_
- Os inserts que já estão no banco voltam em ~20 s; os que pedem busca e captura, em 3 a 11 min. _1º teste · 2026-10-10_
- openai.com, claude.com, perplexity.ai, Gamma e Canva bloqueiam a captura (Cloudflare, "Um momento…"): vá para a doc
  oficial (developers.openai.com, docs.anthropic.com), o blog ou o model card do produto. _1º teste_
- Capturas começam em branco enquanto a página carrega: corte o começo com um trecho (`banco.py trecho`). _1º teste_
- Sites com WebGL pesado (esferas 3D) podem sair pretos na captura com a máquina carregada; um vídeo do banco curto
  demais pode virar câmera lenta (`ffmpeg -vf "setpts=PTS/0.42,minterpolate=fps=30:mi_mode=blend"`). _1º teste_
- Exemplos "do que não fazer" (site genérico, site poluído) são os mais difíceis de achar prontos: descreva na marcação
  um tipo concreto e achável (ex.: "a galeria de templates do Lovable"). Nunca monte um mockup sem dizer. _1º teste_
- Apague do banco o que foi capturado e não serviu (`banco.py apagar`): os subagentes deixavam lixo. _1º teste_
- **[técnica] Site pesado sai no loader.** Site 3D/WebGL (lusion, igloo, resn) gravado desde o 1º quadro saiu só na tela
  de carregamento: espere a página carregar antes de gravar (ou corte o começo com um trecho). Páginas do Cloudflare
  ("Attention Required") não servem — troque de site. _do 18 · 3-niveis-de-sites-com-ia · 2026-10-14_
- **[técnica] Só as boas, sem repetir.** Ligue ao insert só as mídias que servem e não repita a mesma mídia em planos
  próximos (uma mídia tinha ido para 3 inserts). _do 18 · 3-niveis-de-sites-com-ia · 2026-10-14_
- **[técnica] "Site genérico de IA" não se acha ao vivo.** Quatro subagentes gastaram o tempo todo procurando um site
  real "roxo, três cards, serifa": não existe como site público. Use o banco; sem nada, deixe sem mídia e peça prints
  ao criador na entrega. _do 18 · 3-niveis-de-sites-com-ia · 2026-10-14_
- **[técnica] Grupos de 3, com limite de tempo.** Um subagente por insert estourou o limite de 20 simultâneos (25
  inserts) e cada um demorou até 11 min: em grupos de 3 (`inserts.py briefs`), com 3 min por insert, a etapa cabe em
  ~3 min. _do 18 · 2026-10-14_
