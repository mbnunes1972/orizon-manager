# Auditoria Florence — Domínio Financeiro / Negociação (Orizon Manager / Dalmóbile)

**Escopo:** `mod_negociacao.py`, `mod_provisoes.py`, `mod_fin/*`, `mod_orcamento_params.py`,
`mod_margens.py`, `mod_medicao.py`, `_ler_aymore.py`, `tabelas_financeiras/*`.
**Ótica:** produção enterprise-grade; dinheiro errado = crítico.
**Método:** leitura integral + execução de sondas (probes) com evidência reproduzível.
**Data:** 2026-07-03. **Status do escopo:** READ-ONLY (nenhum código/banco alterado).

Convenção de severidade: 🔴 Crítico / 🟠 Alto / 🟡 Médio / 🔵 Baixo / ℹ️ Info.

---

## Sumário executivo

O núcleo de cálculo (`mod_negociacao`, Aymoré, Cartão) é coerente, testado com âncoras reais
(LELEU) e satisfaz o invariante "loja recebe exatamente `valor_avista`". Porém há **um defeito
crítico de integridade** em Total Flex (retorna `ok:True` com parcela impossível e total ao
cliente errado), **uso sistemático de `float` para dinheiro** (risco de centavos em produção),
**duas modalidades financeiras sem nenhum teste** (`total_flex`, `venda_programada`) e
**validações de negócio declaradas nas tabelas mas não aplicadas no código** (passo de carência
Aymoré). Detalhes abaixo.

---

## 🔴 Críticos

### F-01 🔴 `total_flex.calcular` retorna `ok:True` com última parcela NEGATIVA e total ao cliente incorreto

**Evidência** — `mod_fin/total_flex.py:237-258` (o dict de retorno tem `"ok": True` fixo) e
`:232` (`total_cli = round(ent + total_parc, 2)` soma cegamente parcelas, inclusive a última
negativa). O `recalcular` interno detecta o problema (`mod_fin/total_flex.py:154-157` devolve
`ok=False`/`ultima_negativa`), mas o wrapper `calcular` **descarta** esse `ok` e nunca o propaga.

Sonda reproduzível:
```
tf.calcular(10000, 0, 3, 0, '2026-06-01', valores_parcelas=[9000, 9000])
# -> ok=True | valor_ultima=-7931.52 | valor_negociado(total_cliente)=10068.48
```
O consultor digitou parcelas que excedem o saldo; a última "fecha" com **−R$ 7.931,52** (parcela
negativa, financeiramente impossível) e o `total_cliente` some para R$ 10.068,48 — abaixo até do
próprio somatório real de caixa.

**Impacto:** contrato/negociação pode ser gravado como válido com plano de pagamento impossível;
o "Valor Total do Contrato" apresentado ao cliente fica errado. Dinheiro incorreto persistido =
crítico. O caminho é atingível pelo endpoint `/calcular_total_flex` (`main.py:1620-1632`), que
repassa `valores_parcelas` do request sem revalidar.

**Recomendação:** propagar o estado de erro do `recalcular`:
`"ok": res["ok"] and not (res.get("ultima_negativa"))`, expor `avisos`/`erros` já existentes e
**recusar** persistência quando `ultima_negativa`. Adicionar teste de regressão (ver F-08).

---

### F-02 🔴 Dinheiro representado em `float` em todo o domínio (sem `Decimal`)

**Evidência** — todos os módulos operam em `float` com `round(...,2)` pontual:
`mod_fin/base.py:20-24` (`pmt`), `mod_fin/aymore.py:91-95`, `mod_fin/cartao.py:72-76`,
`mod_negociacao.py:31-93`, `mod_provisoes.py:122-133`. Nenhum uso de `decimal.Decimal`.

Sonda: `provisoes_orcamento({"CFO":0.1,"Val_Liq":0.3,...})` → `Cust_Var=0.1` correto **porque**
há `round`, mas a arquitetura depende de `round` defensivo em cada ponto; qualquer soma
intermediária não-arredondada acumula erro (ex.: `total_via`/`total_bri` em `mod_negociacao.py:66-67`
somam floats crus antes do `round` final da linha 88-89).

**Impacto:** em sistema real de vendas, divergências de centavo entre "soma das parcelas" e
"valor do contrato", e entre as **duas** fórmulas de `Cust_Var` (motor vs `cust_var_marg_cont`),
podem aparecer. É o achado clássico "dinheiro em float". Severidade crítica pela natureza do
domínio, ainda que hoje mascarada pelos `round`.

