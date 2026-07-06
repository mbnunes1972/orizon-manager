# Auditoria de Qualidade — Domínio Contrato / Ciclo / Projeto / Integração Omie

**Sistema:** Orizon Manager / Dalmóbile — vendas de móveis planejados (produção).
**Escopo:** `mod_contrato.py`, `contrato_editar.py`, `mod_proposta.py`, `mod_ciclo.py`, `mod_arvore.py`, `mod_omie.py`, `promob_grupos.py`, `mod_qualidade_xml.py`, `scripts/`, mais os pontos de entrada HTTP relevantes em `main.py`/`storage.py`.
**Data:** 2026-07-03  |  **Metodologia:** leitura integral de cada função/classe do escopo, rastreamento dos call-sites em `main.py`, revisão da suíte de testes. Read-only; nenhum arquivo de produção alterado.
**Ótica:** enterprise-grade gold — completude, robustez de I/O externo, tratamento de erro, idempotência, cobertura de teste.

---

## Sumário executivo

O domínio de **contrato (motor puro)** e **ciclo** é de qualidade alta: funções pequenas, documentadas, sem stubs, e com boa cobertura de teste (`test_contrato.py`, `test_ciclo.py`, `test_arvore.py`). Os problemas concentram-se na **fronteira de I/O externo**: a integração Omie (`mod_omie.py`) e o parsing de XML (`promob_grupos.py`) **não têm nenhum teste**, o parser de XML está **exposto a XXE** (billion-laughs / leitura de arquivo local via `xml.etree.ElementTree` sem hardening), o upload de XML tem **path traversal** pelo nome de arquivo do multipart, e há **um bug latente de import** (`io` não importado em `gerar_excel`) e um **retry HTTP que não re-tenta erros de rede**. A assinatura eletrônica de contrato usa um hash SHA-256 de dados públicos **sem segredo do servidor** (não é prova de integridade contra a própria loja). Vários `scripts/` referenciam o caminho `.docx`/Jinja do contrato que a `CLAUDE.md` declara **aposentado** — infraestrutura morta/enganosa.

---

## Achados

### 1. Parsing de XML sem defesa contra XXE / billion-laughs
**Severidade:** 🔴

**Evidência:** `promob_grupos.py:8,266-274` e `mod_omie.py:4,201-202`
```python
import xml.etree.ElementTree as ET
...
def ler_xml(caminho):        tree = ET.parse(caminho)
def ler_xml_str(...):        root = ET.fromstring(xml_string)
...
def _extrair_cliente_e_ambiente(xml_str):
    root = ET.fromstring(xml_str)
```
Todo o XML do Promob entra por `POST /carregar` e `POST /api/projetos/<nome>/ambientes` (`main.py:1389-1394`, `main.py:3100`) e é parseado direto por `ET.fromstring` sobre conteúdo **enviado pelo cliente**, sem `resolve_entities=False`, sem limitar profundidade nem tamanho.

**Impacto:** `xml.etree.ElementTree` do CPython não expande entidades externas por padrão (mitiga XXE de leitura de arquivo/SSRF na versão atual), mas **não protege contra "billion laughs" / entity-expansion recursiva**, que ainda é aceita e pode esgotar CPU/memória do processo `http.server` single-thread — negando o serviço para todos os usuários da rede. Um XML malicioso (ou corrompido pelo Promob) derruba o servidor.

**Recomendação:** trocar por `defusedxml` (`from defusedxml.ElementTree import fromstring, parse`) em `promob_grupos.py` e `mod_omie.py`, ou no mínimo impor teto de tamanho no corpo (ver Achado 4) e rejeitar `<!DOCTYPE`/`<!ENTITY` antes do parse. Adicionar teste com XML de bomba de entidades garantindo rejeição.

---

### 2. Path traversal no nome do arquivo XML enviado
**Severidade:** 🔴

