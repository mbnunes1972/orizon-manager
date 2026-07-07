# Auditoria do módulo Fiscal (NF-e / NFS-e) — 2026-07-07

> **⏱ Atualização 2026-07-07 — 🔴 Altos corrigidos** (branch `feat/fiscal-altos-auditoria`, suíte 641):
> **A1** — chave Fernet + segredos agora no `.gitignore` versionado. **A2/A3/A5** — `mod_fiscal.prontidao_emitente`
> barra com 400 claro: NF-e de produto fora do Simples, UF do emitente vazia (+ normalização do CFOP), e NFS-e sem
> IM/IBGE/cód-serviço/alíquota. **A4** — NFS-e usa ref por tentativa (`NFSE-<projeto>-<n>`); rejeitada/cancelada
> libera nova emissão; a UI reexibe a form com o motivo anterior.
>
> **⏱ Atualização 2026-07-07 — 🟠 Médios corrigidos** (branch `feat/fiscal-medios-auditoria`, suíte 648):
> **A6** — config da rede (segredos/ambiente/perfil-emissão/perfil-fiscal) passa a exigir `pode_editar_dados_rede`
> (edição + escopo), não o predicado de leitura. **A7** — `cancelar_nfse` valida a justificativa (15-255) no backend.
> **A9** — `emitir` persiste a autorização **antes** de baixar XML/DANFE (falha na baixa não perde a nota; `consultar`
> rebaixa). **A10** — RET da NFS-e por regime (MEI=5, ME/EPP=6). **A11** — backfill de IBGE alinha cidade/UF à mesma
> fonte (ViaCEP). **A8** (idempotência) fica mitigado: NFS-e resolvida por A4; produto recuperável por novo upload
> (novo `doc_id` → novo ref) e a prontidão A2/A5 evita o caso comum (dado faltante) antes de gerar rejeição.
> **Restam só 🟡 Baixos:** A12 (unicidade do PerfilEmissao), A13 (2º clique → 500), A14 (NFS-e não conclui a etapa 15).


> Auditoria **adversarial** (4 frentes independentes, só leitura) do módulo fiscal. Objetivo: achar furos reais
> antes de produção. Companheiro de `2026-07-07-revisao-por-frente.md`.
> **Veredito geral:** o **isolamento multi-tenant e o tratamento de segredos estão sólidos** (sem furo
> cross-tenant explorável; token cifrado, write-only, cert nunca guardado, produção bloqueada por padrão).
> Os riscos reais estão em **(a) uma chave de cripto protegida só localmente**, **(b) um beco-sem-saída quando a
> NFS-e é rejeitada**, e **(c) hardcodes fiscais que podem gerar nota autorizada porém errada** para cenários
> fora do "Simples + venda interna". Nada disso quebra o caminho feliz já provado (2 emissões reais autorizadas).

## Achados priorizados

| # | Severidade | Achado | Tipo |
|---|---|---|---|
| A1 | 🔴 Alto | Chave Fernet (`config/fiscal.key`) protegida só por `.git/info/exclude` (local) | Segurança |
| A2 | 🔴 Alto | PIS/COFINS CST "49" fixo p/ qualquer regime → **nota errada silenciosa** (não-Simples) | Correção fiscal |
| A3 | 🔴 Alto | UF do emitente vazia → CFOP 6102 (interestadual) em venda interna → **nota errada silenciosa** | Correção fiscal |
| A4 | 🔴 Alto | NFS-e rejeitada **trava a etapa** (ref fixo + dedup Focus + UI sem re-emissão) | Bug de produto |
| A5 | 🟠 Médio | Dados fiscais ausentes (IM, alíquota ISS, IBGE) → recusa/erro genérico, sem 400 claro | Robustez |
| A6 | 🟠 Médio | Endpoints de config da **rede** gated por leitura (`pode_ver_rede`), não por edição | Segurança |
| A7 | 🟠 Médio | `cancelar_nfse` sem validar justificativa (15-255) no backend (só a UI valida) | Robustez |
| A8 | 🟠 Médio | Idempotência incompleta: status ≠ autorizado reenvia a **mesma ref** → rejeição em cache | Ciclo de vida |
| A9 | 🟠 Médio | Não-atomicidade: falha ao baixar XML após autorizar desfaz o registro de uma nota **real** | Ciclo de vida |
| A10 | 🟠 Médio | RET="6" fixo (quebra MEI); origem ICMS "0" fixa; natureza="1" fixa | Correção fiscal |
| A11 | 🟠 Médio | Inconsistência CEP↔cadastro: IBGE do ViaCEP vs cidade/UF digitados à mão | Correção fiscal |
| A12 | 🟡 Baixo | `PerfilEmissao` sem `UniqueConstraint(owner_tipo, owner_id, tipo_doc)` → ambiguidade | Integridade |
| A13 | 🟡 Baixo | 2º clique em "Emitir" simultâneo → 500 (IntegrityError) em vez de resposta idempotente | Robustez |
| A14 | 🟡 Baixo | NFS-e autorizada **não** conclui a etapa 15 (só a NF-e produto marca "emitida") | Consistência |

