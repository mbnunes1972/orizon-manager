# Modulos_Orizon_v12 — Responsável por função no Cronograma + Função×Perfil em Usuários da Loja

**Data:** 2026-07-10 · **Status:** implementado (Sessão 57) · **Suíte:** 793 verdes

Três frentes do v12 (as demais seções do doc são contexto/futuro).

## 1. Usuários da Loja — Função × Perfil (correção)

**Achado (surfaced ao usuário):** a coluna "Perfil" da tela Usuários da Loja bindava `Usuario.nivel`,
que **é** o campo de controle de acesso (`perfis.py` deriva toda permissão dele) — não uma função de
cargo. A premissa do spec ("Perfil guarda Função") estava factualmente invertida. Decisão do usuário
(Opção 1): **não** renomear nivel; adicionar **Função** separada.

- **Função** (coluna nova na tela): `funcao_nome` **derivada** do Funcionário vinculado
  (`Usuario.funcionario_id → Funcionario.funcao_id → Funcao.nome`) — referenciada, **não duplicada** no
  Usuário. Vazia ("—") para contas sem Funcionário vinculado.
- **Perfil** (mantido): `Usuario.nivel` — nível de acesso, **inalterado**, segue acionando `perfis.py`.
- Backend: `/api/admin/usuarios` serializa `funcao_nome` (batch). Frontend: coluna "Função" na tabela.

> Pendência anotada (não desta frente): ao formalizar os níveis de acesso, **partir do que já existe em
> `perfis.py`** (já construído) em vez de desenhar do zero.

## 2. Cronograma de Projeto Padrão (Config) — função responsável por fase

- `config_financeira_json.cronograma_padrao[*].funcao_id` (→ Tabela de Funções) — a **função** que
  executa a fase (ex.: Medição → Medidor), não uma pessoa. `mod_cronograma.cronograma_padrao` normaliza.
- Config → Cronograma: cada fase ganha um dropdown **Função responsável** (do catálogo `/api/funcoes`),
  ao lado do prazo. Prazo segue editável só por Gerente/Diretor com reautenticação (v11).

## 3. Cronograma do Projeto — funcionário específico filtrado por função

- `CicloEtapa.funcao_responsavel_id` (herdada do padrão no D0) + `responsavel_funcionario_id` (nasce
  vazio). Migração idempotente.
- `mod_cronograma.gerar_cronograma_projeto` herda `funcao_responsavel_id` de cada fase no D0 (não
  sobrescreve funcionário já escolhido).
- `POST /api/projetos/<nome>/ciclo/<cod>/responsavel {funcionario_id}` — valida que o funcionário
  pertence à loja **e tem a função exigida** (`funcao_id == funcao_responsavel_id`); vazio limpa.
- `GET /api/funcionarios?funcao_id=X` — filtra o dropdown pela função exigida.
- `/ciclo` serializa `funcao_responsavel_id/nome` + `responsavel_funcionario_id/nome`.
- Frontend: cada card de etapa mostra "Responsável — função <X>: <select>" (só funcionários da função;
  aviso se nenhum). O select persiste via o endpoint.

## Testes
- `tests/test_cronograma.py`: herança de função no D0; restrição por função (Montador barrado em fase de
  Medidor, Medidor aceito); `/ciclo` expõe função+funcionário; filtro `?funcao_id`; `funcao_nome` em
  Usuários da Loja com Perfil (nivel) inalterado.

## Notas de decisão
- **Função derivada, não duplicada** — em Usuário e no Cronograma do Projeto a função vem do cadastro do
  Funcionário; o Cronograma só referencia por id.
- **Perfil (nivel) intocado** — evita qualquer risco ao controle de acesso; a formalização dos níveis
  fica para uma etapa seguinte, partindo de `perfis.py`.
