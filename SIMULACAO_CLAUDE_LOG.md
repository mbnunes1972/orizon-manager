# SIMULAÇÃO_CLAUDE_LOG.md — Orizon Manager | Dalmóbile

Log dedicado dos testes ponta a ponta "Simulação Claude N" (cadastro → contrato → medição → PE →
implantação/produção/entrega → NF-e/NFS-e), rodados de forma humanizada (como a Vera) contra o app
real e o `orizon.db` real do projeto. Cada rodada ganha uma entrada abaixo, registrando **fatos**
(o que foi confirmado), **evoluções** (o que melhorou desde a rodada anterior) e **retrocessos**
(bugs/regressões encontrados). Este arquivo é sobre o *processo de teste*; decisões de arquitetura e
histórico de desenvolvimento continuam no `DEV_LOG.md`.

**Nota sobre numeração:** já existiam rodadas anteriores registradas no `DEV_LOG.md` (Sessão 67 —
"Simulação Claude", com dados reais dos 3 XMLs Promob; e uma segunda rodada, pasta
`PROJETOS/Simulacao_Claude_2/`). A numeração aqui recomeça em **Simulação Claude 1** como uma série
de acompanhamento nova e dedicada — não é a mesma sequência do DEV_LOG. Sem conflito de nome: o
`nome_safe` do projeto novo é `Simulacao_Claude_1`, distinto das pastas antigas.

---

## Simulação Claude 1 — 2026-07-12 (em andamento)

### Contexto / estado do ambiente antes de começar
- **Banco corrompido:** o `orizon.db` real (na pasta do projeto) falhou em `PRAGMA integrity_check`
  ("database disk image is malformed") logo no início da sessão. Diagnóstico: cabeçalho SQLite
  declarava 378 páginas, arquivo físico só tinha 377 — corrupção real, não intermitência. Sem backup
  local disponível. Usuário autorizou reconstrução (sem dados importantes em risco).
- **Mount da sessão Cowork com leitura instável em arquivos grandes:** `main.py`, `database.py`,
  `mod_ciclo.py`, `mod_contabil.py` apareciam truncados no meio de uma linha (erro de sintaxe
  reprodutível, estável entre releituras — não é flakiness, é truncamento real do lado da leitura).
  Confirmado que o `HEAD` do git estava correto e completo (`ast.parse` limpo via
  `git archive HEAD` extraído num checkout isolado) — nenhum código-fonte foi perdido, é uma
  limitação da ponte de leitura desta sessão Cowork pra pasta montada, não do arquivo real.
- **Reconstrução:** `orizon.db` recriado do zero via `seed.py` a partir de um checkout limpo
  (`git archive HEAD`), escrito de volta no arquivo real (sobrescrita in-place, sem apagar/renomear).
  Zero projetos, 6 usuários seed + 1 admin bootstrap (`sad2026`, criado automaticamente pelo
  `main.py`). `PRAGMA integrity_check` = ok.
- **Zerado uma segunda vez** entre a Fase 1 (cadastros) e a checagem seguinte — causa não totalmente
  isolada (best guess: reconstrução/reset feito por outra sessão paralela — Claude Code + Vera —
  trabalhando no fechamento do design system v1.4 no mesmo `orizon.db`). Reconstruído de novo,
  desta vez a partir do `HEAD` já com o design v1.4 comitado (`8ede78d`).
- **Git:** `HEAD` em `8ede78d` — `feat(design): design system v1.4 (cobre/carvao) + identidade
  visual v1.0 (glifo)`, já mergeado. Nenhuma perda de trabalho comitado confirmada.

### Fatos confirmados (rodada anterior à renumeração, dados perdidos no reset — repetir)
*(a primeira tentativa de cadastro — cliente Luciano Alves, parceira Lúcia dos Santos, projeto
"Simulação Claude 3" — rodou completa até a Aprovação Financeira I e foi validada, mas os dados
foram perdidos no reset do banco antes da conferência manual do usuário. Achados técnicos válidos,
reaproveitados como contexto pra próxima rodada:)*

- Motor de negociação responde corretamente a desconto geral + específico por ambiente, forma de
  pagamento Aymoré parcelado, custo de viagem e brinde.
- **Achado:** Custo de Viagem e Brinde são parâmetros do **projeto** (`projetos_meta.parametros_json`),
  não por orçamento — rateados pelo pool inteiro do projeto entre os orçamentos concorrentes. Não é
  bug, mas vale confirmar se é o comportamento de produto esperado quando 2 orçamentos coexistem.
