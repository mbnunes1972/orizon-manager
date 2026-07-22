# Termo Aditivo — modelo jurídico completo + modais sequenciais (2026-07-22)

## Demanda
Substituir o corpo-esqueleto atual do `termo_aditivo` (3 linhas, ver `CONTRATOS/aditivo_2.pdf`)
pelo modelo jurídico do advogado (`mod_aditivo.doc`, raiz do repo), no MESMO formato do Modelo de
Contrato (`contrato_template/contrato.md`): Markdown com `[MARCADORES]`, cláusulas `#`, bloco de
assinaturas idêntico. As partes que **dependem do caso concreto** — considerandos, lista integral
de itens, inclusões, exclusões, valores/pagamento — são preenchidas por **modais sequenciais com
texto editável**: o sistema pré-preenche a partir dos dados do projeto e o operador ajusta antes
de gerar. O documento já nasce preparado para o caso de **não haver inclusões e/ou exclusões**.

## O que JÁ existe (aproveitar, não recriar)
- `mod_documentos.TIPOS` inclui `"termo_aditivo"` (modelo por loja, versão imutável, uma ativa).
- `mod_contrato.gerar_pdf_aditivo` / `montar_html_aditivo` (corpo congelado via
  `ctx["_corpo_md_aditivo"]`) — mesmo motor WeasyPrint do contrato.
- Marcadores da Fatia 3 da Revisão de PE (2026-07-21): `NUM_ADITIVO`, `NUM_CONTRATO_ORIGINAL`,
  `AMBIENTES_COMPLEMENTO`, `VALOR_ORIGINAL_COMPLEMENTO`, `VALOR_NOVO_COMPLEMENTO`,
  `VALOR_COMPLEMENTO`, preenchidos via `ctx["_aditivo"]`.
- Fonte de dados para pré-preencher: pool de ambientes do contrato (originais), Revisão de PE
  (original → novo por ambiente), `Val_Cont`/parcelas do orçamento do contrato.

## O modelo novo — `contrato_template/termo_aditivo.md`
Arquivo entregue junto desta spec. Estrutura (fiel ao `mod_aditivo.doc`, generalizada com
marcadores — nada de razão social/cidade cravadas):

- **Título**: `[ORDINAL_ADITIVO] TERMO ADITIVO AO CONTRATO…` (PRIMEIRO/SEGUNDO/…, computado pela
  contagem de aditivos do contrato — o `NUM_ADITIVO` segue existindo como código TA…).
- **Preâmbulo**: qualificação por referência ao CONTRATO nº `[NUM_CONTRATO_ORIGINAL]` firmado em
  `[DATA_CONTRATO_ORIGINAL]` (marcador novo — a `DATA_CONTRATO` do catálogo é a do documento
  corrente; aqui precisamos da data do contrato ORIGINAL).
- **`[ADITIVO_CONSIDERANDOS]`** (modal 1).
- **Cláusula Primeira** — itens `1.` `[ADITIVO_LISTA_INTEGRAL]` (modal 2), `1.1.`
  `[ADITIVO_INCLUSOES]` (modal 3), `1.2.` `[ADITIVO_EXCLUSOES]` (modal 4).
- **Cláusula Segunda** — item `2.` `[ADITIVO_VALORES]` (modal 5) + `2.1.` fixo (remissão a
  atraso/reserva de domínio/garantias do CONTRATO).
- **Cláusula Terceira** — ratificação (texto fixo do advogado) + `3.1.` integração ao CONTRATO.
- **Fecho e assinaturas**: mesmo bloco do `contrato.md` (Contratada/Contratante/Testemunhas 1 e 2
  com os marcadores vivos do catálogo) + `[LOJA_CIDADE] - [LOJA_UF], [DATA_ADITIVO].` +
  `[TEXTO_COMPLEMENTAR]` no fim (padrão dos modelos).

## Modais sequenciais (wizard de geração do aditivo)
Cinco passos, todos com **textarea editável** + botão **"Restaurar texto padrão"**; o texto final
de cada passo entra no marcador correspondente. Preview do PDF antes de gerar (padrão da
proposta/contrato). Conteúdo pré-preenchido:

