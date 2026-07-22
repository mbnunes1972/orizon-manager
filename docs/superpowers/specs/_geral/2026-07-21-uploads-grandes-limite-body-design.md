# Uploads grandes — teto de body + nginx em TODAS as versões (2026-07-21)

## Contexto (diagnóstico fechado em 2026-07-21)
O upload do `XML/ASuíte Master.xml` (6,3 MB) falha em produção com `Error: TypeError: Failed to
fetch`. O arquivo está **íntegro** — validado com o parser real (`integracoes/promob_grupos.
ler_xml_str`): projeto "Orçamento", R$ 65.278,02, 12 grupos; encoding/BOM idênticos aos XMLs
menores que carregam. A causa é o **nginx da produção sem `client_max_body_size`** (runbook do
`DEV_RULES.md`, passo 3): o default é **1 MB**, e TODOS os XMLs reais (2,4–6,7 MB) estouram — o
nginx corta a conexão com o browser ainda enviando o corpo, e o `fetch` reporta "Failed to fetch"
sem status. Do lado do app não há teto nenhum: o `do_POST` lê o body inteiro em memória (dívida já
anotada em `main.py` ~2849). Esta frente fecha o problema nas três camadas (infra, backend,
frontend) e nos **QUATRO ambientes**: local (WSL), dev teste (pré-homolog **A**, `:8765` em
`167.88.33.121`), teste pré-homolog (**B**, `:8766` no mesmo servidor) e produção
(`orizonsolution.com.br`, VPS `179.197.77.9`).

## Convenção de limites (decidida)
- **nginx: `client_max_body_size 64M`** (borda externa, folgada de propósito).
- **App: teto de 50 MB** no ponto único de leitura do body (constante, override por env
  `ORIZON_MAX_BODY_MB`). App < nginx **de propósito**: assim quem responde o erro amigável em JSON
  é sempre o app, nunca o reset seco do proxy. Maior arquivo real hoje: 6,7 MB — folga de ~7×.

## Parte 1 — Infra (fazer HOJE, junto do deploy da versão nova) — por ambiente
1. **Produção** (`ssh root@179.197.77.9`): em `/etc/nginx/sites-available/orizon`, adicionar
   `client_max_body_size 64M;` dentro de **CADA bloco `server { }`** — o certbot criou o de 443
   além do de 80; conferir os dois. Depois: `nginx -t && systemctl reload nginx`.
2. **Dev teste — pré-homolog A** (`167.88.33.121:8765`, env `/root/orizon-A.env`): verificar se há
   nginx/proxy na frente (por domínio ou porta); se houver, aplicar a MESMA linha no server block
   correspondente e recarregar. Se o acesso é direto na porta, nada de nginx a fazer — o teto do
   app cobre. `ORIZON_MAX_BODY_MB`, se for customizar, vai no env **desta** instância.
3. **Teste pré-homolog B** (`167.88.33.121:8766`, env `/root/orizon-B.env`): mesmo procedimento da
   A — são instâncias independentes no mesmo servidor; conferir e aplicar **nas duas**, cada uma
   com seu server block (se proxiada) e seu arquivo de env.
4. **Local (WSL, `./run.sh` → `:8765`)**: sem proxy — o teto do app cobre; nada de infra.
5. **Runbook**: editar o passo 3 do `DEV_RULES.md` acrescentando `client_max_body_size 64M;` no
   template do nginx, para o próximo provisionamento não repetir o buraco.

## Parte 2 — Backend (`main.py`), com TDD
- Teto no(s) ponto(s) únicos de leitura do body — HOJE são três, todos com o mesmo padrão
  `length = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(length)`:
  `do_POST` (~2819), o segundo leitor (~7370) e o `do_PUT` (~7809). Extrair um helper
  `_ler_body(self)` usado pelos três:
  - `Content-Length > teto` → **NÃO ler o body**; responder `413` JSON
    `{"ok": false, "erro": "Arquivo grande demais (máx. 50 MB)."}` e **fechar a conexão**
    (`Connection: close`) — sem drenar 100 MB pra memória só pra recusar.
  - `Content-Length` ausente/inválido → segue o comportamento atual (`b'{}'`).
  - Teto configurável: `ORIZON_MAX_BODY_MB` (default 50); validação no bootstrap no padrão de
    `porta_do_ambiente` (valor inválido = erro claro, não default silencioso).
- Isso quita a dívida anotada em ~2849 — **remover/atualizar aquele comentário**, apontando pro
  helper.
