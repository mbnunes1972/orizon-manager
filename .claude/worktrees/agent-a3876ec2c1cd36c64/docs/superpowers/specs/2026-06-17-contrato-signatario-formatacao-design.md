# Sub-projeto E — Contrato: signatário, testemunhas, formatação + enforcement de aprovação

**Data:** 2026-06-17
**Projeto:** Omie_V3 — Dalmóbile / Orizon / Inspirium
**Escopo:** Corrigir bugs encontrados em teste (modal sobreposto; aprovação sem ambiente) e ajustar o documento do contrato (2º signatário = cliente; fluxo "é o cliente cadastrado?"; testemunhas provisórias; "CPF"→"CPF/CNPJ"; tags de nomenclatura nos campos editáveis).
**Origem:** bugs reportados pelo usuário durante teste manual do fluxo completo.

---

## 1. Contexto e causas-raiz (investigadas)

- **Bug 2 — modal sobreposto:** em `gerarContrato()`, o popup "Cadastro Incompleto" (`mostrarErroComAcao`) tem callback `() => { if (cliId) cliAbrirModal(cliId); }` que **não remove** o `#modal-aprovacao-overlay`. Resultado: cadastro abre por cima do modal de aprovação, que fica aberto.
- **Bug 3 — aprovação sem ambiente:** `POST /api/projetos/<nome>/contrato` **não verifica** se o orçamento tem ambientes / se a etapa 4 (Primeiro orçamento) está concluída. Gera contrato com orçamento vazio e chega à assinatura. (Lacuna §3.3 deixada em aberto no Sub-projeto C.)
- **Assinatura (bugs 1 e 4):** o modelo (`modelo_contrato_final.docx`) tem na área de assinatura: par. 127 `INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA CNPJ: 19.152.134/0001-56` (CONTRATADA, fixa); par. 128 `Iberê Ferreira Machado CPF: 787.834.108-72` (**2º signatário = CLIENTE**, hoje preenchido como exemplo); e dois pares `NOME:/Documento:` (par. 138-141) = **duas testemunhas**. O código atual em `preencher_contrato`:
  - sobrescreve o par. 128 com `consultor_nome` (**errado** — deve ser o **cliente**);
  - preenche o 1º par `NOME:/Documento:` (Testemunha 1) com o cliente (**errado** — testemunhas são outras pessoas).

### Decisões validadas com o usuário
- 2º signatário = **cliente**. Ao gerar, **perguntar se o signatário é o cliente cadastrado**: se sim, usa nome+CPF/CNPJ do cadastro; **se não, abrir modal com TODOS os dados do contrato** (identificação + endereços), que substituem o cadastro **para este contrato**.
- Testemunhas (provisório, até painel de loja): **Jaime Perinazzo** `CPF/CNPJ xxx.xxx.xxx-xx` e **Felipe Guizalberte** `CPF/CNPJ yyy.yyy.yyy-yy`.
- Trocar **"CPF" → "CPF/CNPJ"** em todo o contrato.
- **Tags de nomenclatura** nos campos editáveis: **rótulo cinza pequeno (~7pt) acima/à esquerda** do valor (ex.: Nome, CPF/CNPJ, CEP, Data, Logradouro).

---

## 2. Bug 2 — popup "Cadastro Incompleto" troca de modal

Em `gerarContrato()` (`static/index.html`), no callback do `mostrarErroComAcao` (ramo `campos_faltando`), fechar o modal de aprovação antes de abrir o cadastro:
```javascript
() => {
  document.getElementById('erro-modal-overlay')?.remove();
  document.getElementById('modal-aprovacao-overlay')?.remove();
  if (cliId) cliAbrirModal(cliId);
}
```

---

## 3. Bug 3 — bloquear aprovação/contrato sem ambiente

- **Backend (autoridade):** em `POST /api/projetos/<nome>/contrato`, logo após `_montar_dados_projeto_para_contrato(...)` retornar `orcamento_dict`, se `not orcamento_dict.get("ambientes")` → **HTTP 400** `"O orçamento não tem ambientes. Conclua o primeiro orçamento (com ambientes) antes de aprovar."`.
- **Frontend (UX):** em `abrirAprovacaoComDados()`, antes de abrir o modal de aprovação, checar se o orçamento ativo tem ambientes (reusar o mesmo critério de `salvarOrcamento`: `_orcAmbientesAtivos?.length`). Se vazio, `mostrarErroModal('Adicione ao menos um ambiente (XML) e salve o orçamento antes de aprovar.')` e não abrir.

---

## 4. Documento do contrato — signatário cliente + testemunhas + CPF/CNPJ + tags

Tudo em `mod_contrato.py` (`preencher_contrato` / `construir_contexto`) e no endpoint.

