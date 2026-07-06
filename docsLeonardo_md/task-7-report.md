# Task 7 — Capa e HTML final — Report

## O que foi feito

Implementadas em `mod_contrato.py` (inseridas logo após `_montar_mapping`, antes de `preencher_contrato`):

- `_html_capa(ctx) -> str`: monta as 5 seções da capa (identificação, endereço residencial,
  endereço de instalação, ambientes do projeto, forma de pagamento), com `#cabecalho`
  (logo + `[NUM_CONTRATO]`/`[DATA_CONTRATO]`), consumindo `_html_ambientes_linhas(ctx.get("_ambientes") or [])`
  e `_html_parcelas_linhas(ctx.get("_pag") or {})` para as linhas dinâmicas, e terminando com
  `<div class="quebra-capa"></div>`.
- `_carregar_md() -> str`: lê `contrato_template/contrato.md`; retorna `""` se o arquivo não existir
  (tolerante — o arquivo só será criado na Task 8).
- `_montar_html_contrato(ctx) -> str`: monta `mapping = _montar_mapping(ctx, pag)` com
  `pag = ctx.get("_pag", {})`, adiciona `mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""`,
  lê o shell `contrato_template/contrato.html`, injeta capa (`<!--CAPA-->`) e corpo (`<!--CORPO-->`,
  via `_html_corpo(_carregar_md())`), e resolve todos os `[MARCADORES]` com `_substituir_marcadores_html`.

Código idêntico ao do brief (Step 3), sem alterações.

## Ajuste no teste (conforme instrução)

O teste do brief continha a linha:
```python
assert "Acordo especial de entrega." in html     # TEXTO_COMPLEMENTAR
```
Essa linha foi **removida** do teste em `tests/test_contrato_pdf.py`, pois `[TEXTO_COMPLEMENTAR]` só
existirá em `contrato.md` (corpo), criado na Task 8. Nesta etapa `_carregar_md()` retorna `""`, o corpo
fica vazio e não há marcador `[TEXTO_COMPLEMENTAR]` no HTML para ser substituído — a asserção falharia
sem relação com um bug real.

Mantido conforme instrução: `ctx["adendo"] = "Acordo especial de entrega."` no setup do teste (inofensivo,
só não é mais verificado nesta task) e a linha `mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""`
na implementação (a fiação correta será exercida pelo teste da Task 8).

## TDD — RED

Teste `test_montar_html_contrato_substitui_e_inclui_secoes` adicionado ao final de
`tests/test_contrato_pdf.py`.

```
$ python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q
F
ImportError: cannot import name '_montar_html_contrato' from 'mod_contrato'
1 failed, 10 deselected in 0.22s
```

## TDD — GREEN

Após implementar `_html_capa`, `_carregar_md` e `_montar_html_contrato`:

```
$ python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q
.
1 passed, 10 deselected in 0.20s
```

## Suíte completa

```
$ python3 -m pytest -q
400 passed, 647 warnings in 12.85s
```
(Warnings são `DeprecationWarning` de `datetime.utcnow()` pré-existentes em outros módulos, sem relação
com esta task.)

## Commit

```
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): montagem da capa HTML + HTML final com marcadores"
```
SHA: `18dfc33` — 2 files changed, 128 insertions(+).

## Arquivos alterados

- `/mnt/e/2026/estudo_de_ia/omie_v3/mod_contrato.py` (+3 funções: `_html_capa`, `_carregar_md`,
  `_montar_html_contrato`)
- `/mnt/e/2026/estudo_de_ia/omie_v3/tests/test_contrato_pdf.py` (+1 teste, ajustado sem a linha
  de TEXTO_COMPLEMENTAR)

## Self-review

- Capa com as 5 seções (identificação, endereço residencial, endereço de instalação, ambientes,
  forma de pagamento) + `#cabecalho` + `<div class="quebra-capa"></div>` no final: OK.
- Ambientes (`_html_ambientes_linhas`) e parcelas (`_html_parcelas_linhas`) injetados nas seções 4 e 5: OK.
- Marcadores da capa (`[NOME_CLIENTE]`, `[CPF]`, endereços, `[TOTAL_CONTRATO]`, `[NUM_PARCELAS]`,
  `[TIPO]` etc.) todos resolvidos por `_substituir_marcadores_html` com o mapping de `_montar_mapping`:
  verificado pelo teste (`html.split("contrato-corpo")[0]` sem `[` remanescente / `NOME_` ausente).
- `_carregar_md` tolera ausência de `contrato.md` (checagem `os.path.exists`) — não lança exceção.
- YAGNI: nenhuma função extra além das 3 pedidas; código igual ao brief, sem adornos.
- Teste verifica comportamento real: usa `construir_contexto` real (não mocka `_montar_mapping`),
  confere strings de negócio (nome do cliente, bairro, valor de ambiente formatado, valor de parcela).
- Saída pristina: nenhum arquivo temporário criado pela implementação; suíte completa 400/400 passou
  sem falhas nem erros novos.

## Concerns

- `contrato_template/contrato.md` ainda não existe (esperado — será criado na Task 8). Até lá, o corpo
  do contrato fica vazio no HTML final; isso é intencional e documentado no brief/instrução desta task.
- `TEXTO_COMPLEMENTAR` está fiado corretamente no mapping, mas seu efeito real só será visível/testável
  quando `contrato.md` contiver o marcador `[TEXTO_COMPLEMENTAR]` (Task 8) — não há verificação end-to-end
  disso ainda, por design.
- O arquivo `task-7-report.md` foi encontrado com conteúdo de uma task antiga não relacionada
  (`parametros_default_loja`), possivelmente de numeração de sprint reaproveitada; foi sobrescrito
  com este relatório.
