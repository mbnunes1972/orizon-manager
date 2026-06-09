# Backlog — Omie_V3

Funcionalidades ordenadas por prioridade. Atualizar a cada sessão de desenvolvimento.

---

## 🔴 Alta prioridade (próximas sprints)

| ID | Módulo | Descrição | Status |
|---|---|---|---|
| US-NEG-BUG-001 | Negociação | Bug: toggle "Incluir custos adicionais?" não persiste entre aberturas do modal | `[BUG]` |
| US-PAR-001 | Parceiros | Cadastro completo de parceiros | `[TODO]` |
| US-PAR-002 | Parceiros | Vincular parceiro ao projeto | `[TODO]` |
| US-PAR-003 | Parceiros | Comissão do parceiro preenche modal automaticamente | `[TODO]` |
| US-CLI-005 | Clientes | Duplo clique no cliente abre projetos vinculados | `[TODO]` |
| US-PRJ-005 | Projetos | Ordenação por data de alteração + botão inverter | `[TODO]` |
| US-PRJ-006 | Projetos | Botão "Novo ambiente" bloqueado em Clientes e Projetos | `[TODO]` |
| US-CLI-UNI | Clientes | Regras de unicidade: homônimos, CPF duplicado, cliente já cadastrado | `[TODO]` |
| US-FIN-BOL | Financeiro | Boleto parcelado até 4x sem juros | `[TODO]` |

---

## 🟡 Média prioridade

| ID | Módulo | Descrição | Status |
|---|---|---|---|
| US-CON-001 | Contratos | Geração automática de contrato após aprovação | `[TODO]` |
| US-CON-002 | Contratos | Fluxo de revisão e assinatura | `[TODO]` |
| US-KAN-001 | Kanban | Pipeline comercial visual | `[TODO]` |
| US-PRJ-006 | Projetos | Particionamento de ambientes | `[TODO]` |
| US-OMIE-001 | Integração | Cadastro automático de cliente no Omie | `[TODO]` |
| US-AUTH-006 | Autenticação | Módulo de configuração de perfis (admin) | `[TODO]` |
| US-DEP-001 | Deploy | Script deploy.sh automatizado no servidor | `[TODO]` |
| US-DEP-002 | Deploy | Variável de ambiente OMIE_HOST (eliminar sed) | `[TODO]` |

---

## 🟢 Baixa prioridade / Futuro

| ID | Módulo | Descrição | Status |
|---|---|---|---|
| US-PV-001 | Pós-venda | Módulo de medição | `[TODO]` |
| US-PV-002 | Pós-venda | Módulo de projeto executivo | `[TODO]` |
| US-PV-003 | Pós-venda | Módulo de implantação e produção | `[TODO]` |
| US-PV-004 | Pós-venda | Módulo de entrega e montagem | `[TODO]` |
| US-PV-005 | Pós-venda | Módulo de assistência técnica | `[TODO]` |
| US-KAN-002 | Kanban | Pipeline operacional (pós-venda) | `[TODO]` |
| US-DB-001 | Banco | Migração SQLite → MySQL | `[TODO]` |
| US-CLI-MOD | Clientes | Módulo de acesso do cliente (acompanhamento) | `[TODO]` |
| US-REDE-001 | Rede | Instância superior para rede de lojas (multi-tenant) | `[TODO]` |
| US-REL-001 | Relatórios | Relatórios gerenciais para Diretor de Rede | `[TODO]` |

---

## ✅ Concluído

| ID | Módulo | Descrição |
|---|---|---|
| US-AUTH-001 | Autenticação | Login/logout com sessão |
| US-AUTH-002 | Autenticação | Três níveis de acesso |
| US-AUTH-003 | Autenticação | Autorização delegada de desconto |
| US-AUTH-004 | Autenticação | Botão de perfil com foto e dados |
| US-NEG-001 | Negociação | Limites de desconto por nível |
| US-NEG-002 | Negociação | Botão OK na sidebar para autorização |
| US-NEG-003 | Negociação | Toggle "Incluir custos adicionais?" |
| US-NEG-004 | Negociação | Valor bruto = original dos XMLs |
| US-NEG-005 | Negociação | Desconto Total sobre bruto original |
| US-CLI-001 | Clientes | Cadastro completo com endereço |
| US-CLI-002 | Clientes | Busca por nome ou CPF |
| US-CLI-003 | Clientes | CEP com busca automática ViaCEP |
| US-CLI-004 | Clientes | Projeto exige cliente obrigatório |
