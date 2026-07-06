# Task 10 — Report: Integração da rota + wire do texto complementar

## O que mudou na rota (`main.py`)

1. Import de `mod_contrato` (linha ~43-45): removido `LibreOfficeIndisponivel` (não usado em
   nenhum outro lugar de `main.py` — confirmado via `grep -n "LibreOfficeIndisponivel" main.py`,
   zero ocorrências após a mudança).
2. Handler `POST /api/projetos/<nome>/contrato` (~L3556-3565): trocado

   ```python
   aviso = None
   try:
       pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
       contrato.pdf_path = pdf_path
   except LibreOfficeIndisponivel as lo:
       contrato.pdf_path = lo.docx_path
       aviso = str(lo)
   ```

   por

   ```python
   aviso = None
   pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
   contrato.pdf_path = pdf_path
   ```

   `aviso` permanece declarado (usado mais abaixo em `if aviso: resp["aviso"] = aviso`) mas
   nunca mais é atribuído — fica sempre `None`, então a chave `"aviso"` nunca aparece na resposta.
   Isso é intencional e mínimo (YAGNI): remover a variável exigiria tocar o bloco de resposta,
   fora do escopo pedido pelo brief (Step 1).

3. **Achado durante a investigação**: a rota `PATCH /api/projetos/<nome>/contrato` (~L4145,
   editar/regenerar contrato) **já** chamava `gerar_pdf_contrato` diretamente, sem
   try/except de LibreOffice — aparentemente migrada em task anterior. Confirmado via
   `grep -n "preencher_contrato\|gerar_pdf_contrato\b" main.py`: as duas únicas chamadas em
   `main.py` são a da rota POST (ajustada aqui) e a do PATCH (já correta). Nenhuma rota em
   `main.py` chama `preencher_contrato` (docx) hoje. Não precisei tocar o PATCH.

4. Texto complementar: nenhuma mudança necessária. `variaveis["adendo"]` já é setado a partir de
   `req.get("adendo")` nas duas rotas, e `_montar_html_contrato` em `mod_contrato.py` já mapeia
   `mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""` (linha 875).

## O que ajustei no E2E (`tests/test_fluxo_completo_e2e.py`) e por quê

`test_contrato_real_geracao_e_assinatura` assumia o caminho antigo (docx + LibreOffice ausente):
esperava `"aviso" in b`, procurava `contrato_<id>.docx` em disco e abria com `python-docx` para
achar as seções "4. Ambientes"/"5. Forma de Pagamento", e tolerava o PATCH devolvendo 500 (docx
gerado mas conversão para PDF falhando sem LibreOffice).

Como agora a geração é sempre PDF direto (WeasyPrint, sem passar por .docx), reescrevi:

- `assert "aviso" not in b` (PDF sempre gerado — sem degradação).
- Verificação do arquivo: `contrato_<id>.pdf` existe em disco e começa com o header `%PDF-` (em
  vez de abrir tabelas do docx).
- **Guard de conteúdo (equivalente ao antigo, adaptado)**: como `gerar_pdf_contrato` não expõe o
  HTML intermediário, usei `monkeypatch` para espionar `main.gerar_pdf_contrato` e capturar o
  `ctx` passado em cada chamada (POST e PATCH); depois reconstruí o HTML com
  `mod_contrato._montar_html_contrato(ctx)` (a mesma função que a geração real usa) e afirmei que
  as seções "4. Ambientes do Projeto"/"5. Forma de Pagamento" e o nome do ambiente do cenário
  ("Cozinha") aparecem no HTML — preserva o guard de regressão da Task 4 (injeção de
  `_ambientes`) tanto na criação quanto na regeneração via PATCH, sem inventar parsing de PDF
  binário (WeasyPrint comprime os streams de texto; não há lib de extração de PDF no ambiente —
  `pdfplumber`/`pypdf`/`PyPDF2`/`fitz` não instalados — então validar via bytes crus do PDF não
  era viável). Usar `_montar_html_contrato` é o padrão já usado pelos testes unitários de
  `test_contrato_pdf.py`.
- PATCH agora espera sempre `st == 200` (antes tolerava 500 pela falha do LibreOffice).
- `arquivo_tipo` apertado para `== "pdf"` (antes `in ("docx", "pdf")`).
- Docstrings/comentários do módulo e do teste atualizados (mencionavam LibreOffice/`.docx` como
  limitação do ambiente — não é mais verdade; WeasyPrint não depende de LibreOffice).

Não toquei `test_fluxo_completo_inicio_ao_fim` além do comentário (ainda usa o hook
`main._registrar_provisao_venda` diretamente — escolha de design válida e fora do escopo desta
task; mantive por não ser exigido pelo brief).

## Comandos + saída

```
$ python3 -m pytest tests/test_fluxo_completo_e2e.py -q
..
2 passed, 53 warnings in 4.80s

$ python3 -m pytest -q
...
FAILED tests/test_contrato.py::test_gerar_pdf_usa_modelo_e_chama_libreoffice
1 failed, 403 passed, 647 warnings in 21.77s
```

A única falha é a pré-existente e planejada (`test_contrato.py::test_gerar_pdf_usa_modelo_e_chama_libreoffice`,
removida na Task 11). Nenhuma outra regressão.

## Arquivos alterados

- `/mnt/e/2026/estudo_de_ia/omie_v3/main.py`
- `/mnt/e/2026/estudo_de_ia/omie_v3/tests/test_fluxo_completo_e2e.py`

## Commit

`f3941a0` — `feat(contrato): rota gera PDF via novo motor; remove fallback LibreOffice`
(`git add main.py tests/test_fluxo_completo_e2e.py`, explícito, sem `-A`).

## Self-review

- Rota POST usa `gerar_pdf_contrato` direto, sem try/except de LibreOffice. ✅
- Import morto (`LibreOfficeIndisponivel`) removido; `grep` confirma zero ocorrências em `main.py`. ✅
- PATCH já estava correto (achado, não modificado). ✅
- E2E alvo (`test_contrato_real_geracao_e_assinatura`) verde. ✅
- Suíte inteira: só a falha pré-existente planejada. ✅
- YAGNI: não toquei `mod_contrato.py` (funções docx), nem a rota `/contrato/editar` (fora do
  escopo — Task 11). Não adicionei dependências novas (nada de lib de PDF parsing) — usei
  `_montar_html_contrato` (já existente) via spy de `monkeypatch`, que é o padrão de teste já
  usado no módulo (`test_contrato_pdf.py`).

## Concerns

- A variável `aviso` em `main.py` (rota POST) ficou "morta" (sempre `None`, nunca atribuída) —
  deixei porque `resp["aviso"]` downstream ainda a referencia condicionalmente; removê-la exigiria
  tocar código fora do escopo do Step 1 do brief. Dá para limpar como parte da Task 11 (quando o
  resto do fallback docx for removido) ou num cleanup separado.
- O guard de "seções injetadas" no E2E agora depende de reconstruir o HTML via
  `_montar_html_contrato(ctx)` capturado por spy, em vez de inspecionar o PDF final diretamente —
  é uma verificação um passo removida do artefato real (não abre o `.pdf` para conferir o texto
  renderizado). Dado que não há lib de extração de texto de PDF disponível no ambiente e a
  cobertura via `_montar_html_contrato` já é o padrão do módulo, julguei aceitável; sinalizando
  para revisão caso se prefira um teste mais "ponta a ponta" (exigiria adicionar uma dependência
  de parsing de PDF).
