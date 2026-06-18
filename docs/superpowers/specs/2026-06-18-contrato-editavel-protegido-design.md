# Contrato editável protegido + edição pontual (Sub-projeto F2) — Design

**Data:** 2026-06-18
**Status:** proposto

## Problema / objetivo

Permitir **correção pontual** do contrato gerado: o usuário (gerente/diretor) abre o
`.docx` no Word ou LibreOffice e edita **apenas os valores de campo** (definidos por
marcadores) — todo o texto fixo (cláusulas, rótulos, layout) fica travado. Ao salvar, o
**PDF é regerado automaticamente**.

Decisões já acordadas com o usuário:
- **Todos os valores de marcador** ficam editáveis (cliente, endereços, consultor,
  testemunhas, entrada, total **e** os valores/datas da grade de parcelas).
- A **senha gerencial** trava a edição **no app** (botão "Editar" exige login
  gerencial, auditado) — reusa a autenticação que já existe. O `.docx` é protegido
  somente-leitura-exceto-campos **sem senha embutida** (evita o algoritmo de hash do
  Word, frágil). Risco aceito: quem já tem o arquivo pode clicar "Parar proteção".
- Botão "Editar" → escolhe Word/LibreOffice → abre o `.docx` → **watcher** regera o PDF
  ao salvar (mudança de mtime + liberação do lock `~$`).

## Mecânica da proteção (OOXML — validado em spike)

- `settings.xml`: `<w:documentProtection w:edit="readOnly" w:enforcement="1"/>` → tudo
  somente leitura.
- Cada **valor** preenchido é envolvido por uma região de exceção editável:
  `<w:permStart w:id="N" w:edGrp="everyone"/> … <w:permEnd w:id="N"/>` (inline, no
  parágrafo, ao redor do(s) run(s) do valor).
- Word e LibreOffice respeitam: só as regiões `everyone` são editáveis. A automação
  server-side (LibreOffice→PDF, assinatura) **lê** o arquivo normalmente (proteção só
  afeta edição interativa).

Spike confirmou: injeção de `documentProtection` + `permStart/permEnd` via lxml, arquivo
reabre válido.

## Arquitetura da solução

### 1. Geração com regiões editáveis (`mod_contrato.py`)

O contrato gerado passa a ser **protegido-editável por padrão** (a automação ignora a
proteção; correções pontuais persistem no `.docx` canônico `contrato_<id>.docx`).

Desafio: envolver **só o valor**, não os rótulos fixos. Hoje `_substituir_marcadores`
colapsa o parágrafo em `runs[0] = texto inteiro` (perde a fronteira rótulo/valor). Para
proteção por valor:

- Reimplementar o preenchimento por **segmentos**: ao substituir marcadores num
  parágrafo, dividir o texto em segmentos `fixo` / `valor` e criar **um run por
  segmento** (preservando a formatação do run original). Registrar os runs de `valor`.
- Para células de valor puro (capa T0–T3, grade): o run inteiro da célula é o valor.
- Para linhas mistas do corpo (`[NOME_CLIENTE] CPF/CNPJ: [CPF]`, consultor,
  `NOME: [TESTEMUNHA_...]`): cada valor vira seu próprio run.
- A grade (`_preencher_grade`) já escreve valores puros por célula → cada célula
  preenchida é um valor.

Após o preenchimento, uma função `_proteger_editaveis(doc, runs_valor)`:
- Insere `permStart`/`permEnd` (edGrp=everyone, ids sequenciais) ao redor de cada run de
  valor (e cada célula de grade preenchida).
- Adiciona `documentProtection edit=readOnly enforcement=1` em `doc.settings.element`.

`preencher_contrato(contrato_id, ctx, protegido=True)`:
- `protegido=True` (default no fluxo real): aplica `_proteger_editaveis`.
- `protegido=False`: comportamento atual (sem proteção) — usado por testes que só
  conferem conteúdo.

Coletar os runs de valor exige que `_substituir_marcadores`/`_preencher_grade` devolvam
as referências. Opção: as funções recebem um acumulador opcional
(`coletor: list = None`) e, quando fornecido, anexam os runs de valor criados. Quando
`None`, comportam-se como hoje (sem mudança para Tasks F1).

### 2. Endpoint "Editar" (`main.py`)

`POST /api/projetos/<nome>/contrato/editar`
- Body: `{ "app": "word"|"libreoffice", "login": "...", "senha": "..." }`.
- **Gate gerencial:** valida `login`/`senha` exigindo nível gerente/diretor (reusa a
  função de autorização gerencial existente — a mesma de reabrir etapas/`autorizar`).
  Registra em `log_acoes_gerenciais` (ação `editar_contrato`).
- Garante que `contrato_<id>.docx` existe e está protegido-editável (regera se preciso,
  a partir do estado atual; ver §1).
- **Abre o arquivo no app escolhido** (a app roda localmente na máquina do usuário —
  modelo desktop single-user):
  - Word: `os.startfile(path)` (abre no app padrão do `.docx`) ou, se `app=="word"`,
    localizar `winword.exe` e `subprocess.Popen([winword, path])`.
  - LibreOffice: `subprocess.Popen([soffice, path])` (reusar a descoberta de caminho do
    LibreOffice já usada para PDF).
