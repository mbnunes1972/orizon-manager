# Painel de Configuração Fiscal · Sub-frente I — Fundação Backend (`PerfilFiscal`) — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Parte da integração NF-e (Focus NFe); é o
> pré-requisito do "mapa fiscal" que monta o payload da NF-e.

## 1. Contexto e recorte

A emissão de NF-e via Focus NFe exige que **nós** forneçamos o bloco fiscal por item (a Focus não
calcula imposto — ver Fase 2). Em vez de fixar CST/CSOSN/CFOP/alíquotas no código, esses valores vêm de
um **PerfilFiscal por CNPJ/loja**. Esta frente é a **fundação backend** desse perfil: modelo de dados,
criptografia dos segredos, endpoints CRUD, o perfil-padrão de teste e a fiação com o `FocusClient`.

**Decomposição (aprovada):**
- **Sub-frente I (esta spec):** modelo `PerfilFiscal` + `fiscal_cripto.py` + `mod_fiscal.py` (default/validação)
  + endpoints + `focus_client_para_loja`. Backend puro/testável, sem UI.
- **Sub-frente II (depois):** o **painel no frontend** (7 blocos, badges de placeholder, troca de ambiente
  explícita).
- **Depois (Fase 3b+):** o **mapa fiscal** (resolve NCM/CFOP/CSOSN do PerfilFiscal → payload) + o concreto
  `EmissorFocusNfe`; emissão real (Fase 4); UI etapa 15 (Fase 5).

Consome/alimenta: o `preview` da Fase 1 (itens precificados) + o `PerfilFiscal` desta frente →
(Fase 3b) mapa fiscal → payload → `FocusClient` (Fase 2). Esta frente entrega a peça que faltava para
o mapa fiscal ter dado real.

## 2. Decisões (brainstorming)

- **Certificado A1 NÃO fica no nosso sistema.** O `.pfx` + senha são enviados ao **painel da Focus**
  (ela guarda o certificado server-side). O `PerfilFiscal` guarda só **referência não-secreta**:
  validade (alerta de vencimento) + CNPJ do certificado. → o segredo mais crítico sai do nosso banco.
- **Criptografia em repouso (`cryptography.Fernet`)** para os únicos segredos que guardamos: os **tokens
  da Focus** (homologação/produção). Ciphertext no banco; **chave-mestra FORA do banco** —
  `ORIZON_FISCAL_KEY` (env) com fallback para keyfile `config/fiscal.key` (gitignored). `cryptography`
  **já está instalada** (48.0.0, transitiva). Cripto **isolada** num módulo trocável (migrar para KMS é
  "retomar depois", sem tocar chamadores).
- **`PerfilFiscal` é tabela dedicada** (1:1 com `Loja`), não JSON na Loja — complementa (não duplica) o
  `cnpj`/endereço que a Loja já tem.
- **Produção bloqueada enquanto houver placeholder:** trocar `ambiente_ativo` para `producao` é ação
  **explícita** e é **rejeitada** se `placeholders` não estiver vazio (impede emitir nota real com valor
  de teste).
- **Segredos nunca no GET nem em log:** o GET devolve só flags de presença (`token_*_definido`); os
  tokens entram por um PUT **write-only**.
- **Permissões:** reusa `editar_dados_loja` + escopo de tenancy (`mod_tenancy.pode_editar_dados_loja`),
  como o painel de config-financeira.

## 3. Modelo de dados — `PerfilFiscal` (`database.py`)

Tabela nova (criada automaticamente por `Base.metadata.create_all` no `init_db` — sem migração manual).

