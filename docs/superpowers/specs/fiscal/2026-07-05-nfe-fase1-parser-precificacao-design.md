# NF-e Fábrica → Loja · Fase 1 — Parser + Precificação (`mod_nfe.py`) — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (Sessão 47)** — branch `feat/nfe-fase1`, `mod_nfe.py` com testes + CLI,
> conferido nos 5 XMLs reais via CLI (ex.: NFe-170942 → linhas=21 distintos=12). Primeira das fases da
> integração NF-e. **Nota p/ Fase 3:** `custo_total`/`venda_total` somam o `custo_unit`/`preco_venda_unit`
> **já arredondados** (2 casas) — pode divergir do total fiscal por centavos; reconciliar na Fase 3 se
> for comparar com o total da NF-e.

## 1. Contexto (a integração completa) e o recorte desta fase

**Triangulação fiscal dos planejados.** A fábrica (Dal Mobile) emite NF-e de saída com todos os
componentes de um pedido e entrega direto ao cliente final. A loja precisa emitir **sua própria NF-e
de venda** para o mesmo cliente, com **markup** sobre o custo de fábrica. O motor fiscal do Omie
recalcula ICMS/IPI/PIS/COFINS do zero (CNPJs/regimes diferentes) — **não** se reaproveita imposto da
fábrica. Saída **item a item** (não "kit"), para reconciliação limpa de estoque no SPED.

A frente foi **decomposta em fases**, cada uma com seu spec→plano→implementação. **[Atualizado 2026-07-05
— guinada de arquitetura]** o motor fiscal deixou de ser o **Omie** e passou a ser a **Focus NFe** (API
REST direta; a Focus **não** calcula imposto — nós fornecemos o bloco fiscal). O parser/precificação
desta fase é **engine-agnostic** e permanece válido; muda apenas a camada final de emissão.

1. **Parser + Precificação (esta spec):** ler o XML da NF-e da fábrica → extrair/consolidar itens →
   classificar padrão/sob-medida → custo (`vUnCom + IPI proporcional`) → **markup** → estrutura de
   *preview*. **Puro, offline, sem emissor/SEFAZ — risco fiscal zero.**
2. **`EmissorFiscal`** (interface) + **cliente HTTP Focus NFe** (Basic-auth token, homolog/prod, POST
   `/nfe?ref`, GET status, cancelar; retry; assíncrono). Infra isolada, testável com mock + homologação.
3. **Mapa fiscal loja → payload NF-e:** dos itens precificados + config fiscal da loja (regime →
   CST/CSOSN, CFOP, alíquotas) monta o `items[]` da Focus. Parametrizado por regime (Simples agora;
   lucro real/presumido depois). O "coração" da guinada — testável offline antes de transmitir.
4. **Emissão real em homologação:** `emitir_nfe_produto`, polling de status, guarda do XML/DANFE
   retornados; cancelar/consultar.
5. **UI da etapa 15** (upload do XML da fábrica, preview, disparo/status).

Cross-cutting: modelo Rede→Loja(CNPJ)→config fiscal + perfil de emissão; NFS-e com interface pronta e
implementação adiada (2º CNPJ + municípios integrados na Focus).

Esta spec cobre **apenas a Fase 1**. Ela produz a estrutura de dados que as fases seguintes consomem.

## 2. Evidência (5 NF-es reais analisadas)

`nfe-dalmobile/NFe-*.xml` (fora do git). Confirmado em 149 linhas / 95 produtos distintos:

- **Formato:** `nfeProc versao="3.10"`, namespace `http://www.portalfiscal.inf.br/nfe` (o parser
  precisa ser namespace-aware; há caso `nfeProc` e pode haver `NFe` puro).
- **`cProd = BASE[ID]`** (ex.: `50079[2131748]`). `BASE` = produto paramétrico da fábrica; `[ID]` =
  peça cortada, único e irrepetível. **Sem colchete = item padrão** (ferragens: corrediças,
  dobradiças, puxadores) — ex.: `80070`.
- **Linhas duplicadas** na mesma NF-e (mesmo `cProd`, mesmo preço, várias linhas qtd 1) →
  **consolidáveis por soma** de `qCom`. Chave = `cProd` completo. (Itens de mesma `BASE` mas `[ID]`
  diferente **não** consolidam.)