**Recomendação:** padronizar dinheiro em `Decimal` (quantize a 2 casas, `ROUND_HALF_UP`) nas
fronteiras de cálculo, ou — se `float` for mantido por pragmatismo — documentar formalmente o
contrato de arredondamento e adicionar testes de invariância de centavos (soma de parcelas ==
total; `Cust_Var` motor == `Cust_Var` recalculado) para bloquear regressões.

---

## 🟠 Altos

### F-03 🟠 Modalidades `total_flex` e `venda_programada` SEM nenhum teste automatizado

**Evidência** — não existem `tests/test_total_flex.py` nem `tests/test_venda_programada.py`
(Glob vazio). A única menção a `total_flex` em testes (`tests/test_orcamento_negociacao.py:19-30`)
verifica **apenas persistência de JSON**, não o cálculo. `venda_programada` não é exercitada em
lugar nenhum. Ambas têm lógica não-trivial: juros compostos por dias reais, fechamento da última
parcela, resíduo de centavos, validação de prazo (395d / 12 meses).

**Impacto:** justamente o módulo com o defeito F-01 (crítico) não tem rede de segurança. Regras
financeiras sem teste = achado por definição no estilo Florence.

**Recomendação:** criar suítes cobrindo: soma das parcelas == financiado (VP), última fecha
saldo (TF), resíduo aplicado na última (VP), `excede_prazo`, entrada, e o caso negativo de F-01.

### F-04 🟠 Passo de carência Aymoré (múltiplos de 5) declarado na tabela mas NÃO validado

**Evidência** — `tabelas_financeiras/aymore.json:10` (`"carencia_step_dias": 5`) e a docstring
`mod_fin/aymore.py:54` ("15 a 120, **múltiplos de 5**"). O código só valida faixa
(`mod_fin/aymore.py:70-71`), nunca o passo.

Sonda: `ay.calcular(100000, 0, 8, 17, '2026-06-01')` → `ok=True`, `carencia_dias=17`.

**Impacto:** aceita carência não homologada pela operadora (ex.: 17, 23 dias). A taxa de retenção
é interpolada pela fórmula de carência (`aymore.py:85`), gerando um custo financeiro que não
corresponde à tabela real do Santander/Aymoré → **valor liberado/parcela divergente do que a
operadora efetivamente pagará**. O endpoint `/calcular_aymore` (`main.py:1548`) usa default 30
mas não impede valores arbitrários vindos do request.

**Recomendação:** validar `carencia % carencia_step == 0` (lendo `carencia_step_dias` da tabela),
retornando `ok:False` caso contrário. Aplicar o mesmo rigor de faixa já existente.

### F-05 🟠 Duas fórmulas de `Cust_Var` mantidas em paralelo — divergência silenciosa possível

**Evidência** — `mod_provisoes.py:89-97` (comentário explícito de risco), `:106-112`
(`cust_var_marg_cont` = CFO + Σ itens) vs `:115-133` (`provisoes_orcamento` = CFO + out_forn +
8 rubricas % + Prov_Imp). São matematicamente equivalentes **apenas se** o mapa `_RUBRICAS` e a
lista de addendos ficarem sincronizados manualmente. O próprio código admite: "senão as duas
fórmulas de Cust_Var divergem silenciosamente".

**Impacto:** margem de contribuição (`Marg_Cont`) — indicador de decisão de venda — pode divergir
entre a tela de negociação e a de provisões editadas ao adicionar/remover uma rubrica.

**Recomendação:** derivar **uma** fonte da outra (ex.: `provisoes_orcamento` retorna os itens e
`cust_var_marg_cont` soma exatamente esse dict) ou adicionar teste que compare os dois caminhos
com o mesmo insumo e falhe em qualquer divergência > 0,01.

---

## 🟡 Médios

### F-06 🟡 `resolver_comissao_venda`: limite de faixa é exclusivo (`< venda_ate`) sem teste de fronteira

**Evidência** — `mod_provisoes.py:73-78`: `if ate is None or _f(val_liq_mes) < _f(ate)`.
Sonda: faixas `[10000→1%, 30000→2%, None→3%]`, `val=10000.0` → **2%** (cai na faixa seguinte);
`val=9999.99` → 1%. Ou seja, "venda até 10.000" **exclui** exatamente 10.000,00.