```python
class PerfilFiscal(Base):
    __tablename__ = "perfil_fiscal"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    loja_id       = Column(Integer, ForeignKey("lojas.id"), nullable=False, unique=True)  # 1:1
    # Identificação fiscal (complementa Loja.cnpj/endereço)
    razao_social        = Column(Text, nullable=True)
    inscricao_estadual  = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)
    # Regime tributário
    regime_tributario   = Column(Text, nullable=True)   # 'simples'|'simples_excesso'|'normal'|'mei'
    csosn_padrao        = Column(Text, nullable=True)    # ex '101'
    # NF-e produto
    cfop_dentro_uf      = Column(Text, nullable=True)    # '5102'
    cfop_fora_uf        = Column(Text, nullable=True)    # '6102'
    serie_nfe           = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)     # bool (Lei da Transparência)
    # NFS-e serviço (só dado agora; emissão adiada)
    cnae_servico          = Column(Text,  nullable=True)
    cod_servico_municipio = Column(Text,  nullable=True)
    aliquota_iss          = Column(Float, nullable=True)
    retencao_json         = Column(Text,  nullable=True)
    municipio_ibge        = Column(Text,  nullable=True)
    # Certificado — REFERÊNCIA apenas (o .pfx vive na Focus)
    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj     = Column(Text,     nullable=True)
    # Perfil de emissão (topologia)
    papel_cnpj    = Column(Text, nullable=True)  # 'central_produto'|'loja_servico'|'loja_produto_servico'|'avulso'
    # Segredos cifrados + ambiente
    focus_token_homolog_enc = Column(Text, nullable=True)   # Fernet ciphertext
    focus_token_prod_enc    = Column(Text, nullable=True)   # Fernet ciphertext
    ambiente_ativo          = Column(Text, default="homologacao")  # 'homologacao'|'producao'
    # Controle de placeholder (dirige os badges da UI na Sub-frente II)
    placeholders_json = Column(Text, nullable=True)   # JSON: lista de chaves de campo não-confirmadas
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## 4. Criptografia — `fiscal_cripto.py` (isolado, trocável)

```python
gerar_chave() -> str                 # Fernet.generate_key().decode() — utilitário (setup)
encrypt(texto: str) -> str           # ciphertext (str); '' / None -> None
decrypt(token: str | None) -> str|None   # texto plano; None -> None
token_definido(enc) -> bool          # True se há ciphertext não-vazio
```

- **Resolução da chave** (`_get_fernet()`): `os.environ["ORIZON_FISCAL_KEY"]` → senão lê `config/fiscal.key`
  → senão **gera** uma chave, grava em `config/fiscal.key` (chmod 600 best-effort no POSIX) e emite um
  `log`/`warning` "chave fiscal gerada". A chave é cacheada no processo.
- **Nunca loga texto plano** nem a chave. `decrypt` de token inválido/adulterado levanta (Fernet
  `InvalidToken`) — o chamador trata.
- `config/fiscal.key` vai para `.git/info/exclude` (ignore local, não ao `.gitignore` versionado).

## 5. Lógica pura — `mod_fiscal.py`

```python
REGIMES = {"simples","simples_excesso","normal","mei"}
PAPEIS  = {"central_produto","loja_servico","loja_produto_servico","avulso"}
AMBIENTES = {"homologacao","producao"}

def perfil_padrao_teste() -> dict:
    """Valores de teste p/ desbloquear (Simples, CFOP 5102/6102, CNAE placeholder, ISS 5%, homolog).
    Retorna {campos..., 'placeholders': [chaves dos campos defaultados]}."""

def validar_config(req: dict) -> (ok, erro):
    """regime_tributario ∈ REGIMES (se enviado); papel_cnpj ∈ PAPEIS; aliquota_iss numérica 0..100;
    ambiente não é editado aqui (endpoint próprio)."""

def pode_ativar_producao(placeholders: list) -> bool:
    """False se restar qualquer placeholder — bloqueia produção com dado de teste."""
```

`perfil_padrao_teste()` inclui em `placeholders` os campos com valor de teste: `regime_tributario`,
`csosn_padrao`, `cfop_dentro_uf`, `cfop_fora_uf`, `cnae_servico`, `aliquota_iss` (e `papel_cnpj` se
defaultado). O CNAE placeholder é um genérico de "instalação e montagem de móveis", **marcado** via
`placeholders`.

## 6. Endpoints (`main.py`) — gated por `editar_dados_loja` + tenancy

Preâmbulo comum: sessão (401), `_ator_dict` + `perfis.pode(nivel,"editar_dados_loja")` senão 403,
`mod_tenancy.pode_editar_dados_loja(ator, loja)` senão 403, loja existe senão 404.

- **`GET /api/admin/lojas/<id>/perfil-fiscal`** → `{ok, existe: bool, perfil: {...campos não-secretos...},
  placeholders: [...], ambiente_ativo, token_homolog_definido: bool, token_prod_definido: bool,
  cert_validade, cert_cnpj}`. Se não existe registro, devolve o **`perfil_padrao_teste()`** com
  `existe:false` (para a UI mostrar e o usuário salvar). **Nunca** devolve o valor dos tokens.
- **`PUT /api/admin/lojas/<id>/perfil-fiscal`** (JSON) → upsert dos campos **não-secretos** +
  `placeholders` (cliente gerencia quais campos seguem como placeholder). Valida via
  `mod_fiscal.validar_config`. **Não** toca em segredos nem em `ambiente_ativo`.
- **`PUT /api/admin/lojas/<id>/perfil-fiscal/segredos`** (JSON, write-only) → recebe
  `{focus_token_homolog?, focus_token_prod?}`, **cifra** (`fiscal_cripto.encrypt`) e grava as colunas
  `_enc`. Enviar `""`/omitir = não altera; enviar `null` explícito = limpar. Responde só `{ok}` — nunca
  ecoa o token.
- **`PUT /api/admin/lojas/<id>/perfil-fiscal/ambiente`** (JSON) → `{ambiente: "homologacao"|"producao"}`.
  Se `producao` e `mod_fiscal.pode_ativar_producao(placeholders)` for False → **400** "Não é possível
  ativar produção com valores de teste pendentes: <chaves>". Ação explícita e visível.

Erros de crypto/persistência → 500 com mensagem genérica (sem vazar segredo).

## 7. Fiação com a Fase 2 — `focus_client_para_loja` (em `mod_fiscal.py`)

```python
def focus_client_para_loja(db, loja_id) -> FocusClient:
    """Monta um FocusClient a partir do PerfilFiscal da loja: escolhe o token do ambiente_ativo,
    decripta, e usa base_url_de(ambiente). Levanta ValueError claro se não há token para o ambiente."""
