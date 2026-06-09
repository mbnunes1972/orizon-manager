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

| Campo | Obrigatório | Formato | Observação |
|---|---|---|---|
| Nome completo | ✓ | Texto livre | |
| CPF | ✓ | 000.000.000-00 | Único no banco |
| E-mail | | email@dominio.com | |
| Telefone | | (12) 3811-5199 | Máscara automática |
| WhatsApp | | (12) 98115-1998 | Máscara automática |
| CEP | | 00000-000 | Busca automática ViaCEP |
| Logradouro | | Texto | Preenchido pelo CEP |
| Número | | Texto | Manual |
| Complemento | | Texto | Manual, opcional |
| Bairro | | Texto | Preenchido pelo CEP |
| Cidade | | Texto | Preenchido pelo CEP |
| Estado (UF) | | 2 letras | Preenchido pelo CEP |
| Observações | | Texto livre | |

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
