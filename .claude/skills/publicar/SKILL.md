---
name: publicar
description: Exporta e publica os vídeos aprovados no editor (Reels e anúncios de perpétuo e pico da Asimov) — encaixa o corpo de um Reels nos CTAs, exporta em 4K/24 fps, cria as pastas no Google Drive, sobe os arquivos, cria/preenche os cards no Notion ("Edição e Publicação - 2026"), atualiza a nota da copy no Obsidian e agenda os Reels (Metricool; automação "comente X" no ManyChat). Use quando o criador aprovar um Reels e pedir para exportar, subir, organizar ou publicar (VSL, aulas e YouTube longo ficam de fora).
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
**Reels com ManyChat ("comente X") tem duas versões**: a do Instagram, com o CTA "comente X", e a do TikTok/YouTube
Shorts, com um CTA "acesse o link da descrição" (lá não há ManyChat). Se o CTA "link da descrição" não foi gravado,
avise o criador antes de exportar.

## 2. Exportar e encaixar

1. Marque as versões aprovadas (`aprovado: true` em `projetos/<slug>/revisoes/vN.json`) e confira que o edicao.json não
   mudou desde a vN (`versoes/vN/edicao.json`).
2. Final de cada projeto (corpo e CTAs), 4K 2160×3840, 24 fps, HEVC, −14 LUFS: `uv run ferramentas/render.py <slug> --final`.
3. Encaixe (corpo + CTA), com a transição destacada na emenda — **TRA-04 Luz colorida** (padrão) ou **brilho branco**:
   ```bash
   uv run ferramentas/encaixar.py <corpo> <cta> --tipo <Reels|VSL|LP|ISCA|Captura|Carrinho> [--transicao brilho-branco]
   ```
   Ele confere áudio (LUFS do fim do corpo × começo do CTA: se o CTA começa mais alto ou mais baixo, entra no nível do
   corpo e volta ao dele numa rampa de 6 s) e cor (luma/saturação dos quadros da emenda), e avisa se a troca vai
   assustar. Com aviso de cor, corrija o look e encaixe de novo antes de subir.
4. As saídas ficam no próprio projeto, em `projetos/<corpo>/final/saidas/<nome> - <tipo>.mp4` (nunca em `~/Movies`), e
   registradas no `edicao.json` → `saidas` do corpo. Ao lado de cada vídeo sai a **transcrição** da saída
   (`<nome> - <tipo>.md`: a fala do corpo e a do CTA, dos `roteiro.md`, com a grafia corrigida e o tempo da emenda); no app, o card mostra "N saídas" e o botão de pasta abre os exports
   no Finder. Se houver saídas por plataforma (Instagram, TikTok, Shorts), uma por arquivo.

## 3. Drive