**Impacto:** ambiguidade de negócio no valor exato do limite (comum em vendas "redondas"). Nenhum
teste cobre a fronteira (`tests/test_provisoes.py:45-49` testa 5000/20000/50000, longe das bordas).
Pode gerar comissão 1 ponto percentual errada em vendas de valor cheio.

**Recomendação:** confirmar a semântica com o negócio (`<` vs `<=`) e adicionar teste de fronteira
explícito documentando a decisão.

### F-07 🟡 `parse_data` mascara data inválida usando "hoje" — datas de parcela silenciosamente erradas

**Evidência** — `mod_fin/base.py:27-32`: qualquer string inválida vira `datetime.today()` sem
erro. Usada para `data_contrato` e para cada data de parcela em VP/TF
(`venda_programada.py:62`, `total_flex.py:129,141`).

**Impacto:** um `data_contrato` malformado (ou `datas_parcelas` corrompido) produz um cronograma
de vencimentos plausível porém errado, sem sinalizar. Em VP a validação de prazo limite passa a
ser medida contra "hoje", não contra a data real do contrato.

**Recomendação:** nas fronteiras de request, validar e rejeitar data inválida (`ok:False`) em vez
de degradar para hoje; manter o fallback só para uso interno controlado.

### F-08 🟡 `sanear_descontos` lança `ValueError` não tratado em chave/valor não-numérico

**Evidência** — `mod_orcamento_params.py:96,99`: `int(pid)` / `float(pct)` sem try.
Sonda: `sanear_descontos({'abc':10}, {1,2})` → `ValueError: invalid literal for int()`.

**Impacto:** entrada malformada do frontend derruba o handler com exceção não classificada (500)
em vez de um 400 com mensagem — inconsistente com o restante do módulo, que valida faixa 0..100
de forma amigável (`:100-101`).

**Recomendação:** capturar coerção inválida e reportar erro de validação estruturado.

### F-09 🟡 Taxas/coeficientes financeiros hardcoded como fallback divergem se a tabela mudar

**Evidência** — `mod_fin/aymore.py:25-32` (`_TAXAS_FALLBACK`, 24 entradas) e
`mod_fin/cartao.py:24-30` (`_FAIXAS_FALLBACK`, 21 entradas) duplicam os números do JSON. Hoje
coincidem (verificado: fallback n=1 = 0.043891 = JSON), mas qualquer atualização de tabela do
Santander/Itaú precisa ser feita em **dois** lugares.

**Impacto:** risco de a operadora atualizar a tabela e o fallback (usado quando o JSON some/falha
ao carregar) aplicar taxa antiga → custo financeiro errado sem aviso.

**Recomendação:** tratar ausência de tabela como erro operacional explícito (falhar alto) em vez
de silenciosamente usar números embutidos; ou gerar o fallback a partir de um único snapshot
versionado com data de vigência.

### F-10 🟡 `venda_programada`: resíduo de centavos concentrado só na ÚLTIMA parcela, sem teto

**Evidência** — `mod_fin/venda_programada.py:58,82`: `ajuste_ultimo = financiado - parcela*n`
somado apenas à última. Sonda (1000/3x): `[333.33, 333.33, 333.34]` — ok para 3. Mas para muitas
parcelas o resíduo é sempre despejado na última; não há verificação de que ele permanece na casa
dos centavos (não há invariante testado).

**Impacto:** baixo em valores normais, mas sem teste garantindo `|ajuste_ultimo| < 0.01*n`. Aceitável,
porém não verificado — some ao esforço de F-03.

**Recomendação:** distribuir o resíduo (spread de centavos) ou ao menos testar o invariante de soma.

---

## 🔵 Baixos

### F-11 🔵 `total_flex.calcular` recebe `taxa_mensal_pct` e a ignora (parâmetro morto/enganoso)

**Evidência** — `mod_fin/total_flex.py:166,169` ("taxa do request ignorada") e o endpoint
`main.py:1627` passa `taxa_mensal_pct=0`. Assinatura sugere que o chamador controla a taxa, mas
ela vem sempre do `config/total_flex.json`.

**Impacto:** confusão de manutenção; um chamador futuro pode crer que está setando a taxa.
**Recomendação:** remover o parâmetro morto ou renomear para `_taxa_mensal_pct_ignorado` com
docstring inequívoca.

### F-12 🔵 Duplicação de `pmt` e de normalização de faixas em três lugares