- **Testes** (`pytest`, antes de commitar): POST sob o teto passa intacto; POST acima do teto
  recebe 413 JSON sem o handler da rota ser tocado; env override respeitado; PUT idem. Suíte
  inteira verde (SQLite + `TEST_DATABASE_URL` se disponível).

## Parte 3 — Frontend (`static/index.html`)
- Tratamento amigável nos uploads `FormData` (pool `/pool`, sobrescrever, nova versão, PE
  `/pe/upload`, NF-e fábrica etapa 15, modelos de documento, e demais `fd.append` de arquivo):
  - resposta **413** → mensagem clara: "Arquivo grande demais (máx. 50 MB)".
  - **falha de rede** (fetch rejeitado — o atual "Failed to fetch") → "Falha de conexão ao enviar
    o arquivo. Verifique a internet e tente de novo; se persistir, o arquivo pode exceder o limite
    do servidor." — nunca mais vazar `Error: TypeError` cru pro usuário.
  - Centralizar num helper JS de upload (um `try/catch` + checagem de `r.status` num lugar só) em
    vez de repetir em cada chamada. Verificar sintaxe com `node --check` no `<script>` extraído.
- Frontend é lido do disco a cada request → validação manual com **Ctrl+F5**, sem restart.

## Parte 4 — Aceite e fechamento (nos QUATRO ambientes)
1. **Aceite real**: carregar `XML/ASuíte Master.xml` (6,3 MB) e `XML/ASUÍTE MASTER - EXECUTIVO.xml`
   (6,7 MB) num projeto de teste — devem subir e criar os ambientes no pool. Rodar em **produção**
   (após deploy + nginx) e nas **duas instâncias de pré-homolog** (A `:8765` e B `:8766`).
2. **Teto amigável**: testar um arquivo > 50 MB forjado (`dd if=/dev/zero`) → 413 com mensagem
   clara. No **local** (`./run.sh`, sem nginx) o 413 deve vir do app — é a prova de que o teto da
   aplicação funciona sozinho, sem proxy na frente.
3. Fechar no padrão do projeto: suíte verde → `DEV_LOG` (nova Sessão) → commit (`fix(uploads): …`)
   → push → re-ingerir o grafo MCP. O deploy de produção segue o runbook do `DEV_RULES.md`.

## Prompt sugerido (colar no Claude Code, na raiz do repo)
> Implemente a frente descrita em `docs/superpowers/specs/_geral/2026-07-21-uploads-grandes-limite-body-design.md`.
> Comece pela Parte 2 (backend, TDD) e depois a Parte 3 (frontend). A Parte 1 (nginx) é manual no
> VPS — me entregue os comandos prontos no final, junto com o checklist de aceite da Parte 4.
> Não mexa em nada além do caminho de leitura de body e dos handlers de upload do frontend.

## Fora do escopo desta frente
Streaming de upload pra disco (evitar body inteiro em memória) e limites por rota/tipo de arquivo —
registrar como dívida futura se o volume crescer; com teto de 50 MB o risco atual é aceitável.

## ✅ Implementado (2026-07-21, Sessão 104)
- **Parte 2**: `max_body_bytes()` + `Handler._ler_body()` no `main.py` — os TRÊS leitores eram
  `do_POST`/`do_PUT`/`do_PATCH` (a spec citava do_PUT 2×; o terceiro era o PATCH). 413 sem ler um
  byte (provado por teste de socket cru que envia só headers), `Connection: close`, mensagem com o
  teto dinâmico. Validação fail-fast no bootstrap (`main()`), dívida do importar de modelos quitada.
  Testes: `tests/test_max_body.py` (11).
- **Parte 3**: helper único `uploadFormData(url, fd)` no `index.html`, adotado nos 13 uploads
  FormData; 413 e falha de rede viram mensagem amigável. Bônus: os 3 uploads da medição não tinham
  try/catch nenhum (rejeição de fetch era unhandled) — agora cobertos pelo helper.
- **Parte 1**: runbook do `DEV_RULES.md` (Passo 3) com `client_max_body_size 64M` + alerta do 2º
  server block do certbot. **VPS A/B (167.88.33.121): SEM nginx** (conferido — serviço inativo,
  sem sites habilitados; acesso direto na porta) → teto do app cobre, nada de infra lá.
  **Produção pendente** (aplicar o 64M nos dois blocos server no próximo deploy de produção).
- **Parte 4 pendente de gente**: aceite manual com os XMLs reais de 6,3/6,7 MB nos ambientes.
