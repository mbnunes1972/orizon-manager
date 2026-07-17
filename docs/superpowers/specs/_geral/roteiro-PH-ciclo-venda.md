# Roteiro de Pré-Homologação — Ciclo de Venda ponta a ponta

**Ambiente:** PRÉ-HOMOLOGAÇÃO — `http://167.88.33.121:8766` · **Fluxo:** cliente → projeto → briefing →
orçamento → negociação → proposta → contrato → assinatura, acompanhando as etapas do ciclo.
**Formato:** cada cenário é para um testador **leigo** executar clicando exatamente o que está escrito, e
marcar ✅ OK / ❌ NOK + observação.

> ⚠️ **Antes de começar:**
> - **Login é o CÓDIGO, não o e-mail** (campo "E-mail", mas digite o código, ex.: `pdm2026`).
> - **Tenha à mão um ambiente exportado do Promob (arquivo XML).** O orçamento é criado arrastando esse XML
>   (um XML = um ambiente). Você, que conhece o Promob, já sabe exportá-lo — traga um de exemplo.
> - Faça este roteiro **depois** do `roteiro-PH-setup-loja-usuarios.md` (precisa de uma loja e um usuário).

**Usuário sugerido:** `pdm2026` / `teste123` (nível **Master** — enxerga tudo e pode aprovar). *(Para testar o
escopo do consultor, use `mds2026` / `teste345`, nível Operador.)*

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

## PH-C02 — Cadastrar um cliente (com endereço completo)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Estar logado (PH-C01) |

> **Importante:** **Telefone e E-mail são obrigatórios** (mesmo sem o `*` no rótulo), e o **endereço completo
> é necessário** — sem ele o contrato (PH-C08) se recusa a ser gerado. Preencha tudo abaixo.

**Passos:**
1. Na barra lateral, clique no módulo **"Cadastro"** e vá até a lista de clientes.
2. Clique em **"+ Novo Cliente"** — abre a janela **"Novo Cliente"**.
3. Preencha:
   - **"Nome completo *":** `João da Silva Teste`
   - **"Tipo de destinatário":** deixe **"Não contribuinte"**.
   - **"CPF":** `111.444.777-35` *(CPF fictício válido — não use `111.111.111-11`, que é rejeitado)*.
   - **"Telefone":** `(12) 99999-0000` **(obrigatório)** · **"E-mail":** `joao.teste@exemplo.com` **(obrigatório)**.
   - **Endereço (obrigatório para o contrato):** CEP, Logradouro, Número, Bairro, Cidade, Estado/UF. Ex.:
     CEP `12210-000`, Logradouro `Rua das Flores`, Número `100`, Bairro `Centro`, Cidade `São José dos Campos`, UF `SP`.
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
   - **"CLIENTE *":** no campo "Buscar por nome ou CPF...", digite `João` e selecione **João da Silva Teste**.
   - **"CONSULTOR RESPONSÁVEL":** (se aparecer) deixe você mesmo.
4. Clique em **"Criar Projeto"**.

**Resultado esperado:** o projeto **"Cozinha João Teste"** é criado e aparece na lista de projetos.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C04 — Preencher o Briefing

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Projeto criado (PH-C03) |

> **Por que aqui:** o sistema **não deixa subir o XML do orçamento** enquanto o Briefing não estiver completo
> (aparece o aviso "⚠ Briefing pendente"). Preencha antes.

**Passos:**
1. Na lista de projetos, dê **duplo-clique** na linha do **"Cozinha João Teste"** (ou clique **"Abrir"**).
2. Clique no botão **"Preencher Briefing"** (ou no aviso "⚠ Briefing pendente").
3. Informe ao menos os **5 campos obrigatórios**: **Tipo de imóvel**, **Budget declarado** (valor), **Categoria
   da proposta**, **Data de entrega desejada**, **Flexibilidade de prazo**. Salve.

**Resultado esperado:** o aviso de "Briefing pendente" desaparece; a etapa **"Briefing"** passa a contar como preenchida.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C05 — Criar o orçamento (adicionar um ambiente via XML)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Briefing preenchido (PH-C04) + ter o arquivo XML do Promob |

**Passos:**
1. Com o projeto aberto, na barra **"Orçamento:"**, clique em **"Novo Ambiente"** — abre **"Adicionar Ambiente"**.
2. **Arraste o arquivo XML do Promob** para a área "Arraste XMLs do Promob aqui" (ou clique nela e selecione o arquivo).
3. Aguarde o ambiente carregar. Se aparecer o botão **"Novo Orçamento"**, o valor do ambiente entra no orçamento.

