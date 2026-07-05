# NF-e Fábrica → Loja · Fase 2 — Interface `EmissorFiscal` + Cliente HTTP Focus NFe — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (Sessão 47)** — branch `feat/nfe`, contrato + cliente HTTP com testes (suíte 457); smoke em homologação pendente do token da Focus. Segunda das fases da integração NF-e (motor: Focus NFe).

## 1. Contexto e recorte

**Guinada de arquitetura (2026-07-05):** o motor fiscal deixou de ser o Omie e passou a ser a **Focus
NFe** (API REST direta). A Focus é camada de **transmissão/autorização** — **não calcula imposto** (nós
fornecemos o bloco fiscal por item). Roadmap completo em
`docs/superpowers/specs/2026-07-05-nfe-fase1-parser-precificacao-design.md` §1.

Esta fase entrega a **fronteira de emissão (contrato) + o transporte HTTP** — isolada, testável **sem**
parser e **sem** regra fiscal. Ela **não** monta o payload com impostos (isso é a Fase 3) nem toca UI
(Fase 5). A Fase 2 pode ser construída e testada por completo **sem o token da Focus** (HTTP mockado);
a validação viva em homologação é um passo manual documentado, para rodar quando o token existir.

## 2. Fatos da API Focus NFe (confirmados na doc)

- **Autenticação:** HTTP **Basic**, o **token como usuário** e **senha em branco** (`Base64("token:")`).
  Token gerado por empresa no painel Focus. Base **homologação** `https://homologacao.focusnfe.com.br`;
  **produção** a confirmar no impl (padrão `https://api.focusnfe.com.br`).
- **Emissão assíncrona:** `POST /v2/nfe?ref=<ref>` (JSON) → **202 `processando_autorizacao`** ou **201
  `autorizado`**. O **`ref` é chave de idempotência do cliente** (reprocessar o mesmo `ref` não duplica).
  O emitente é identificado pelo token **e** por `cnpj_emitente` no corpo.
- **Consulta:** `GET /v2/nfe/{ref}?completa=0|1` → `status` ∈ {`processando_autorizacao`, `autorizado`,
  `erro_autorizacao`, `cancelado`} + `ref, chave_nfe, numero, serie, status_sefaz, mensagem_sefaz,
  caminho_xml_nota_fiscal, caminho_danfe, caminho_xml_cancelamento, erros[] (codigo, mensagem)`.
- **Cancelamento:** `DELETE /v2/nfe/{ref}` com corpo `{"justificativa": "..."}` (**15–255 chars**) →
  `status "cancelado"`, `caminho_xml_cancelamento`.
- **Impostos:** o cliente fornece `cfop`, `codigo_ncm`, `icms_situacao_tributaria` (CST/CSOSN),
  `pis_situacao_tributaria`, `cofins_situacao_tributaria`, alíquotas/valores. **A Focus não calcula.**
  (Consumido na Fase 3; a Fase 2 só transporta o dict pronto.)

## 3. Decisões (brainstorming)

- **Fronteira Fase 2 × Fase 3:** a Fase 2 = **contrato (`EmissorFiscal` ABC + DTOs) + transporte
  (`FocusClient`) + normalizador**. O concreto `EmissorFocusNfe` (que implementa a ABC montando o payload)
  fica na **Fase 3** — a Fase 2 **não** cria classe com método pela metade.
- **HTTP:** `requests` (já usado no `mod_omie.omie_post`, 2.33.1). Retry/backoff espelhando o `omie_post`
  (3 tentativas; rede/5xx/429). Sem dependências novas.
- **Config:** `focus_config.json` em disco (`_BASE_DIR`), **gitignored** (como `omie_config.json`).
  Config **por loja** é Fase 3/5; na Fase 2 o `FocusClient` recebe `token`/`base_url` **injetados**
  (o loader de config é conveniência fina).
- **Assíncrono explícito:** `enviar_nfe` retorna o resultado inicial (pode ser `processando`); quem
  chama polla via `consultar_nfe`/`aguardar_processamento`. Sem bloquear dentro do `enviar_nfe`.
