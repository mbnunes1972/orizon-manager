# Módulo de Integração Omie — SPEC

**Status:** `[IMPLEMENTADO]` (parcial)

---

## Visão geral

Integração entre o sistema Omie_V3 e o ERP Omie para envio de pedidos de venda.

---

## Fluxo de exportação

```
Orçamento aprovado no Omie_V3
    → XMLs do Promob classificados em grupos
    → Grupos enviados como itens do pedido (R$1,00 × subtotal)
    → Pedido criado no Omie via API
    → Código do pedido salvo no projeto.json
```

---

## Grupos de produtos

Os itens do Promob são classificados em **16 grupos padronizados**. Cada grupo é cadastrado no Omie como um produto com:
- Valor unitário: R$ 1,00
- Quantidade: igual ao subtotal do grupo em R$

`[VALIDAR]` — Os 16 grupos estão documentados em `promob_grupos.py`. Confirmar se estão corretos.

---

## API Omie

### Configuração
- App Key e App Secret configurados na sidebar do sistema
- Visíveis apenas para perfil Diretoria

### Limites
- Rate limit: 240 requisições por minuto
- HTTP 425: bloqueio por rate limit — sistema aguarda e tenta novamente

### Endpoint principal
- `IncluirPedVenda` — criação de pedido de venda

### Regras de NCM
- NCMs enviados **sem** pontuação (só números)

---

## Busca de cliente no Omie

- Rota: `POST /buscar_cliente`
- Busca por CPF na API do Omie
- Se encontrado: retorna código do cliente para vinculação
- Se não encontrado: cliente será cadastrado no Omie automaticamente ao exportar

---

## Status da integração

| Funcionalidade | Status |
|---|---|
| Envio de pedido de venda | `[IMPLEMENTADO]` |
| Busca de cliente por CPF | `[IMPLEMENTADO]` |
| Cadastro automático de cliente | `[TODO]` |
| Sincronização bidirecional de clientes | `[TODO]` |
| Pedidos de compra (pós-venda) | `[TODO]` |
| Emissão de NF | `[TODO]` |

---

## Arquivos relevantes

- `mod_omie.py` — funções de integração com API Omie
- `promob_grupos.py` — classificação de grupos Promob
- `omie_config.json` — credenciais (não versionar)
- `omie_grupos_cache.json` — cache dos grupos cadastrados no Omie