**Resultado esperado:** o ambiente aparece com um **valor** e a faixa mostra **"Valor Bruto"** preenchido
(depois "Desconto" e "Valor à Vista").

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C06 — Negociar (desconto e parcelas)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Orçamento com valor (PH-C05) |

**Passos:**
1. Na tela do projeto, localize a barra lateral **"Parâmetros"**.
2. Em **"Desconto (%)"**, digite um valor pequeno (ex.: `5`).
3. Em **"Parcelas"**, escolha uma quantidade (ex.: `10`).
4. Observe o **"Valor à Vista"** recalcular. *(Desconto alto demais para o seu perfil dispara um pedido de autorização — no teste, use um desconto baixo.)*

**Resultado esperado:** o valor final (à vista) muda conforme o desconto; as parcelas aparecem coerentes.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C07 — Gerar a Proposta em PDF

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Orçamento negociado (PH-C06) |

> **Atenção:** o que gera a proposta é o botão **"🖨 Imprimir"** — **não** existe um botão chamado "Proposta".

**Passos:**
1. Na linha de ações do orçamento (na tela de negociação), clique em **"🖨 Imprimir"**.
2. Aguarde abrir/baixar o **PDF da proposta**.

**Resultado esperado:** abre (ou baixa) um **PDF da proposta** com os dados do cliente, os ambientes e os valores negociados.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C08 — Aprovar e gerar o Contrato

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Proposta conferida (PH-C07); cliente com endereço completo (PH-C02) |

**Passos:**
1. Na tela do projeto, clique no botão **"✓ Aprovar"** (dica "Aprovar orçamento e iniciar contrato").
2. Abre a janela **"Aprovar Orçamento"**, mostrando o **Cliente** e a **Condição de Pagamento** (Entrada,
   Forma de Pagamento e Parcelas — **tudo somente-leitura**, vem da negociação do PH-C06). Se quiser, escreva
   algo no campo livre **"Adendo (opcional)"**.
3. Clique em **"Gerar Contrato"**.
4. Vai aparecer um pop-up perguntando **"O signatário do contrato é o próprio cliente cadastrado?"** — clique **"Sim"**.

**Resultado esperado:** o contrato é gerado e o projeto avança para a etapa **"Contrato"** do ciclo, com opção
de abrir o **PDF do contrato** (**"⬇ Abrir PDF"**). *(Se o cliente estiver sem endereço completo, o sistema
recusa com uma mensagem listando os campos faltando — volte ao PH-C02.)*

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C09 — Assinar o contrato (loja e cliente)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Contrato gerado (PH-C08) |

> **Contexto:** o contrato precisa de **duas assinaturas** — a **1ª** (loja) e a **2ª** (cliente). Só depois das
> duas ele fica "assinado". Antes da 2ª, é obrigatório informar a data de entrega.

**Passos:**
1. Abra as **"Etapas do Projeto"** (botão no projeto) e expanda a etapa **"Contrato"**.
2. *(Recomendado)* Clique em **"⬇ Abrir PDF"** e confira o contrato.
3. Marque a caixa **"Li o contrato e estou de acordo com os termos"** — isso revela a seção **"Assinaturas:"**.
4. Clique em **"Assinar como loja"** → na janela, preencha **"Nome completo"** e **"CPF"**, marque **"Li e aceito
   os termos do contrato"** e clique **"Confirmar Assinatura"**.
5. **Antes da 2ª assinatura:** preencha o campo **"Data de entrega esperada (cliente)"** (na mesma tela do
   contrato) e clique **"Validar"**. *(Sem isso a assinatura final é recusada.)*
6. Clique em **"Assinar como cliente"** → preencha e clique **"Confirmar Assinatura"**.

**Resultado esperado:** após a 1ª assinatura aparece "(aguardando assinatura)"; após a 2ª aparece
**"✓ Contrato assinado — ambas as partes confirmaram."**

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-C10 — Conferir as etapas do ciclo (Orçamento → Contrato)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Master |
| **Pré-condições** | Contrato assinado (PH-C09) |

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
- [ ] Cenários PH-C01 a PH-C10 marcados ✅ OK.
- [ ] Bugs/estranhezas anotados (com print, se possível).
