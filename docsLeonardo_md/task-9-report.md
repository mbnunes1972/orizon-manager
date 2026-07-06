# Task 9 Report — Motor de PDF (WeasyPrint)

## Status: CONCLUÍDO

Nota: este arquivo (`task-9-report.md`) já continha um relatório de uma feature não relacionada
("Modal de comissão de vendas") de outro plano/sessão. Foi sobrescrito por instrução explícita
da tarefa (path fixo em `.superpowers/sdd/task-9-report.md`). O plano real desta frente é
`docs/superpowers/plans/2026-07-02-contrato-html-pdf.md` (12 tasks, branch `feat/contrato-html-pdf`).

## O que foi feito

`gerar_pdf_contrato` em `mod_contrato.py` (antes: `docx → LibreOffice`, assinatura
`(contrato_id, variaveis)`) foi substituída pela versão que renderiza o HTML final
(`_montar_html_contrato`) via WeasyPrint. Nova assinatura:
`gerar_pdf_contrato(contrato_id: int, ctx: dict, destino: str = None) -> str`.

```python
def gerar_pdf_contrato(contrato_id: int, ctx: dict, destino: str = None) -> str:
    """Renderiza o contrato (HTML -> PDF) via WeasyPrint. Retorna o caminho do PDF."""
    from weasyprint import HTML
    destino = destino or CONTRATOS_DIR
    os.makedirs(destino, exist_ok=True)
    html = _montar_html_contrato(ctx)
    pdf_path = os.path.join(destino, f"contrato_{contrato_id}.pdf")
    HTML(string=html, base_url=CONTRATO_TEMPLATE_DIR).write_pdf(pdf_path)
    return pdf_path
```

Nenhuma outra função docx (`preencher_contrato`, `_converter_pdf`, `_libreoffice_cmd`,
`LibreOfficeIndisponivel`, etc.) foi tocada/removida — isso é escopo da Task 11.

## TDD

**RED** — teste adicionado a `tests/test_contrato_pdf.py` (smoke, `@skip_sem_weasy`, WeasyPrint
v69 instalado no ambiente → roda de verdade, não pula):

```
$ python3 -m pytest tests/test_contrato_pdf.py -k gerar_pdf_contrato -q
F
TypeError: gerar_pdf_contrato() got an unexpected keyword argument 'destino'
1 failed, 11 deselected in 0.22s
```

**GREEN** — após substituir o corpo da função:

```
$ python3 -m pytest tests/test_contrato_pdf.py -k gerar_pdf_contrato -q
.
1 passed, 11 deselected in 0.81s
```

Confirmação manual adicional (fora do pytest) do PDF real gerado: 25.239 bytes, header
`b'%PDF-'`, sem nenhuma linha em stderr (WeasyPrint não emitiu warnings — o corpo do contrato
está vazio nesta etapa porque `contrato_template/contrato.md` ainda não existe, Task 8; só a
capa renderiza, como esperado).

## Suíte completa

```
$ python3 -m pytest -q
FAILED tests/test_contrato.py::test_gerar_pdf_usa_modelo_e_chama_libreoffice
FAILED tests/test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura
2 failed, 399 passed, 633 warnings in 12.27s
```

Ambas as falhas são consequência **esperada e documentada no plano** desta substituição
(não são regressões introduzidas fora de escopo):

1. `test_contrato.py::test_gerar_pdf_usa_modelo_e_chama_libreoffice` — chama
   `gerar_pdf_contrato(contrato_id=99, variaveis=ctx)` (kwarg antigo `variaveis`, mocka
   `subprocess.run`/LibreOffice). Testa exatamente o comportamento docx que esta task troca.
   Remoção agendada explicitamente na **Task 11** ("Remover testes específicos de docx").
2. `test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura` — esperava
   `"aviso" in b` (degradação graciosa .docx quando `LibreOfficeIndisponivel`). Como o novo
   motor WeasyPrint não depende de LibreOffice, `main.py` (que ainda envolve a chamada em
   `try/except LibreOfficeIndisponivel`) não lança mais a exceção e gera o PDF direto — o
   ajuste desse teste/rota é objeto explícito da **Task 10** ("Integração da rota... remove
   o fallback LibreOffice").

O brief da própria Task 10 no plano confirma essa sequência: "Expected: PASS (com os testes
de docx ainda presentes vão falhar — serão removidos na Task 11...)". Por isso não toquei
`main.py`, `tests/test_contrato.py` nem `tests/test_fluxo_completo_e2e.py` — fora do escopo
explícito desta task (`git add` restrito a `mod_contrato.py tests/test_contrato_pdf.py`).

## Self-review

- [x] Gera PDF real (`%PDF-` confirmado duas vezes: teste + verificação manual).
- [x] Usa `base_url=CONTRATO_TEMPLATE_DIR` (resolve logo/CSS relativos do template).
- [x] Cria `destino` via `os.makedirs(destino, exist_ok=True)` se não existir.
- [x] Não removeu nenhuma outra função docx (`preencher_contrato` e cadeia seguem intactas).
- [x] YAGNI — implementação idêntica ao brief, sem extras.
- [x] Sem warnings do WeasyPrint no render (stderr vazio na chamada manual).
- [ ] Suíte 100% verde — NÃO, 2 falhas conhecidas/esperadas (detalhadas acima), a resolver
      nas Tasks 10 e 11 do próprio plano.

## Arquivos

- `/mnt/e/2026/estudo_de_ia/omie_v3/mod_contrato.py` (função `gerar_pdf_contrato`, linha ~1019)
- `/mnt/e/2026/estudo_de_ia/omie_v3/tests/test_contrato_pdf.py` (teste `test_gerar_pdf_contrato_gera_pdf`)

## Commit

```
1106b4f feat(contrato): motor de PDF via WeasyPrint (substitui docx->LibreOffice)
```//git add explícito: mod_contrato.py tests/test_contrato_pdf.py

## Concerns

- As 2 falhas remanescentes na suíte completa são esperadas e resolvidas pelas Tasks 10/11
  do mesmo plano (`docs/superpowers/plans/2026-07-02-contrato-html-pdf.md`); sinalizo para
  quem for orquestrar a próxima task não se assustar com o "FAILED" e seguir o plano.
- O corpo do contrato ainda está vazio no PDF (só capa) porque `contrato_template/contrato.md`
  não existe (Task 8 no plano, mas o `progress-contrato-html-pdf.md` já lista Task 8 como
  concluída — vale conferir se o `.md` já foi criado noutra branch/commit antes de investigar
  mais a fundo, caso o corpo vazio persista após a Task 8 estar de fato mergeada aqui).
- `task-9-report.md` sobrescreveu um relatório antigo de outra feature (não relacionado);
  mencionado no topo deste arquivo para rastreabilidade.