---

## Detalhe

### 🔴 A1 — Chave Fernet protegida só localmente *(CORRIGIDO nesta sessão — pendente commit do `.gitignore`)*
`config/fiscal.key` (a chave que decripta **todos** os tokens Focus) **não** estava no `.gitignore` versionado —
só no `.git/info/exclude`, que é **local e não vai para clones/VPS**. Como `config/` já é rastreado, um
`git add config/` (ou `git add .`) numa outra máquina estagiaria a chave. **Correção aplicada:** adicionadas as
regras `config/fiscal.key`, `*.key`, `focus_config.json`, `nfe_amostras/` ao `.gitignore`. Falta **commitar**
(o CLAUDE.md pede não commitar `.gitignore`; esta é uma exceção de segurança intencional — pedir OK).

### 🔴 A2 — PIS/COFINS CST "49" fixo para qualquer regime *(nota errada silenciosa)*
`mapa_fiscal.py:7-8,70-71,105-106` — `PIS_CST="49"`/`COFINS_CST="49"` são constantes aplicadas **sempre**, sem
ramificar por `regime_tributario`. O próprio TODO (linhas 66-67) admite. O Emitente **aceita** cadastro Lucro
Real/Presumido (`REGIME_FOCUS["normal"]=3`), e nesse caso a NF-e sairia com CST de PIS/COFINS do Simples — a
SEFAZ **autoriza** (CST 49 é aceito), gerando nota fiscalmente incorreta **sem erro**. **Recomendação:** ramificar
PIS/COFINS + CSOSN/ICMS por regime, **ou bloquear** emissão (400) quando `regime ∉ {simples, mei}` até existir a lógica.

### 🔴 A3 — UF do emitente vazia → CFOP interestadual em operação interna *(nota errada silenciosa)*
`mapa_fiscal.py:86-87` — `dentro = emit["uf"] == dest["uf"]`. Se a UF do emitente for `None`/""/`"sp"`/`"SP "`, a
comparação falha e cai em `cfop_fora` (6102, interestadual) para uma operação **interna** (5102). A SEFAZ autoriza
o 6102 → nota com CFOP errado, silenciosamente. **Recomendação:** normalizar (`.strip().upper()`) e **bloquear**
a emissão se a UF do emitente estiver vazia.

### 🔴 A4 — NFS-e rejeitada trava a etapa (beco-sem-saída) *(bug de produto)*
Combinação de três fatos: (1) ref fixo por projeto `NFSE-<projeto>` (`main.py:4404`); (2) `emitir` só faz
short-circuit em `autorizado` (`nfe_emissao.py:80`) — em `erro` reenvia a **mesma ref**, que a Focus devolve do
cache (RPS rejeitado é "morto"); (3) o GET popula `g["nfse"]` com **qualquer** documento de serviço, sem filtrar
status (`main.py:1497-1508`), e a UI só mostra a form "Emitir NFS-e" quando `nfse` é `null` (`static/index.html:8941`).
Resultado: **a 1ª NFS-e rejeitada tranca a tela** — o usuário só vê "Consultar", nunca consegue emitir a correta.
(A NF-e produto escapa porque o ref inclui o `doc_id` da fábrica → novo XML = novo ref.) **Recomendação:** liberar
a re-emissão quando `status ∈ {erro, cancelado}` (backend + form) e/ou tornar o ref recuperável (`NFSE-<projeto>-<n>`).

### 🟠 A5 — Dados fiscais ausentes viram payload com `None` (sem 400 claro)
`resolver_emitente` não verifica prontidão fiscal; `montar_payload*` propaga `None` de IM, alíquota ISS, IBGE do
prestador, UF. O endpoint `emitir-nfse` (`main.py:4384-4409`) não valida nada disso → a prefeitura/SEFAZ recusa e o
usuário recebe um genérico "Falha na emissão" (`4418-4419`), não uma mensagem dizendo **qual** campo falta.
**Recomendação:** um validador de "prontidão do Emitente" (IE p/ produto; IM+IBGE+alíquota+cód. serviço p/ serviço)
que retorne **400 específico** antes de chamar a Focus. *(Já existe o bom exemplo da IE do contribuinte, `main.py:4322`.)*

### 🟠 A6 — Config da rede gated por leitura, não por edição
PUT de segredos, ambiente (virar produção) e perfil-emissão **da rede** usam `pode_ver_rede` (`main.py:4653,4721,4752`),
um predicado de **leitura**, enquanto os equivalentes de **loja** usam `pode_editar_dados_loja`. Na prática só
super_admin/admin_rede passam (papéis elevados), mas a assimetria significa que um `admin_rede` só-leitura poderia
**gravar tokens** e **virar produção**. **Recomendação:** exigir capability de edição nesses PUTs de rede.

### 🟠 A7 — `cancelar_nfse` sem validar justificativa no backend
`focus_client.py:65-68` valida 15-255 chars para NF-e; `cancelar_nfse` (`:77-79`) **não** valida — só a UI o faz
(`static/index.html:9030`). Cliente que fure a UI manda justificativa curta e o comportamento fica a cargo da
prefeitura. **Recomendação:** replicar a validação 15-255 em `cancelar_nfse`.

