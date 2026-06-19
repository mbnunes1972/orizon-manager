# Spec — Sub-projeto 4: Workflow de Medição

> Omie_V3 | Dalmóbile | Data: 2026-06-18
> Parte 4 de 4 da decomposição (itens 6 e 7). Depende do Sub-projeto 2 (perfis, incl. `medidor`). Status: aprovado para plano.

## Contexto

As etapas do ciclo **9 "Solicitação de medição"** e **10 "Planta de pontos medidos"**
hoje são concluídas por toggle genérico, sem upload nem autorização. Requisitos:

- **(6)** A solicitação de medição (etapa 9) é feita pelo **upload do arquivo de
  solicitação** e confirmada por **senha do medidor**.
- **(7)** Renomear a etapa 10 para **"Medição"**; registrar o **parecer do medidor**
  (Aprovado / Reprovado / Aprovado Parcialmente — neste, campo editável com os
  ambientes aprovados); a liberação exige o **parecer** + o **arquivo promob** (Planta
  de Pontos Medidos). O caso **Reprovado** tem fluxo comercial próprio (abaixo).

A infraestrutura já existe: upload multipart (`_parse_multipart` → `(arquivos, campos)`),
armazenamento (`storage_salvar_binario`, `PROJETOS/<nome>/...`), popup de credenciais
(`pedirCredenciaisGerente`), auditoria (`log_acoes_gerenciais`), perfis (`perfis.py`,
inclui `medidor`).

## Decisões (confirmadas com o usuário)

- **Etapa 9:** operador logado faz o upload; conclusão exige **login+senha do Medidor
  (ou Diretor)** via popup.
- **Quem confirma/registra (etapas 9 e parecer da 10):** Medidor ou Diretor.
- **Parecer Reprovado — dois passos:** (1) medidor registra "Reprovado" + planta →
  etapa fica **em andamento** (não conclui); (2) Gerente de Vendas / Gerente Adm-Fin /
  Diretor anexa o **documento de aprovação do cliente** (upload, exigido só nesse caso)
  + senha → conclui, gravando quem autorizou.
- **Bloquear** a conclusão direta das etapas 9/10 pelo toggle genérico.

## Detalhamento

### 1. Capacidades novas (`perfis.py`)

- `registrar_medicao` = True para `medidor` e `diretor`; False nos demais.
- `aprovar_medicao_reprovada` = True para `gerente_vendas`, `gerente_adm_fin`, `diretor`;
  False nos demais.
- Adicionar ambas as flags a todos os perfis e ao `_DEFAULT` (False por padrão).

### 2. Modelo `Medicao` (`database.py`) — 1 por projeto

```
class Medicao:
    id                        PK
    projeto_nome              (unique)
    # Etapa 9 — solicitação
    solicitacao_arquivo       (nome do arquivo salvo, ou None)
    solicitacao_por           FK usuarios (quem confirmou)
    solicitacao_em            DateTime
    # Etapa 10 — parecer + planta
    parecer                   ("aprovado" | "reprovado" | "parcial" | None)
    ambientes_aprovados       Text (só no parcial)
    planta_arquivo            (nome do arquivo promob)
    medidor_id                FK usuarios
    medicao_em                DateTime
    # Reprovado — decisão comercial
    doc_cliente_arquivo       (nome do arquivo, só no reprovado)
    excecao_por               FK usuarios (quem autorizou a exceção)
    excecao_em                DateTime
```
Tabela criada por `Base.metadata.create_all` (sem migração de dados). Arquivos em
`PROJETOS/<nome_safe>/medicao/`.

### 3. Helpers puros — `mod_medicao.py` (testável)

```python
PARECERES = {"aprovado", "reprovado", "parcial"}

def validar_parecer(parecer, ambientes_aprovados):
    # erro se parecer ∉ PARECERES; erro se parecer == "parcial" e ambientes vazio.
    # retorna lista de erros (vazia se ok).
```

### 4. Backend — endpoints dedicados (`main.py`)

Helper de credencial reutilizável (generaliza o `_aprovador_financeiro`): uma função
que valida login+senha (usuário ativo, senha correta) e uma capacidade de `perfis`.
Sugestão: `_usuario_com_capacidade(db, login, senha, capacidade)` → `Usuario|None`.