**Evidência:** `main.py:171-172` (parser) → `mod_omie.py:252-253` (gravação)
```python
# main.py _parse_multipart:
arquivos.append((params["filename"], payload.decode("utf-8", "ignore")))
# mod_omie._adicionar_ambientes:
for nome_arq, conteudo in arquivos_xml:
    storage_salvar_texto(os.path.join(pasta_xmls, nome_arq), conteudo)
```
`storage_salvar_texto` (`storage.py:37-40`) faz `os.makedirs(os.path.dirname(caminho))` e grava **sem validar** que `caminho` está dentro de `pasta_xmls`. O `filename` vem cru do multipart, sem `os.path.basename` nem sanitização. O mesmo `filename` também vira `amb['arquivo']` e depois `arquivo_path` persistido no `projeto.json`.

**Impacto:** um `filename` como `..\..\..\config\perfis_config.json` (ou caminho absoluto em alguns casos) faz o backend gravar/sobrescrever arquivos **fora** da pasta do projeto — corrupção de config, injeção de arquivos, ou escrita em qualquer diretório com permissão do processo. Também `_arquivar_xmls` (`mod_omie.py:769-777`) e `bloquear_projeto` (que percorre `os.listdir`) herdam nomes não confiáveis.

**Recomendação:** sanitizar o nome logo no parser — `nome = os.path.basename(params["filename"])` e rejeitar componentes `..`/separadores; validar em `storage_salvar_texto` que `os.path.abspath(caminho).startswith(os.path.abspath(pasta))`. Cobrir com teste de traversal.

---

### 3. `gerar_excel` levanta `NameError` — `io` nunca importado
**Severidade:** 🟠

**Evidência:** `mod_omie.py:756` usa `io.BytesIO()`, mas o topo do módulo (`mod_omie.py:4`) importa `os, re, time, json, unicodedata, uuid` — **não `io`**. Grep confirma zero `import io` no arquivo.
```python
buf = io.BytesIO()   # linha 756 — NameError em runtime
```
A função é importada em `main.py:35` mas **nunca é chamada** em nenhum handler (grep: única ocorrência é o import). Ou seja, é código morto que só falharia se re-conectado.

**Impacto:** dívida latente: qualquer rota futura que reative a exportação Excel quebra imediatamente com `NameError`, sem aviso em tempo de import. Sinal de que a função nunca foi exercitada e não tem teste.

**Recomendação:** adicionar `import io` (ou `from io import BytesIO`) e um teste mínimo de `gerar_excel`, **ou** remover a função e o import morto em `main.py` se a exportação Excel foi de fato aposentada.

---

### 4. Corpo de request lido sem limite de tamanho (DoS de memória)
**Severidade:** 🟠

**Evidência:** `main.py:1354-1355`, `main.py:3702-3703`, `main.py:3877-3878`
```python
length = int(self.headers.get("Content-Length", 0))
body   = self.rfile.read(length) if length else b'{}'
```
`Content-Length` é confiado sem teto; `int(...)` sem `try` (um header não numérico gera `ValueError` 500 não tratado). Combinado com o parse de XML (Achado 1) e multipart em memória, um upload grande é totalmente materializado em RAM no processo single-thread.

**Impacto:** um único cliente pode esgotar memória/segurar o servidor (que é single-thread — bloqueia todos). Header malformado vira exceção não tratada.

**Recomendação:** impor `MAX_BODY` (ex. 25 MB) e retornar 413 acima disso; `try/except ValueError` no parse do header. Aplicar antes do `read`.

---

### 5. `omie_post` não re-tenta erros de rede (retry ilusório)
**Severidade:** 🟠

