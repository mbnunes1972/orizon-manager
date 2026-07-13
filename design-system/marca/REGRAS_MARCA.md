# Orizon Manager — Regras da Marca (v1.0)

Fonte da verdade da identidade visual do produto Orizon Manager. Vive em `design-system/marca/` no repo `orizon-manager`, ao lado dos assets que governa. Alterações de marca passam por este arquivo primeiro.

## 1. Arquitetura de marca

**Orizon Soluções** é a marca-mãe (identidade em marrom fosco e dourado, tipografia Cormorant Garamond + Montserrat). **Orizon Manager** é a marca do sistema de gestão: herda da mãe a família cromática quente (cobre, dourado, carvão) e ganha construção própria de software. A assinatura de endosso é "uma solução Orizon Soluções" e aparece apenas em materiais de marketing — nunca dentro do produto.

A decisão registrada em julho/2026: a identidade azul-tecnologia original (navy `#0B1D3A`, azul `#0066FF`, ciano `#00B8C9`) foi **descontinuada**. Ela rompia a herança da marca-mãe e conflitava com o design system do produto. Materiais legados em azul devem ser recolorizados conforme a tabela da seção 3 antes de nova circulação.

## 2. Elementos da marca

A marca tem três elementos, cada um com território próprio.

**O glifo (agulha)** é o símbolo do produto: um círculo fino com uma agulha de bússola bicolor — norte em dourado sólido, sul vazado. O círculo é simultaneamente bússola e o "O" de Orizon. É o elemento de uso diário: sidebar, tela de login, favicon, ícones de app, avatar. Arquivos oficiais nesta pasta: `glifo-fundo-escuro.svg` (versão principal), `glifo-fundo-claro.svg`, `glifo-mono-branco.svg`, `glifo-mono-carvao.svg`, `glifo-favicon.svg`.

**O emblema completo** (cúpula com barras, anel tracejado, lupa e horizonte) é o símbolo de marketing: site, cartões, propostas, apresentações, materiais para a rede Dalmóbile. Seu desenho original permanece intocado — apenas as cores migram do azul para a família cobre (seção 3). O emblema não entra no produto: em telas, seu detalhamento vira ruído abaixo de 48px.

**O wordmark** é "Orizon" em Montserrat Bold com tracking levemente positivo (0.02em), seguido de "MANAGER" em Montserrat SemiBold, caixa alta, tracking largo de 0.42em. "Orizon" usa a cor de texto principal do fundo em questão; "MANAGER" usa sempre a cor de cobre correspondente ao fundo (seção 3). Nunca reconstruir o wordmark em outra fonte ou tracking.

## 3. Cores da marca

A paleta segue o princípio dos tokens do design system: cada cor tem um papel fixo e um valor equivalente por fundo — nunca a mesma cor nos dois contextos.

| Papel | Sobre fundo escuro (carvão) | Sobre fundo claro (areia/branco) |
|---|---|---|
| Carvão-café — wordmark, fundos, mono escuro | `#121111` (fundo) / `#EDE8E2` (texto) | `#1A1310` |
| Cobre — círculo do glifo, "MANAGER", destaques | `#A5643C` | `#8C5230` |
| Dourado — norte da agulha, detalhes finos | `#D3A254` | `#B8823D` |
| Cobre claro — sul da agulha, apoio | `#C9976D` | `#8C5230` |
| Cinza-quente — textos secundários | `#A9A6A2` | `#8A8177` |
| Areia — fundo claro institucional | — | `#F0EBE4` |

Recolorização do emblema legado (mapa azul→cobre): navy `#0B1D3A` → carvão-café `#1A1310`; azul `#0066FF` → cobre `#A5643C`; ciano `#00B8C9` → dourado `#D3A254`; cinza-azulado `#8A96A3` → cinza-quente `#A29A90`; gelo `#E6EBF1` → areia `#F0EBE4`. Cada cor herda exatamente o papel da que substitui.

Regras de aplicação: cobre e dourado são sempre **chapados e foscos** — degradês metálicos, texturas e brilhos são proibidos. Dourado é tempero, não prato: nunca em áreas grandes, apenas em traços, pontos e detalhes. Sobre fotografias ou fundos de contraste incerto, usar exclusivamente as versões monocromáticas.

## 4. Geometria e compensação óptica do glifo

Construção de referência (viewBox 120×120): círculo de raio 40 centrado, agulha norte de (60,27) a (60,68) com meia-largura 5.5, agulha sul vazada de (60,93) a (60,54) com meia-largura 4.5. O norte aponta sempre para cima — a agulha nunca rotaciona.

Linha fina evapora em tamanho pequeno; por isso o glifo tem três pesos formais, e reduzir a versão errada é violação de marca:

| Tamanho de exibição | Peso | Especificação |
|---|---|---|
| 40px ou mais | Fino | traço do círculo 3, sul vazado com traço 1.75 (`glifo-fundo-escuro.svg` e variantes) |
| 20–39px (sidebar, botões) | Médio | traço do círculo ≈5, agulha alargada, sul vazado com traço 2.5 |
| Abaixo de 20px (favicon) | Robusto | traço do círculo 8, sul **fecha em cobre claro sólido** — vazado não existe nesse tamanho (`glifo-favicon.svg`) |

Área de respiro mínima: metade do diâmetro do círculo em todos os lados, livre de qualquer outro elemento. Tamanho mínimo absoluto: 14px.

## 5. Composições (lockups)

Duas composições oficiais. **Horizontal** (padrão de produto): glifo à esquerda, wordmark à direita, alinhados pelo centro óptico, espaço entre eles igual ao raio do círculo — é a composição da sidebar e do cabeçalho de documentos. **Vertical** (login, capas, avatar com nome): glifo centralizado acima do wordmark, espaço igual a meio raio. Em espaços exíguos, o glifo aparece sozinho — nunca o wordmark sozinho sem o glifo em materiais oficiais, exceto em texto corrido.

## 6. Usos proibidos

Não rotacionar, espelhar, inclinar ou distorcer o glifo. Não aplicar sombras, contornos extras, brilhos ou degradês. Não usar as cores azuis legadas em nenhum material novo. Não recolorir fora dos pares fundo-escuro/fundo-claro da seção 3. Não colocar o glifo colorido sobre fundos que não sejam carvão, areia ou branco — em qualquer outro fundo, usar as versões monocromáticas. Não usar o emblema completo dentro do produto nem abaixo de 48px. Não recriar o glifo à mão: usar sempre os SVGs oficiais desta pasta.

## 7. Relação com o design system da UI

A marca e a UI compartilham a mesma família cromática, mas não os mesmos valores: a UI é governada pelo `orizon-tokens.css` (accent `#A56B45`, linha `#532A14`, carvão H2), e a marca pelos valores da seção 3. Componente de interface nunca usa hex da marca diretamente, e material de marca nunca referencia tokens da UI — os dois sistemas evoluem coordenados, porém independentes, e este arquivo com o `orizon-tokens.css` são as duas fontes da verdade. Na sidebar do produto, usa-se `glifo-mono-branco.svg` ou o `glifo-fundo-escuro.svg` no peso médio; na tela de login, a composição vertical sobre carvão.

## 8. Tagline

"Gestão que conecta · Controle que impulsiona" — as palavras destacadas ("conecta", "impulsiona") usam o cobre do fundo correspondente, nunca o azul legado. A tagline aparece apenas em materiais de marketing.

---
*v1.0 — julho/2026. Decisões de origem: migração azul→cobre (coerência com a marca-mãe Orizon Soluções), glifo da agulha aprovado sem linha de horizonte, três pesos de compensação óptica.*
