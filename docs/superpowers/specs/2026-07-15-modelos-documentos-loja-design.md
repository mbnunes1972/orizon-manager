# Modelos de documentos da loja — design

**Data:** 2026-07-15
**Estado:** aprovado, não implementado
**Escopo:** Fundação (registro de modelos por loja, provado no Contrato) + migração da Proposta comercial
**Fora de escopo:** tipos de documento novos ("+documentos") — spec seguinte

---

## 1. Problema

A aba **Config › Documentos** (`cfgDocumentosRender()`, `static/index.html:2915`) mostra três cards
mortos ("Contrato", "Proposta comercial", "Demais documentos") marcados como *em construção*. Nenhum
é clicável.

O objetivo: a loja deve poder **subir seu próprio documento** (Word/LibreOffice/texto), o sistema
**aplica o modelo Orizon** (extrai o conteúdo, o visual vem do template), pede os **dados
complementares** que faltam, e o modelo fica **registrado num painel de modelos da loja**.

Hoje o modelo do contrato é **um arquivo único da instalação** — `mod_contrato._carregar_md()`
(`mod_contrato.py:724-727`) lê `contrato_template/contrato.md` do disco, sem `loja_id`. Numa rede
multi-loja, "documentos **da loja**" não se sustenta assim.

## 2. Decisões (e o porquê)

| # | Decisão | Motivo |
|---|---|---|
| D1 | **Sem IA em produção.** Wizard determinístico. | Documento com valor jurídico. Zero dependência de API, zero custo por conversão, testável com pytest. O projeto não tem nenhuma integração LLM hoje (`requirements.txt`). |
| D2 | **Modelo por loja, global como fallback.** | Cumpre "documentos da loja". Loja sem modelo próprio segue idêntica a hoje → migração zero. |
| D3 | **Importação via LibreOffice, não python-docx.** | O .docx usa numeração **automática** do Word (`numId/ilvl`): "1.1", "2.3", "a)" **não estão** em `paragraph.text`. `python-docx` produziria um contrato com as cláusulas **sem número**. Já documentado em `scripts/extrair_clausulas_docx.py:4-7`. |
| D4 | **PDF não é convertido, só armazenado.** | Extração de PDF perde a hierarquia de cláusulas (volta texto corrido com cabeçalho/rodapé/número de página). O jurídico sempre tem o .docx. |
| D5 | **`.docx`, `.odt`, `.doc`, `.rtf`, `.md`, `.txt` na entrada.** | `soffice --headless --convert-to txt` normaliza todos os formatos binários pelo mesmo caminho — um pipeline só. |
| D6 | **Versão de modelo é imutável; o contrato fixa a versão que usou.** | `gerar_pdf_contrato()` (`mod_contrato.py:823-829`) **regenera** `CONTRATOS/contrato_<id>.pdf` sobrescrevendo pelo id, lendo o modelo do disco na hora. Sem isso, trocar o modelo reescreve as cláusulas de um contrato **já assinado**, em silêncio. |
| D7 | **Proposta migra para Markdown + WeasyPrint.** | Completa a aposentadoria do docx já feita no contrato. `mod_proposta` já usa o mesmo dicionário de marcadores (`mod_proposta.py:12-13`) — só o renderizador difere. |
| D8 | **Capacidade nova `gerir_documentos`.** | Trocar cláusula de rescisão ≠ corrigir o telefone da loja. Reusar `editar_dados_loja` ampliaria em silêncio o poder de quem já a tem. |

**Precedente que o desenho segue:** `Contrato.loja_snapshot_json` (`database.py:836`) já congela os
dados da loja no momento da geração (F3). D6 é o mesmo padrão aplicado ao corpo do documento.

**Restrição de ambiente:** a migração SQLite→PostgreSQL está decidida mas **não implementada**
(CLAUDE.md, 2026-07-15). Este desenho fica em SQLAlchemy + `_migrar_colunas`, neutro para o cutover.

## 3. Dados