- **IPI por item** (`vIPI`/`IPITrib` presentes em 100% dos itens das 5 amostras; todas CRT3).
- **`infAdProd` é NÃO-CONFIÁVEL:** deveria ser `COR LARGURA ALTURA` (ex.: `EBANO 622 600`), mas há
  muitos casos só-cor (`MDF BP BRANCO`), cor+1-número (`FOSCO 2420`), número solto (`970`) ou ausente
  (justamente os itens padrão). → o parser **carrega o raw sempre** e parseia dimensões **best-effort**,
  **nunca falha** por causa dele.

**Nota fiscal (para as fases seguintes):** as amostras (2016) são **CRT3 com IPI**, não Simples/CSOSN101.
A Fase 1 é agnóstica a regime (custo = `vUnCom + IPI`, e `IPI=0` cobre o caso Simples). Confirmar, antes
da Fase 3/4, se as NF-es **atuais** da fábrica ainda trazem IPI.

## 3. Decisões (brainstorming)

- **Markup:** **percentual único global** (parâmetro/config). `preco_venda = custo × (1 + pct/100)`.
- **Base do markup:** custo por unidade = `(vProd + vIPI) / qCom` **após consolidação** (equivale a
  `vUnCom + IPI_proporcional`). **Nunca** sobre `vProd` puro.
- **`infAdProd`:** tolerante — dimensões só quando os 2 últimos tokens são numéricos; caso contrário
  `None`; raw sempre preservado.
- **Entrega:** módulo puro `mod_nfe.py` + suíte pytest (fixtures **anonimizados**) + **CLI de eyeball**
  (`python3 mod_nfe.py <arquivo.xml> [markup_pct]`) que imprime a tabela precificada + totais. **Sem
  endpoint HTTP / UI nesta fase** (isso é a Fase 5).
- **Sem dependências novas:** `xml.etree.ElementTree` (padrão do projeto, como `promob_grupos.py`).
  Módulo puro: **sem** rede, **sem** SQLAlchemy.

## 4. Módulo `mod_nfe.py` — interface

Funções pequenas, testáveis isoladamente:

- **`parse_nfe(xml)`** → `dict`. `xml` = `str` ou `bytes`. Namespace-aware (localiza `infNFe`
  independentemente do wrapper). Retorna:
  ```python
  {
    "cabecalho": {"nNF","serie","dhEmi","natOp",
                  "emit": {"cnpj","nome","crt"},
                  "dest": {"nome","doc"}},          # doc = CNPJ ou CPF do destinatário
    "itens": [ {"nItem","cProd","xProd","ncm","cfop","uCom",
                "qCom": float, "vUnCom": float, "vProd": float,
                "vIPI": float,                        # 0.0 se ausente
                "infAdProd": str|None} , ... ]        # raw
  }
  ```
- **`split_cprod(cprod)`** → `(base, id_peca, tipo)`. Regex `^(.+?)\[([^\]]+)\]$`: com colchete →
  `(base, id_peca, "sob_medida")`; sem colchete → `(cprod, None, "padrao")`.
- **`parse_infadprod(texto)`** → `{"cor","largura","altura"}` ou `None`. Só quando há ≥3 tokens e os
  **2 últimos** são inteiros; `cor` = tokens restantes unidos; `largura/altura` = int. Senão `None`.
- **`consolidar(itens)`** → lista consolidada. Agrupa por `cProd` (preservando a 1ª ocorrência para os
  campos estáticos: xProd, ncm, cfop, uCom, vUnCom, infAdProd); **soma** `qCom`, `vProd`, `vIPI`.
- **`precificar(itens_consolidados, markup_pct)`** → itens precificados. Para cada item:
  `custo_unit = (vProd + vIPI) / qCom`; `preco_venda_unit = round(custo_unit * (1 + markup_pct/100), 2)`.
  Anexa `base`, `id_peca`, `tipo` (via `split_cprod`) e `dim` (via `parse_infadprod`).
