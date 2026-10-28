# 05 · Enriquecimento

Como as mídias de cada insert aparecem (onde fica cada card, como entra, se mexe e sai, com os sons de apoio) e o
movimento de câmera nos planos de Full ator. Tudo vem de **presets aprovados** pelo criador (`biblioteca/presets/`):
receitas genéricas que se adaptam ao nº de mídias, à proporção delas e à divisão da tela.

> **Antes de começar, leia `biblioteca/aprendizados/enriquecimento.md` (+ `biblioteca/exemplos/<categoria>/aprendizados/enriquecimento.md`)**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## A referência: a edição dos exemplos

Cada plano dos roteiros de exemplo da categoria (`biblioteca/exemplos/<categoria>/roteiros/*.md`, os mesmos da direção)
diz como ele foi editado, logo abaixo da marcação:
```
[Tela dividida · insert: o terminal rodando /graphify]
edição: Mergulho — no comando citado
transição de saída: corte seco
“tu pode simplesmente rodar o Graphify”
```
Antes de escolher, leia essas linhas: elas mostram, plano a plano, que preset o criador usa em cada tipo de fala, com
que frequência a mídia se mexe e quando há zoom ou mergulho (quase sempre, nada: "Corte seco", "sem movimento"). Siga o
padrão delas: zoom, mergulho e zoom no ator só onde a fala pede como nos exemplos (um detalhe citado, a virada), nunca
para preencher.

## Rodar

```bash
uv run ferramentas/presets.py listar              # os aprovados: nome, onde vale, nº de mídias, proporções, sons
uv run ferramentas/presets.py escolher <slug>     # cada insert com mídia e sem preset recebe o 1º favorito da situação
```

**A cada leva de inserts que fica pronta** (um subagente voltou): `inserts.py juntar <slug>`, os presets desses inserts e,
em segundo plano, o pré-render (fotografa a camada do que já está pronto para o cache; se um já está rodando, sai sem
fazer nada e o próximo pega o resto):
```bash
uv run ferramentas/render.py <slug> --camadas     # em segundo plano (run_in_background)
```

`escolher` usa as favoritas que o criador marcou por **situação** (modo de tela × nº de mídias × proporção, em
`biblioteca/presets/ordem.json`). Ele imprime a escolha de cada insert e o motivo.

**Sempre revise a escolha:** o `escolher` põe o 1º favorito da situação em todos, e quase toda tela dividida com 1 mídia
cai no mesmo (no 1º teste, 9 de 12 inserts com "Corte seco"). Alterne entre os favoritos da situação (`presets.py listar`
mostra as situações ★) para os inserts vizinhos não ficarem iguais.

## Quando trocar à mão

Edite `inserts.pedidos[i].enriquecimento` no `edicao.json`:
- `preset`: o id de outro preset que sirva (`presets.py listar`). Varie entre inserts vizinhos parecidos para o vídeo
  não ficar repetitivo; mantenha o favorito nos inserts mais importantes (abertura, a ferramenta principal).
- `ajustes` (só este insert; escolher a opção que o preset já é = não mexer):

| id | opções | efeito |
|---|---|---|
| entrada · saida | Lenta · Normal · Rápida | duração da entrada/saída ×1,4 ou ×0,7 |
| zoom | Menos · Normal · Mais | quanto o zoom aproxima |
| zona | Topo à esquerda … Base à direita (3×3) | ponto da imagem que fica parado no zoom de saída |
| forma | Card · Tela toda | card centrado com cantos e sombra, ou a área inteira (só se a mídia não for cortada) |
| camera | Parado · Leve · Mais | zoom lento contínuo: 0, 1,5 %/s, 3 %/s |
| desfoque | Sem · Normal · Mais | desfoque na entrada |
| tamanho | Menor · Normal · Maior | tamanho do card ×0,86 / ×1,12 |
| proximo | Antes · Normal · Depois | quando a mídia seguinte entra |
| deslize | Pouco · Como na referência · Até a borda | só em card que transborda e desliza |
| som | Sem · Baixo · Médio | os sons de apoio do preset neste insert |
| y · largura | "−25…25" · "70…130" (texto) | sobe/desce os cards (% da área) · largura (%) |

Ex.: um print com texto pequeno pede `"zoom": "Mais"` e `"zona"` no ponto do texto; uma sequência rápida de 3 mídias
num insert curto pede `"entrada": "Rápida"`.

**Ator embaixo** (`enriquecimento.divisao: "atras"`, o ator numa janela embaixo, com a cabeça saindo por cima;
`enriquecimento.ator.escala` muda o tamanho, padrão 0,55): precisa do recorte da silhueta, senão a janela mostra só o
peito. Rode uma vez por projeto, em segundo plano: `uv run ferramentas/recorte.py <slug>`.

## Full ator

Em `inserts.ator_planos[<plano>]`: `zoom_lento` (+3 %/s, até +15 %, nunca para) ou `zoom_seco` (+18 % de uma vez, até o
fim do plano). O centro é o rosto. **Padrão: sem movimento** (sem a chave), como na maioria dos Full ator dos exemplos
("edição: sem movimento"). Movimento só onde os exemplos da categoria usam numa fala parecida (uma frase curta de impacto,
a virada) — nunca pela duração do plano.

## Fundo e card do comentário

- `inserts.fundo`: o fundo atrás dos inserts com moldura, para o vídeo todo: `gradiente` (padrão, escuro), `chuva`
  (vídeo escuro), `verde_claro`, `papel`, `nevoa`. Mídias escuras pedem fundo claro e vice-versa.
- Comentário + insert + ator: o card usa o texto do plano; `pedido.comentario` aceita `{"avatar": 0-4, "escala": 0.6-1.3,
  "x": %, "y": %}` só se a posição automática cobrir algo importante; `"ate": "<id da palavra>"` tira o card depois dessa
  palavra e o plano segue com o mesmo insert e a mesma divisão (no sim sim sim, o card some no "Sim"; e a foto, `avatar`,
  muda a cada pergunta). _simsim-aplicativos v4 c2/c3 · 2026-10-21_

Tempo esperado: < 1 min.