### 4.1 2º signatário = cliente
No loop de parágrafos de `preencher_contrato`, o ramo que hoje casa `"Ferreira Machado"/"787.834"` passa a preencher com **nome + CPF/CNPJ do cliente** (do `ctx`): `f"{cliente_nome} CPF/CNPJ: {cliente_cpf}"` (em vez de `consultor_nome`). A linha da INSPIRIUM (par. 127) **não é tocada**.

### 4.2 Testemunhas (provisório)
Preencher os dois pares `NOME:/Documento:`:
- Testemunha 1 → `NOME: Jaime Perinazzo` / `CPF/CNPJ: xxx.xxx.xxx-xx`
- Testemunha 2 → `NOME: Felipe Guizalberte` / `CPF/CNPJ: yyy.yyy.yyy-yy`

Constantes em `mod_contrato.py` marcadas como provisórias (`# TODO: vir do painel de configuração de loja`). Remover o `break` atual que parava no 1º par.

### 4.3 "CPF" → "CPF/CNPJ"
Após preencher, varrer o documento (parágrafos + células de tabela) e substituir o texto `"CPF"` por `"CPF/CNPJ"`, **sem** duplicar onde já está `"CPF/CNPJ"`. Aplicar via runs para preservar formatação. Cobre rótulos da capa ("CPF"), linha de assinatura e onde mais aparecer.

### 4.4 Tags de nomenclatura (rótulo cinza pequeno acima)
Para cada **campo editável** preenchido pelo código (células de valor das tabelas da capa + parágrafos preenchidos: data, signatário cliente, testemunhas), inserir **acima do valor** uma linha/`run` em fonte pequena (~7pt) e cor cinza com o nome do campo (ex.: "Nome", "CPF/CNPJ", "CEP", "Data", "Logradouro", "Número", "Bairro", "Cidade", "Estado/UF", "Telefone", "E-mail", "Modalidade", "Entrada"…). Implementar via helpers `_set_cell`/`_set_para` recebendo um `rotulo` opcional que adiciona a tag.

### 4.5 Fluxo "é o cliente cadastrado?" + modal de signatário
- **Frontend:** ao clicar "Gerar Contrato", perguntar (confirm/modal) **"O signatário é o próprio cliente cadastrado?"**.
  - **Sim** → segue o fluxo atual (POST /contrato usa o cadastro).
  - **Não** → abrir um **modal com todos os dados do contrato** (nome, CPF/CNPJ, e-mail, telefone, endereço residencial completo, instalação), pré-preenchido a partir do cadastro e editável; ao confirmar, `gerarContrato` envia esses dados como `signatario_override` no corpo do POST.
- **Backend:** `POST /contrato` aceita um campo opcional `signatario_override` (dict com os mesmos campos de `cliente_dict`). Se presente, **usa-o no lugar do `cliente_dict`** ao montar o contexto (`construir_contexto`) e ao validar (`validar_cliente_para_contrato`). Sem ele, comportamento atual (cadastro).

---

## 5. Testes

1. **Backend:** `POST /contrato` sem ambientes → 400 (bug 3). Com `signatario_override`, o contexto/validação usam o override (helper testável: `construir_contexto` já recebe um dict — testar com override).
2. **Documento (geração + inspeção docx):** par. 128 = nome+CPF/CNPJ do cliente; testemunhas = Jaime/Felipe; nenhum "CPF" isolado (tudo "CPF/CNPJ"); tags de nomenclatura presentes (fonte pequena/cinza) acima dos valores. Reproduzir via `preencher_contrato` e inspecionar o `.docx` (como nas verificações anteriores).
3. **Frontend (Playwright/manual):** popup "Cadastro Incompleto" fecha o modal de aprovação e abre o cadastro (bug 2); aprovação sem ambiente bloqueada; fluxo "é o cliente cadastrado?" sim/não (modal de signatário).

---

## 6. Fora de escopo
- Painel de configuração de loja para testemunhas reais (futuro) — por ora hardcoded.
- Assinatura digital em si (apenas o documento gerado muda).

---

## 7. Arquivos afetados (estimativa)

| Arquivo | Mudança |
|---|---|
| `mod_contrato.py` | par.128 = cliente; testemunhas provisórias; "CPF"→"CPF/CNPJ"; tags de nomenclatura; `construir_contexto`/override |
| `main.py` | gate de ambiente em `POST /contrato`; aceitar `signatario_override` |
| `static/index.html` | bug 2 (popup troca modal); bug 3 (pré-check ambiente); fluxo "é o cliente cadastrado?" + modal de signatário |
| `tests/` | gate de ambiente; override no contexto; (doc inspecionado em runtime) |