```

Usa `focus_config.base_url_de` (Fase 2) e `focus_client.FocusClient` (Fase 2). É o ponto por onde a
Fase 4 emitirá de verdade, por loja — substituindo o `focus_config.json` global para uso real.

## 8. Segurança (requisitos obrigatórios)

- **Tokens Focus:** só cifrados no banco; **nunca** em GET, **nunca** em log, **nunca** no frontend.
- **Certificado A1:** não é armazenado por nós (vai pra Focus); guardamos só validade + CNPJ.
- **Chave Fernet:** fora do banco (env/keyfile), fora do git, fora de log.
- **Troca para produção:** ação explícita + bloqueada com placeholders pendentes (evita nota real com
  dado de teste). `ambiente_ativo` default `homologacao`.

## 9. Testes

- **`tests/test_fiscal_cripto.py`:** roundtrip `encrypt`/`decrypt`; ciphertext ≠ plaintext e muda entre
  chamadas (IV do Fernet); `decrypt` de token adulterado levanta; chave lida de `ORIZON_FISCAL_KEY`
  (monkeypatch env); `token_definido`.
- **`tests/test_mod_fiscal.py`:** `perfil_padrao_teste` traz os defaults + `placeholders` esperados;
  `validar_config` (regime/papel inválidos, iss fora de faixa); `pode_ativar_producao` (lista vazia→True,
  não-vazia→False).
- **`tests/test_perfil_fiscal_e2e.py`** (fixtures do conftest: `seed`/`app_db` module-scoped → resetar):
  - `GET` sem registro → `existe:false` + `perfil_padrao_teste` + flags de token `false`.
  - `PUT` salva config; `GET` reflete; `placeholders` persistidos.
  - `PUT /segredos` cifra: a **coluna `_enc` no banco não é o texto plano** e o GET **não** devolve o
    token; `token_homolog_definido` vira `true`.
  - `PUT /ambiente producao` com placeholders → **400**; após esvaziar placeholders (via PUT) → **200**.
  - **Tenancy/perm:** consultor (sem `editar_dados_loja`) → 403; usuário de outra loja → 403; não
    autenticado → 401.
  - `focus_client_para_loja`: com token de homologação definido → devolve `FocusClient` com base_url de
    homologação e token decriptado; sem token para o ambiente → `ValueError`.

Suíte verde (`python3 -m pytest -q`, baseline 470).

## 10. Fora de escopo (Sub-frente II / fases seguintes)

- **Painel no frontend** (7 blocos, badges "valor de teste — confirmar com contabilidade", modal de
  troca de ambiente) — **Sub-frente II**.
- **Mapa fiscal** (CST/CSOSN/CFOP/alíquotas por item a partir do PerfilFiscal) + `EmissorFocusNfe` +
  emissão real — Fase 3b/4.
- **NFS-e real** (só capturamos a config agora; emissão depende de 2º CNPJ + município integrado).
- **Upload do certificado** (fluxo operacional no painel da Focus, não no nosso sistema).
- **Migração de secrets manager/KMS** — "retomar depois" (a cripto é isolada para permitir isso).