1. **Considerandos** (`[ADITIVO_CONSIDERANDOS]`): default = os 3 CONSIDERANDOS do modelo do
   advogado (alteração do Projeto Executivo — itens 1.5.1; 2.3(b); 2.3.4 a 2.3.6 do CONTRATO;
   alteração substancial de produtos/serviços; constatação na medição — item 2.3(a)), cada um em
   parágrafo próprio para o operador apagar os que não se aplicam.
2. **Lista integral** (`[ADITIVO_LISTA_INTEGRAL]`): default =
   *"Com base na solicitação do CLIENTE, a lista de produtos e materiais adquiridos passa a ser a
   seguinte, substituindo integralmente, para todos os efeitos, o rol constante do CONTRATO e de
   seus anexos:"* + **lista COMPLETA dos ambientes vigentes pós-alteração, inclusive os não
   alterados** (nome de exibição + valor contratual), gerada do pool/Revisão de PE.
3. **Inclusões** (`[ADITIVO_INCLUSOES]`):
   - **com inclusões** (default quando a comparação detecta ambiente/item novo): *"Diante do rol
     constante do item 1, promove-se a inclusão dos seguintes produtos e materiais, que não
     constavam do texto original do CONTRATO:"* + lista dos incluídos;
   - **sem inclusões** (default automático): *"Registram as PARTES que o presente TERMO ADITIVO
     não promove a inclusão de produtos ou materiais em relação ao rol original do CONTRATO."*
4. **Exclusões** (`[ADITIVO_EXCLUSOES]`): simétrico —
   *"Diante do rol constante do item 1, promove-se a exclusão dos seguintes produtos e materiais,
   que constavam do texto original do CONTRATO:"* + lista; ou, sem exclusões: *"Registram as
   PARTES que o presente TERMO ADITIVO não promove a exclusão de produtos ou materiais em relação
   ao rol original do CONTRATO."*
5. **Valores e pagamento** (`[ADITIVO_VALORES]`):
   - **com alteração de valor** (default se `Val_Cont` novo ≠ original): *"Diante das alterações
     promovidas nos itens precedentes, o valor total do CONTRATO passa de R$ [original] para
     R$ [novo], resultando em diferença de R$ [delta], a ser paga da seguinte forma: [condições
     — forma, nº de parcelas e datas]"* — pré-preenchido com os números do motor (original →
     novo → diferença) e as condições negociadas;
   - **sem alteração**: *"As alterações promovidas nos itens precedentes não implicam modificação
     dos valores nem das condições de pagamento fixados no CONTRATO, que permanecem integralmente
     vigentes."*

A adaptação ao caso "sem inclusões/exclusões/alteração de valor" é feita pelo **VALOR default do
marcador** (frase negativa própria), não por lógica condicional no template — o motor de
substituição continua burro e o texto sai gramaticalmente correto nos dois cenários, com a
numeração das cláusulas estável (1.1/1.2 nunca somem; viram declaração negativa, prática usual).

## Integração (pontos de código)
- **`mod_marcadores.CATALOGO`** — marcadores novos (escopo `documento`): `ORDINAL_ADITIVO`,
  `DATA_ADITIVO`, `DATA_CONTRATO_ORIGINAL`, `ADITIVO_CONSIDERANDOS`, `ADITIVO_LISTA_INTEGRAL`,
  `ADITIVO_INCLUSOES`, `ADITIVO_EXCLUSOES`, `ADITIVO_VALORES`. **Regra do projeto:** mexer em
  `_montar_mapping` (`mod_contrato.py`) NO MESMO commit — o teste anti-drift trava os dois juntos.
  Valores vêm de `ctx["_aditivo"]` estendido: `{ordinal, data_aditivo, data_contrato_original,
  considerandos, lista_integral, inclusoes, exclusoes, valores}`.
