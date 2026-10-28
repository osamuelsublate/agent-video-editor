# 07 · Transições

Em cada troca de plano, uma transição com som. O padrão vem das **favoritas que o criador marcou por par de grupos**
(de onde sai → para onde vai): Full ator · Tela dividida · Tela cheia (9 pares, 2 favoritas cada, em
`biblioteca/transicoes/ordem.json`).

> **Antes de começar, leia `biblioteca/aprendizados/transicoes.md` (+ `biblioteca/exemplos/<categoria>/aprendizados/transicoes.md`)**: o que o criador já corrigiu em vídeos anteriores. Não repita esses erros.

## Rodar

```bash
uv run ferramentas/transicoes.py listar            # a biblioteca e as favoritas de cada par
uv run ferramentas/transicoes.py variar <slug>     # cada corte recebe uma das 2 favoritas do seu par, meio a meio
```

Sem escolha, o corte usa a 1ª favorita do par. `variar` dá variedade sem sair do gosto do criador; rode sempre na v1.

Depois confira contra os exemplos da categoria: cada plano dos roteiros (`biblioteca/exemplos/<categoria>/roteiros/*.md`)
traz a `transição de saída` usada no corte para o seguinte. Onde eles usam efeito (luz, brilho) e onde é corte seco
(quase sempre): ponha efeito só em cortes parecidos com os deles, e troque por `corte-seco` o que o `variar` enfeitou à toa.

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