- **`preview(xml, markup_pct)`** → estrutura de handoff (parse → consolida → precifica):
  ```python
  {
    "cabecalho": {...},                 # de parse_nfe
    "markup_pct": float,
    "itens": [ {"cProd","base","id_peca","tipo","xProd","ncm","cfop","uCom",
                "qCom","vUnCom","vProd","vIPI",
                "custo_unit","preco_venda_unit",
                "cor","largura","altura",           # None se infAdProd não parseou
                "infAdProd"} , ... ],
    "totais": {"n_linhas","n_distintos","n_padrao","n_sob_medida",
               "custo_total": round(Σ custo_unit*qCom, 2),
               "venda_total": round(Σ preco_venda_unit*qCom, 2)}
  }
  ```
  `n_linhas` = itens antes de consolidar; `n_distintos` = depois.

**CLI:** `if __name__ == "__main__":` lê o arquivo do `argv[1]`, `markup_pct` do `argv[2]` (default
constante `MARKUP_TESTE_PADRAO = 30.0`, documentada como valor de teste), chama `preview` e imprime uma
tabela legível (cProd, tipo, xProd curto, qCom, custo_unit, preco_venda_unit) + os totais. Uso só para
conferência manual offline; não faz parte de nenhum fluxo de produção.

## 5. Testes (`tests/test_nfe.py`)

Fixtures **anonimizados** em `tests/fixtures/nfe/` — XMLs pequenos derivados da estrutura real, **sem
CNPJ/CPF/endereço reais** (emit/dest fictícios), cobrindo os casos:

- `nfe_basica.xml`: 2 itens sob-medida + 1 linha duplicada (mesmo cProd) + 1 item padrão (sem colchete);
  `infAdProd` no formato `COR L A` num item e ausente no padrão.
- `nfe_infadprod_variado.xml`: casos só-cor, cor+1-número, número-solto, ausente.
- `nfe_sem_ipi.xml`: item com `IPI` sem `vIPI` (caso Simples) → `vIPI=0.0`.

Casos de teste:

1. **`parse_nfe`** extrai cabeçalho (nNF, emit CNPJ/CRT, dest) e os campos de cada `<det>`, com
   namespace; `vIPI` ausente → `0.0`.
2. **`split_cprod`**: `50079[2131748]` → `("50079","2131748","sob_medida")`; `80070` →
   `("80070", None, "padrao")`.
3. **`parse_infadprod`**: `"EBANO 622 600"` → `{cor:"EBANO",largura:622,altura:600}`;
   `"METROPOLITAN 2406 185"` idem; `"MDF BP BRANCO"` → `None`; `"FOSCO 2420"` → `None`; `"970"` → `None`;
   `None`/`""` → `None`.
4. **`consolidar`**: 2 linhas idênticas (cProd X, qCom 1 cada, vProd/vIPI iguais) → 1 item com `qCom=2`,
   `vProd`/`vIPI` somados; 2 itens de mesma BASE mas `[ID]` diferente permanecem separados.
5. **`precificar`**: custo_unit = `(vProd+vIPI)/qCom`; markup 30% → `preco_venda_unit` correto e
   arredondado a 2 casas; item sem IPI → custo = vUnCom.
6. **`preview`**: totais coerentes (`n_linhas` > `n_distintos` quando há duplicata; `n_padrao +
   n_sob_medida == n_distintos`; `custo_total`/`venda_total` batendo com a soma manual do fixture).
7. **Robustez**: `infAdProd` fora do padrão não quebra o `preview` (item entra com `dim=None`).

Suíte deve seguir verde (`python3 -m pytest -q`).

## 6. Fora de escopo (Fases seguintes / YAGNI)

- Qualquer chamada a emissor fiscal (interface `EmissorFiscal`, cliente Focus NFe, payload/impostos,
  emissão/consulta/cancelamento) — Fases 2-4.
- UI / endpoint HTTP / upload na etapa 15 — Fase 5.
- Persistência do preview no banco / vínculo com projeto — Fase 5 (nesta fase o preview é só retorno de
  função / saída do CLI).
- Markup por grupo/categoria, mapa fiscal (CST/CSOSN/CFOP/alíquotas por regime), config fiscal por loja —
  decisões das Fases 2+.
- Parsing "confiável" de dimensões do `infAdProd` — permanece best-effort; validação em amostra maior
  fica para quando/se a dimensão virar requisito (Fase 2+).
