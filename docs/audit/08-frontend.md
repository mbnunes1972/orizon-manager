# Auditoria de Frontend — Orizon Manager / Dalmóbile

**Escopo:** `static/index.html` (9.195 linhas, 500 KB — HTML+CSS+JS inline, sem build/framework) e `static/login.html`.
**Data:** 2026-07-03
**Estilo:** Florence (rigoroso, enterprise-grade, com evidências)
**Natureza:** READ-ONLY. Software de **produção**.

---

## Sumário executivo

O frontend inteiro do sistema é **um único arquivo de 9.195 linhas** contendo CSS (linhas 8–376), marcação HTML (377–1.827) e **um bloco `<script>` monolítico de ~7.723 linhas** (1.828–9.551). São **345 funções de topo** e **293 handlers de evento inline** (`onclick=`, `oninput=`, etc.) num escopo global único, com **dezenas de variáveis globais mutáveis** (`_orcAmbientesAtivos`, `_negBaseValues`, `_previewNeg`, `_planoPagamento` em `window`, `_impostosLiberados`, ...). Não há módulos, nem separação de camadas, nem sistema de testes de frontend.

Pontos positivos: existe uma função de escape (`esc`, linha 1.829) usada de forma **razoavelmente** consistente no conteúdo de texto; a maioria dos `fetch` está em `try/catch`; autenticação e verificação de senha de gerente são feitas no servidor; nenhum uso de `eval`/`new Function`/`document.write`.

Pontos de maior risco: (1) `esc()` **não escapa aspas**, e há dados do usuário interpolados dentro de strings JS em atributos `onclick` → **XSS armazenado / quebra de handler**; (2) dados de perfil do usuário (telefone, WhatsApp, e-mail, **foto**) persistidos **apenas em `localStorage`**, violando a regra do projeto de persistência no backend; (3) **nenhum** `fetch` tem timeout/`AbortController`; (4) autorizações sensíveis (liberação de taxa/desconto/impostos) vivem **só em flags de cliente**, contornáveis via devtools; (5) insustentabilidade arquitetural do arquivo único.

---

## Achados

### F-01 — `esc()` não escapa aspas → XSS armazenado / quebra de handler em `onclick`
**Severidade:** 🔴 Crítico

**Evidência:**
- `static/index.html:1829`
  ```js
  const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  ```
  A função escapa apenas `& < >` — **não** escapa `"` nem `'`.
- `static/index.html:2869` (dropdown de busca de clientes, dados vindos de `/api/clientes`):
  ```js
  `<div onclick="npSelecionarCliente(${c.id},'${esc(c.nome)}','${esc(c.cpf||'')}','${esc(c.email||'')}','${esc(c.telefone||c.whatsapp||'')}')" ...>`
  ```
- `static/index.html:2389`:
  ```js
  onclick="projStatusSet('${esc(p.nome_safe||'')}','${s}')"
  ```
- Também em `static/index.html:2990`, `3005`, `6359` (`npSelecionarParceiro(...,'${esc(p.nome)}',...)`).

**Impacto:** Um nome de cliente/parceiro/projeto contendo aspa simples (caso legítimo comum: `O'Brien`, `D'Ávila`) **quebra o handler** e o registro fica inclicável. Pior: um nome malicioso como `',alert(document.cookie),'` ou `');<payload>//` injeta código no contexto do atributo `onclick`, resultando em **XSS armazenado** (o dado veio do banco via `/api/clientes` e é renderizado sem escape de contexto JS). Como o app confia em cookie de sessão, isso permite ações em nome do usuário logado.

**Recomendação:** Estender `esc()` para escapar `"`→`&quot;` e `'`→`&#39;`; **melhor ainda**, abandonar handlers inline com dados interpolados: usar `addEventListener` com `dataset`/closures, ou construir elementos com `textContent`/`createElement`. Onde for necessário passar objeto ao handler, usar o padrão já presente na linha 5.976 (`JSON.stringify(c).replace(/"/g,'&quot;')`) — mas de forma sistemática.

