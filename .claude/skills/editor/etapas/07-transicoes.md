# 07 · Transições

Em cada troca de plano, uma transição com som. O padrão vem das **favoritas que o criador marcou por par de grupos**
(de onde sai → para onde vai): Full ator · Tela dividida · Tela cheia (9 pares, 2 favoritas cada, em
`biblioteca/transicoes/ordem.json`).

> **Antes de começar, leia `biblioteca/aprendizados/transicoes.md` (+ `biblioteca/exemplos/<categoria>/aprendizados/transicoes.md`)**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## Rodar

```bash
uv run ferramentas/transicoes.py listar            # a biblioteca e as favoritas de cada par
uv run ferramentas/transicoes.py variar <slug>     # como nos exemplos: corte seco em ~9 de cada 10 cortes, efeito nas trocas de assunto
```

Rode sempre na v1. O `variar` segue a edição dos exemplos (a `transição de saída` de cada plano dos roteiros, em
`biblioteca/exemplos/<categoria>/roteiros/*.md`: nos Reels, 89% corte seco): grava corte seco em quase todos os cortes
(mesmo onde a 1ª favorita do par tem efeito, que seria o padrão do corte sem escolha) e uma das favoritas com efeito em
~1 de cada 10, nas trocas de assunto (o tipo de tela muda e a fala fecha uma frase), espaçadas; nunca uma com whoosh ou
riser. Depois confira contra os exemplos e mova um efeito para a virada de verdade, se o `variar` errou o ponto.

## A biblioteca (7)

| id | efeito | som |
|---|---|---|
| `corte-seco` | nenhum | — |
| `corte-clique` | seco | clique |
| `corte-camera` | seco | câmera |
| `subida-ao-corte` | seco | riser que termina no corte |
| `luz-colorida` | luz colorida varre o quadro | clique |
| `zoom-desfoque` | aproxima e desfoca até o corte | whoosh |
| `brilho-branco` | véu branco sobe até o corte | riser |

## À mão

Em `edicao.transicoes["<plano que entra>"] = {"id": "<transição>", "par": "<tipo_de>><tipo_para>"}` (o par com os tipos
exatos dos dois planos; `transicoes.py variar` mostra). Use para dar peso a um momento (virada do vídeo → `brilho-branco`
ou `zoom-desfoque`) ou para limpar excesso (três efeitos seguidos cansam: troque o do meio por `corte-seco`). Para voltar
ao padrão, apague a chave.

Tempo esperado: segundos.