- Dispara o **watcher** (§3) em background e responde imediatamente
  `{ ok: true, editando: true }`.

### 3. Watcher (regera PDF ao salvar)

Thread em background por sessão de edição:
- Registra `mtime` inicial do `.docx`.
- Poll a cada ~2 s:
  - Detecta salvamento: `mtime` aumentou **e** o lock sumiu — Word usa
    `~$contrato_<id>.docx`; LibreOffice usa `.~lock.contrato_<id>.docx#`. Considerar
    salvo quando o arquivo está sem lock e abrível em modo exclusivo.
  - Regera o PDF (`gerar_pdf_contrato`/LibreOffice) a partir do `.docx` editado e
    atualiza `contrato.pdf_path`/timestamp.
  - Registra no log e encerra a thread (uma regeração por sessão; ou repetir até timeout
    se o usuário salvar várias vezes — ver "Decisões abertas").
- **Timeout** (ex.: 30 min) para não vazar threads se o usuário nunca salvar/fechar.
- Robustez Windows: enquanto o Word está aberto, o arquivo fica bloqueado; regerar só
  após liberar. Em LibreOffice idem.

### 4. Frontend — botão "Editar" (`static/index.html`)

- Na etapa do contrato, botão "✎ Editar contrato".
- Abre um modal: **login + senha** (gerencial) + escolha **Word / LibreOffice**.
- `POST /api/projetos/<nome>/contrato/editar`. Mostra status:
  "Abrindo no <app>… ao salvar, o PDF será regerado."
- Feedback quando o watcher regerar o PDF (poll de status simples ou mensagem informando
  que pode levar alguns segundos após salvar/fechar).

## Fluxo

```
[Editar] → modal (login gerencial + app) → POST .../contrato/editar
  → valida nível gerencial (audita) → garante .docx protegido-editável
  → abre no Word/LibreOffice → watcher(mtime+lock)
  → usuário corrige só os campos → salva/fecha
  → watcher regera PDF → atualiza contrato.pdf_path
```

## Testes

**Unit (`tests/test_contrato.py`):**
- `_proteger_editaveis`: doc gerado com `protegido=True` tem `documentProtection
  edit=readOnly` e pelo menos um par `permStart/permEnd` por valor; `protegido=False` não
  tem nenhum.
- Conteúdo idêntico entre `protegido=True/False` (proteção não altera os valores).
- Os valores ficam **dentro** das regiões editáveis e os rótulos fixos **fora** (checar
  posição de `permStart`/`permEnd` relativa ao run do valor numa linha mista).

**Backend (endpoint):**
- `POST .../contrato/editar` sem nível gerencial → 403/erro; com nível gerencial → ok e
  registra `log_acoes_gerenciais`.
- App launch e watcher: testar a lógica de detecção de salvamento (mtime+lock) com um
  arquivo temporário simulado (sem abrir o Word de verdade); a abertura do app é
  isolada atrás de uma função injetável para não exigir GUI no teste.

**Verificação runtime (manual, honesta):**
- Gerar contrato → abrir o `.docx`: confirmar que o texto fixo não pode ser editado e os
  campos sim (Word **e** LibreOffice — verificação visual, pois é a única forma real).
- Editar um valor, salvar/fechar → confirmar que o PDF foi regerado com a correção.
- Conferir o registro em `log_acoes_gerenciais`.

> Nota honesta: o comportamento "só campos editáveis" só se confirma de verdade abrindo
> no Word/LibreOffice (interativo). Os testes automatizados cobrem a estrutura OOXML
> (documentProtection + permStart/permEnd nas posições certas) e a lógica do
> endpoint/watcher; a confirmação visual final é manual.

## Decisões abertas (para o review do spec)

1. **Quantas regerações por sessão:** uma (no primeiro salvar/fechar) ou repetir a cada
   salvamento até o timeout? Sugestão: repetir a cada salvamento, com debounce, até
   timeout/fechamento.
2. **Sempre protegido vs. cópia separada:** sugiro o `contrato_<id>.docx` canônico já
   protegido (correções persistem; automação ignora a proteção). Alternativa: gerar uma
   cópia `contrato_<id>_editavel.docx` só ao clicar "Editar".

## Fora de escopo
- Senha embutida no `.docx` (algoritmo de hash do Word) — descartado a favor do gate no
  app.
- Painel de configuração de loja (testemunhas dinâmicas) — futuro.

## Arquivos afetados
- `mod_contrato.py` — `_proteger_editaveis`, coletor de runs de valor em
  `_substituir_marcadores`/`_preencher_grade`, parâmetro `protegido` em
  `preencher_contrato`.
- `main.py` — endpoint `POST .../contrato/editar`, gate gerencial, launch do app, watcher.
- `static/index.html` — botão "Editar contrato" + modal (login gerencial + app).
- `tests/test_contrato.py` — testes de proteção/regiões; testes do watcher/endpoint.