**Evidência** — `pmt` em `mod_fin/base.py:20`, `mod_margens.py:9`; normalização de faixas em
`mod_fin/__init__.py:27-71` **e** `mod_margens.py:15-54` (com um ramo `parcelado_proprio` e uma
taxa flex hardcoded `2.0` no fallback, `mod_margens.py:51`, que não existe no caminho principal).

**Impacto:** lógica financeira duplicada com pequenas divergências (o fallback de `mod_margens`
usa `taxa_juros_mensal_pct` e 2.0 default; o principal usa `custo_pct=0`). Manutenção divergente.
**Recomendação:** consolidar em `mod_fin` como fonte única; `mod_margens._normalizar_faixas` já
delega — remover o fallback inline redundante.

### F-13 🔵 `carregar_json` / `_carregar` duplicados entre `mod_fin/base.py` e `mod_fin/__init__.py`

**Evidência** — `mod_fin/base.py:11-17` e `mod_fin/__init__.py:13-19` implementam o mesmo leitor
com caminhos-base calculados de formas diferentes (`dirname(dirname(__file__))` vs `__file__+".."`).
**Impacto:** manutenção; se a estrutura de pastas mudar, um pode quebrar e o outro não.
**Recomendação:** unificar em `base.carregar_json`.

### F-14 🔵 `_juros` (Total Flex) aceita `dias` negativo (data anterior à referência) → juros negativo

**Evidência** — `mod_fin/total_flex.py:30-32`: `dias = (dt - ref).days` sem piso em 0. Em
`recalcular` há validação de ordem crescente (`:142-143`), mas `calcular` monta o input antes; e o
`_parcela` calcula juros mesmo assim.
**Impacto:** baixo (a validação de ordem normalmente barra), mas o cálculo de juros não é
defensivo isoladamente. **Recomendação:** `dias = max(0, (dt-ref).days)` dentro de `_juros`.

---

## ℹ️ Informativos / observações positivas

- **INF-1** Invariante central "loja recebe exatamente `valor_avista`" está testado e passa para
  Aymoré e Cartão em varredura de n×carência (`tests/test_aymore.py:62-69`,
  `tests/test_cartao.py:52-58`). Bom.
- **INF-2** `mod_negociacao` tem âncora numérica real (LELEU) com waterfall por ambiente e
  fechamento de soma (`tests/test_negociacao.py:13-127`). Cobertura sólida do motor.
- **INF-3** Guardas de divisão por zero presentes nos pontos-chave: `pmt` (`base.py:22`),
  `desc_tot`/`markup` (`mod_negociacao.py:79-80`), `marg_cont` (`mod_provisoes.py:111,133`),
  `fator_com>0`/`fator_desc>0` (`mod_negociacao.py:52-53`). Bom.
- **INF-4** `_ler_aymore.py` é script utilitário de inspeção de planilha (não roda em produção,
  usa caminhos relativos e `openpyxl`); fora do caminho crítico. Sem achado, mas convém movê-lo
  para `scripts/` ou `tools/` para não confundir com módulo de runtime.
- **INF-5** `mod_medicao.validar_parecer` é completo e correto para seu escopo mínimo
  (`mod_medicao.py:7-15`); sem stubs.

**Varredura de incompletude:** nenhum `pass`, `NotImplementedError`, `TODO`/`FIXME` ou `raise`
não intencional encontrado nos módulos do escopo — não há stubs. Os `return {"ok": False,...}`
são caminhos de validação legítimos, não código faltante. (Exceção conceitual: F-01, onde o
caminho de erro existe mas **não é propagado**.)

---

## Placar por severidade

| Severidade   | Qtde | IDs |
|--------------|------|-----|
| 🔴 Crítico   | 2    | F-01, F-02 |
| 🟠 Alto      | 3    | F-03, F-04, F-05 |
| 🟡 Médio     | 5    | F-06, F-07, F-08, F-09, F-10 |
| 🔵 Baixo     | 4    | F-11, F-12, F-13, F-14 |
| ℹ️ Info      | 5    | INF-1 .. INF-5 |
| **Total**    | **14 achados + 5 notas** | |

**Prioridade de correção sugerida:** F-01 (integridade de dado financeiro) → F-03 (rede de teste
que teria pego F-01) → F-04 (taxa fora da tabela homologada) → F-02 (dívida arquitetural de
`float`) → F-05.