- Os 6 marcadores da Fatia 3 (`AMBIENTES_COMPLEMENTO` etc.) **continuam válidos** — o fluxo de
  complemento do PE passa a usar o modelo novo, com os modais pré-preenchidos pelos dados que hoje
  alimentam aqueles marcadores; manter os antigos no catálogo (modelos de loja podem citá-los).
- **Endpoint de geração**: recebe os 5 blocos editados + congela `modelo_versao_id` do
  `termo_aditivo` ativo da loja (mesmo padrão de imutabilidade do contrato — regerar um aditivo
  assinado reproduz o texto original). Os blocos editados são persistidos no registro do aditivo
  (são parte do documento assinado, não recalculáveis).
- **Seed/ativação do modelo**: `contrato_template/termo_aditivo.md` é a fonte; ativar como modelo
  `termo_aditivo` da loja pelo painel de modelos (ou seed que insere a v1 para lojas sem modelo
  ativo). Lojas com redação própria importam o delas — o wizard/modais funcionam igual, desde que
  o modelo use os marcadores `ADITIVO_*` (o `analisar_corpo` já avisa marcador desconhecido).
- **Frontend**: wizard de 5 passos no ponto onde hoje se gera o aditivo (Revisão de PE/ciclo);
  numeração `TA…` e ordinal computados; preview antes de gerar.

## Testes
Anti-drift CATALOGO×mapping (novos marcadores); render do modelo com os 5 blocos (com e sem
inclusões/exclusões/alteração de valor — 4 combinações mínimas); congelamento de versão do
modelo; ordinal (1º aditivo → PRIMEIRO, 2º → SEGUNDO); e2e: contrato → Revisão de PE → aditivo
PDF com lista integral + inclusão + valores conferidos ao centavo.

## Decisões/observações
- O `mod_aditivo.doc` cita cláusulas específicas do contrato-padrão (1.5.1, 2.3 etc.) — mantidas
  no default dos considerandos por serem o vocabulário do contrato vigente; loja com contrato
  próprio edita no modal (ou no modelo dela).
- "São José dos Campos" e "INSPIRIUM…" cravados no .doc viraram `[LOJA_CIDADE]`/`[NOME_EMPRESA]`
  etc. — modelo serve a qualquer loja da rede.
- `DATA_CONTRATO_ORIGINAL` é marcador NOVO de propósito: `DATA_CONTRATO` continua significando "a
  data do documento corrente" nos demais modelos; sobrecarregá-lo aqui quebraria contratos.

## ✅ Implementado (2026-07-22, Sessão 105)
Tudo da spec, com estas decisões de execução:
- **Wizard = 1 modal com 5 passos sequenciais** (Voltar/Avançar/Restaurar/Visualizar PDF/Gerar),
  não 5 modais distintos — mesma UX, menos chrome.
- **Preview** = POST `/aditivo` com `preview:true` → PDF inline com o contexto REAL, sem persistir
  nada (rollback); não usa o preview de modelos (aquele renderiza contexto de exemplo).
- **Seed**: loja sem modelo ativo ganha v1 de `contrato_template/termo_aditivo.md` na 1ª geração
  (o "ou seed" da spec) — o erro "importe um em Config → Documentos" só resta se o arquivo do
  template sumir do repo.
- **2º aditivo**: gerar com o último ASSINADO exige `novo:true` (o 403 de "regerar assinado"
  continua; criar o próximo é ação explícita — botão "Novo Termo Aditivo"). Ordinal = posição na
  contagem de aditivos do contrato.
- **`\n`→`<br>` no mapping do corpo-documento**: a substituição de marcadores roda depois de o
  corpo virar `<p>` por linha, então valor multi-linha (considerandos, listas) colapsaria sem isso.
- `DATA_CONTRATO_ORIGINAL` = data da 1ª assinatura do contrato (fallback: `gerado_em`).
- Testes: `tests/test_aditivo_modelo.py` (unidade/render) + `tests/test_aditivo_wizard_e2e.py`
  (e2e ao centavo, com inclusão real e 2º aditivo). Anti-drift de marcadores no de sempre.