### 🟠 A8 / A9 — Idempotência e atomicidade
- **A8:** re-emissão sobre registro em `erro` reenvia a mesma ref → Focus devolve a rejeição em cache; para a
  NF-e produto é mitigado pelo ref por-doc, para a NFS-e é o A4.
- **A9:** `nfe_emissao.py:104-108` marca `autorizado` → baixa XML/DANFE pela rede → `commit`. Se a baixa falhar, a
  exceção sobe **antes** do commit e o endpoint faz `rollback` — desfazendo o registro de uma nota **que já foi
  autorizada de verdade**. É auto-recuperável via `consultar` (que rebaixa os docs, `:120-123`), mas frágil.
  **Recomendação:** commitar a autorização **antes** de baixar os binários (duas transações).

### 🟠 A10 / A11 — Hardcodes e consistência de dados
- RET="6" (ME/EPP) fixo quebra **MEI** (seria 5); origem ICMS "0" (nacional) fixa erra produto **importado**;
  `natureza_operacao="1"` e `finalidade_emissao=1` fixos erram operação fora do município / devolução. Todos
  **autorizam** com enquadramento errado. São defaults conscientes p/ o caso atual (INSPIRIUM ME/EPP, Simples),
  mas viram dívida no momento em que houver outro perfil.
- A11: o backfill grava o IBGE do ViaCEP mas o payload segue mandando **cidade/UF digitados à mão** — se
  divergirem, tomador com município inconsistente. **Recomendação:** ao resolver o IBGE, validar/atualizar cidade+UF.

### 🟡 A12 / A13 / A14 — Integridade e robustez
- A12: `PerfilEmissao` sem `UniqueConstraint(owner_tipo, owner_id, tipo_doc)` → se duplicar (migração/insert manual),
  qual emitente "vence" é indeterminado. **Recomendação:** adicionar a constraint + `order_by` defensivo no resolver.
- A13: 2º clique simultâneo em "Emitir" colide no `UNIQUE(ref)` → 500. Não cria nota dupla (bom), mas devolve erro.
  **Recomendação:** capturar `IntegrityError` e responder com o registro existente (idempotente).
- A14: a NFS-e autorizada **não** marca a etapa 15 como "emitida" (só a NF-e produto o faz). Confirmar se é
  intencional; se não, é inconsistência.

---

## O que está sólido (verificado, não precisa mexer)
- **Segredos:** token **write-only** (GET nunca devolve o valor); Fernet correto; chave some → falha limpa
  (`InvalidToken`), não vaza plaintext; token nunca em log/erro/URL; **certificado A1 nunca guardado**; sem token no git.
- **Produção:** dupla trava — `permitir_producao=True` **não existe em nenhuma rota** + `pode_ativar_producao`
  recusa virar produção com placeholders. Produção é inalcançável por acidente.
- **Isolamento multi-tenant:** emissão sempre resolve loja/emitente do **ator** (nunca id do cliente); consultar/
  cancelar exigem que o `ref`/documento pertença ao **projeto da URL** e à **loja do usuário** (teste
  `test_consultar_cancelar_cross_tenant_via_ref_404`); header de loja ativa validado contra membership.
- **Multi-CNPJ:** precedência override loja → default rede → self correta; emissão sob CNPJ da central da rede
  provada (`test_emitir_produto_sob_emitente_central_da_rede`).
- **Carimbo de homologação** restrito a NF-e produto em homologação; **guarda de IE do contribuinte** com 400 claro;
  **só-dígitos** em CPF/CNPJ/CEP; **`_ibge_por_cep` offline-safe**; `consumidor_final`/indicador IE corretos.

---

## Plano de remediação sugerido (priorizado)
1. **A1** — commitar o `.gitignore` (fechar o vazamento da chave em clones/VPS). *(feito no working tree)*
2. **A4** — destravar re-emissão de NFS-e rejeitada (bug de produto que impede uso real).
3. **A2 + A3 + A5** — "prontidão fiscal": validar regime/UF/IE/IM/alíquota/IBGE e **bloquear com 400 claro** o que
   hoje gera nota errada silenciosa ou recusa genérica. (Frente fiscal focada, TDD.)
4. **A7 + A13 + A9** — endurecer backend (justificativa NFS-e; 2º clique idempotente; atomicidade da baixa).
5. **A6 + A12 + A14** — segurança de config da rede; constraint do PerfilEmissao; concluir etapa na NFS-e.
6. **A10 + A11** — refino de hardcodes (MEI/origem/natureza) e consistência CEP↔IBGE — quando surgir 2º perfil de emitente.

> Sugestão de agrupar em US: **US-40 (segurança: .gitignore + config rede)**, **US-41 (NFS-e re-emissão)**,
> **US-42 (prontidão fiscal + regime/UF/CFOP)**, **US-43 (robustez do ciclo: justificativa/idempotência/atomicidade)**.