### Tabela nova `documento_modelos`

| coluna | tipo | papel |
|---|---|---|
| `id` | Integer PK | |
| `loja_id` | FK `lojas.id`, not null | tenancy |
| `tipo` | Text, not null | `contrato` \| `proposta`. A coluna é texto livre, mas a validação **só aceita esses dois** nesta entrega; `custom` entra no spec seguinte sem alterar o schema. |
| `versao` | Integer, not null | sequencial por (`loja_id`, `tipo`) |
| `nome` | Text | rótulo exibido no painel. Default = `origem_nome` sem extensão, editável no passo 3 do wizard. |
| `corpo_md` | Text, not null | **o conteúdo**: Markdown com marcadores |
| `origem_nome` | Text | nome do arquivo que o lojista subiu |
| `origem_path` | Text | caminho do original guardado |
| `origem_sha256` | Text | auditoria |
| `ativo` | Integer, default 0 | 1 = vigente para esse (`loja_id`, `tipo`) |
| `criado_em` | DateTime | |
| `criado_por_id` | FK `usuarios.id` | quem trocou a cláusula |

**Invariantes:**
- Uma versão **nunca muda** depois de criada. Editar = criar a versão seguinte. (Se a linha fosse
  mutável, o ponteiro de D6 não garantiria nada.)
- Único por (`loja_id`, `tipo`, `versao`).
- No máximo uma linha com `ativo=1` por (`loja_id`, `tipo`).

### Coluna nova `contratos.modelo_versao_id`

FK → `documento_modelos.id`, **nullable**. Gravada na geração do contrato; a regeração lê o
`corpo_md` daquela versão. `NULL` = contrato legado → cai no arquivo global do disco.

Os `contrato_1/2/3.pdf` existentes têm `NULL` e seguem idênticos: **backfill nenhum**.

`contratos.template_path` (`database.py:825`, default `"config/contrato_template.docx"`) é resquício
do caminho docx aposentado. **Fica onde está, sem uso** — é `nullable=False` e mexer nele altera
contrato legado sem servir ao objetivo desta entrega.

### Arquivos

`documentos_loja/<loja_id>/<tipo>/v<N>/<original>` — a "pasta do sistema". Entra no `.gitignore`
(dado de cliente, como `orizon.db`).

## 4. Módulos

Três módulos, um propósito cada, testáveis isoladamente.

### `mod_marcadores.py` — o catálogo

Hoje `mod_contrato._montar_mapping()` (`mod_contrato.py:575`) sabe **calcular os valores**, mas nada
no sistema sabe **quais marcadores existem** — que é o que a tela precisa mostrar e o que valida um
documento importado.

- `CATALOGO` — cada marcador com rótulo legível e escopo (`cliente` / `loja` / `pagamento` /
  `projeto`).
- `analisar_corpo(corpo_md, loja) → {conhecidos_usados, desconhecidos, ausentes, cravados}`.

**Marcadores novos, escopo loja:** `LOJA_LOGRADOURO`, `LOJA_NUMERO`, `LOJA_BAIRRO`, `LOJA_CIDADE`,
`LOJA_UF`, `LOJA_CEP`. Sem eles o preâmbulo do contrato não tem como ser parametrizado (§6). A tabela
`lojas` já tem todos os campos (`database.py:381-387`).

**Anti-drift:** teste que trava catálogo ↔ `_montar_mapping` (§8).

### `mod_documentos_import.py` — normalização e extração (sem banco)

- `normalizar(path) → texto`
  - `.docx/.odt/.doc/.rtf` → `soffice --headless --convert-to "txt:Text (encoded):UTF8"`, via o
    `mod_contrato._libreoffice_cmd()` que já existe (`mod_contrato.py:867`, já resolve o caminho do
    binário no Windows e no servidor).
  - `.md/.txt` → leitura direta.
  - `.pdf` → levanta erro com mensagem explicando o porquê (D4).
