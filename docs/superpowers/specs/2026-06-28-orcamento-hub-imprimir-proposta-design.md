# Design — Etapa Orçamento como hub + Imprimir Orçamento (proposta)

**Data:** 2026-06-28
**Frente:** Ciclo — etapas como hub de artefatos (foco no Orçamento) + 1º documento do banco (#8): a Proposta
**Status:** proposto (decisões fechadas no brainstorm; aguarda revisão)
**Relacionado:** `docs/modulos/contratos/SPEC.md` (direção do banco de documentos por loja, #8),
`docs/processos/FLUXO_38_ETAPAS.md` (ciclo de 20 etapas), `mod_contrato.py` (motor de documento).

## Contexto

Cada etapa do ciclo deveria, ao ser aberta, **dar acesso aos artefatos daquela etapa** (documentos,
arquivos, dados). Hoje só algumas fazem isso (Contrato, Medição). Este slice aplica o padrão às
etapas de **Orçamento**, e introduz o **primeiro documento gerado além do contrato — a Proposta** —
que será o 1º tipo do banco de documentos da loja (#8) quando este chegar.

A negociação tem hoje os botões **Salvar Orçamento** e **Aprovar Orçamento** (`static/index.html:1142-1143`).
O motor de documento (`mod_contrato`) já gera `.docx` por substituição de `[MARCADOR]` e converte para
PDF via LibreOffice (com fallback `.docx` quando ausente) — será **reaproveitado** para a Proposta.

## Decisões (fechadas no brainstorm)

- **Escopo:** foco nas etapas de **Orçamento** (4) e **Aprovação do orçamento** (6). As demais etapas
  recebem o mesmo padrão "clicar → artefatos" depois, incrementalmente.
- **Renomear** a etapa 4 de **"Primeiro orçamento" → "Orçamento"** (o código `4` não muda).
- **Etapa Orçamento (card):** lista os orçamentos do projeto como **botões (um por orçamento)**.
  Clicar **abre o orçamento na tela de negociação** (read-only se o projeto estiver fechado — já
  suportado). Cada botão também tem **🖨 Imprimir** (gera a Proposta daquele orçamento). Após o
  fechamento, os botões continuam (abrem em leitura).
- **Etapa Aprovação do orçamento (6):** aponta para o **orçamento aprovado** = o orçamento de origem
  do contrato (`contrato.orcamento_id`); botões "Abrir orçamento aprovado" + "Imprimir proposta".
- **Botão "Imprimir Orçamento"** na negociação, junto de Salvar/Aprovar — gera a Proposta do
  orçamento ativo.
- **Proposta:** modelo **global** `modelo_proposta.docx` (por loja fica para o #8), baseado na **1ª
  página do contrato** — cabeçalho da loja, partes (cliente + loja), **ambientes + valores**,
  **condições de pagamento**, validade; **sem as cláusulas** do contrato.
- **Geração sob demanda, SEM salvar:** a Proposta é renderizada a cada requisição a partir do
  orçamento atual; **sem registro no banco** e **sem arquivamento** (o arquivo é só o meio de
  renderização — escrito num temporário e servido inline).
- **Exibição:** abre como **PDF de página inteira** (nova aba), igual ao contrato.
- **Acesso:** escopo operacional por loja (`escopo_operacional` + `_obj_da_loja`), com IDOR (404
  para orçamento de outra loja) e 401 anônimo.

## Arquitetura

**Novo módulo `mod_proposta.py` (fino, reaproveita `mod_contrato`):**
- `contexto_proposta(cliente: dict, usuario: dict, loja: dict, orcamento_dict: dict, breakdown: dict) -> dict`
  — monta o `{MARCADOR: valor}` da proposta: reusa os campos de `mod_contrato.construir_contexto`
  (cliente/loja/consultor/pagamento) e acrescenta os da oferta comercial: lista de ambientes,
  valor bruto, desconto, valor negociado/total, validade da proposta.
- `gerar_proposta(orcamento_id: int, variaveis: dict) -> tuple[str, bool]` — preenche
  `modelo_proposta.docx` (via o motor de marcadores de `mod_contrato`: `_substituir_marcadores`)
  num diretório temporário, tenta converter para PDF (helper de LibreOffice de `mod_contrato`);
  retorna `(caminho, eh_pdf)` — o `.docx` quando o LibreOffice está ausente. **Não persiste** nada.
- `_MODELO_PROPOSTA = modelo_proposta.docx` (novo template na raiz).

**Template `modelo_proposta.docx` (novo):** criado a partir da 1ª página do contrato (mesmos campos
de cabeçalho/partes/pagamento) + bloco de ambientes/valores; sem as cláusulas. Marcadores reusam os
nomes do contexto do contrato onde aplicável (`[CLIENTE_NOME]`, `[NOME_EMPRESA]`, `[PGTO_*]`, etc.)
e novos para a oferta (`[AMBIENTES_LISTA]`, `[VALOR_BRUTO]`, `[DESCONTO]`, `[VALOR_TOTAL]`,
`[VALIDADE]`).

**Backend (`main.py`):**
- `GET /api/orcamentos/<id>/proposta/pdf` — sessão obrigatória (401); `escopo_operacional` (403);
  `orc = _obj_da_loja(db, Orcamento, id, loja_id)` (404). Reusa
  `_montar_dados_projeto_para_contrato`/`_loja_dict_para_contrato` (cliente/loja/ambientes) e
  `_negociacao_breakdown` (valores), chama `mod_proposta.gerar_proposta`, e **serve inline** o
  arquivo (PDF ou docx), com `Content-Disposition: inline; filename="proposta_<id>.<ext>"`.

**Frontend (`static/index.html`):**
- Renomear o rótulo da etapa 4 para "Orçamento".
- Botão **"🖨 Imprimir Orçamento"** ao lado de Salvar/Aprovar (linha ~1142) →
  `<a href="/api/orcamentos/${_orcamentoAtivoId}/proposta/pdf" target="_blank">` (abre em nova aba).
- Card da etapa **Orçamento**: render que lista os orçamentos do projeto (via os orçamentos já
  carregados) — cada um com "Abrir" (carrega na negociação: reusa a troca de orçamento ativo
  existente) e "🖨 Imprimir" (link para a proposta daquele id).
- Card da etapa **Aprovação do orçamento**: mostra o orçamento aprovado (de `contrato.orcamento_id`,
  via `GET /contrato`) com "Abrir" + "Imprimir proposta".

**`mod_ciclo.py`:** `ETAPA_NOME["4"] = "Orçamento"` (era "Primeiro orçamento").

## Fora de escopo
- Modelo de proposta **por loja** (Padrão/Personalizado) — fica para o banco de documentos #8.
- Aplicar o padrão "etapa → artefatos" às demais etapas (incremental, depois).
- Persistir/arquivar a proposta ou versioná-la (gera-se sob demanda).
- Outros documentos do processo (ordem de produção, termo de entrega, etc.) — escopo do #8 / a
  definir com a lista de documentos por etapa.

## Erros / bordas
- Orçamento sem ambientes → a proposta gera assim mesmo (lista vazia) ou retorna 400 "sem ambientes"?
  **Decisão:** gera com a lista de ambientes que houver (não bloqueia; a proposta é informativa).
- LibreOffice ausente → entrega `.docx` (degradação graciosa, como o contrato).
- Orçamento de outra loja → 404; anônimo → 401.

## Testes
- **Puro (`tests/test_proposta.py`):** `mod_proposta.contexto_proposta` produz os marcadores
  esperados (cliente, loja, ambientes, valor bruto/desconto/total, pagamento) a partir de dicts de
  cliente/loja/orçamento/breakdown.
- **e2e (`tests/test_proposta_e2e.py`):** `GET /api/orcamentos/<id>/proposta/pdf` autenticado →
  200 + corpo não vazio (docx no ambiente sem LibreOffice); **IDOR** (dir de outra loja → 404);
  **401** anônimo. Hermético: isola o diretório temporário de render (fixture).
- **Frontend:** verificação manual — rótulo "Orçamento", botão Imprimir, lista de orçamentos no card,
  orçamento aprovado na etapa 6.

## Arquivos afetados
- **Novo:** `mod_proposta.py`, `modelo_proposta.docx`, `tests/test_proposta.py`,
  `tests/test_proposta_e2e.py`.
- **Editado:** `main.py` (rota GET proposta/pdf), `static/index.html` (rótulo + botão Imprimir +
  cards das etapas Orçamento/Aprovação), `mod_ciclo.py` (`ETAPA_NOME["4"]`).