---

### F-02 — Dados de perfil do usuário persistidos só em `localStorage` (viola regra de persistência no backend)
**Severidade:** 🟠 Alto

**Evidência:**
- `static/index.html:2112` `mpSalvarPerfil()` grava telefone/WhatsApp/e-mail **somente** em `localStorage`, sem nenhum `fetch` de backend:
  ```js
  saved.telefone = tel; saved.whatsapp = wpp; saved.email = eml;
  localStorage.setItem(key, JSON.stringify(saved));   // linha 2121
  ```
- `static/index.html:2098` `mpTrocarFoto()` grava a **foto do usuário** (data URL base64) em `localStorage` (`saved.foto = e.target.result`, linha 2106).
- Leitura em `_carregarDadosExtrasUsuario()` (`static/index.html:2059`), chave `omie_user_extras_<id>`.

**Impacto:** Contradiz diretamente a regra permanente do projeto ("todo dado/documento do projeto persistido no banco/disco, nunca só no navegador"). Esses dados **se perdem** ao limpar o navegador, e **não aparecem** em outro dispositivo/navegador. A foto base64 também **estoura a cota** de `localStorage` (~5 MB) facilmente. Como o `localStorage` é por-origem e não por-usuário do SO, num computador compartilhado da loja um usuário pode **ver os dados de perfil de outro**.

**Recomendação:** Persistir telefone/WhatsApp/e-mail/foto via endpoint do backend (associado ao usuário autenticado); usar `localStorage` no máximo como cache de leitura, nunca como fonte de verdade.

---

### F-03 — Insustentabilidade arquitetural: arquivo único de 9.195 linhas, escopo global
**Severidade:** 🟠 Alto

**Evidência:**
- Um único `<script>` de ~7.723 linhas (`static/index.html:1828`–`9551`).
- **345** funções de topo e **293** handlers inline (`onclick/oninput/...`) — contagens via Grep.
- Dezenas de globais mutáveis declaradas em `let`/`window` (`static/index.html:1833`–`4389`): `_negBaseValues`, `_negSelLocal`, `_descIndividual`, `_orcAmbientesAtivos`, `_orcamentoAtivoId`, `window._planoPagamento` (linha 3.292), `_impostosLiberados`, `_tfTaxaLiberada`, etc.
- Interceptador global que **sobrescreve `window.fetch`** (`static/index.html:1836`) para injetar `X-Loja-Ativa`.

**Impacto:** Manutenção de altíssimo risco: qualquer nome de função/variável colide no mesmo escopo; impossível testar unidades isoladas; um erro de sintaxe em qualquer ponto quebra **todo** o app; revisão de código e diffs ficam ilegíveis; onboarding lento. O monkey-patch de `window.fetch` é global e silencioso (engole erros — `catch(e){}` na linha 1.845), dificultando depuração.

**Recomendação:** Plano de modularização incremental: extrair o `<script>` para arquivos `.js` versionados (ES modules), quebrar por domínio (clientes, orçamento, negociação, pagamento, admin), reduzir globais encapsulando estado em objetos/módulos. Introduzir ao menos verificação de sintaxe no CI (`node --check`) e, idealmente, testes de unidade para a lógica pura de UI.

---

### F-04 — Nenhum `fetch` tem timeout / `AbortController`
**Severidade:** 🟠 Alto

**Evidência:**
- Grep por `AbortController|AbortSignal|signal:|timeout` no arquivo: **0 ocorrências**.
- 118 chamadas `fetch`/XHR no total; exemplos sem timeout: `static/index.html:3795` (`/calcular_aymore`), `2856` (`/api/clientes`), `5701` (`negociacao-preview`).
- Dependências de rede externa também sem timeout: `static/index.html:6021` e `9401` (`https://viacep.com.br/...`).