- `extrair_corpo(texto) → markdown` — lógica promovida de `scripts/extrair_clausulas_docx.py`: corta
  a capa (mantém de "CONTRATO DE COMPRA E VENDA" em diante), transforma `CLÁUSULA ...` em heading
  `#`, tira indentação, insere `[TEXTO_COMPLEMENTAR]` antes do fecho.

**O corte importa:** `extrair_corpo` é função pura sobre texto → testa com fixture `.txt` **sem
LibreOffice instalado**. Só `normalizar` toca `subprocess`.

### `mod_documentos.py` — o registro (único que fala com o banco)

- `resolver_modelo(loja_id, tipo) → corpo_md` — versão ativa da loja; senão, o arquivo global.
- `criar_versao(loja_id, tipo, corpo_md, origem, usuario_id) → modelo`
- `ativar(modelo_id)` — liga esta, desliga a anterior, atômico.
- `listar(loja_id) → [modelos]`

### Renderizador compartilhado

O genérico (markdown + mapping → HTML → WeasyPrint) sai do `mod_contrato` para um módulo
compartilhado. A capa e as grades de parcelas/ambientes (`_html_parcelas_linhas`,
`_html_ambientes_linhas`) **ficam** no `mod_contrato` — são do contrato, não do motor.

## 5. Fluxo do wizard

1. **Arquivo** — upload (reusa `_parse_multipart_arquivos()`, `main.py:252`) → `normalizar` →
   `extrair_corpo` → `corpo_md` preliminar. Nada é salvo ainda.
2. **Revisão** — a análise determinística responde três perguntas:
   - **Marcadores conhecidos ausentes.** Documento sem `[NOME_CLIENTE]` ou sem o bloco de
     testemunhas sai um contrato quebrado.
   - **Marcadores desconhecidos.** `[FOO]` fora do catálogo **bloqueia a ativação**: `_aplica_mark()`
     (`mod_contrato.py:246`) mantém no texto o marcador sem correspondência → imprimiria literalmente
     "[FOO]" no PDF. Ou mapeia para um conhecido, ou remove.
   - **Dados da loja cravados.** Varre o corpo atrás do CNPJ, nome, cidade e endereço da própria loja
     (CNPJ/CPF comparados sem pontuação) e propõe cada troca por marcador — o lojista aprova uma a
     uma.
3. **Preview e ativação** — renderiza o PDF com um cliente de exemplo (mostra exatamente o que sai);
   **Ativar** (gate `gerir_documentos`) cria a versão N+1 e desativa a anterior.

## 6. Por que a detecção de "cravados" é necessária

O `contrato_template/contrato.md` atual traz a CONTRATADA **cravada no texto**:

- linha 3: "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA, ... com sede a Avenida Barão do Rio Branco,
  736 – Jardim Esplanada – São José dos Campos – SP – CEP: 12.242-800, inscrita no CNPJ/MF sob o n.
  19.152.134/0001-56"
- linha 90: foro da Comarca de **São José dos Campos**

Numa rede multi-loja isso é exatamente o dado que precisa virar marcador — e é o que o usuário
descreveu como "dados complementares". A detecção não adivinha: compara com o cadastro da própria
loja e **propõe**.

## 7. Tela, endpoints, permissão

**Painel** — `cfgDocumentosRender()` passa a listar os modelos da loja (tipo, versão ativa, quem
ativou, quando). Clicar em "Contrato" abre o modal: versão vigente, histórico, "Importar novo
modelo".

**Endpoints:**

| método | rota | papel |
|---|---|---|
| GET | `/api/documentos/marcadores` | catálogo |
| GET | `/api/documentos/modelos` | modelos da loja |
| POST | `/api/documentos/modelos/importar` | analisa; **não salva** |
| POST | `/api/documentos/modelos/preview` | PDF de exemplo |
| POST | `/api/documentos/modelos` | cria a versão e ativa |

Todos escopados por `loja_id` da sessão (tenancy).

