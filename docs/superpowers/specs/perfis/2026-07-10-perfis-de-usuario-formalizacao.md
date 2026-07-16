# Perfis de Usuário — formalizar os níveis de acesso (Admin)

**Data:** 2026-07-10 · **Status:** implementado (Sessão 60) · **Suíte:** 816 verdes

A "frente irmã" do §8 (Regras_Funcoes_Perfis): dar rosto de primeira classe ao que `perfis.py` **já**
governa. Não é um editor nem muda o modelo de acesso — é **surface + documentação** read-only da fonte
única. Continuação natural da Fase 0 (perfis.py como fonte única).

## O que já existia (mostrado ao usuário)
`perfis.py` = 12 perfis com uma matriz de capacidades (`ver_parametros`, `autorizar`,
`aprovar_financeiro`, `gerir_usuarios`, `registrar_medicao`, `aprovar_medicao_reprovada`,
`editar_dados_loja`, `executar_pe`, `revisar_pe`, `gerir_redes`, `gerir_lojas`) + `desconto_max`. Já
governa todo o enforcement. Faltava apenas expor/nomear.

## Mudanças
- **`perfis.py`:** `CAPACIDADES` (metadados legíveis: `slug → {rotulo, descricao, grupo}`) + `matriz()`
  (perfis com capacidades resolvidas, escopo loja/plataforma, desconto_max) — derivado de `PERFIS`,
  read-only. Fonte de verdade continua sendo `PERFIS`.
- **`main.py`:** `GET /api/admin/perfis-matriz` — serve `matriz()` + metadados; gate `gerir_usuarios`.
- **`static/index.html`:** a aba **Admin › Perfis de Usuário** (que existia com a ferramenta legada de
  "perfil ativo" single-user + editor de desconto — vestigial desde a Fase 0) foi **substituída** pela
  matriz real: tabela perfil × capacidades (chips com rótulos amigáveis), escopo, desconto máx +
  legenda "o que cada capacidade significa". Read-only. Isso aposenta a tela legada (`cfgSetPerfil`/
  `cfgRenderizarPerfis`/`cfgSalvarLimites` ficam sem uso).
- **`docs/USUARIOS.md`:** nota sobre a tela e os três eixos (Perfil × Função × Escopo).

## Testes (`tests/test_perfis_matriz.py`)
- Todo slug de capacidade usado em `PERFIS` tem metadado em `CAPACIDADES` (e todo metadado é uma
  capacidade real do `_DEFAULT) — trava anti-inconsistência.
- Cada capacidade tem rótulo/descrição/grupo.
- `matriz()` deriva de `perfis.py` (diretor=autorizar/50%/loja; consultor=[]/10%; super_admin fora da
  loja).
- Endpoint: gate `gerir_usuarios` (diretor 200; consultor 403).

## Fora de escopo (mantido para o futuro)
Editor de perfis por loja / definição de acessos por módulo (REQUIREMENTS P1) — esta frente só
**formaliza o que já roda**.
