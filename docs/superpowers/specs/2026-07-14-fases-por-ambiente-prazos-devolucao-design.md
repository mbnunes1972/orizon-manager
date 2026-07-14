# Fases por Ambiente + Prazos + Devolução/Cancelamento fora do Ciclo — Design (RASCUNHO)

**Data:** 2026-07-14 · **Status:** rascunho p/ brainstorm (decisões marcadas). Consolida os requisitos
levantados no teste manual da AF/PE. Não construir antes de fechar as decisões.

## Contexto

Generalizar o "desmembrar em fases" (hoje pontual na 11c) para uma **ação por ambiente** ao longo do
ciclo, com **prazos por fase**, e tirar **devolução/cancelamento pós-AF1** do ciclo (tratados fora,
supervisionados pela auditoria contábil). Reusa `mod_parcelas` (`ParcelaProjeto`/`ParcelaAmbiente`),
`mod_cronograma`, `cancelar_contrato`, `devolver_venda`, `auditoria_contabil`.

## 1. Desmembramento por ambiente — a partir da Solicitação de Medição (etapa 9)

- De **etapa 9 em diante**, cada fase (etapa), ao abrir, **lista os ambientes contratados** com **box de
  seleção** (checkboxes) dos que sofrerão a **ação daquela fase**.
- A ação incide sobre os **selecionados**; os **não-selecionados desmembram para outra fase** — uma
  **fase paralela** no mesmo projeto (`ParcelaProjeto`), com seu próprio avanço de etapas.
- O **documento gerado** na fase segue o modelo e **registra a ação sobre os ambientes selecionados**.
- Enquanto houver **> 1 ambiente a concluir**, o botão **"Desmembrar em fases"** fica disponível, até
  todos concluídos.

## 2. Subfase "Projeto Executivo" (ex-"Revisão de PE", código 11c) — botões + senha

**Rename (SÓ display):** subfase 11c "Revisão de PE" → **"Projeto Executivo"**; etapa-mãe 11 → **"Especificação
Técnica"**. Códigos/IDs mantidos (`11c`, `pe_projeto_executivo`, `SUBFASES_PE`, `arquivo_pe`, `_podePE`) —
código diz "PE", UI diz "Projeto Executivo/Especificação Técnica" (ver nota de nomenclatura).

**Botões — todos NA MESMA LINHA e do MESMO TAMANHO:**
1. **Carregar Projeto Executivo** — sobe os XMLs para a pasta de PE; **sobrescreve em revisões**; cada
   revisão incrementa o indicador **[Rev1, Rev2…]** ao lado do nome da subfase.
2. **PE × PV** — compara os **valores de fábrica**: XMLs **vendidos (PV = Projeto Vendido)** × **Projeto
   Executivo (PE)**. Abre o modal de comparação (formato CFO validado).
3. **Desmembrar Fases** — Fase B (`particionar_por_selecao` + endpoint B.2); selecionável enquanto houver
   **> 1 ambiente pendente**.
4. **Aprovar** — letras em **dourado escuro**; aprova a fase (ambientes selecionados) → vira **"Aprovado"
   em verde escuro**; as demais fases seguem pendentes. Quando **todas** aprovadas, a subfase **trava**.

**Senha (modelo desta subfase):**
- **Livre até concluir** — Carregar / PE×PV / Desmembrar **sem senha**.
- **Concluir (Aprovar) exige a senha do PRÓPRIO usuário** (auto-confirmação, NÃO gerencial).
- **Reabrir (após travada) exige senha GERENCIAL.**

## 3. Prazos por fase (todo projeto tem cronograma)

- **Toda fase tem prazo registrado**, dentro do **limite do contrato** (detalhe a tratar em breve).
- O **prazo-limite de aprovação** aparece **para todos os ambientes**.
- **Desmembrar exige indicar um novo prazo de conclusão** para os ambientes remanescentes.
- Se esse novo prazo **exceder o limite do cronograma** do projeto → **exige senha de aprovação**
  (step-up). `mod_cronograma` já gera `data_prevista_conclusao` por etapa a partir do D0 + Cronograma
  Padrão; **todo projeto deve ter cronograma**.

## 4. Devolução e Cancelamento — fora do ciclo (pós-AF1)

- ✅ Já feito: removidos os botões de **devolução** das AF; **cancelamento só na AF1** (etapa 8).
- **Após a AF1**, devolução/cancelamento acontecem num **módulo próprio, fora do ciclo**: seleciona-se o
  **contrato**, e as **reversões contábeis são SUPERVISIONADAS** — o **documento de auditoria contábil**
  que acompanhou o contrato permite **comparar as reversões** (antes × depois) e garantir a coerência do
  processo. Reusa `devolver_venda`/`cancelar_contrato` + `auditoria_contabil`.

## Peças novas prováveis

| Peça | O que é |
|---|---|
| **Ação por ambiente** | seleção (checkbox) de ambientes por etapa (9+); backend registra a ação nos selecionados |
| **Auto-desmembramento** | não-selecionados → nova `ParcelaProjeto` (fase paralela) |
| **Prazo por fase** | `data_prevista_conclusao` por fase; validação contra o cronograma; step-up se exceder |
| **Botão Aprovar por fase** | dourado escuro → verde escuro (tokens novos, ex.: `--gold-dark`/`--ok-strong`) |
| **Módulo de Devolução/Cancelamento fora do ciclo** | tela de seleção de contrato + reversão supervisionada pela auditoria |

## Decisões em aberto (confirmar antes de construir)

1. **"Outra fase"** = nova `ParcelaProjeto` paralela no mesmo projeto, com ciclo próprio a partir da
   etapa do desmembramento — confirma? A contabilidade (provisões/receita diferida) do ambiente
   **acompanha** a nova fase (reusa `congelar_parcelas`, que já congela Val_Cont por fase)?
2. **Escopo das etapas** com seleção de ambiente: da **9** até qual? (Medição, PE, Conferência,
   Produção, Entrega, Montagem…?) Cada uma com uma "ação" própria que o documento registra.
3. **Quais documentos** por etapa carregam a lista de ambientes (nos modelos)?
4. **Cronograma obrigatório**: hoje `gerar_cronograma_projeto` roda no D0 (assinatura). Garantir que
   **todo projeto** tenha cronograma antes da medição — criar default se faltar?
5. **Gate do prazo excedido**: qual capacidade aprova (Diretor `autorizar`, ou Gerente Adm/Fin)?
6. **Cores**: confirmar "dourado escuro" (Aprovar) e "verde escuro" (Aprovado) como tokens novos.

## Plano por fases (quando aprovado)

- **A** — Cronograma obrigatório + prazo por fase (modelo + validação contra o limite; step-up se exceder).
- **B** — Seleção de ambiente por etapa (9+) + auto-desmembramento (nova `ParcelaProjeto`), TDD no núcleo.
- **C** — Modal "Carregar PE" (11c): desmembrar + Aprovar por fase (dourado→verde), sem botão de revisão.
- **D** — Documentos por fase (modelos + lista de ambientes da ação).
- **E** — Módulo Devolução/Cancelamento fora do ciclo (seleção de contrato + reversão supervisionada).
