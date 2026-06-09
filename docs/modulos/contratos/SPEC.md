# Módulo de Contratos — SPEC

**Status:** `[TODO]`

---

## Visão geral

O módulo de contratos gerencia a geração, assinatura e aprovação dos contratos de venda após a aprovação do orçamento. Segue o fluxo padrão de mercado para contratos de móveis planejados.

---

## Fluxo do contrato

```
Orçamento aprovado
    → Geração do contrato (automática)
    → Revisão interna (gerente)
    → Envio ao cliente
    → Assinatura do cliente
    → Confirmação da assinatura
    → Contrato vigente → Pós-venda inicia
```

---

## Tipos de contrato

| Tipo | Descrição |
|---|---|
| Contrato de Venda | Documento principal — condições comerciais, valores, prazo |
| Folha de Capa | Resumo do projeto com ambientes e valores `[VALIDAR]` |
| Termo de Venda Programada | Específico para modalidade Venda Programada |
| Projeto Executivo | Aprovação técnica — gerado na fase de pós-venda |

---

## Dados do contrato

O contrato é gerado automaticamente com base nos dados do projeto aprovado:

- **Partes:** dados da loja + dados do cliente
- **Objeto:** lista de ambientes com valores
- **Valor total:** conforme orçamento aprovado
- **Forma de pagamento:** conforme modalidade selecionada
- **Cronograma de pagamento:** parcelas com datas
- **Prazo de entrega:** `[VALIDAR]` — definir prazo padrão por tipo de produto
- **Condições gerais:** cláusulas padrão da Dalmóbile `[VALIDAR]`

---

## Geração do contrato `[TODO]`

**Opções de implementação:**
1. Geração de PDF via Python (`reportlab` ou `weasyprint`)
2. Preenchimento de template Word (`.docx`) via `python-docx`
3. HTML para PDF via navegador

**Recomendação:** usar template Word (`.docx`) — já existe infraestrutura no projeto para geração de documentos Word.

---

## Assinatura `[TODO]`

**Opções:**
1. Assinatura presencial — imprimir, assinar, digitalizar
2. Assinatura digital simples — upload de documento assinado
3. Integração com plataforma de assinatura eletrônica (DocuSign, ClickSign, D4Sign) `[VALIDAR preferência]`

---

## Status do contrato

| Status | Descrição |
|---|---|
| `gerado` | Contrato gerado, aguardando revisão |
| `revisado` | Aprovado internamente pelo gerente |
| `enviado` | Enviado ao cliente |
| `assinado` | Cliente assinou |
| `vigente` | Em vigor — pós-venda pode iniciar |
| `cancelado` | Contrato cancelado |

---

## Repositório de modelos `[TODO]`

- Templates de contrato armazenados em `templates/contratos/`
- Cada modelo é um arquivo `.docx` com campos marcados para preenchimento automático
- `[VALIDAR]` — quais modelos existem atualmente na Dalmóbile?

---

## User Stories

**US-CON-001** — Como gerente, quero gerar automaticamente o contrato após a aprovação do orçamento.

**US-CON-002** — Como gerente, quero revisar e aprovar o contrato antes de enviá-lo ao cliente.

**US-CON-003** — Como consultor, quero registrar a assinatura do cliente no sistema.

**US-CON-004** — Como qualquer usuário, quero consultar o histórico de contratos de um projeto.