- **Achado (fragilidade de API, não reproduz pela UI real):** `POST /api/projetos/<nome>/parametros`
  com payload parcial zera comissão do arquiteto e fidelidade antes do 1º save completo — a tela real
  sempre manda o objeto inteiro, então não afeta uso normal, mas é um ponto de hardening.
- Confirmado: assinatura do contrato gera lançamentos de venda (`1.1.02×2.1.06`), Custo de Fábrica
  como ativo diferido (`1.1.06.06×2.1.04.06`) e custo financeiro (`5.5.03×2.1.05`) automaticamente.
  As outras 7 rubricas ficaram zeradas por a loja seed ter Config Financeira com percentuais em zero
  (não é bug — precisa de uma loja com config preenchida pra validar as 10 rubricas completas).
  `2.1.04.14`/`1.1.06.14` (Outros Fornecedores) nasceram zeradas, como esperado.

### Evoluções desde o início desta sessão
- Corrupção de banco diagnosticada com precisão (offset de página exato), não só "parece corrompido".
- Estabelecido fluxo seguro de reconstrução (checkout limpo isolado + seed.py + sobrescrita in-place)
  que preserva o `orizon.db` real sem depender de `rm` (bloqueado por permissão na pasta montada).

### Retrocessos / pendências em aberto
- **Banco zerou 2x nesta sessão** sem causa 100% confirmada na segunda vez — hipótese mais forte é
  reset concorrente pela sessão paralela (Claude Code + Vera). Ainda não confirmado com o usuário.
- Ainda não recebida a confirmação do usuário, rodando comandos no WSL real dele, de que o
  `orizon.db` que o servidor local lê bate byte-a-byte com o que esta sessão Cowork escreve — ponto
  de sincronia entre o mount do Cowork e o filesystem real segue como incerteza não resolvida.
- Config Financeira da loja seed com percentuais zerados impede validar as 10 rubricas completas
  nesta simulação (só valida a mecânica com Custo de Fábrica).

### Rodada concluída (mesmo dia, sequência 2) — cadastro → Aprovação Financeira I

**Novo achado ambiental (não é bug do Orizon Manager):** o mount desta sessão Cowork não sustenta
`commit()` de SQLite de forma confiável — reproduzido `disk I/O error` mesmo num banco novo/vazio,
em todos os `journal_mode` testados. Contorno: rodar o `orizon.db` de trabalho fora do mount (disco
local do sandbox) e sincronizar os bytes pro caminho montado em checkpoints (cópia bruta, não via
SQLite). Deleção de arquivo (`rm`) também é bloqueada nesse mount ("Operation not permitted") —
sobrescrita de conteúdo (`open(path,'wb')`) funciona normalmente. **Pendência:** pedir ao usuário
para confirmar `PRAGMA integrity_check` no `orizon.db` real, fora desta sessão Cowork (ex.: no WSL
dele), pra fechar de vez a dúvida de sincronia entre os dois lados.

**Fatos confirmados:**
- Cliente Luciano Alves (CPF 523.647.189-37), parceira Lúcia dos Santos (comissão 5%), projeto
  "Simulação Claude 1" (`nome_safe=Simulacao_Claude_1`) com parceiro vinculado.
- Loja seed estava com endereço incompleto (faltava CEP/logradouro/número/bairro/cidade/estado,
  exigido para gerar contrato) — completado via `PATCH /api/admin/lojas/1` antes da assinatura.
- Orçamento A (4 ambientes): VBVO 226.180,65 · CFO 81.359,22 · Com_Arq 10.407,52 · **Val_Cont
  236.854,55** · Aymoré 10x R$ 20.685,45.
- Orçamento B (3 ambientes, sem Suíte Master): VBVO 182.028,24 · CFO 65.477,13 · Com_Arq 8.316,09 ·
  **Val_Cont 188.491,63** · Aymoré 10x R$ 15.849,16.
- Confirmado de novo (2ª vez): comissão do arquiteto e fidelidade já vêm herdadas corretas do
  parceiro (5%/ativa) antes de qualquer save; custo de viagem exige `fora_da_sede=true` pra ter
  efeito no motor — detalhe de payload, não bug.
- Confirmado de novo: Custo de Viagem/Brinde são parâmetros do **projeto**, rateados pelo pool
  inteiro (por isso o Orçamento B recebeu proporção menor: R$4.023,96/R$750, não os R$5.000/R$1.000
  cheios).
- Contrato assinado (loja + cliente). Ciclo parado corretamente na etapa 8 (Aprovação Financeira I
  = pendente).