**Evidência:** `mod_omie.py:26-70`
```python
for tentativa in range(3):
    ...
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        ...
    except Exception as e:
        msg_e = str(e).lower()
        if "connectionreset" in msg_e or ...:  raise Exception("OMIE_BLOQUEIO_425: ...")
        if "timed out" in msg_e or ...:        raise Exception("OMIE_BLOQUEIO_425: ...")
        if tentativa == 2: raise
        raise            # <-- re-raise incondicional na 1ª tentativa
```
O único caminho que efetivamente re-tenta é o rate-limit (`continue` dentro do `if not resp.ok`). Para **qualquer** exceção de rede (timeout, connection reset, DNS), o `except` converte em erro e **`raise` imediato** — o `for range(3)` nunca faz a 2ª tentativa. O `raise` na penúltima linha torna `if tentativa == 2: raise` redundante.

**Impacto:** falha transitória de rede (comum em API externa) aborta a exportação de pedidos no meio, sem o retry que o loop aparenta oferecer. Resiliência prometida pela estrutura não existe.

**Recomendação:** para timeout/reset, aplicar backoff e `continue` enquanto `tentativa < 2`; só levantar após esgotar. Distinguir erro transitório (retriable) de bloqueio 425 (não retriable). Cobrir com teste mockando `requests.post`.

---

### 6. Parâmetro `no_rotate` morto em toda a camada Omie
**Severidade:** 🟡

**Evidência:** `mod_omie.py:26` declara `no_rotate=False`; passado explicitamente em **9 call-sites** (`mod_omie.py:181,321,386,461,467,508,594,606,620`), mas **nunca referenciado** no corpo de `omie_post`.

**Impacto:** vestígio de uma feature de rotação de chave removida. Ruído que sugere um comportamento (não rotacionar credencial) que não existe mais — engana quem lê e mantém.

**Recomendação:** remover o parâmetro e limpar os call-sites, ou reimplementar a rotação se ainda for requisito.

---

### 7. Assinatura eletrônica sem segredo — hash não é prova de integridade
**Severidade:** 🟠

**Evidência:** `mod_contrato.py:48-50`
```python
def calcular_hash_assinatura(nome, cpf, contrato_id, timestamp):
    dados = f"{nome}|{cpf}|{contrato_id}|{timestamp}"
    return hashlib.sha256(dados.encode("utf-8")).hexdigest()
```
Usado em `main.py:3372`. Todos os insumos são dados **públicos/controláveis** (nome, CPF, id sequencial, timestamp). Não há chave/segredo do servidor (HMAC), nem hash do PDF renderizado, nem verificação de que o `cpf` assinado corresponde ao CPF do cliente/loja do contrato (`main.py:3340-3347` só exige não-vazio).

**Impacto:** o hash é **reproduzível por qualquer parte**, logo não prova quem assinou nem que o documento não mudou — não tem valor probatório de assinatura eletrônica. Além disso, `parte='cliente'` pode ser registrada com qualquer nome/CPF digitado pela loja (sem conferência), e o contrato fecha a etapa 7 e marca o projeto como "fechado" (`main.py:3395-3408`).

**Recomendação:** usar HMAC com segredo do servidor e incluir o hash do PDF gerado; validar que `cpf` casa com o cliente/loja do contrato; registrar evidência forte (IP já é gravado — bom). Se a intenção é só "aceite" e não assinatura jurídica, documentar explicitamente para não induzir a erro.

---

### 8. Etapa 7 pode ser fechada sem PDF de contrato existente
**Severidade:** 🟡

**Evidência:** `main.py:3358-3408` (assinar) vs `main.py:3419-3540` (gerar PDF). O handler de `assinar` busca o último `Contrato` e, ao ter ambas as partes, marca `status='assinado'`, conclui a etapa 7 e faz `upsert_projeto_status(nome_safe,'fechado')`. Não há verificação de que o `pdf_path` do contrato foi gerado nem de que o pagamento não ficou desatualizado (`contrato_desatualizado` existe em `mod_contrato.py:454` mas o guard só é consultado no GET de status, `main.py:1326`, não no fluxo de assinar).

