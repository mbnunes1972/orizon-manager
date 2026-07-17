# Roteiro de Pré-Homologação — Setup de Loja/Rede + Usuários

**Ambiente:** PRÉ-HOMOLOGAÇÃO — `http://167.88.33.121:8766` · **Fluxo:** criar rede, lojas e usuários (base de tudo).
**Formato:** cada cenário é para um testador **leigo** executar clicando exatamente o que está escrito, e
marcar ✅ OK / ❌ NOK + observação. Ver o *template* na `2026-07-16-plano-de-testes.md` (Seção 4).

> ⚠️ **Antes de começar — três coisas que confundem:**
> 1. **Login é o CÓDIGO, não o e-mail.** O campo se chama "E-mail" e mostra um exemplo de e-mail, mas você
>    digita o **código de login** (ex.: `sad2026`). Ignore o formato de e-mail.
> 2. **Criar Rede e Loja abre uma "janelinha" do navegador** (aquele pop-up cinza de digitar texto), não um
>    formulário bonito dentro do sistema. É normal.
> 3. **"PDV" não existe como item separado** no sistema — só existem **Rede** e **Loja**. Neste roteiro o
>    "PDV" é criado como **mais uma loja**. *(A confirmar com o responsável se o PDV deve ser tratado diferente.)*

**Usuários já existentes no ambiente (criados pela carga inicial):**

| Papel | Login | Senha | Nível |
|-------|-------|-------|-------|
| Administrador da Plataforma | `sad2026` | `trocar123` | super_admin |
| Master (loja) | `pdm2026` | `teste123` | Master |
| Gerencial (loja) | `lds2026` | `teste234` | Gerencial |
| Operador (loja) | `mds2026` | `teste345` | Operador |

---

## PH-01 — Entrar no sistema como Administrador da Plataforma

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Administrador da Plataforma (super_admin) |
| **Pré-condições** | Ter o endereço `http://167.88.33.121:8766` aberto no navegador |

**Passos:**
1. Abra `http://167.88.33.121:8766` — vai aparecer a página de entrada.
2. Clique no botão **"Entrar"** (no topo ou no CTA "Acessar minha conta").
3. No campo **"E-mail"**, digite exatamente: `sad2026` *(é o código de login, não um e-mail)*.
4. No campo **"Senha"**, digite: `trocar123`.
5. Clique no botão **"Entrar"**.

**Resultado esperado:** você entra no sistema. Na barra lateral escura à esquerda aparece a seção **"Admin"**
com o item **"Admin"** (engrenagem). A trilha no topo mostra **"Plataforma"**.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-02 — Criar uma Rede

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Administrador da Plataforma |
| **Pré-condições** | Ter feito o PH-01 (estar logado) |

**Passos:**
1. Na barra lateral, clique em **"Admin"** (engrenagem).
2. Confirme que a trilha no topo mostra **"Plataforma"**. Localize o quadro **"Redes"** (deve dizer "Nenhuma rede.").
3. Clique no botão **"+ Nova rede"**.
4. Vai abrir uma **janelinha do navegador** perguntando **"Nome da rede:"** — digite: `Rede Dalmóbile` e confirme (OK).
5. Abre outra janelinha **"CNPJ (opcional):"** — pode deixar em branco e confirmar (OK).

**Resultado esperado:** aparece a mensagem **"Rede criada."** e a rede **"Rede Dalmóbile"** passa a aparecer na
tabela (colunas "Nome" e "CNPJ"), com um botão **"Entrar ›"** ao lado.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-03 — Criar as 4 lojas + o "PDV" (5 lojas no total)

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Administrador da Plataforma |
| **Pré-condições** | Ter criado a rede (PH-02) |

> **Nota:** cada loja precisa de um **código de 3 letras único** (usado na numeração do contrato). Repita os
> passos abaixo **5 vezes**, uma por loja da lista.

**Lista de lojas a criar (nome → código):**
1. `Dalmóbile São José` → `DSJ`
2. `Dalmóbile Taubaté` → `DTA`
3. `Dalmóbile Jacareí` → `DJA`
4. `Dalmóbile Caçapava` → `DCA`
5. `PDV Shopping` → `PDV`  *(este é o "PDV" — criado como loja)*

**Passos (repetir para cada loja da lista):**
1. Na trilha do topo, clique em **"Rede Dalmóbile"** (para operar dentro da rede) — ou clique **"Entrar ›"** na linha da rede.
2. Localize o quadro **"Lojas da rede"** e clique em **"+ Nova loja"**.
3. Na janelinha **"Nome da loja:"**, digite o **nome** da loja (ex.: `Dalmóbile São José`) e confirme.
4. Na janelinha **"Código (3 letras, único…):"**, digite o **código** (ex.: `DSJ`) e confirme.
5. Confirme a mensagem **"Loja criada."** e repita para a próxima loja da lista.

**Resultado esperado:** ao final, a tabela **"Lojas da rede"** mostra as **5 lojas** (nome + código), cada uma
com botão **"Entrar ›"**.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-04 — Criar um usuário dentro de uma loja

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Administrador da Plataforma |
| **Pré-condições** | Ter as lojas criadas (PH-03) |

**Passos:**
1. Na tabela de lojas, clique em **"Entrar ›"** na loja **"Dalmóbile São José"**.
2. Clique na aba **"Usuários da loja"**.
3. Clique no botão **"+ Novo usuário"** — abre a janela **"Novo usuário"**.
4. Preencha:
   - **Nome:** `Maria Consultora`
   - **Login:** `maria.dsj`
   - **Senha:** `teste123`
   - **Perfil:** escolha **"Operador"** na lista *(Operador = consultor de vendas; as opções são Master, Gerencial, Operador)*.
   - Os demais campos (Telefone, E-mail, CPF…) são opcionais.
5. Clique no botão de salvar da janela.

**Resultado esperado:** aparece **"Usuário criado."** e **"Maria Consultora"** passa a aparecer na lista de
usuários da loja. *(Opcional: repita criando um **"Master"** e um **"Gerencial"** para testar os 3 níveis.)*

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## PH-05 — Administrador "entrar" numa loja e depois voltar

| Campo | Conteúdo |
|-------|----------|
| **Persona** | Administrador da Plataforma |
| **Pré-condições** | Ter lojas criadas (PH-03) |

> **Contexto:** o Administrador da Plataforma não tem loja própria; ele "entra" numa loja para operar dentro
> dela. Não existe um seletor de loja no topo para este caso — usa-se o **"Entrar ›"** do console Admin.

**Passos:**
1. No console **"Admin"**, na tabela de lojas, clique **"Entrar ›"** em **"Dalmóbile Taubaté"**.
2. Observe a **trilha no topo**: deve passar a mostrar **"…› Dalmóbile Taubaté"**.
3. Para sair da loja, clique em **"Rede Dalmóbile"** (ou **"Plataforma"**) na própria trilha.

**Resultado esperado:** ao entrar, a trilha mostra o nome da loja e você opera **dentro** dela; ao clicar no
nível acima da trilha, você volta ao contexto da rede/plataforma.

**Registro:** ☐ OK ☐ NOK — Observação: __________________________________

---

## Encerramento
- [ ] Todos os cenários acima marcados ✅ OK.
- [ ] Bugs/estranhezas anotados nas observações (com print, se possível).
- Próximo roteiro: **`roteiro-PH-ciclo-venda.md`** (a venda de ponta a ponta), que usa uma dessas lojas e um
  usuário criado aqui.