- **NFS-e:** só o contrato (`emitir_nfse_servico`) — qualquer implementação levanta `NotImplementedError`
  até haver 2º CNPJ + município integrado.

## 4. Componentes e interfaces

### 4.1 `emissor_fiscal.py` — contrato neutro (sem dependência de Focus)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

class StatusNota(str, Enum):
    PROCESSANDO = "processando"      # Focus: processando_autorizacao
    AUTORIZADO  = "autorizado"       # Focus: autorizado
    ERRO        = "erro"             # Focus: erro_autorizacao
    CANCELADO   = "cancelado"        # Focus: cancelado
    DESCONHECIDO = "desconhecido"    # qualquer outro / ausente

@dataclass
class ResultadoEmissao:
    ref: str
    status: StatusNota
    chave: str | None = None
    numero: str | None = None
    serie: str | None = None
    status_sefaz: str | None = None
    mensagem_sefaz: str | None = None
    xml_url: str | None = None            # caminho_xml_nota_fiscal
    danfe_url: str | None = None          # caminho_danfe
    xml_cancelamento_url: str | None = None
    erros: list = field(default_factory=list)   # [{"codigo","mensagem"}]
    raw: dict = field(default_factory=dict)     # resposta bruta (auditoria)

class EmissorFiscal(ABC):
    @abstractmethod
    def emitir_nfe_produto(self, nota) -> ResultadoEmissao: ...
    @abstractmethod
    def consultar_status(self, ref: str) -> ResultadoEmissao: ...
    @abstractmethod
    def cancelar(self, ref: str, justificativa: str) -> ResultadoEmissao: ...
    def emitir_nfse_servico(self, servico) -> ResultadoEmissao:
        raise NotImplementedError("NFS-e será implementada quando houver 2º CNPJ + município integrado.")
```

`resultado_de_focus(dados: dict) -> ResultadoEmissao`: normalizador puro que mapeia a resposta da Focus
para `ResultadoEmissao` (traduz `status` string → `StatusNota`; copia chave/numero/serie/sefaz/caminhos/
erros; guarda `raw`). Status desconhecido/ausente → `StatusNota.DESCONHECIDO`.

### 4.2 `focus_client.py` — cliente HTTP puro (fala o JSON da Focus)

```python
class FocusError(Exception):
    def __init__(self, mensagem, status_code=None, erros=None):
        super().__init__(mensagem)
        self.status_code = status_code
        self.erros = erros or []

class FocusClient:
    def __init__(self, token: str, base_url: str, timeout: int = 20): ...
    def enviar_nfe(self, ref: str, payload: dict) -> dict         # POST {base}/v2/nfe?ref={ref}
    def consultar_nfe(self, ref: str, completa: bool = False) -> dict   # GET {base}/v2/nfe/{ref}?completa=0|1
    def cancelar_nfe(self, ref: str, justificativa: str) -> dict  # DELETE {base}/v2/nfe/{ref} body {justificativa}
    def baixar(self, caminho: str) -> bytes                       # GET {base}{caminho} (xml/danfe)
    def aguardar_processamento(self, ref, timeout=60, intervalo=3) -> dict  # polla consultar_nfe
