Escreva um preset de motion novo em {raiz}/biblioteca/motions/presets/{preset}.html (id: {preset}) para o editor de
Reels em {raiz}.
Leia antes: {raiz}/biblioteca/aprendizados/motions.md (o que o criador já corrigiu, em qualquer vídeo) e
{exemplos}/aprendizados/motions.md (os gostos dele nos vídeos de {categoria}, a categoria deste; pode não existir); os recusados em
{raiz}/biblioteca/motions/presets/_recusados/ (o JSON do topo tem o `motivo`), para não repetir; 2 presets existentes
(prompt.html e lettering.html) e {raiz}/render/motion/runtime.js: copie a estrutura (o JSON <script id="preset">
com nome, descricao, fundo, duracao, sons, "a_revisar": true e "projeto": "{projeto}"; o <script id="campos">; o <style>; a timeline do GSAP
pausada entregue com motion.pronto(tl); motion.som/motion.digitar/motion.curva/motion.aCada).
Pedido: {pedido}
Formato: {formato} ({palco}) · duração ~{duracao} s · fala: "{fala}"
{extra}
Regras: poucos elementos; quase nenhum texto além de rótulos curtos (campos editáveis com esses padrões); entrada curta
e suave, chegada longa (curva perto de 0.25,0.1,0.1,1 em 0,8–1 s), nunca linear; a cena nunca para até o corte; fontes
Inter, Instrument Serif ou SF Pro; sons só da biblioteca (biblioteca/sons/catalogo.json). Texto legível num celular (não
menor que ~28 px no palco de 1080). No formato vertical, deixe livre a faixa do meio da altura (~45–55%): a legenda
passa ali.
Teste: abra render/motion.html?preset={preset}&formato={formato}&duracao={duracao}&tocar=1 com o servidor
(`uv run ferramentas/servidor.py <porta livre>`) e fotografe 4 instantes com Playwright; olhe as imagens e corrija até
ficar limpo e legível. No fim, grave a prévia que a página Motions do app toca: `uv run ferramentas/render.py
previas-motions {preset}`. Não ligue o motion ao plano (quem edita liga) e não edite outros arquivos. Responda com o id,
os campos e 1 linha sobre como ficou.
