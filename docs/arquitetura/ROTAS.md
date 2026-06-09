# Rotas HTTP — Omie_V3

## Convenções

- Todas as rotas retornam JSON
- Sucesso: `{"ok": true, ...}`
- Erro: `{"ok": false, "erro": "mensagem"}`
- Autenticação via cookie `omie_session`

---

## Autenticação

| Método | Rota | Descrição |
|---|---|---|
| GET | `/login` | Tela de login (HTML) |
| GET | `/logout` | Encerra sessão → redireciona para /login |
| GET | `/api/auth/me` | Retorna usuário da sessão atual |
| POST | `/api/auth/login` | Autentica usuário, seta cookie |
| POST | `/api/auth/logout` | Invalida sessão |
| POST | `/api/auth/verificar_desconto` | Verifica se desconto está dentro do limite |
| POST | `/api/auth/autorizar_desconto` | Autorização delegada com log |

### POST `/api/auth/login`
```json
// Request
{ "login": "pdm2026", "senha": "teste123" }

// Response
{ "ok": true, "token": "...", "usuario": {
    "id": 1, "nome": "Pedro da Mota", "login": "pdm2026",
    "nivel": "diretor", "limite_desconto": 50.0,
    "pode_ver_parametros": true
}}
```

### POST `/api/auth/autorizar_desconto`
```json
// Request
{
  "login_autorizador": "lds2026",
  "senha_autorizador": "teste234",
  "desconto_pct": 18.0,
  "contexto": { "origem": "modal_params" }
}

// Response sucesso
{ "ok": true, "autorizador": {...}, "mensagem": "Desconto de 18.0% autorizado por Luiz da Silva." }

// Response erro
{ "ok": false, "erro": "Usuário ou senha do autorizador inválidos." }
```

---

## Configuração

| Método | Rota | Descrição |
|---|---|---|
| GET | `/config` | Retorna configuração Omie (app_key, app_secret) |
| POST | `/config` | Salva configuração Omie |
| GET | `/perfis` | Retorna configuração de perfis |
| POST | `/perfis` | Salva configuração de perfis |
| GET | `/perfis/ativo` | Retorna perfil ativo |
| POST | `/perfis/ativo` | Define perfil ativo |

---

## Clientes

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/clientes` | Lista todos os clientes |
| GET | `/api/clientes/buscar?q=texto` | Busca por nome ou CPF |
| GET | `/api/clientes/<id>` | Retorna cliente por ID |
| POST | `/api/clientes` | Cria novo cliente |
| PUT | `/api/clientes/<id>` | Atualiza cliente |
| DELETE | `/api/clientes/<id>` | Remove cliente |

### POST `/api/clientes`
```json
// Request
{
  "nome": "João Silva",
  "cpf": "123.456.789-00",
  "email": "joao@email.com",
  "telefone": "(12) 3811-5199",
  "whatsapp": "(12) 98115-1998",
  "cep": "12345-678",
  "logradouro": "Rua das Flores",
  "numero": "123",
  "complemento": "Apto 4",
  "bairro": "Centro",
  "cidade": "São José dos Campos",
  "estado": "SP",
  "observacoes": ""
}
```

---

## Parceiros `[TODO]`

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/parceiros` | Lista todos os parceiros |
| GET | `/api/parceiros/buscar?q=texto` | Busca por nome ou CPF/CNPJ |
| GET | `/api/parceiros/<id>` | Retorna parceiro por ID |
| POST | `/api/parceiros` | Cria novo parceiro |
| PUT | `/api/parceiros/<id>` | Atualiza parceiro |

---

## Projetos

| Método | Rota | Descrição |
|---|---|---|
| GET | `/projetos` | Lista projetos |
| GET | `/projetos/buscar?q=texto` | Busca projetos |
| POST | `/projetos/novo` | Cria novo projeto |
| POST | `/projetos/<nome>/margens` | Salva margens do projeto |
| POST | `/projetos/<nome>/ambientes/adicionar` | Adiciona ambiente via XML |
| POST | `/projetos/<nome>/ambientes/remover` | Remove ambiente |
| POST | `/projetos/<nome>/ambientes/selecao` | Atualiza seleção de ambientes |

### POST `/projetos/novo`
```json
// Request
{
  "nome_projeto": "Apartamento Silva",
  "cliente_id": 1
}

// Response
{ "ok": true, "projeto": { "nome_safe": "apartamento_silva", ... } }
```

### POST `/projetos/<nome>/margens`
```json
// Request
{
  "desconto_pct": 10.0,
  "custo_financeiro_pct": 0.0,
  "fora_da_sede": false,
  "custo_viagem": 0.0,
  "brinde": 0.0,
  "brinde_ativo": false,
  "comissao_arq_pct": 0.0,
  "comissao_arq_ativa": false,
  "fidelidade_pct": 0.0,
  "fidelidade_ativa": false,
  "incluir_custos": false
}
```

---

## Negociação / Cálculos

| Método | Rota | Descrição |
|---|---|---|
| POST | `/calcular_margens` | Calcula margens por ambiente |
| POST | `/calcular_aymore` | Simula financiamento Aymoré |
| POST | `/calcular_cartao` | Simula parcelamento cartão |
| POST | `/calcular_venda_programada` | Simula venda programada |
| POST | `/calcular_total_flex` | Simula Total Flex |
| GET | `/pagamentos` | Lista modalidades de pagamento disponíveis |

---

## Integração Omie

| Método | Rota | Descrição |
|---|---|---|
| POST | `/carregar` | Carrega XMLs do Promob e cria projeto no Omie |
| POST | `/confirm` | Confirma pedido no Omie |
| POST | `/cancel` | Cancela operação em andamento |
| POST | `/exportar` | Exporta orçamento aprovado para o Omie |
| POST | `/buscar_cliente` | Busca cliente na API do Omie pelo CPF |
| POST | `/vincular_cliente` | Vincula cliente Omie ao projeto |
| POST | `/limpar_cliente` | Remove vínculo com cliente Omie |
| GET | `/logs` | Retorna logs da operação em andamento |

---

## Páginas (GET)

| Rota | Descrição |
|---|---|
| `/` | App principal (SPA) — requer autenticação |
| `/login` | Tela de login |
| `/logout` | Encerra sessão |