Antes de numerar, **liste a pasta raiz** e ache o maior número (filtre por `createdTime` recente; a de Ads tem 1000+ pastas
e a primeira página não basta). Crie a pasta pelo MCP do Drive (`create_file` com mimeType de pasta) e **suba os vídeos
pelo rclone** (o remote `asimov:`, autorizado pelo criador na conta com acesso às pastas; o token fica em
`~/.config/rclone/rclone.conf`, nunca mostre):
```bash
rclone copy "<arquivo>" asimov: --drive-root-folder-id <id da pasta> --drive-chunk-size 64M
rclone lsl asimov: --drive-root-folder-id <id da pasta>     # confira nome e tamanho
```
Nem o MCP do Drive nem o navegador sobem arquivos grandes (o upload do Claude in Chrome tem limite de 10 MB), e o Drive
Desktop está fora: ele dá conflito com o app da câmera (EOS Canon). Sem o remote (`rclone listremotes` vazio), rode
`rclone config create asimov drive scope=drive` e peça ao criador para autorizar no navegador. O rclone avisa que o
client_id compartilhado dele será desligado em 2026: quando parar, crie um client_id próprio
(https://rclone.org/drive/#making-your-own-client-id).

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

- **Reels** (template Reels `3063ee05-7ee5-81c4-9d86-d23a41763aac`): título = o nome do vídeo (ex.: "3 níveis de IA"),
  **ícone 📱** (como os demais Reels);
  Mídia 📸 Reels / Tiktok. No corpo: o roteiro (a fala do vídeo, `projetos/<corpo>/roteiro.md` sem as marcações + o CTA
  do Reels) e a **descrição** proposta com a skill `roteiro-to-descricao` (vault: `~/Obsidian Notes/3 Skills/`).
- **Perpétuo** (template Criativo `3063ee05-7ee5-816f-b147-f12935ee6519`), um card por funil: título `[FUNIL]_NNN_Nome`
  (ex.: `[VSL]_1085_3 Níveis de IA`), ícone 💰; Produto (ex.: 🤖 FIA), Mídia 💰 Criativo, Etapa do Funil Topo;
  **Campanha**: LP em branco · VSL `[COD_PROD]_VSL_Nome_do_ad` · ISCA `[COD_PROD]_ISCA_Nome_do_ad`; **Landing Page em branco**
  (o criador preenche).
- **Pico · Black** (template Criativo): título **`P2🟡BF26_Nome_do_ad`** (ex.: `P2🟡BF26_3_niveis_de_IA`), com
  **Nível prioridade = P2🟡 Importante mas não urgente** (o prefixo do título é a prioridade); Fase Black Friday (Captura ou
  Carrinho), Produto Black Friday, Público Black Friday (Público geral), Mídia 💰 Criativo. A pasta do Drive segue
  `XX Nome do Ad` (ex.: `21 Rodrigo 3 níveis de IA`).

**Copy de tráfego (todo anúncio: perpétuo LP, VSL, ISCA e pico):** no corpo do card, um **toggle H2 "COPY DE TRÁFEGO"**
com **3 títulos** diferentes (`### Títulos`, uma lista; curtos, até ~40 caracteres) e **2 textos principais**
(`### Texto principal 1`, o longo, em 4–5 parágrafos; `### Texto principal 2`, o curto, num parágrafo), sempre terminando
no CTA do funil (LP: comprar/começar hoje; VSL: assistir à aula gratuita, curiosidade, ainda não é venda; ISCA: pegar a
isca; captura da Black: cadastrar na live). O template Criativo já traz um toggle vazio "Copy de Descrições (Tráfego)"
com Texto principal 1–3: substitua esse bloco inteiro pelo novo (`notion-update-page` → `update_content`). Escreva a
partir do roteiro do corpo e do CTA; preços só conferidos em https://asimov.academy/#assine (mudam); sem superlativos
que a fala não sustenta.

## 5. Obsidian

O paralelo do Notion no vault (`~/Obsidian Notes/1 Copies/`): **uma nota de copy por card**, com só o emoji do
formato no início do nome (📱 Reels, 🎥 YouTube, 📺 VSL, 💰 ads), sem outros emojis antes. Ache a nota do rascunho
pelo nome ou por uma frase da fala (`grep -rl` em `1 Copies/`); o título dela costuma ser outro (ex.: "3 níveis de IA"
era `🧑🏼‍🔧📱💰 Quizz Descubra teu nível de IA`). Ao fechar o vídeo:
- **O nome passa a ser o do vídeo no Notion**, com o funil no começo nos anúncios: **📱 `<nome>`** com o corpo e os
  CTAs orgânicos (ManyChat, TikTok: publicados juntos) e uma **💰 `<VSL|LP|ISCA|Pico Captura|Pico Carrinho> - <nome>`**
  por saída de anúncio, cada uma com o corpo e o CTA dela (ex.: `📱 3 níveis de IA`, `💰 VSL - 3 níveis de IA`). A nota
  do rascunho vira a 📱 (renomeada); atualize os `[[links]]` que apontavam para ela.
- **Corpo da nota = a transcrição final**, a fala de `roteiro.md` (só as linhas entre aspas, sem marcações), em
  `# Corpo` e `# CTA <tipo>`. Corrija o que a transcrição errou (Cloud → Claude, Zmove → Asimov). Mantenha a linha
  `Referência:` e o frontmatter.
- **Tags** = `<produto>/<funil>`: produto `🤖fia` (agentes de IA, skills) ou `🖼️fid` (design com IA: sites, front-end,
  edição); funil `ad-lp`, `ad-vsl`, `reels-vsl` (Reels com CTA para a VSL) ou `isca` (ex.: `🤖fia/ad-vsl`). Pico tem
  a tag do pico (`💰pico/black26`) no lugar, inclusive o Reels com CTA da Black.
- **👁️ na frente do nome de toda nota que você criar ou editar** (ex.: `👁️📱 3 níveis de IA`): o criador confere e
  tira o 👁️. Uma nota em que você só trocou um `[[link]]` não ganha 👁️ (renomeá-la quebraria os links para ela).
- **Renomear pelo shell não atualiza os links** (só o Obsidian faz isso): antes de `mv`, confira que o destino não
  existe; depois, `grep -rl "<nome antigo>]]"` no vault (fora de `.obsidian/`) e troque cada `[[link]]`.
- **`scheduled`** = o **Prazo** do card correspondente no Notion (a data de publicação), entre aspas: `"2026-10-16"`.
- Sem nota: crie em `1 Copies/1 Priorizar/` com o frontmatter do template `2 Notas/Engine/templates/T-Copy.md`
  (`publicado:`, `scheduled:`, `tags:`).

## 6. Agendar (Metricool e ManyChat)

Só os orgânicos (Reels; os anúncios sobem pelo gerenciador de anúncios, fora daqui). Pelo MCP do **Metricool**: marca
`rodrigotadewald` (`blogId` 7482213, fuso `America/Sao_Paulo`), com Instagram, TikTok, YouTube e Facebook. O vídeo
entra em `media` como **link do Drive** (a pasta do passo 3; o Drive está vinculado no Metricool), não como arquivo.
Antes de agendar, liste o que já está na fila (`getScheduledPosts`) e mostre o plano (vídeo, legenda, redes, data e
hora); só agende depois de um "sim". Data = o Prazo do card; sem hora definida, `getBestTimeToPostByNetwork`.
Por rede: Instagram `instagramData.type: "REEL"`; YouTube `youtubeData.type: "short"`, com `title` e
`madeForKids: false`; TikTok `tiktokData` com o `title`. `autoPublish: true` (publica sozinho).

**Sem ManyChat:** tudo pelo Metricool, na data do Prazo, numa postagem só com as redes.

**Com ManyChat ("comente X para receber o link")**, um Reels por vez:
1. **Instagram (versão "comente X")**: agende pelo Metricool **para o mesmo dia** (nunca dias antes).
2. **ManyChat, no navegador do criador (Claude in Chrome)**: crie a automação com o gatilho **"próxima publicação ou
   Reel"**, a palavra-chave, as respostas públicas no comentário e a DM com o link. Antes, confira no Metricool que nada
   (outro post, carrossel, outro Reels) sai antes deste: a automação se prende ao **próximo** post publicado. Modelo:
   Automação → "Auto-DM de links dos comentários" (conta `fb3802114`). Mostre a automação e só publique com o "sim".
3. **TikTok e YouTube Shorts (versão "acesse o link da descrição")**: pelo Metricool, numa postagem à parte, com a
   descrição dizendo **onde está o link** em cada rede.

Depois que sair, confira que a automação ficou presa no Reels certo (ManyChat → a automação → o post do gatilho).

## 7. Entrega

Mande ao criador **todos os links do Notion criados/preenchidos** (para conferência), os das pastas do Drive, a lista das notas 👁️ do Obsidian para conferir e o que ficou agendado (Metricool, com o link do planner, e a automação do ManyChat). Depois,
os vídeos seguem a etapa de conclusão do editor (Calibragem e aprendizados).

## Aprendizados (manter atualizado)