**Impacto:** um contrato pode ser "assinado/fechado" com pagamento divergente do que foi renderizado, ou sem o artefato PDF, deixando estado inconsistente entre o que o cliente viu e o que o sistema registra.

**Recomendação:** no `assinar`, exigir contrato com PDF gerado e reprovar se `contrato_desatualizado(...)` for verdadeiro; transação única cobrindo assinatura + fechamento de etapa.

---

### 9. `scripts/` de template apontam para o caminho `.docx` aposentado
**Severidade:** 🟡

**Evidência:** `scripts/configurar_template_contrato.py`, `scripts/preparar_template_contrato.py`, `scripts/criar_template_placeholder.py` geram `config/contrato_template.docx` com placeholders **Jinja2** (`{{ cliente_nome }}`, `{% if tem_adendo %}`). A `CLAUDE.md` declara: *"O caminho `.docx`/LibreOffice do contrato foi **aposentado**"* — o contrato hoje é HTML+Markdown→WeasyPrint (`mod_contrato.py:806-814`), que usa marcadores `[MARCADOR]`, não Jinja. `configurar_template_contrato.py:11` lê `Modelo de Contrato.docx`, arquivo que **não existe** na raiz (grep/ls não encontram).

**Impacto:** scripts de manutenção mortos/quebrados no repositório, referenciando um pipeline abandonado e um modelo inexistente. Risco de alguém executá-los achando que configuram o contrato ativo (não configuram) — retrabalho e confusão. Vários scripts (`normalizar_assinaturas`, `organizar_assinaturas`, `inserir_marcador_tipo`) mutam `modelo_contrato_mapeado.docx`, também fora do pipeline HTML atual.

**Recomendação:** mover scripts do pipeline `.docx` aposentado para `scripts/legado/` com README, ou removê-los. Manter apenas o que serve ao pipeline WeasyPrint e à proposta (que ainda usa `.docx`).

---

### 10. `carregar_xmls` engole exceções por ambiente e retorna `ok:True` mesmo com falhas
**Severidade:** 🟡

**Evidência:** `mod_omie.py:214-240`
```python
except Exception as e:
    ambientes.append({... "total": 0.0, "grupos": [], "erro": str(e)})
...
return {"ok": True, ..., "ambientes": ambientes, ...}
```
Um XML corrompido vira um ambiente com `total=0` e chave `erro`, mas o retorno global é sempre `ok:True`. O handler `/carregar` (`main.py:1394-1405`) não inspeciona `erro` por ambiente antes de seguir. Um ambiente que falhou entra no `total_projeto` como zero, silenciosamente subvalorizando o orçamento.

**Impacto:** falha de parse fica invisível; orçamento sai menor do que deveria sem nenhum alerta ao consultor. Erro financeiro silencioso.

**Recomendação:** propagar contagem de ambientes com `erro` no topo do payload (`n_erros`) e sinalizar no frontend; considerar `ok:False` quando algum ambiente falhou.

---

### 11. Números/strings mágicos e caminhos hardcoded na integração Omie
**Severidade:** 🔵

**Evidência:**
- `mod_omie.py:26` URL `https://app.omie.com.br/api/v1` embutida; `timeout=10` default, `range(3)` tentativas — todos literais.
- `mod_omie.py:416,422` categoria escolhida por regex `^1[.]\d+[.]\d+$` (heurística frágil de plano de contas).
- `promob_grupos.py:19-34` NCMs marcados *"# confirmar"* em produção (grupos 10 e 11) — imposto fiscal potencialmente incorreto.
- `mod_omie.py:497,513` NCM fallback `94036000` hardcoded; `criar_cliente` telefone `"00"/"000000000"` fixo.
- `mod_contrato.py:23` `_TRACO="--------"`, grade fixa de 24 parcelas espalhada por várias funções.

**Impacto:** manutenção difícil; NCM "a confirmar" tem consequência fiscal real; heurística de categoria quebra se o plano de contas mudar.