**Impacto:** Se o backend ou o ViaCEP travarem (sem responder), a Promise fica **pendente indefinidamente**. Handlers com `btn.disabled = true` + spinner (padrão do `login.html:185`) podem deixar a UI **presa** sem recuperação. Em rede móvel/instável (uso via Termius/celular documentado no projeto), isso degrada muito a experiência.

**Recomendação:** Criar um wrapper `fetchComTimeout(url, opts, ms)` usando `AbortController` e um teto (ex.: 15–30 s), reutilizado em todo o app; garantir `finally` que reabilita botões e limpa spinners.

---

### F-05 — Autorizações sensíveis mantidas apenas em flags de cliente (contornável)
**Severidade:** 🟠 Alto

**Evidência:**
- `static/index.html:4234` — `let _impostosLiberados = false; // não persistido: recarregar re-bloqueia`.
- `static/index.html:4350` `_tfTaxaLiberada = true` e `static/index.html:4366`–`4367`:
  ```js
  _descBloqueioRemovido = true;
  document.getElementById('neg-desconto').removeAttribute('max');
  ```
  Após verificação de senha de gerente, o **limite de desconto é liberado apenas removendo o atributo `max`** do input e setando flags de cliente.

**Impacto:** A verificação de senha em si é server-side (`/api/gerente/verificar`, linha 4.339) — bom. Porém a **consequência** (liberar taxa de juros, remover limite de desconto, liberar impostos) fica só no cliente. Qualquer usuário pode, via devtools, setar `_descBloqueioRemovido = true` / remover o `max` / `_impostosLiberados = true` e **burlar os limites de perfil** sem senha de gerente. Se o backend **não revalidar** os limites no `salvar`, isso é uma falha de controle de negócio (descontos/margens fora de política).

**Recomendação:** Confirmar e garantir que o backend **reaplica** todos os limites de desconto/taxa e o gate de impostos no momento de salvar (server-authoritative). O frontend deve ser apenas conveniência visual; nunca a fronteira de autorização.

---

### F-06 — Erros de rede tratam o payload JSON, mas não o status HTTP; risco em respostas não-JSON
**Severidade:** 🟡 Médio

**Evidência:**
- Padrão recorrente: verifica-se `d.ok` (campo do JSON), não `r.ok` (status HTTP). Ex.: `static/index.html:3801`–`3803`:
  ```js
  d = await r.json();
  } catch(e) { console.error('[AYMORE]', e); return; }
  if (!d.ok) { console.warn('[AYMORE]', d.erro); return; }
  ```
- Grep por `.ok/.status`: 110 ocorrências, mas quase sempre referindo-se ao campo do payload (`d.ok`/`sv.ok`), raramente ao `Response.ok`.

**Impacto:** Se o backend devolver **HTTP 500/502/404 com corpo não-JSON** (página de erro, proxy, timeout do servidor web), `r.json()` lança e cai no `catch` que apenas dá `return` silencioso (ou `console.error`) — o usuário **não recebe feedback** e a operação "some" sem explicação. Em vários pontos o `catch` não exibe nada ao usuário.

**Recomendação:** Checar `if(!r.ok)` explicitamente e exibir mensagem de erro consistente (toast). Padronizar um helper de request que já trata status, parse e feedback de erro.

---

### F-07 — POSTs sem proteção CSRF (auth por cookie de sessão)
**Severidade:** 🟡 Médio

**Evidência:**
- `login.html:190`–`200`: login via `/api/auth/login`; usuário salvo em `sessionStorage` — a sessão real é presumivelmente cookie (não há `Authorization: Bearer` em nenhum request; Grep por `token/bearer/authorization` só retorna labels de UI e `app_secret`).
- Grep por `csrf|xsrf|X-CSRF`: **0 ocorrências**. Dezenas de POSTs mutadores (`/config`, `/projetos/novo`, `.../status`, `.../margens`, `/api/auth/liberar_impostos`, ...).