- `POST /api/projetos/<nome>/medicao/solicitacao` — multipart: arquivo + `login`/`senha`.
  Valida `registrar_medicao`; salva o arquivo em `medicao/`; grava `solicitacao_*`;
  conclui a etapa 9 (respeitando `pode_avancar`); responsável = confirmador; auditoria
  (`acao="medicao_solicitacao"`). 403 se credencial sem `registrar_medicao`.
- `POST /api/projetos/<nome>/medicao/parecer` — multipart: planta (arquivo) + campos
  `parecer`, `ambientes_aprovados` + `login`/`senha`. Valida `registrar_medicao` e
  `mod_medicao.validar_parecer`; salva planta; grava `parecer`/`ambientes`/`medidor`.
  - `aprovado`/`parcial` → conclui a etapa 10 (responsável = medidor); auditoria.
  - `reprovado` → marca a etapa 10 como **em_andamento** (não conclui); auditoria.
- `POST /api/projetos/<nome>/medicao/decisao-reprovado` — multipart: doc cliente +
  `login`/`senha`. Só válido se `parecer == "reprovado"`. Valida
  `aprovar_medicao_reprovada`; salva doc; grava `excecao_*`; **conclui** a etapa 10;
  auditoria (`acao="medicao_excecao_reprovado"`). 403 se credencial sem a capacidade.
- `GET /api/projetos/<nome>/medicao` → estado da medição (parecer, flags de arquivos
  presentes, nomes, responsáveis) para render dos cards.
- `GET /api/projetos/<nome>/medicao/arquivo/<tipo>` (`solicitacao|planta|doc_cliente`)
  → serve o arquivo (Content-Type/Disposition), gate de sessão.
- **Guard:** no `PATCH /api/projetos/<nome>/ciclo/<codigo>`, se `codigo in {"9","10"}` e
  status conclusivo, rejeitar (400) com mensagem para usar o fluxo de Medição.

### 5. Renomear etapa 10 → "Medição"

- `mod_ciclo.ETAPA_NOME["10"] = "Medição"`.
- Frontend `ETAPAS_CICLO`: item código "10" nome "Medição".

### 6. Frontend (`static/index.html`)

- Card etapa 9: upload do arquivo de solicitação + botão "Confirmar (medidor)" →
  popup `pedirCredenciaisGerente` → `POST /medicao/solicitacao` (multipart). Mostra o
  arquivo já enviado quando houver.
- Card etapa 10: select de parecer (Aprovado/Reprovado/Parcial); campo de ambientes
  visível só no Parcial; upload da planta; botão "Registrar parecer" → credenciais
  (medidor/diretor) → `POST /medicao/parecer`. Se reprovado e ainda pendente, mostra o
  2º passo: upload do documento do cliente + botão "Liberar (decisão comercial)" →
  credenciais (vendas/adm-fin/diretor) → `POST /medicao/decisao-reprovado`.
- Estado carregado por `GET /medicao`; mensagens de erro via `avisoPopup`.

### 7. Auditoria

Cada ação (solicitação, parecer, decisão reprovado) registra em `log_acoes_gerenciais`
quem agiu, projeto, etapa.

## Fora de escopo (YAGNI)

- Parsing/validação do conteúdo dos arquivos promob (apenas armazenamento).
- Tratamento downstream do "Reprovado" além de registrar a decisão e liberar.
- Versionamento de múltiplas medições por projeto (1 registro por projeto; reabrir
  sobrescreve).

## Verificação

- **pytest:** `mod_medicao.validar_parecer` (parcial sem ambientes → erro; parecer
  inválido → erro; aprovado ok); `perfis.pode(slug, "registrar_medicao")` e
  `("aprovar_medicao_reprovada")` para os perfis certos.
- **API real (curl, multipart):** etapa 9 — operador sobe + medidor confirma (ok);
  não-medidor → 403. Etapa 10 — aprovado/parcial concluem (parcial sem ambientes →
  erro); reprovado fica em andamento e só conclui via decisao-reprovado com senha
  gerencial (medidor sozinho não conclui reprovado); guard do PATCH genérico 9/10 →
  400; auditoria registrada. Suíte completa verde.

## Processo

Pipeline superpowers: spec → plano (writing-plans) → implementação com revisão a nível
de controlador → verificação (pytest + API real) → merge local.
