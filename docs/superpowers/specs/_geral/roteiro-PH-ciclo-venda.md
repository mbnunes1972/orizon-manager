# Roteiro de Pré-Homologação — Ciclo de Venda ponta a ponta

**Ambiente:** PRÉ-HOMOLOGAÇÃO — `http://167.88.33.121:8766` · **Fluxo:** cliente → projeto → orçamento →
negociação → proposta → contrato → assinatura, acompanhando as etapas do ciclo.
**Formato:** cada cenário é para um testador **leigo** executar clicando exatamente o que está escrito, e
marcar ✅ OK / ❌ NOK + observação.

> ⚠️ **Antes de começar:**
> - **Login é o CÓDIGO, não o e-mail** (campo "E-mail", mas digite o código, ex.: `pdm2026`).
> - **Você vai precisar de UM ARQUIVO XML do Promob** (um ambiente exportado) para criar o orçamento — o
>   sistema cria "ambientes" arrastando XMLs do Promob. **Peça esse arquivo de exemplo antes de começar**
>   (sem ele, o passo do orçamento não roda). Guarde-o no computador do teste.
> - Faça este roteiro **depois** do `roteiro-PH-setup-loja-usuarios.md` (precisa de uma loja e um usuário).

**Usuário sugerido para este roteiro:** `pdm2026` / `teste123` (nível **Master** — enxerga tudo e pode
aprovar). *(Se quiser testar o escopo do consultor, use o `mds2026` / `teste345`, nível Operador.)*

---

## PH-C01 — Entrar como vendedor

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master (vendedor com permissão ampla) |
| **Pré-condições** | Ambiente aberto no navegador |

**Passos:**
1. Abra `http://167.88.33.121:8766` e clique **"Entrar"**.
2. Campo **"E-mail"**: digite `pdm2026`. Campo **"Senha"**: digite `teste123`. Clique **"Entrar"**.

**Resultado esperado:** entra no sistema; na barra lateral aparece o item **"Projetos"** (seção "Atalhos").

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C02 — Cadastrar um cliente

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Estar logado (PH-C01) |

**Passos:**
1. Na barra lateral, clique no módulo **"Cadastro"** e vá até a lista de clientes.
2. Clique em **"+ Novo Cliente"** — abre a janela **"Novo Cliente"**.
3. Preencha:
   - **"Nome completo *":** `João da Silva Teste`
   - **"Tipo de destinatário":** deixe **"Não contribuinte"**.
   - **"CPF":** `111.111.111-11` (fictício) · **"Telefone"/"E-mail":** opcionais.
4. Salve o cliente. *(Se aparecer aviso de homônimo, clique "É um homônimo — continuar".)*

**Resultado esperado:** o cliente **"João da Silva Teste"** é salvo e passa a aparecer na lista de clientes.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C03 — Criar um projeto

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Ter o cliente cadastrado (PH-C02) |

**Passos:**
1. Na barra lateral, clique em **"Projetos"**.
2. Clique em **"+ Novo Projeto"**.
3. Preencha:
   - **"NOME DO PROJETO *":** `Cozinha João Teste`
   - **"CLIENTE *":** no campo de busca "Buscar por nome ou CPF...", digite `João` e selecione **João da Silva Teste**.
   - **"CONSULTOR RESPONSÁVEL":** (se aparecer) deixe você mesmo.
4. Clique em **"Criar Projeto"**.

**Resultado esperado:** o projeto **"Cozinha João Teste"** é criado e aparece na lista de projetos.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C04 — Criar o orçamento (adicionar um ambiente)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Projeto criado (PH-C03) **+ ter o arquivo XML do Promob de exemplo** |

**Passos:**
1. Na lista de projetos, dê **duplo-clique** na linha do **"Cozinha João Teste"** (ou clique **"Abrir"**) — abre a tela do projeto.
2. Na barra **"Orçamento:"**, clique em **"Novo Ambiente"** — abre **"Adicionar Ambiente"**.
3. **Arraste o arquivo XML do Promob** para a área "Arraste XMLs do Promob aqui" (ou clique nela e selecione o arquivo).
4. Aguarde o ambiente ser carregado. Se aparecer o botão **"Novo Orçamento"**, o valor do ambiente entra no orçamento.