```

- **Auth:** `requests` com `auth=(token, "")` (Basic; senha vazia).
- **`enviar_nfe`:** POST com `params={"ref": ref}`, `json=payload`. Retorna `resp.json()` (com
  `_http_status` embutido, para o chamador distinguir 201/202). Não bloqueia (não polla).
- **`cancelar_nfe`:** valida `15 <= len(justificativa) <= 255` antes de chamar (senão `ValueError`).
- **Retry/backoff** (espelha `omie_post`): até 3 tentativas em **erro de conexão/timeout**, **5xx** e
  **429**; `time.sleep` entre tentativas (respeita `Retry-After` se presente, senão backoff simples).
  Em erro terminal (4xx ≠ 429 sem retry, ou esgotou tentativas) → `FocusError(mensagem, status_code,
  erros)` extraindo `mensagem`/`erros` do corpo quando houver.
- **`aguardar_processamento`:** loop `consultar_nfe` até `status != "processando_autorizacao"` ou
  estourar `timeout`; retorna o último dict. (Usado por conveniência; produção real pode usar webhook —
  fora de escopo.)
- **`base_url`:** sem barra final; paths concatenados. `enviar_nfe`/etc. usam `/v2/nfe`.

### 4.3 Config — `focus_config.json` (gitignored)

`{ "ambiente": "homologacao" | "producao", "token": "...", "cnpj_emitente": "..." }`.
Getter `get_focus_config() -> dict` (lê o arquivo; erro claro se ausente). Helper
`base_url_de(ambiente) -> str` (homologacao → `https://homologacao.focusnfe.com.br`; producao →
`https://api.focusnfe.com.br`). **Onde colocar:** um módulo fino `focus_config.py` (não misturar com
`storage.py`), seguindo o padrão de `omie_config.json`. Adicionar `focus_config.json` ao
`.git/info/exclude` local (não ao `.gitignore` versionado — ruído do projeto).

## 5. Testes

**`tests/test_emissor_fiscal.py`** (puro, sem rede):
- `StatusNota`/`ResultadoEmissao` existem com os campos previstos.
- `resultado_de_focus`: mapeia `autorizado`→AUTORIZADO com chave/numero/serie/caminhos;
  `processando_autorizacao`→PROCESSANDO; `erro_autorizacao`→ERRO com `erros[]`; `cancelado`→CANCELADO com
  `xml_cancelamento_url`; status ausente/estranho→DESCONHECIDO; `raw` preservado.
- `EmissorFiscal` não instancia (ABC); `emitir_nfse_servico` de uma subclasse mínima levanta
  `NotImplementedError`.

**`tests/test_focus_client.py`** (`requests` mockado via `monkeypatch`/`unittest.mock`; `time.sleep`
mockado):
- `enviar_nfe`: chama `POST {base}/v2/nfe` com `params ref`, `auth=(token,"")`, `json=payload`; retorna o
  dict com o http status acessível.
- `consultar_nfe`: `GET .../v2/nfe/{ref}` com `completa` 0/1 conforme flag.
- `cancelar_nfe`: `DELETE .../v2/nfe/{ref}` com `{justificativa}`; justificativa < 15 ou > 255 →
  `ValueError` **antes** de qualquer request.
- **Retry:** 500 seguido de 200 → 2 tentativas e sucesso; 3× 500 → `FocusError(status_code=500)`; erro de
  conexão idem; 429 respeita retry e faz backoff; 4xx (ex. 422) sem retry → `FocusError` com `erros[]` do
  corpo.
- `aguardar_processamento`: `processando`→`processando`→`autorizado` retorna no 3º poll; estoura timeout →
  retorna o último `processando` (sem loop infinito).
- **Nenhuma chamada de rede real.** Suíte verde (`python3 -m pytest -q`).

**Smoke test manual (documentado, fora da suíte):** com `focus_config.json` de homologação preenchido,
um script/CLI curto envia um payload NF-e Simples mínimo, polla até `autorizado`, e baixa XML/DANFE —
roda quando o token existir. Não faz parte do `pytest`.

## 6. Fora de escopo (Fases seguintes / YAGNI)

- Montagem do payload NF-e / bloco de impostos por regime (CST/CSOSN/CFOP/alíquotas) e o concreto
  `EmissorFocusNfe` — **Fase 3**.
- Parser/precificação do XML da fábrica — **Fase 1** (`mod_nfe.py`).
- UI / endpoint HTTP / etapa 15 / persistência do resultado e vínculo com projeto — **Fase 5**.
- Config fiscal **por loja** (Rede→Loja→perfil de emissão) e multi-CNPJ — Fase 3+/cross-cutting.
- NFS-e real, webhooks, produção — depois (só o contrato de NFS-e fica pronto agora).