**Recomendação:** externalizar endpoint/timeout/tentativas para config; validar NCMs com o contador e remover os "# confirmar"; centralizar o teto de 24 parcelas numa constante.

---

### 12. Caches de módulo mutáveis globais na camada Omie (estado compartilhado)
**Severidade:** 🔵

**Evidência:** `mod_omie.py:311-312` `_categoria_cache=[None]`, `_cc_cache=[None]`; `_grupos_cache` importado de `storage`. `exportar_ambientes` reseta `_categoria_cache[0]=None` no início (`mod_omie.py:550-551`), mas `buscar_categoria`/`garantir_conta_corrente` gravam nesses globais.

**Impacto:** num servidor `http.server` multi-thread (o padrão `ThreadingHTTPServer` é comum), duas exportações concorrentes de redes/lojas diferentes compartilham o mesmo cache de categoria/conta-corrente — vazamento de dado entre tenants. Mesmo single-thread, é acoplamento oculto.

**Recomendação:** escopar o cache por credencial/loja (dict keyed) ou passar como parâmetro; documentar a premissa single-thread se for o caso.

---

### 13. `_libreoffice_cmd` só cobre Windows; produção declarada é WSL/Ubuntu
**Severidade:** 🔵

**Evidência:** `mod_contrato.py:829-837` só checa caminhos `C:\Program Files\...` e cai no literal `"libreoffice"`. A `CLAUDE.md` diz ambiente WSL/Ubuntu. A proposta (`mod_proposta.py:38-42`) depende disso; se `libreoffice` não estiver no PATH, cai em `LibreOfficeIndisponivel` e devolve `.docx` sem PDF — degradação silenciosa.

**Impacto:** proposta pode sair sem PDF em produção sem sinalização clara ao usuário além do flag `eh_pdf=False`.

**Recomendação:** tornar o caminho do LibreOffice configurável e logar quando cair no fallback docx.

---

### 14. `data_contrato` sempre "hoje" ignora recdebito/reemissão; timezone naïve
**Severidade:** 🔵

**Evidência:** `mod_contrato.py:796` `"data_contrato": datetime.now().strftime("%d/%m/%Y")` (local, sem TZ) e `main.py:3370,3378` usam `datetime.utcnow()` para a assinatura. Mistura de `now()` local (data do contrato) e `utcnow()` (assinatura) no mesmo domínio.

**Impacto:** inconsistência de fuso entre a data impressa no contrato e o timestamp de assinatura/hash; regerar o contrato muda a data impressa mesmo para um contrato já numerado.

**Recomendação:** padronizar fuso (America/Sao_Paulo) e persistir a data de emissão junto do `Contrato` em vez de recomputar a cada render.

---

### 15. Cobertura de teste ausente nos módulos de maior risco
**Severidade:** 🟠

**Evidência:** existem testes para `mod_contrato` (`test_contrato.py`, 40+ casos), `mod_ciclo` (`test_ciclo.py`), `mod_arvore` (`test_arvore.py`), `mod_qualidade_xml` (`test_qualidade_xml.py`). **Não há nenhum** `test_omie*.py`, `test_promob*.py` nem `test_proposta*.py` (grep em `tests/`). Ou seja, `mod_omie.py` (827 linhas, toda a I/O externa e criação de cliente/pedido) e `promob_grupos.py` (classificador fiscal de 100+ regras + parser XML) rodam **sem rede de segurança**.

**Impacto:** os módulos com maior superfície de falha (rede, parsing, classificação fiscal) são os menos testados. As regras de `classificar()` — que determinam NCM e agrupamento de valor — podem regредir sem detecção, afetando imposto e orçamento.

**Recomendação:** adicionar testes de `classificar()` (tabela de refs conhecidas → grupo esperado), de `_ler_xml_root` com XML fixture (incl. malformado e bomba de entidades), e de `omie_post`/`exportar_ambientes` com `requests` mockado (retry, rate-limit, ajuste de quantidade decimal).