**Permissão** — `gerir_documentos`, nova em `perfis.CAPS_SELECIONAVEIS` (`perfis.py:252`), ligada por
padrão só no master. Leitura do painel segue `ver_parametros`.

**Testemunhas** — já resolvidas: `lojas.testemunha1_nome/cpf` e `testemunha2_nome/cpf`
(`database.py:388-391`), consumidas em `_montar_mapping()` (`mod_contrato.py:584-587`) e casadas com
`[NOME_TESTEMUNHA_1]`/`[CPF_TESTEMUNHA_1]`. O wizard apenas **verifica** que o documento importado
tem o bloco de assinatura; o cadastro não muda.

## 8. Proposta comercial

Ganha `proposta_template/proposta.{md,html,css}`, espelhando `contrato_template/`. O
`modelo_proposta.docx` atual entra como **o primeiro import** — valida o pipeline com um documento
real, não com fixture.

Marcadores próprios já existentes (`mod_proposta.py:18-24`): `AMBIENTES_LISTA`, `VALOR_BRUTO`,
`DESCONTO_PCT`, `VALOR_TOTAL`, `VALIDADE` → entram no catálogo, escopo `projeto`.

Isso deixa `mod_contrato._substituir_marcadores` (caminho python-docx) **sem chamador** → removido.
O LibreOffice recua para a importação.

## 9. Testes (TDD)

| teste | prova |
|---|---|
| `extrair_corpo` preserva numeração de cláusula, corta a capa, insere `[TEXTO_COMPLEMENTAR]` | D3/D5 — fixture `.txt`, sem LibreOffice |
| `normalizar` rejeita `.pdf` com mensagem clara | D4 |
| catálogo ↔ `_montar_mapping` sem drift | o catálogo não apodrece |
| versão imutável; só uma ativa por (loja, tipo) | invariantes §3 |
| `resolver_modelo` cai no arquivo global quando a loja não tem modelo | D2 — nada quebra |
| loja A não enxerga modelo da loja B | tenancy |
| **regerar contrato antigo, com modelo novo já ativo, reproduz as cláusulas originais** | **D6 — sem este verde, o versionamento é decorativo** |
| marcador desconhecido bloqueia ativação | §5 — evita "[FOO]" no PDF |
| `gerir_documentos` barra quem não tem a capacidade | D8 |
| `test_arquitetura_modulos` reconhece os módulos novos | padrão do projeto |

Frontend não tem teste JS (CLAUDE.md) → verificação manual + `node --check` no `<script>`.

## 10. Sequência de implementação

1. `mod_marcadores.py` (catálogo + teste anti-drift) — nada depende de nada
2. `mod_documentos_import.py` (`extrair_corpo` puro → `normalizar`)
3. Tabela + `mod_documentos.py` (registro, invariantes, `resolver_modelo` com fallback)
4. `contratos.modelo_versao_id` + binding na geração ← **o teste de D6 fecha aqui**
5. Capacidade `gerir_documentos`
6. Endpoints
7. Painel + wizard (frontend)
8. Renderizador compartilhado + migração da proposta

O `preview` do passo 6 usa o renderizador **do `mod_contrato`, como está hoje** — a extração do
renderizador compartilhado (passo 8) é exigência da proposta, não do contrato. Passos 1-7 entregam o
card Contrato clicável e funcionando sem tocar no motor de renderização.

Os passos 1-4 entregam a garantia jurídica antes de existir tela — se algo tiver que ser cortado, é
da tela para baixo, nunca de 1-4.

## 11. Fora de escopo (spec seguinte)

**"+documentos" — tipos de documento novos.** A pergunta que este spec não responde: **o que dispara
um documento custom?** Um "Termo de Medição" registrado no painel não serve de nada se nada no ciclo
o emite. Isso é gancho no ciclo/projeto + anexação — feature própria, e a mais cara das três.

A coluna `tipo` já nasce preparada (`contrato` | `proposta` | `custom`), e o painel já nasce
genérico: o spec seguinte acrescenta linhas e um gancho, não remodela nada.
