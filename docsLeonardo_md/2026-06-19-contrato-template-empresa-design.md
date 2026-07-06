# Design — Alinhar geração de contrato ao template reestruturado (empresa + CPFs separados)

> Data: 2026-06-19 · Correção/alinhamento (intercalado entre sub-projetos 1 e 2). Disparado por
> uma edição do template `modelo_contrato_mapeado.docx` feita no Word.

## Contexto / Problema

O usuário reestruturou o bloco de assinatura/qualificação do template, introduzindo marcadores
separados para nome e documento de cada parte e adicionando a empresa:
`[NOME_EMPRESA]`, `[CNPJ_EMPRESA]`, `[NOME_CLIENTE]`/`[CPF_CLIENTE]`,
`[NOME_TESTEMUNHA_1]`/`[CPF_TESTEMUNHA_1]`, `[NOME_TESTEMUNHA_2]`/`[CPF_TESTEMUNHA_2]`.

Isso quebrou **6 testes** em `tests/test_contrato.py`. Diagnóstico (após ler o motor):

- O motor do **corpo/tabelas** (`_subst_paragrafo`) já opera em `par.text` (texto concatenado dos
  runs), então **já lida com marcadores fragmentados** em múltiplos runs (o Word fragmenta ao
  editar). Prova: `[NOME_TESTEMUNHA_2]` está fragmentado **e** é substituído normalmente.
- A causa real das falhas é **(a) mapeamentos faltando** (`NOME_EMPRESA`, `CNPJ_EMPRESA`,
  `CPF_CLIENTE`, `CPF_TESTEMUNHA_1`, `CPF_TESTEMUNHA_2` não estão em `_montar_mapping`) e
  **(b) testes que validam a estrutura antiga** (CPF inline "CPF/CNPJ: …", agora marcador
  separado).
- O único trecho **realmente** frágil a fragmentação é a substituição no **cabeçalho**
  (`_substituir_marcadores`, ramo dos headers), que é por-`w:t` (run a run) — e o cabeçalho
  carrega o **número e a data do contrato**. Robustecer esse ramo é defensivo e evita quebra
  futura ao editar o cabeçalho no Word.

## Decisões (acordadas)

- **Motor robusto a runs:** sim — aplicar ao ramo do **cabeçalho** (o corpo já é robusto).
- **Estrutura final, alinhar agora.**
- **Empresa por constante:** os valores reais **já constam no template** (cláusula de
  qualificação + bloco centralizado), então `_NOME_EMPRESA`/`_CNPJ_EMPRESA` recebem esses valores
  reais (não placeholder), com TODO para o futuro **configurador de lojas**. (Decisão original era
  placeholder, revista ao descobrir que o dado real já estava no documento — evita regredir o
  contrato e manter consistência interna.)

## Mudanças

### `mod_contrato.py`
- **Constantes** (junto de `_TELEFONE_LOJA`/`_EMAIL_LOJA`) — valores reais já presentes no
  template:
  ```python
  _NOME_EMPRESA = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"  # TODO: configurador de lojas
  _CNPJ_EMPRESA = "19.152.134/0001-56"                            # TODO: configurador de lojas
  ```
  (Sem colchetes — não colidem com a detecção de marcadores `[...]`.)
- **`_montar_mapping`** ganha:
  - `"NOME_EMPRESA": _NOME_EMPRESA`
  - `"CNPJ_EMPRESA": _CNPJ_EMPRESA`
  - `"CPF_CLIENTE":  ctx.get("cliente_cpf", "") or ""`  (mesmo valor de `CPF`)
  - `"CPF_TESTEMUNHA_1": _TESTEMUNHAS[0][1]`
  - `"CPF_TESTEMUNHA_2": _TESTEMUNHAS[1][1]`
- **Cabeçalho cross-run:** no ramo dos headers de `_substituir_marcadores`, em vez de substituir
  `w:t` por `w:t`, processar **por parágrafo** do header (concatena runs → aplica `_aplica_mark`
  → reescreve), reaproveitando a mesma abordagem do corpo. Marcador sem chave permanece intacto.

### `tests/test_contrato.py` (atualizar os 6)
- `test_preencher_signatario_e_testemunhas`: trocar a asserção do formato antigo
  ("Ana Cliente\nCPF/CNPJ:") pela nova estrutura — nome e CPF em marcadores/linhas separados
  (após substituição: nome do cliente e o CPF preenchido em linhas próprias).
- `test_assinaturas_nome_e_cpf_em_linhas_separadas`: ajustar para a nova estrutura (linha do nome
  seguida da linha do CPF preenchido, não mais o rótulo "CPF/CNPJ:" inline).
- `test_geracao_completa_sem_marcadores_remanescentes`, `test_protegido_mantem_texto_e_valores`,
  `test_geracao_completa_com_forma_parcela`: passam a verde com os mapeamentos novos (sem
  marcador remanescente). Os placeholders `PREENCHER …` não têm colchetes, então não são
  flagrados pela regex de "marcador remanescente".
- `test_assinatura_cliente_mesmo_estilo_da_empresa`: ajustar à nova linha da empresa
  (`[NOME_EMPRESA]`) — confirmar o estilo/normalização do bloco (Heading 2) coerente com o
  template atual; se a normalização (`scripts/normalizar_assinaturas.py`) precisar reconhecer a
  linha da empresa, ajustar o alvo do teste e/ou o script de forma idempotente.

## Testes / Verificação

- **pytest:** os 6 testes voltam a passar; suíte inteira verde.
- **Dados reais (ver [[contrato-verificacao-dados-reais]] e [[gui-verification-playwright]]):**
  gerar um contrato real (via app, com `/calcular_*`) e confirmar — nenhum marcador `[...]`
  remanescente no `.docx`; `[NOME_EMPRESA]`/`[CNPJ_EMPRESA]` aparecem como os placeholders;
  CPFs do cliente/testemunhas preenchidos; número/data no cabeçalho corretos.

## Fora de escopo

- **Configurador de lojas** (origem real de nome/CNPJ/testemunhas/telefone/email) — projeto
  futuro; aqui ficam só os placeholders.
- Retomar o **sub-projeto 2** (trava pós-assinatura) após esta correção entrar na `main`.