**Impacto:** Sem token anti-CSRF, se o cookie de sessão não for `SameSite=Strict/Lax`, um site malicioso pode disparar POSTs autenticados em nome do usuário. (Fetch same-origin do próprio app não precisa de token, mas a defesa contra origem externa depende inteiramente do cookie ser `SameSite`.)

**Recomendação:** Garantir `SameSite=Lax`/`Strict` no cookie de sessão (verificação no backend — fora do escopo deste arquivo) e/ou adotar token CSRF por request. Documentar a decisão.

---

### F-08 — Confiança cega em campos da resposta do servidor ao renderizar
**Severidade:** 🟡 Médio

**Evidência:**
- `static/index.html:3835` `d.parcelas.map(...)`, `4094` `aviso.innerHTML = '⚠ ' + d.avisos.join('<br>⚠ ')` — avisos do servidor concatenados como HTML.
- `static/index.html:3806`–`3813`: acesso direto a `d.valor_liberado`, `d.taxa_retencao_pct.toLocaleString(...)` sem verificar existência/tipo.

**Impacto:** Se `d.parcelas` vier ausente ou `d.taxa_retencao_pct` vier `null` (contrato de API mudou, erro parcial), a renderização lança `TypeError` e o painel quebra. `d.avisos` renderizado como HTML (linha 4.094) confia que o servidor nunca envie markup malicioso — acoplamento de segurança ao backend.

**Recomendação:** Validar/normalizar o payload antes de usar (defaults, `Array.isArray`, optional chaining); tratar `d.avisos` como texto (`textContent`) a menos que HTML seja intencional e sanitizado.

---

### F-09 — Ausência total de cabeçalhos/estratégia de cache; 500 KB parseados a cada carga
**Severidade:** 🟡 Médio

**Evidência:**
- `static/index.html` é servido **lido do disco a cada request** (documentado no CLAUDE.md) e tem 500 KB num único arquivo com HTML+CSS+JS inline.
- Sem `<link rel="stylesheet">` de CSS externo cacheável (todo CSS é inline, 8–376); JS todo inline (não cacheável separadamente).
- Fontes carregadas de `fonts.googleapis.com` (`static/index.html:7`) — dependência externa em render-blocking.

**Impacto:** Todo carregamento baixa e faz parse dos 500 KB novamente (o navegador não consegue cachear CSS/JS por serem inline). Em conexões lentas/móveis, o tempo até interativo é alto. A memória de projeto ("versão antiga após deploy = cache") mostra que a estratégia de cache já causou confusão operacional.

**Recomendação:** Extrair CSS/JS para arquivos versionados com hash no nome (cache-busting) e `Cache-Control` longo; manter o HTML pequeno e no-cache. Isso reduz o payload por navegação e melhora o parse.

---

### F-10 — Código morto: renderização baseada em `_negBaseValues`, que é sempre vazio
**Severidade:** 🟡 Médio

**Evidência:**
- `static/index.html:5019` `tbody.innerHTML = _negBaseValues.map(...)` e `static/index.html:4841` `_negBaseValues.filter(...).reduce(...)` (função `totalComDescontoAmb`, marcada "Legado — mantido por seguranca").
- CLAUDE.md declara explicitamente: "**`_negBaseValues` nunca é populado (sempre `[]`)** — não confie nele".

**Impacto:** Blocos de renderização/cálculo que nunca produzem saída (ou produzem tabela vazia), confundindo quem mantém o código e mascarando a lógica real (motor/preview). Risco de alguém "consertar" o caminho errado.

**Recomendação:** Remover o caminho morto (`_negBaseValues` render/`totalComDescontoAmb` legado) ou, se houver receio, isolar e marcar com deprecação clara + data de remoção.

---

### F-11 — Ruído de depuração e dívida em produção (`console.*`, comentário de placeholder de auth)
**Severidade:** 🔵 Baixo