- Lançamentos na assinatura: `1.1.02×2.1.06` R$236.854,55 (venda), `1.1.06.06×2.1.04.06` R$81.359,22
  (Custo de Fábrica, ativo diferido), `5.5.03×2.1.05` R$22.704,23 (custo financeiro Aymoré).
  `2.1.04.14`/`1.1.06.14` (Outros Fornecedores) = zero, como esperado (config financeira da loja
  seed com percentuais zerados — mesma ressalva da rodada anterior, ainda não resolvida).

**Evoluções desde a rodada anterior:** nenhuma divergência funcional nova encontrada — tudo bateu
com o que já estava documentado. Driver de simulação (`sim_runner.py`) agora idempotente e reusável
pras próximas fases.

**Retrocessos:** nenhum novo (o zeramento de banco já estava registrado acima; a causa raiz virou o
achado do `disk I/O error` do mount, o que explica melhor por que reconstruções anteriores pareciam
"sumir" — se o Cowork tentou em algum momento gravar via SQLite direto no mount, o commit
provavelmente falhou silenciosamente ou corrompeu o journal).

### Rodada concluída (mesmo dia, sequência 3) — Aprovação Financeira I → Medição → PE → parada em Aprovação Financeira II

**Coordenação de acesso concorrente:** usuário parou o próprio `python3 main.py` (rodava em
PowerShell nativo do Windows, **não WSL** — hipótese de drvfs da rodada anterior estava errada;
causa mais provável era mesmo dois processos disputando o mesmo `orizon.db` ao mesmo tempo: o
servidor real do usuário + esta sessão) antes desta fase rodar, evitando conflito de escrita.

**Fatos confirmados:**
- Etapa 8 (Aprovação Financeira I) concluída via Provisões Rev 1 (decisão "concorda", cópia da
  Venda) + `PATCH /ciclo/8`.
- Etapas 9 (Solicitação de Medição) e 10 (Medição) concluídas via `POST /medicao/solicitacao` e
  `POST /medicao/parecer` — **ambas exigem upload obrigatório** (`mod_ciclo.guarda_conclusao`
  bloqueia sem documento); subiram `.txt` de teste com sucesso.
- Etapas 11a/11b/11c (Planta de Pontos de PE, Reunião de Alinhamento, Revisão de PE) concluídas —
  **também exigem upload obrigatório** cada uma.
- **Divergência importante vs. o roteiro original:** a Aprovação Financeira II (etapa 11d) **não
  tem campo pra "PE revisado" nem "novo custo de fábrica"** — pela arquitetura FASE D2, CFO e
  Val_Liq são **base congelada da Rev 1** ("base congelada" é comentário literal no código). O que
  existe de fato é o botão Provisões → **Rev 2** (Concorda/Revisa por rubrica) + botão "Aprovar
  (gerencial)". A diferença real de custo só entraria depois, no matching da NF-e (sobra vira
  `4.4.02`).
- Valores calculados (documentados nas observações da 11d, sem confirmar a aprovação):
  - PE revisado (95% do Val_Cont vendido R$236.854,55) = R$225.011,82 — sem campo na API, só
    registrado em observação.
  - Novo CFO (−20% de R$81.359,22 por migração) = R$65.087,38 — sem campo na API, idem.
  - **Outros Fornecedores (10% do CFO ORIGINAL) = R$8.135,92 — esse lançou de verdade**, via Rev 2
    (rubrica `out_forn`, decisão `revisa`). Efeito confirmado: `cust_var` 89.495,14, `marg_cont`
    caiu de 0,5886 para 0,5474.
- Etapa 11d ficou **pendente de propósito** (aprovação final não confirmada), como pedido.

**Achado de risco operacional (novo):** como o banco foi resetado, os IDs voltam a começar do 1 —
e a nomeação de arquivo em `CONTRATOS/`/`PROJETOS/` é por ID sequencial, não por nome do projeto.
Isso colidiu com um `contrato_1.pdf` real pré-existente (sobrescrito; o agente salvou como
`.bak_pre_sim` por precaução). Usuário confirmou que era dado de teste antigo, mandou apagar —
apagado (via `allow_cowork_file_delete`, já que `rm` direto é bloqueado nesse mount). **Risco
permanece pras próximas fases** (Implantação/Produção/Entrega vão gerar mais documentos por ID) —
usuário optou por aceitar o risco com backup automático em vez de isolar os arquivos da simulação.

**Retrocessos:** nenhum bug novo do app — só a lacuna de "campo pra PE revisado" no roteiro vs. a
arquitetura real (que é intencional, não bug: FASE D2 congela a base na Rev 1 por design).

### Próximos passos
Usuário revisando a Aprovação Financeira II antes de confirmar. Depois: Implantação do Pedido,
Produção, Entrega no Depósito (anexando arquivo), NF-e dos produtos + NFS-e na proporção padrão.
