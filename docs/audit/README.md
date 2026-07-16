# Auditoria Florence — Orizon Manager

Auditoria profunda, estilo Florence, do sistema Orizon Manager / Dalmóbile sob a ótica de **produção enterprise-grade**. Realizada em **2026-07-03** por 8 auditorias independentes em paralelo. Cada documento é autocontido, com evidências `arquivo:linha`, severidade (🔴 Crítico / 🟠 Alto / 🟡 Médio / 🔵 Baixo / ℹ️ Info) e recomendações concretas.

## 👉 Comece aqui
**[00 — Sumário Executivo](00-sumario-executivo.md)** — veredito, placar consolidado, temas críticos transversais e roteiro de remediação em 3 ondas.

## Relatórios
| # | Documento | Foco | 🔴 | 🟠 |
|---|-----------|------|:--:|:--:|
| 01 | [Arquitetura](01-arquitetura.md) | Monólito `main.py`, schema, camadas, tenancy, config | 4 | 5 |
| 02 | [Qualidade — Financeiro](02-qualidade-financeiro.md) | Negociação, provisões, Aymoré, cartão, total flex, margens | 2 | 3 |
| 03 | [Qualidade — Contrato/Ciclo/Integração](03-qualidade-dominio.md) | Contrato/PDF, ciclo, árvore, Omie, XML Promob | 2 | 5 |
| 04 | [Segurança](04-seguranca.md) | AuthN/AuthZ, tenancy, injection, segredos, upload | 4 | 5 |
| 05 | [Performance](05-performance.md) | Concorrência, banco/índices, N+1, I/O por request | 3 | 6 |
| 06 | [Dívida Técnica](06-divida-tecnica.md) | Inventário: TODOs, mocks, hardcodes, debug, código morto | 2 | ~9 |
| 07 | [Dependências & Testes](07-dependencias-testes.md) | Pins/CVEs/supply-chain, cobertura, CI | 6 | 5 |
| 08 | [Frontend (SPA)](08-frontend.md) | `static/index.html` — XSS, estado, sustentabilidade | 1 | 4 |

**Total aproximado:** ~120 achados (~24 críticos, ~42 altos).

## Veredito em uma linha
Núcleo de domínio (cálculo financeiro + tenancy de negócio) em **nível gold e bem testado**; a plataforma ao redor (segredos, autenticação de infra, concorrência, engenharia de release, frontend) tem **lacunas críticas** a resolver antes de operar como multiusuário/multiloja exposto. Ver Onda 1 do sumário.

## Metodologia e limites
- Análise **estática** (leitura de código + sondas pontuais); a suíte não foi executada como parte da auditoria.
- Análise de CVEs por conhecimento, **não** por scan ao vivo — recomenda-se `pip-audit`/Dependabot.
- Excluídos da análise: `.claude/worktrees/` (snapshot duplicado), `.git`, `__pycache__`, `.pytest_cache`, `*.bak*`.
- Nenhum código, banco ou configuração foi modificado durante a auditoria.
