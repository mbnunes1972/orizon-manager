# Modulos_Orizon_v11 — Cronograma do Ciclo (acesso corrigido + automação)

**Data:** 2026-07-10 · **Status:** implementado (Sessão 55) · **Suíte:** 790 verdes

Documento como-implementado da seção **Cronograma do Ciclo** do `Modulos_Orizon_v11.docx`. As demais
seções do v11 (reorg de módulos, Captação, Estoque, etc.) são contexto/futuro — fora desta frente.

## 1. Correção de acesso às etapas (trava só a edição)

**Bug:** etapas futuras ficavam **inacessíveis** — `renderCiclo` suprimia o `onclick` do cabeçalho do
card quando `bloqueada` (etapa cuja anterior não está concluída), então não dava nem para expandir.

**Correção (frontend):** o cabeçalho do card é **sempre clicável**. Resultado, por estado:
- **Futura:** visível/expansível, corpo em leitura ("🔒 Conclua a etapa anterior"), indicador de cadeado.
- **Atual:** visível + edição completa (inalterado).
- **Concluída:** já era visível; mantém "✓ Concluído". Nunca escondida.

`bloqueada` mantém seu significado ("futura — conclua a anterior"), usado pelos corpos de card para
esconder ações; só a inacessibilidade do cabeçalho foi removida.

## 2. Datas por etapa

- `CicloEtapa.data_prevista_conclusao` (nova coluna, migração idempotente).
- `data_conclusao` = `CicloEtapa.concluido_em` (reuso — já era preenchida ao concluir).
- `/ciclo` serializa ambas; cada card mostra 📅 prevista e ✓ concluída.

## 3. Cronograma de Projeto Padrão (Config)

- `config_financeira_json.cronograma_padrao`: lista `{codigo, prazo_dias}` (dias a partir de D0) por
  etapa. Default em `mod_provisoes.config_financeira_default()` (etapas 8–20).
- **Config → Cronograma** (nova aba): edita o prazo de cada etapa; salva via
  `PUT /api/admin/lojas/<id>/config-financeira` (mesmo canal das provisões/comissão).
- GET config-financeira e `_cfg_financeira_loja` fazem **merge com o default** → lojas com config
  anterior ao v11 ganham `cronograma_padrao` sem perder o que já tinham.

## 4. Gatilho — assinatura do contrato (D0)

Decisão do usuário: **D0 = assinatura total** (ambas as partes) — o ponto onde a etapa 7 conclui e o
projeto vai a "fechado". No mesmo bloco, `mod_cronograma.gerar_cronograma_projeto(db, projeto, cfg, D0)`
cria/atualiza `data_prevista_conclusao = D0 + prazo` para cada etapa do Cronograma Padrão. Idempotente
(recomputa do D0, preserva `concluido_em`), **fail-soft** (não bloqueia a assinatura).

## 5. Edição de `data_prevista_conclusao` — reautenticação + auditoria

- `POST /api/projetos/<nome>/ciclo/<codigo>/data-prevista` `{login, senha, data_prevista}`.
- **Reautenticação Gerente+**: `Usuario.check_senha` + `perfis.pode(nivel, "autorizar")` (diretor /
  gerente_vendas) — mesmo padrão dos gates financeiros.
- **Auditoria**: `LogAcaoGerencial(acao="editar_data_prevista", projeto_nome, etapa_alvo, contexto=
  {valor_antigo, valor_novo})` — quem/quando/old→new.
- **Frontend**: o lápis de edição só aparece para Gerente+ (`_podeAutorizarFront`); abre modal
  `modal-crono` que confirma a senha do próprio usuário.

## Testes
- `tests/test_cronograma.py`: motor (data prevista = D0+prazo, normalização, idempotência preservando
  conclusão) + HTTP (reauth Gerente edita e audita; consultor barrado; senha errada barrada).
- `tests/test_provisoes.py`: default passa a incluir `cronograma_padrao`.

## Notas de decisão
- **data_conclusao reusa concluido_em** — evita coluna redundante.
- **Concluída sem edição** (bloqueio pleno de edição em etapas concluídas): não incluído nesta frente —
  exigiria reescrever ~15 renderizadores de card com um flag distinto de `bloqueada` (que hoje significa
  "conclua a anterior"), em fluxo sensível sem teste visual. O acesso (bug reportado) está corrigido;
  travas de edição pós-conclusão já existem pontualmente (ex.: parceiro após assinatura).