---

### 16. `main()` de `promob_grupos.py` acessa `ambientes[0]` sem guardar contra lista vazia
**Severidade:** 🔵

**Evidência:** `promob_grupos.py:311-323` — se todos os XMLs falharem no parse, `ambientes` fica vazio e `nome_base = ...ambientes[0]['projeto']...` levanta `IndexError`. É CLI de manutenção, não o servidor, mas está no escopo "produção".

**Impacto:** crash não amigável no utilitário de linha de comando com entrada ruim.

**Recomendação:** early-return com mensagem quando `not ambientes`.

---

### 17. `_parse_pagamento` faz `float()` sem proteção em campos externos
**Severidade:** 🔵

**Evidência:** `mod_contrato.py:402` `entrada_val = float(pag.get("entrada_valor") or 0)` e `mod_contrato.py:433` `total_cliente = pag.get("total_cliente") or 0` — se o frontend enviar `"entrada_valor": "abc"`, o `float()` levanta `ValueError` não tratado (o `try/except` só cobre o `json.loads`, `mod_contrato.py:395-398`). Idem `main.py:3433` `float(req.get("entrada_valor") or 0)`.

**Impacto:** payload malformado quebra a geração do contrato com 500 em vez de erro de validação claro.

**Recomendação:** coerção defensiva (`_to_float` com fallback) nos campos numéricos vindos do cliente.

---

## Pontos positivos (para não regredir)

- `mod_ciclo.py`: fonte única de verdade, puro, sem I/O, totalmente testado (gating, cascata de reabertura, bloqueio por contrato assinado). Exemplar.
- `mod_arvore.py`: separação limpa de PII, escopo de tenancy validado, erros mapeados para HTTP via exceções tipadas.
- `mod_contrato.py` (motor puro): substituição de marcadores robusta, escape HTML dos valores no caminho WeasyPrint (`mod_contrato.py:723` — evita injeção no PDF), rateio de valor por ambiente com reconciliação de resíduo testada.
- `mod_qualidade_xml.py`: puro, com tolerância de arredondamento explícita e testado.
- `bloquear_projeto`/`verificar_integridade_xmls` (`mod_omie.py:264-307`): hash SHA-256 dos XMLs para detectar adulteração pós-aprovação — bom controle de integridade.
- `_converter_pdf` (`mod_contrato.py:840-860`): timeout de 120s e tratamento diferenciado de `FileNotFoundError`/`CalledProcessError`/`TimeoutExpired`.

---

## Placar por severidade

| Severidade | Qtd | Achados |
|---|---|---|
| 🔴 Crítico | 2 | #1 XXE/entity-expansion no parse de XML; #2 path traversal no upload |
| 🟠 Alto | 5 | #3 `io` não importado (`gerar_excel`); #4 body sem limite (DoS); #5 retry HTTP ilusório; #7 assinatura sem segredo; #15 sem testes em Omie/Promob |
| 🟡 Médio | 4 | #6 `no_rotate` morto; #8 etapa 7 fecha sem PDF/guard; #9 scripts `.docx` aposentados; #10 `carregar_xmls` mascara falha |
| 🔵 Baixo | 6 | #11 mágicos/NCM "a confirmar"; #12 cache global multi-tenant; #13 LibreOffice só Windows; #14 timezone naïve; #16 `ambientes[0]` sem guard; #17 `float()` sem proteção |
| ℹ️ Infos | — | ver "Pontos positivos" |
| **Total** | **17** | |

**Nota de encerramento:** o núcleo de regra de negócio (contrato puro, ciclo, árvore) está em nível gold. O risco enterprise real está na fronteira de entrada não confiável (XML/multipart) e na integração externa (Omie), justamente onde não há testes. Priorizar #1, #2 e #15.
