# DEV_LOG — Secretária Orizon

**Repositório:** github.com/mbnunes1972/secretaria_orizon  
**VPS:** 167.88.33.121 — porta 8766  
**Stack:** Python 3.12 · Claude API · SQLite · Evolution API (WhatsApp) · Web Speech API

---

## STATUS ATUAL

**Fase:** PLANEJAMENTO CONCLUÍDO — aguardando início do desenvolvimento  
**Próxima ação:** Passo 1 — criar endpoints de leitura no Omie_V3 (main.py)  
**Bugs abertos:** nenhum

---

## DECISÕES ARQUITETURAIS

| Decisão | Escolha | Motivo |
|---|---|---|
| Acesso ao banco Omie_V3 | Endpoints REST (não SQLite direto) | Protege integridade do DB; separação de responsabilidades |
| Canal de alertas | WhatsApp via Evolution API (self-hosted) | Zero custo; controle total no VPS |
| Reconhecimento de voz | Web Speech API (nativo browser) | Sem dependência externa; funciona offline |
| Autenticação | JWT compartilhado com Omie_V3 | Usuário loga uma vez; sem atrito |
| Deploy | systemd (não Docker) | Consistência com Omie_V3 |
| Porta | 8766 | Omie_V3 usa 8765; sem conflito |

---

## CONTEXTO DO PROJETO

A Secretária é um agente operacional da Orizon Soluções. Ela conhece o fluxo
comercial de 38 etapas (6 fases) documentado em:
`omie_v3/docs/processos/FLUXO_38_ETAPAS.md`

Ela NÃO substitui o Omie_V3 — consome dados dele e atua como camada de
inteligência e comunicação sobre o processo.

**Usuários:**
- Diretor (Marcelo) — vê todas as lojas
- Gerentes — veem apenas sua loja
- Consultores — veem apenas suas negociações

**Lojas:**
- São José dos Campos
- Caraguatatuba
- Fortaleza

---

## HISTÓRICO DE SESSÕES

### Sessão 2026-06-15 (sessão 1 — planejamento)

**Objetivo:** Definir arquitetura e criar documentação base

**Realizado:**
- Prototipagem da interface (painel com voz + chat) — aprovado
- Arquitetura definida: Python + Claude API + Evolution API + Web Speech API
- Decisão: endpoints REST no Omie_V3 (não acesso direto ao SQLite)
- Decisão: WhatsApp via Evolution API self-hosted
- Decisão: JWT compartilhado com Omie_V3
- Documentação criada:
  - `docs/modulos/secretaria/SPEC.md`
  - `docs/modulos/secretaria/IMPLEMENTACAO.md`
  - `docs/historias/US_EP08.md`
  - `DEV_LOG.md` (este arquivo)
  - `.bat` para criação da estrutura no Windows

**Próxima sessão:** Iniciar Bloco A — Passo 1 (endpoints no Omie_V3)

---

## BUGS ABERTOS

_Nenhum ainda — desenvolvimento não iniciado._

---

## REFERÊNCIAS

- Omie_V3 DEV_LOG: `omie_v3/DEV_LOG.md`
- Fluxo comercial: `omie_v3/docs/processos/FLUXO_38_ETAPAS.md`
- Protótipo da interface: aprovado na sessão 2026-06-15
- Evolution API docs: https://doc.evolution-api.com
- Claude API docs: https://docs.anthropic.com
