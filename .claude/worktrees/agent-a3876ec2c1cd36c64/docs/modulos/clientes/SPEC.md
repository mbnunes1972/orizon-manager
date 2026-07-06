# Módulo de Clientes — SPEC

**Status:** `[IMPLEMENTADO]`

---

## Visão geral

Cadastro centralizado de clientes com endereço completo, busca por nome/CPF, integração com ViaCEP e vinculação obrigatória a projetos.

---

## Funcionalidades

### Lista de clientes
- Exibição em tabela/cards com nome, CPF, cidade e telefone
- Busca em tempo real por nome ou CPF
- Duplo clique no cliente → abre modal com projetos vinculados `[TODO]`
- Botão "Novo cliente"

### Cadastro/Edição
- Modal com todos os campos
- Busca automática de endereço via CEP (API ViaCEP)
- Máscara automática em telefone e WhatsApp
- Validação de CPF único

### Cadastro mínimo na criação
- A criação de um cliente exige apenas **nome + e-mail + telefone**. **CPF é opcional na criação** (assim como o endereço).
- Validação no backend: `validar_cadastro_minimo` (em `POST /api/clientes`). Faltando nome, e-mail ou telefone, retorna HTTP 400 indicando os campos ausentes; o formulário de novo cliente também valida antes do submit.
- CPF e endereço são cobrados **depois**, na aprovação do orçamento / geração do contrato (ver "Cadastro completo antes do contrato"). O cliente nasce com o mínimo e é completado antes de virar contrato.

### Cadastro completo antes do contrato
- Antes da **geração do contrato**, o cadastro precisa estar **COMPLETO**: nome, CPF, e-mail, telefone e **endereço residencial completo** (logradouro, número, bairro, cidade, CEP, UF); endereço de **instalação** quando diferente do residencial.
- Validação no backend: `validar_cliente_para_contrato` (autoridade única do que falta), aplicada no `POST /api/projetos/<nome>/contrato`. Faltando algo, o endpoint retorna **HTTP 400** com a lista `campos_faltando`.
- No frontend, esse 400 dispara o popup **"Cadastro Incompleto"**, listando exatamente os campos faltando retornados pelo backend, com botão **"Abrir Cadastro"** que leva ao painel de cadastro do cliente. O modal de aprovação **não** edita mais dados do cliente — o painel de cadastro é o único lugar para completá-los.

### Vinculação com projetos
- Todo projeto exige um cliente associado (`cliente_id`)
- Ao criar projeto: campo de busca de cliente por nome ou CPF
- Se cliente não existir: botão "+ Cadastrar novo cliente" abre modal com nome pré-preenchido
- Após cadastro, cliente é auto-selecionado no formulário de projeto

---

## Regras de unicidade

`[TODO]` — A implementar:

1. **Verificação por nome:** ao digitar, verificar homônimos (busca case-insensitive)
   - Se houver homônimo: *"Já existe um cliente com este nome. É um homônimo?"*
   - Sim → prosseguir, exigir CPF e email
   - Não → abrir o cliente encontrado

2. **Verificação por CPF:** ao informar CPF, verificar duplicidade
   - Se existir: não permitir cadastro duplicado

3. **Cliente encontrado:** perguntar:
   - *"Este cliente já possui projetos. Deseja abrir um projeto existente ou criar um novo?"*
   - Abrir existente → lista de projetos do cliente
   - Criar novo → formulário de novo projeto vinculado ao cliente

---

## Campos do cadastro

Coluna **"Obrigatório na criação"** = exigido por `validar_cadastro_minimo` ao criar o cliente.
Coluna **"Obrigatório p/ contrato"** = exigido por `validar_cliente_para_contrato` antes de gerar o contrato.

| Campo | Obrig. na criação | Obrig. p/ contrato | Formato | Observação |
|---|---|---|---|---|
| Nome completo | ✓ | ✓ | Texto livre | |
| E-mail | ✓ | ✓ | email@dominio.com | |
| Telefone | ✓ | ✓ | (12) 3811-5199 | Máscara automática |
| CPF | | ✓ | 000.000.000-00 | Único no banco; cobrado antes do contrato |
| WhatsApp | | | (12) 98115-1998 | Máscara automática |
| CEP | | ✓ | 00000-000 | Busca automática ViaCEP |
| Logradouro | | ✓ | Texto | Preenchido pelo CEP (residencial) |
| Número | | ✓ | Texto | Manual |
| Complemento | | | Texto | Manual, opcional |
| Bairro | | ✓ | Texto | Preenchido pelo CEP |
| Cidade | | ✓ | Texto | Preenchido pelo CEP |
| Estado (UF) | | ✓ | 2 letras | Preenchido pelo CEP |
| Endereço de instalação | | condicional | — | Exigido quando difere do residencial (`inst_*`) |
| Observações | | | Texto livre | |

---

## Integração ViaCEP

Ao digitar 8 dígitos no campo CEP:
1. Requisição GET para `https://viacep.com.br/ws/{cep}/json/`
2. Se encontrado: preenche logradouro, bairro, cidade, estado
3. Se não encontrado: exibe mensagem de erro
4. Indicador de carregamento durante a busca

---

## Integração Omie `[TODO]`

- Ao cadastrar cliente, verificar se CPF já existe no Omie via `/buscar_cliente`
- Se existir: importar dados e salvar `omie_codigo`
- Se não existir: cadastrar no Omie ao exportar o primeiro orçamento

---

## Rotas

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/clientes` | Lista todos |
| GET | `/api/clientes/buscar?q=` | Busca por nome ou CPF |
| GET | `/api/clientes/<id>` | Retorna um cliente |
| POST | `/api/clientes` | Cria novo |
| PUT | `/api/clientes/<id>` | Atualiza |
| DELETE | `/api/clientes/<id>` | Remove |

---

## User Stories

**US-CLI-001** — Como consultor, quero cadastrar um novo cliente com todos os seus dados de contato e endereço.

**US-CLI-002** — Como consultor, quero buscar um cliente pelo nome ou CPF para não cadastrar duplicatas.

**US-CLI-003** — Como consultor, quero que o CEP preencha automaticamente o endereço para agilizar o cadastro.

**US-CLI-004** — Como consultor, ao criar um projeto, quero buscar o cliente existente ou cadastrar um novo na mesma tela.

**US-CLI-005** — Como consultor, ao dar duplo clique em um cliente, quero ver seus projetos e poder abrir ou criar um.