**Evidência:**
- **22** ocorrências de `console.log/debug/info/warn/error` (Grep), ex.: `static/index.html:3802` `console.error('[AYMORE]', e)`, `2709`–`2710` `console.warn('auto-save ...')`.
- **14** marcadores de dívida (`TODO/FIXME/legado/...`).
- `static/index.html:1504` — texto exibido na UII: *"A função `perfil_ativo_get()` será substituída por leitura do token do usuário."* — admissão de placeholder de autorização ainda pendente.

**Impacto:** `console.*` em produção pode vazar detalhes internos e polui o console; comentário de placeholder indica controle de perfil ainda não definitivo. Baixo risco isolado, mas soma dívida.

**Recomendação:** Remover/《gatear》logs por flag de debug; concluir a migração do `perfil_ativo` para leitura do token/servidor e remover o aviso da UI.

---

### F-12 — UX bloqueante: `alert/confirm/prompt` e handlers de erro silenciosos
**Severidade:** 🔵 Baixo

**Evidência:**
- **4** usos de `alert/confirm/prompt` (Grep) — diálogos síncronos que travam a thread.
- Vários `catch` sem feedback ao usuário (ex.: `static/index.html:3802` `return;` após `console.error`), enquanto existe um `showToast` (usado em 4.364) que poderia padronizar o feedback.

**Impacto:** Experiência inconsistente: alguns erros mostram toast, outros somem silenciosamente; `confirm/alert` bloqueiam e destoam do design system.

**Recomendação:** Padronizar feedback via `showToast`/modais do próprio app; eliminar `alert/confirm` nativos.

---

### F-13 — Dependências externas de terceiros em runtime (Google Fonts, ViaCEP) sem fallback
**Severidade:** ℹ️ Info

**Evidência:**
- `static/index.html:7` (Google Fonts, render-blocking) e `login.html:8` (`@import` de fonte).
- `static/index.html:6021` e `9401`: `fetch('https://viacep.com.br/...')` para autopreenchimento de endereço.

**Impacto:** Indisponibilidade/lentidão desses serviços afeta a UI (fontes) e o preenchimento de endereço. Sem timeout (ver F-04), o CEP pode travar o fluxo. Também há implicação de privacidade (o CEP do cliente vai a um terceiro).

**Recomendação:** Hospedar as fontes localmente; adicionar timeout e fallback gracioso ao ViaCEP (permitir digitação manual imediata).

---

## Placar por severidade

| Severidade      | Qtd | Achados |
|-----------------|-----|---------|
| 🔴 Crítico      | 1   | F-01 |
| 🟠 Alto         | 4   | F-02, F-03, F-04, F-05 |
| 🟡 Médio        | 5   | F-06, F-07, F-08, F-09, F-10 |
| 🔵 Baixo        | 2   | F-11, F-12 |
| ℹ️ Info         | 1   | F-13 |
| **Total**       | **13** | |

---

## Recomendações priorizadas (ordem de ataque)

1. **F-01** — Corrigir `esc()` (escapar aspas) e revisar os ~6 handlers `onclick` que interpolam dados; validar com um nome contendo `'`. *(risco de XSS em produção)*
2. **F-05** — Confirmar que o backend revalida limites de desconto/taxa/impostos no salvar; a fronteira de autorização não pode ser o cliente.
3. **F-02** — Mover perfil do usuário (tel/wpp/email/foto) para o backend; parar de usar `localStorage` como fonte de verdade.
4. **F-04 / F-06** — Introduzir um helper único de request com timeout (`AbortController`), checagem de `r.ok` e feedback de erro consistente.
5. **F-03 / F-09** — Iniciar modularização incremental (extrair CSS/JS versionados) e verificação de sintaxe no CI. Ganho composto de manutenção, performance e cacheabilidade.

> Observação de método: análise estática READ-ONLY sobre `static/index.html` e `static/login.html`. Achados de segurança de fronteira (F-05, F-07) dependem da verificação correspondente **no backend Python**, fora do escopo deste arquivo — recomenda-se cruzar com a auditoria de backend.
