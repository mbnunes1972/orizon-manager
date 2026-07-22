# Cabeçalho no Aditivo + Painel de Documentos: upload por seletor, Novo Documento e exemplos (2026-07-22)

## Demanda (do usuário)
1. **Cabeçalho no Termo Aditivo aos moldes do Contrato** (logo + identificador da rede à esquerda;
   número e data à direita).
2. **Painel Config → Documentos**: botão **"Upload de Modelo"** com um seletor com os nomes de cada
   tipo de documento; botão **"Novo Documento"** onde o usuário dá um NOME ao documento e seleciona
   a qual **etapa do ciclo** ele se associa. *(Como inserir a geração desses documentos no ciclo é
   frente FUTURA — por ora só se registra o vínculo.)*
3. Após criar o documento e subir o modelo, usar uma **suíte de formatação** (solução sugerida
   abaixo; pode ser responsabilidade da IA) e disponibilizar **link de visualização** do modelo.
4. Os botões existentes (Contrato, Proposta Comercial, Aditivo) devem permitir **visualizar um
   exemplo** (PDF com dados fictícios + dados reais da loja).

## Parte 1 — Cabeçalho nos documentos de corpo-só
`_montar_html_corpo_documento` (mod_contrato) hoje descarta a `<!--CAPA-->`; passa a injetar o
bloco `#cabecalho` do contrato (helper `_html_cabecalho()` compartilhado com `_html_capa` — um
lugar só, sem cópia). Marcadores do bloco: `[REDE_IDENTIFICADOR]`, `[NUM_CONTRATO]` (no aditivo o
ctx já carrega o nº TA), `[DATA_CONTRATO]` (data do documento corrente). Vale para Termo Aditivo,
Aprovação do PE e documentos customizados — todos os "corpo-só".

## Parte 2 — Tipos de documento CUSTOMIZADOS
- Tabela nova **`documento_tipos`** (loja_id, slug `doc_<nome-slugificado>`, nome, etapa_ciclo
  opcional, criado por/em; único por loja+slug). Os 4 tipos nativos NÃO viram linha.
- O slug `doc_[a-z0-9_]+` é path-safe por construção (o tipo vira componente de diretório em
  `documentos_loja/<loja>/<tipo>/`); validação de FORMA nos pontos db-free (staging) e de
  EXISTÊNCIA onde há db (criar_versao/endpoints).
- Endpoints: `GET /api/documentos/tipos` (lista os da loja) e `POST /api/documentos/tipos`
  ({nome, etapa_ciclo}; exige `gerir_documentos`; nome duplicado → erro claro).
- `documento_modelos` funciona igual para slugs custom (versões imutáveis, uma ativa) — todo o
  fluxo importar → analisar → ativar é REUSADO sem cópia.

## Parte 3 — Painel Config → Documentos
- **Barra de ações** (quem tem `gerir_documentos`): "Upload de Modelo" (modal com seletor de tipo
  — nativos + customizados — que desemboca no modal de importação existente já no tipo certo) e
  "Novo Documento" (modal nome + seletor de etapa do ciclo → POST tipos → card novo na grade).
- **Cards**: os 4 nativos (o de Aprovação do PE entra; some o placeholder "em construção") + um
  card por tipo customizado (mostra a etapa associada). Cada card ganha **"Ver exemplo"**:
  preview do modelo ATIVO (sem precisar importar nada) com dados fictícios de cliente + dados
  reais da loja.
- **Preview por tipo** (`POST /api/documentos/modelos/preview`): sem `corpo_md` no request usa o
  modelo ativo da loja (fallback: padrão do sistema p/ contrato e termo_aditivo). Render por tipo:
  contrato/proposta = capa+corpo (como hoje); termo_aditivo = corpo-só + cabeçalho com
  `ctx["_aditivo"]` de EXEMPLO (ordinal PRIMEIRO, blocos preenchidos com ambientes fictícios);
  aprovacao_pe e customizados = corpo-só + cabeçalho (aprovação com `_aprovacao_pe` de exemplo).

## Parte 4 — Suíte de formatação (solução sugerida)
**v1 (existe e é o que se usa agora):** o pipeline de importação já é a suíte — LibreOffice
achata a numeração do Word → `corpo_md` com cláusulas numeradas → análise de marcadores
(desconhecidos bloqueiam, essenciais ausentes avisam, cravados viram marcador com aprovação
humana) → PDF de exemplo → ativar. Para documentos customizados o mesmo pipeline vale inteiro.
**v2 (sugestão, decidir depois):** botão "Formatar com IA" no wizard — envia o corpo importado +
o catálogo de marcadores para um LLM (Claude) reformatar: numerar cláusulas fora do padrão,
sugerir onde cravar marcadores, padronizar títulos `#`. Sai como proposta de DIFF que o operador
revisa antes de ativar (mesma filosofia dos "cravados": IA propõe, humano aprova). Até lá, a
formatação fina de um modelo específico pode ser pedida à IA da sessão de dev (responsabilidade
da IA, como cogitado pelo usuário).

## Fora do escopo (registrado para a próxima frente)
Inserção dos documentos customizados NO CICLO (gerar/assinar o documento na etapa associada,
gates de conclusão). O vínculo `documento_tipos.etapa_ciclo` já fica gravado para isso.

## Testes
Cabeçalho no HTML do aditivo; CRUD de tipos (permissão, duplicado, slug); importar/ativar modelo
de tipo customizado; preview sem corpo_md por tipo (contrato, termo_aditivo com exemplo, custom);
suíte inteira verde.