**Resultado esperado:** o ambiente aparece com um **valor** e a faixa mostra **"Valor Bruto"** preenchido
(depois "Desconto" e "Valor à Vista"). *(Se você não tiver o XML, marque NOK e anote "faltou XML de exemplo".)*

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C05 — Negociar (desconto e parcelas)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Orçamento com valor (PH-C04) |

**Passos:**
1. Na tela do projeto, localize a barra lateral **"Parâmetros"**.
2. Em **"Desconto (%)"**, digite um valor pequeno (ex.: `5`).
3. Em **"Parcelas"**, escolha uma quantidade (ex.: `10`).
4. Observe o **"Valor à Vista"** recalcular. *(Se o desconto for alto demais para o seu perfil, aparece um botão de pedir autorização — para o teste, use um desconto baixo.)*

**Resultado esperado:** o valor final (à vista) muda conforme o desconto; as parcelas aparecem coerentes.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C06 — Gerar a Proposta em PDF

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Orçamento negociado (PH-C05) |

> **Atenção:** o que gera a proposta é o botão **"🖨 Imprimir"** — **não** existe um botão chamado "Proposta".

**Passos:**
1. Na linha de ações do orçamento (na tela de negociação), clique em **"🖨 Imprimir"**.
2. Aguarde abrir/baixar o **PDF da proposta**.

**Resultado esperado:** abre (ou baixa) um **PDF da proposta** com os dados do cliente, os ambientes e os
valores negociados.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C07 — Aprovar e gerar o Contrato

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Proposta conferida (PH-C06) |

**Passos:**
1. Na tela do projeto, clique no botão **"✓ Aprovar"** (dica "Aprovar orçamento e iniciar contrato").
2. Abre uma janela de aprovação mostrando pagamento/parcelas. Preencha, se pedir, **"Endereço de instalação"**
   (há um botão **"= Cliente"** para copiar o endereço do cliente) e **"Entrada (R$)"**.
3. Clique em **"Gerar Contrato"**.

**Resultado esperado:** o contrato é gerado; o projeto avança para a etapa **"Contrato"** do ciclo, com opção
de abrir o **PDF do contrato** (**"⬇ Abrir PDF"**).

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C08 — Assinar o contrato (loja e cliente)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Contrato gerado (PH-C07) |

> **Contexto:** o contrato precisa de **duas assinaturas** — a **1ª** (loja) e a **2ª** (cliente). Só depois
> das duas ele fica "assinado".

**Passos:**
1. Abra as **"Etapas do Projeto"** (botão no projeto) e expanda a etapa **"Contrato"**.
2. *(Recomendado)* Clique em **"⬇ Abrir PDF"** e confira o contrato.
3. Marque a caixa **"Li o contrato e estou de acordo com os termos"** — isso revela a seção **"Assinaturas:"**.
4. Clique em **"Assinar como loja"** → na janela, preencha **"Nome completo"** e **"CPF"**, marque **"Li e aceito
   os termos do contrato"** e clique **"Confirmar Assinatura"**.
5. Clique em **"Assinar como cliente"** → repita o preenchimento e **"Confirmar Assinatura"**.

**Resultado esperado:** após a 1ª assinatura aparece "(aguardando assinatura)"; após a 2ª aparece
**"✓ Contrato assinado — ambas as partes confirmaram."**

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C09 — Conferir as etapas do ciclo (Orçamento → Contrato)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Contrato assinado (PH-C08) |

> **Contexto:** não existe um único botão "Concluir etapa" — cada etapa fecha do seu jeito (preencher, aprovar,
> assinar…). A numeração **pula da 4 (Orçamento) para a 7 (Contrato)** — é esperado, as etapas 5 e 6 foram removidas.

**Passos:**
1. No projeto, abra **"Etapas do Projeto"**.
2. Confira que as etapas **"Cadastro do Cliente"**, **"Criação do projeto"**, **"Briefing"**, **"Orçamento"** e
   **"Contrato"** aparecem como concluídas (✓) ou em andamento, na ordem.
3. Observe que a etapa seguinte (**"Aprovação financeira I"**) aparece como próxima/pendente.

**Resultado esperado:** o ciclo reflete o progresso da venda: da etapa 4 (Orçamento) até a 7 (Contrato)
concluídas, com a próxima etapa indicada.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## Encerramento
- [ ] Todos os cenários acima marcados ✅ OK.
- [ ] Bugs/estranhezas anotados (com print, se possível).
- [ ] **Bloqueio conhecido:** o PH-C04 depende de um **XML do Promob de exemplo** — providenciar antes do teste.
