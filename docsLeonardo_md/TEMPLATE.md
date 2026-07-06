# Template de User Story

---

## Formato padrão

```
ID: US-[MÓDULO]-[NÚMERO]
Título: [Título curto]
Status: [TODO] / [IMPLEMENTADO] / [BUG] / [CANCELADO]

Como [tipo de usuário],
Quero [ação ou funcionalidade],
Para que [benefício ou objetivo].

Critérios de aceite:
- [ ] [Critério 1]
- [ ] [Critério 2]
- [ ] [Critério 3]

Regras de negócio:
- [Regra 1]
- [Regra 2]

Notas técnicas:
- [Observação relevante para implementação]

Dependências:
- [US-XXX-YYY] — outra story que deve ser concluída antes
```

---

## Exemplo preenchido

```
ID: US-CLI-002
Título: Buscar cliente por nome ou CPF
Status: [IMPLEMENTADO]

Como consultor,
Quero buscar um cliente pelo nome ou CPF,
Para que eu não cadastre o mesmo cliente duas vezes.

Critérios de aceite:
- [x] Campo de busca filtra em tempo real
- [x] Busca funciona por nome parcial (case-insensitive)
- [x] Busca funciona por CPF com ou sem formatação
- [ ] Se houver homônimo, sistema pede confirmação com CPF/email

Regras de negócio:
- CPF deve ser único no banco
- Nomes homônimos são permitidos desde que o CPF seja diferente

Notas técnicas:
- Rota: GET /api/clientes/buscar?q=texto
- Busca em campos: nome, cpf

Dependências:
- US-CLI-001 — Cadastrar cliente
```

---

## Prefixos por módulo

| Módulo | Prefixo |
|---|---|
| Autenticação | US-AUTH |
| Clientes | US-CLI |
| Parceiros | US-PAR |
| Projetos | US-PRJ |
| Negociação | US-NEG |
| Financeiro | US-FIN |
| Contratos | US-CON |
| Kanban | US-KAN |
| Integração Omie | US-OMIE |
| Medição | US-MED |
| Projeto Executivo | US-PE |
| Implantação | US-IMP |
| Produção | US-PROD |
| Entrega | US-ENT |
| Montagem | US-MON |
| Assistência | US-ASS |
