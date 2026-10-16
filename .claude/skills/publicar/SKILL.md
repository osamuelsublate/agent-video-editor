---
name: publicar
description: Exporta e publica os vídeos aprovados no editor (Reels e anúncios de perpétuo e pico da Asimov) — encaixa o corpo de um Reels nos CTAs, exporta em 4K/24 fps, cria as pastas no Google Drive, sobe os arquivos e cria/preenche os cards no Notion ("Edição e Publicação - 2026"). Use quando o criador aprovar um Reels e pedir para exportar, subir, organizar ou publicar (VSL, aulas e YouTube ficam de fora).
---

# Publicar: do aprovado ao Drive e ao Notion

Vale para **Reels e anúncios** (Reels, perpétuo LP/VSL/ISCA, pico). VSL, aulas e YouTube são outro processo.
As regras do `~/Movies/CLAUDE.md` valem aqui: **nunca apagar nem sobrescrever vídeo** (antes de copiar/mover, confira que
o destino não existe) e a **regra de ouro**: antes de criar qualquer pasta no Drive ou card no Notion, mostre ao criador o
plano completo (cada arquivo → qual pasta, o nome exato de cada pasta e cada card, os valores de cada campo) e só execute
depois de um "sim" claro.

## 1. Quais saídas

Ao aprovar um Reels, o criador diz (ou você pergunta) **quais CTAs se encaixam no corpo e que tipo de vídeo cada
encaixe vira**. Os CTAs são projetos do editor (categoria 💰 CTA), gravados para entrar depois do corpo: o áudio deles
continua a trilha do corpo (`audio.continua: "<corpo>"` no edicao.json do CTA, `audio.fade_fim: false` no do corpo).
Exemplo (mvi-0719, 16/10): corpo + CTA ManyChat → **Reels**; + CTA VSL → **Perpétuo VSL**; + CTA LP → **Perpétuo LP**;
+ CTA da live da Black → **Pico · Captura**.

## 2. Exportar e encaixar

1. Marque as versões aprovadas (`aprovado: true` em `projetos/<slug>/revisoes/vN.json`) e confira que o edicao.json não
   mudou desde a vN (`versoes/vN/edicao.json`).
2. Final de cada projeto (corpo e CTAs), 4K 2160×3840, 24 fps, HEVC, −14 LUFS: `uv run ferramentas/render.py <slug> --final`.
3. Encaixe (corpo + CTA), com a transição destacada na emenda — **TRA-04 Luz colorida** (padrão) ou **brilho branco**:
   ```bash
   uv run ferramentas/encaixar.py <corpo> <cta> "<saida.mp4>" [--transicao brilho-branco]
   ```
   Ele confere áudio (LUFS do fim do corpo × começo do CTA) e cor (luma/saturação dos quadros da emenda) e avisa se a
   troca vai assustar. Com aviso, corrija (nível da voz, look) e encaixe de novo antes de subir.
4. Os arquivos ficam em `~/Movies/<pasta do bruto>/editados/`, com nomes claros (`3 níveis de IA - Reels.mp4`,
   `3 níveis de IA - VSL.mp4`…). Se houver saídas por plataforma (Instagram, TikTok, Shorts), uma por arquivo.

## 3. Drive

Antes de numerar, **liste a pasta raiz** e ache o maior número (filtre por `createdTime` recente; a de Ads tem 1000+ pastas
e a primeira página não basta). Crie a pasta pelo MCP do Drive (`create_file` com mimeType de pasta) e **suba os vídeos
pelo navegador do criador** (Claude in Chrome: a página da pasta no Drive e o `file_upload` no campo de arquivo) — o MCP
não sobe arquivos grandes.

| Saída | Pasta raiz | Nome da pasta |
|---|---|---|
| Reels | "Rodrigo" `1j9kZtWZJZgh7eb31qnqKLOJYB_nD3Dtp` | `n_nome_do_reels` (ex.: `56_3_niveis_de_ia`) |
| Perpétuo LP / VSL / ISCA | Ads `15Igbv6wQnMihfrFh-f_25zBY8XMxdw1w` | `NNN [COD_PROD FUNIL] Nome do ad` (ex.: `1085 [FIA VSL] 3 Níveis de IA`), uma pasta por funil |
| Pico · Captura (Black) | `11TDBjW0vvaaldLq_wboyC4XzborO65pn` | `XX Nome do Ad` (ex.: `21 Rodrigo 3 níveis de IA`) |
| Pico · Carrinho (Black) | `11yWWQni7MmyonmpOzIvMCHb6iYAbYL2U` | idem |

Perpétuo: **LP** faz o pitch direto para a landing page (compra); **VSL** convida para uma aula gratuita (curiosidade,
ainda não é venda); **ISCA** atrai para uma isca digital.

## 4. Notion

Base "Edição e Publicação - 2026", data source `3063ee05-7ee5-8134-a30f-000bbc36e56c` (título = chave `""`). Pelo MCP do
Notion (ou pelo navegador do criador, se algum campo não aceitar). Em todos: **Responsável pela gravação, Copywriter e
Editor = Rodrigo Tadewald** (`8147cc82-d2ee-4a16-ab14-0fec77b9f1a5`), **Prazo = hoje**, **Status = ✔️ Aguardando
Publicação**, **Formato = 📽️ Vídeo**, **Perfil = Rodrigo**, **Link da Pasta = a pasta do Drive**. Antes de criar, procure
o card pelo nome: se o criador já criou, preencha esse.

- **Reels** (template Reels `3063ee05-7ee5-81c4-9d86-d23a41763aac`): título = o nome do vídeo (ex.: "3 níveis de IA");
  Mídia 📸 Reels / Tiktok. No corpo: o roteiro (a fala do vídeo, `projetos/<corpo>/roteiro.md` sem as marcações + o CTA
  do Reels) e a **descrição** proposta com a skill `roteiro-to-descricao` (vault: `~/Obsidian Notes/3 Skills/`).
- **Perpétuo** (template Criativo `3063ee05-7ee5-816f-b147-f12935ee6519`), um card por funil: título `[FUNIL]_NNN_Nome`
  (ex.: `[VSL]_1085_3 Níveis de IA`), ícone 💰; Produto (ex.: 🤖 FIA), Mídia 💰 Criativo, Etapa do Funil Topo;
  **Campanha**: LP em branco · VSL `[COD_PROD]_VSL_Nome_do_ad` · ISCA `[COD_PROD]_ISCA_Nome_do_ad`; **Landing Page em branco**
  (o criador preenche).
- **Pico** (template Criativo): título = o nome da pasta (`XX Nome do Ad`); Fase Black Friday (Captura ou Carrinho),
  Produto Black Friday, Público Black Friday (Público geral), Mídia 💰 Criativo.

## 5. Entrega

Mande ao criador **todos os links do Notion criados/preenchidos** (para conferência) e os das pastas do Drive. Depois,
os vídeos seguem a etapa de conclusão do editor (Calibragem e aprendizados).

## Aprendizados (manter atualizado)
