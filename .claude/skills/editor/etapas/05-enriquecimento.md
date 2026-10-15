# 05 · Enriquecimento

Como as mídias de cada insert aparecem (onde fica cada card, como entra, se mexe e sai, com os sons de apoio) e o
movimento de câmera nos planos de Full ator. Tudo vem de **presets aprovados** pelo criador (`biblioteca/presets/`):
receitas genéricas que se adaptam ao nº de mídias, à proporção delas e à divisão da tela.

> **Antes de começar, leia `biblioteca/aprendizados/enriquecimento.md`**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## Rodar

```bash
uv run ferramentas/presets.py listar              # os aprovados: nome, onde vale, nº de mídias, proporções, sons
uv run ferramentas/presets.py escolher <slug>     # cada insert com mídia e sem preset recebe o 1º favorito da situação
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

## Full ator

Em `inserts.ator_planos[<plano>]`: `zoom_lento` (+3 %/s, até +15 %, nunca para) ou `zoom_seco` (+18 % de uma vez, até o
fim do plano). O centro é o rosto. Proposta inicial (ajuste com as revisões do criador):
- Full ator de 3 s ou mais → `zoom_lento`;
- frase curta de impacto (conclusão, virada, "e o mais curioso é…") → `zoom_seco`;
- dois Full ator seguidos (separados por um corte) não usam o mesmo movimento.

## Fundo e card do comentário

- `inserts.fundo`: o fundo atrás dos inserts com moldura, para o vídeo todo: `gradiente` (padrão, escuro), `chuva`
  (vídeo escuro), `verde_claro`, `papel`, `nevoa`. Mídias escuras pedem fundo claro e vice-versa.
- Comentário + insert + ator: o card usa o texto do plano; `pedido.comentario` aceita `{"avatar": 0-4, "escala": 0.6-1.3,
  "x": %, "y": %}` só se a posição automática cobrir algo importante.

Tempo esperado: < 1 min.
