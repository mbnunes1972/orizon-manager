# Fase 4 — Comissão por Papel (Mapa/Etapa) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao concluir cada etapa operacional do ciclo, preparar automaticamente a comissão do executor daquela etapa na folha do mês de conclusão — como item editável — e somá-la à parte variável da folha, unificando a comissão do Consultor como um item de origem `venda`.

**Architecture:** Nova tabela `comissao_folha` (itens de comissão por funcionário/competência). Um novo módulo `mod_comissao.py` resolve papel↔etapa, a base (Σ `order_total` dos ambientes atribuídos no Mapa) e o % da Função, criando/atualizando itens **idempotentes por `ref_etapa`**. O gatilho fica em `_set_etapa_status` (caminho central de conclusão). `mod_folha.gerar_folha` passa a somar os itens em `parte_variavel`; o Consultor vira um item `origem='venda'`. Contábil inalterado (simples: 5.3.01 na paga).

**Tech Stack:** Python (http.server + SQLAlchemy), pytest (SQLite; suíte também validada em Postgres), frontend single-file `static/index.html`.

**Convenções do repo (obrigatório):**
- Coluna nova em tabela existente → `_add_cols` (SQLite) **e** `_migrar_colunas_pg` (Postgres). **Tabela nova** é criada por `create_all()` em ambos os dialetos — confirmar que `init_db()` cria `comissao_folha` no Postgres (Task 1 verifica).
- Backend TDD. Frontend via `node --check` (maior `<script>` no WSL).
- Worktree sob `.claude/worktrees/`; FF-merge para `main`. Não commitar `perfis_config.json`; não tocar WIP de migração do usuário. Push só quando pedido.

---

## Fontes de dados existentes (não recriar)
- **`CicloEtapa`**: `concluido_em`, `funcao_responsavel_id` (Função executora), `responsavel_funcionario_id` (executor). Conclusão passa por `_set_etapa_status(db, nome_safe, codigo, status, responsavel_id)` (`main.py:305`), que seta `concluido_em` quando `status ∈ mod_ciclo.STATUS_CONCLUSIVOS`.
- **`atribuicoes_ambiente`** (Mapa): `papel`, `funcionario_id`, `pool_ambiente_id` (NULL = projeto inteiro), `projeto_nome`.
- **`PoolAmbiente`**: `projeto_id` (= nome_safe), `order_total` (valor do ambiente).
- **`mod_escopo`**: `PAPEIS`, `PAPEL_FUNCOES`, `resolver_responsavel(atribuicoes, pool_ambiente_id, papel)`.
- **`mod_ciclo.ETAPA_NOME`**: 10=Medição, 11=Projeto executivo, 17=Montagem, 18=Assistência pós Montagem.
- **`mod_folha`** (Fase 3): `_resolver_pct_funcao(com, base)`, `vendas_liquido_consultor`, `calcular_folha`, `gerar_folha`.

---

### Task 1: Tabela `comissao_folha` (modelo + verificação de migração)

**Files:**
- Modify: `database.py` (novo modelo, junto a `FolhaPagamento` ~linha 273)
- Test: `tests/test_comissao.py` (novo)

- [ ] **Step 1: Escrever teste que falha (tabela existe com colunas)**

Criar `tests/test_comissao.py`:
```python
def test_comissao_folha_tabela_existe(app_db):
    cols = {c.name for c in app_db.ComissaoFolha.__table__.columns}
    for c in ("funcionario_id","competencia","origem","papel","projeto_nome","etapa_codigo",
              "base","base_ajustada","pct","valor","status","ref_etapa"):
        assert c in cols
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py::test_comissao_folha_tabela_existe -q`
Expected: FAIL (`app_db` sem `ComissaoFolha`).

- [ ] **Step 3: Implementar o modelo**

Em `database.py`, após a classe `FolhaPagamento`:
```python
class ComissaoFolha(Base):
    """Item de comissão de um funcionário numa competência (Fase 4). Um funcionário pode ter vários
    (por etapa/projeto). origem='papel' vem da conclusão de etapa (Mapa); origem='venda' é a comissão
    do Consultor. A parte variável da Folha = Σ valor dos itens (status != 'cancelado')."""
    __tablename__ = "comissao_folha"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id        = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    competencia    = Column(String(7), nullable=False)          # 'AAAA-MM' = mês de concluido_em
    origem         = Column(String(10), nullable=False, default="papel")  # papel | venda
    papel          = Column(String(30), nullable=True)          # projeto_executivo|medicao|montagem|assistencia|venda
    projeto_nome   = Column(Text,     nullable=True)            # nome_safe (rastreabilidade)
    etapa_codigo   = Column(String(8), nullable=True)           # etapa que disparou (papel); NULL p/ venda
    base           = Column(Float,    nullable=True, default=0.0)   # Σ order_total dos ambientes (ou vendas líq.)
    base_ajustada  = Column(Float,    nullable=True)            # override manual da base
    pct            = Column(Float,    nullable=True, default=0.0)
    valor          = Column(Float,    nullable=True, default=0.0)   # base_efetiva × pct/100
    status         = Column(String(12), nullable=False, default="previsto")  # previsto|confirmado|cancelado
    ref_etapa      = Column(String(120), nullable=True)        # idempotência: '<projeto>:<etapa>:<func>' ou 'venda:<func>:<comp>'
    criado_em      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("ref_etapa", name="uq_comissao_ref_etapa"),)
```

- [ ] **Step 4: Garantir criação no Postgres já povoado**

`create_all()` cria tabelas ausentes em qualquer dialeto, mas confirme que o caminho de init roda para Postgres. Em `_migrar_colunas_pg()` (idempotente), **não** é necessário para tabela nova; adicionar um comentário e, por segurança, um `CREATE TABLE IF NOT EXISTS` só se `create_all` não for chamado no boot PG (checar `init_db`). Se `init_db()` já chama `Base.metadata.create_all(ENGINE)` incondicionalmente, nada a fazer aqui além do teste do Step 5.

- [ ] **Step 5: Verificar criação (SQLite via teste; PG manual)**

Run: `python3 -m pytest tests/test_comissao.py::test_comissao_folha_tabela_existe -q`
Expected: PASS.
Verificação PG (manual, no fim da fase): subir com `DATABASE_URL` de dev e confirmar `comissao_folha` em `inspect(ENGINE).get_table_names()`.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_comissao.py
git commit -m "feat(comissao): tabela comissao_folha (itens de comissão por funcionário/competência)"
```

---

### Task 2: `mod_comissao` — papel↔etapa e base por ambiente

**Files:**
- Create: `mod_comissao.py`
- Test: `tests/test_comissao.py`

- [ ] **Step 1: Escrever testes que falham (papel_da_etapa + base_ambientes)**

```python
import mod_comissao

def test_papel_da_etapa():
    assert mod_comissao.papel_da_etapa("10") == "medicao"
    assert mod_comissao.papel_da_etapa("11") == "projeto_executivo"
    assert mod_comissao.papel_da_etapa("11a") == "projeto_executivo"
    assert mod_comissao.papel_da_etapa("17") == "montagem"
    assert mod_comissao.papel_da_etapa("18") == "assistencia"
    assert mod_comissao.papel_da_etapa("13") is None   # produção não gera comissão de papel

def test_base_ambientes_projeto_inteiro(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Med", status="ativo"); db.add(f); db.flush()
    db.add(app_db.PoolAmbiente(projeto_id="PBase", nome="a", nome_exibicao="Cozinha",
                               xml_path="x", ambientes_json="[]", order_total=8000.0))
    db.add(app_db.PoolAmbiente(projeto_id="PBase", nome="b", nome_exibicao="Quarto",
                               xml_path="y", ambientes_json="[]", order_total=2000.0))
    # atribuição projeto-inteiro (pool_ambiente_id NULL) para medição
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PBase", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    db.commit()
    base = mod_comissao.base_ambientes(db, "PBase", "medicao", f.id)
    assert base == 10000.0     # projeto inteiro = Σ order_total
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py -q -k "papel_da_etapa or base_ambientes"`
Expected: FAIL (módulo/funcs inexistentes).

- [ ] **Step 3: Implementar `mod_comissao.py` (papel + base)**

```python
"""mod_comissao.py — Comissão por papel (Fase 4). Ao concluir uma etapa operacional, prepara a
comissão do executor na folha do mês de conclusão. Base = Σ order_total dos ambientes atribuídos no
Mapa (projeto inteiro se atribuição = NULL) × % da Função. Itens em comissao_folha, somados na Folha."""
from datetime import datetime

import mod_folha
from database import (ComissaoFolha, CicloEtapa, Funcionario, Funcao,
                      PoolAmbiente, AtribuicaoAmbiente)

# Etapa operacional → papel do Mapa (só estas geram comissão de papel).
PAPEL_POR_ETAPA = {
    "10": "medicao",
    "11": "projeto_executivo", "11a": "projeto_executivo", "11b": "projeto_executivo",
    "11c": "projeto_executivo", "11d": "projeto_executivo", "11e": "projeto_executivo",
    "17": "montagem",
    "18": "assistencia",
}


def papel_da_etapa(codigo):
    return PAPEL_POR_ETAPA.get(str(codigo))


def base_ambientes(db, projeto_nome, papel, funcionario_id):
    """Σ order_total dos ambientes atribuídos a (papel, funcionario) no Mapa. Atribuição projeto-inteiro
    (pool_ambiente_id NULL) → Σ de TODOS os ambientes do projeto."""
    atrs = (db.query(AtribuicaoAmbiente)
            .filter_by(projeto_nome=projeto_nome, papel=papel, funcionario_id=funcionario_id).all())
    if not atrs:
        return 0.0
    if any(a.pool_ambiente_id is None for a in atrs):     # projeto inteiro
        total = (db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all())
        return round(sum(p.order_total or 0.0 for p in total), 2)
    ids = {a.pool_ambiente_id for a in atrs}
    pools = db.query(PoolAmbiente).filter(PoolAmbiente.id.in_(ids)).all()
    return round(sum(p.order_total or 0.0 for p in pools), 2)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_comissao.py -q -k "papel_da_etapa or base_ambientes"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_comissao.py tests/test_comissao.py
git commit -m "feat(comissao): mod_comissao — papel_da_etapa + base_ambientes (Σ order_total do Mapa)"
```

---

### Task 3: `preparar_comissao_etapa` (upsert idempotente)

**Files:**
- Modify: `mod_comissao.py`
- Test: `tests/test_comissao.py`

- [ ] **Step 1: Escrever teste que falha**

```python
import json
from datetime import datetime

def test_preparar_comissao_etapa_cria_item(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    com = {"por_meta": False, "pct": 3.0}
    fn = app_db.Funcao(loja_id=loja, nome="Medidor", usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Med", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    db.add(app_db.PoolAmbiente(projeto_id="PComis", nome="a", nome_exibicao="Cozinha",
                               xml_path="x", ambientes_json="[]", order_total=10000.0))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PComis", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    et = app_db.CicloEtapa(projeto_nome="PComis", etapa_codigo="10", status="concluido",
                           concluido_em=datetime(2026, 7, 15), funcao_responsavel_id=fn.id,
                           responsavel_funcionario_id=f.id)
    db.add(et); db.commit()
    item = mod_comissao.preparar_comissao_etapa(db, loja, et); db.commit()
    assert item is not None
    assert item.competencia == "2026-07"
    assert item.papel == "medicao"
    assert item.base == 10000.0
    assert item.pct == 3.0
    assert item.valor == 300.0
    assert item.status == "previsto"
    # idempotente: rechamar não duplica
    mod_comissao.preparar_comissao_etapa(db, loja, et); db.commit()
    n = db.query(app_db.ComissaoFolha).filter_by(projeto_nome="PComis", etapa_codigo="10").count()
    assert n == 1
    db.close()


def test_preparar_comissao_etapa_sem_comissao_nao_cria(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Semcom", usa_comissao_vendas=0, status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="X", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    et = app_db.CicloEtapa(projeto_nome="PSem", etapa_codigo="10", status="concluido",
                           concluido_em=datetime(2026, 7, 1), funcao_responsavel_id=fn.id,
                           responsavel_funcionario_id=f.id)
    db.add(et); db.commit()
    assert mod_comissao.preparar_comissao_etapa(db, loja, et) is None
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py -q -k "preparar_comissao"`
Expected: FAIL (`preparar_comissao_etapa` inexistente).

- [ ] **Step 3: Implementar `preparar_comissao_etapa` + `cancelar_comissao_etapa`**

Em `mod_comissao.py`:
```python
def _pct_funcao(funcao, base):
    if not funcao or not funcao.comissao_json:
        return 0.0
    import json
    try:
        com = json.loads(funcao.comissao_json)
    except (ValueError, TypeError):
        return 0.0
    return mod_folha._resolver_pct_funcao(com, base)


def preparar_comissao_etapa(db, loja_id, etapa):
    """Cria/atualiza (idempotente por ref_etapa) o item de comissão do executor da etapa concluída.
    Retorna o item, ou None se não se aplica (sem papel, sem executor funcionário, ou função sem comissão)."""
    papel = papel_da_etapa(etapa.etapa_codigo)
    if not papel or not etapa.responsavel_funcionario_id or not etapa.concluido_em:
        return None
    funcao = db.get(Funcao, etapa.funcao_responsavel_id) if etapa.funcao_responsavel_id else None
    base = base_ambientes(db, etapa.projeto_nome, papel, etapa.responsavel_funcionario_id)
    pct = _pct_funcao(funcao, base)
    if pct <= 0:
        return None
    comp = etapa.concluido_em.strftime("%Y-%m")
    ref = "%s:%s:%d" % (etapa.projeto_nome, etapa.etapa_codigo, etapa.responsavel_funcionario_id)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item is None:
        item = ComissaoFolha(loja_id=loja_id, funcionario_id=etapa.responsavel_funcionario_id,
                             origem="papel", papel=papel, projeto_nome=etapa.projeto_nome,
                             etapa_codigo=etapa.etapa_codigo, ref_etapa=ref)
        db.add(item)
    if item.status == "confirmado":     # já foi para folha paga — não recalcula
        return item
    base_ef = item.base_ajustada if item.base_ajustada is not None else base
    item.competencia = comp; item.base = base; item.pct = pct
    item.valor = round(float(base_ef) * pct / 100.0, 2); item.status = "previsto"
    db.flush()
    return item


def cancelar_comissao_etapa(db, projeto_nome, etapa_codigo, funcionario_id):
    """Cancela o item (reabertura de etapa), se não confirmado (folha não paga)."""
    ref = "%s:%s:%d" % (projeto_nome, etapa_codigo, funcionario_id)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item and item.status != "confirmado":
        item.status = "cancelado"; db.flush()
    return item
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_comissao.py -q -k "preparar_comissao"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_comissao.py tests/test_comissao.py
git commit -m "feat(comissao): preparar_comissao_etapa (idempotente) + cancelar_comissao_etapa"
```

---

### Task 4: Gatilho na conclusão da etapa (`_set_etapa_status`)

**Files:**
- Modify: `main.py` (`_set_etapa_status` ~linha 305; reabertura ~linha 5766)
- Test: `tests/test_comissao.py`

- [ ] **Step 1: Escrever teste que falha (endpoint que conclui etapa gera item)**

Usar o fluxo HTTP que conclui uma etapa (ex.: montagem/medição) e assertar que o item foi criado. Se o caminho HTTP for complexo, testar o hook diretamente via `_set_etapa_status` importado de `main`, montando o cenário e checando o item. Ex. (direto):
```python
def test_set_etapa_status_dispara_comissao(seed, app_db, monkeypatch):
    import main, json
    from datetime import datetime
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Montador", usa_comissao_vendas=0,
                       comissao_json=json.dumps({"por_meta": False, "pct": 2.0}), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Mnt", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    db.add(app_db.PoolAmbiente(projeto_id="PHook", nome="a", nome_exibicao="Sala",
                               xml_path="x", ambientes_json="[]", order_total=5000.0))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PHook", papel="montagem",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    et = app_db.CicloEtapa(projeto_nome="PHook", etapa_codigo="17", status="em_andamento",
                           funcao_responsavel_id=fn.id, responsavel_funcionario_id=f.id, loja_id=loja) \
         if "loja_id" in {c.name for c in app_db.CicloEtapa.__table__.columns} else \
         app_db.CicloEtapa(projeto_nome="PHook", etapa_codigo="17", status="em_andamento",
                           funcao_responsavel_id=fn.id, responsavel_funcionario_id=f.id)
    db.add(et); db.commit()
    main._set_etapa_status(db, "PHook", "17", "concluido", None); db.commit()
    item = db.query(app_db.ComissaoFolha).filter_by(projeto_nome="PHook", etapa_codigo="17").first()
    assert item is not None and item.valor == 100.0   # 5000 × 2%
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py::test_set_etapa_status_dispara_comissao -q`
Expected: FAIL (hook ausente).

- [ ] **Step 3: Acoplar o gatilho em `_set_etapa_status`**

Em `main.py`, dentro de `_set_etapa_status`, após setar `concluido_em`/`responsavel_id` no ramo conclusivo:
```python
    if status in mod_ciclo.STATUS_CONCLUSIVOS:
        etapa.concluido_em = datetime.utcnow()
        etapa.responsavel_id = responsavel_id
        try:
            import mod_comissao
            db.flush()   # concluido_em disponível
            loja_id_etapa = getattr(etapa, "loja_id", None) or _loja_id_do_projeto(db, nome_safe)
            mod_comissao.preparar_comissao_etapa(db, loja_id_etapa, etapa)
        except Exception as _e:
            print("[COMISSAO] preparar falhou:", _e)   # nunca bloqueia a conclusão da etapa
    return etapa
```
Se não existir helper de loja do projeto, usar o loja_id resolvido no handler chamador; alternativamente derivar via `Projeto.loja_id`. Ler o contexto de `_set_etapa_status` e escolher a fonte de `loja_id` já disponível (ex.: `Projeto` do `nome_safe`).

- [ ] **Step 4: Cancelamento na reabertura**

Em `main.py:~5766` (onde `concluido_em = None` reabre a etapa), após reabrir:
```python
    try:
        import mod_comissao
        if e.responsavel_funcionario_id:
            mod_comissao.cancelar_comissao_etapa(db, e.projeto_nome, e.etapa_codigo, e.responsavel_funcionario_id)
    except Exception as _e:
        print("[COMISSAO] cancelar falhou:", _e)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_comissao.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_comissao.py
git commit -m "feat(comissao): gatilho na conclusão de etapa (_set_etapa_status) + cancelamento na reabertura"
```

---

### Task 5: `gerar_folha` soma itens; Consultor vira item `venda`

**Files:**
- Modify: `mod_folha.py` (`gerar_folha`; helper novo `_upsert_item_venda`; `calcular_folha` mantém fixa/benefícios)
- Test: `tests/test_folha.py`, `tests/test_comissao.py`

- [ ] **Step 1: Escrever teste que falha (parte variável = Σ itens)**

Em `tests/test_comissao.py`:
```python
def test_gerar_folha_soma_itens_de_comissao(seed, app_db):
    import mod_folha, mod_provisoes, json
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Montador", salario_fixo=1000.0, usa_comissao_vendas=0, status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Mnt", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    # dois itens de comissão de papel na competência
    for i, v in enumerate((150.0, 250.0)):
        db.add(app_db.ComissaoFolha(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
               origem="papel", papel="montagem", projeto_nome="P%d" % i, etapa_codigo="17",
               base=0.0, pct=0.0, valor=v, status="previsto", ref_etapa="P%d:17:%d" % (i, f.id)))
    db.commit()
    cfg = mod_provisoes.config_financeira_default()
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    assert reg.parte_variavel == 400.0        # 150 + 250
    assert reg.total == 1400.0                # fixa 1000 + 400
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py::test_gerar_folha_soma_itens_de_comissao -q`
Expected: FAIL (parte_variavel não soma itens).

- [ ] **Step 3: Refatorar `gerar_folha` para somar itens (+ Consultor como item)**

Em `mod_folha.py`, adicionar helper e ajustar `gerar_folha`:
```python
from database import ComissaoFolha


def _total_itens_comissao(db, loja_id, funcionario_id, competencia):
    q = (db.query(ComissaoFolha)
         .filter_by(loja_id=loja_id, funcionario_id=funcionario_id, competencia=competencia)
         .filter(ComissaoFolha.status != "cancelado").all())
    return round(sum(float(i.valor or 0.0) for i in q), 2)


def _upsert_item_venda(db, loja_id, f, competencia, cfg):
    """Consultor: garante um item origem='venda' com a comissão de vendas do mês (idempotente)."""
    funcao = db.get(Funcao, f.funcao_id) if f.funcao_id else None
    if not (funcao and funcao.usa_comissao_vendas):
        return
    base = vendas_liquido_consultor(db, loja_id, f.usuario_id, competencia)
    pct = mod_provisoes.resolver_comissao_venda(cfg, base, 0.0)
    ref = "venda:%d:%s" % (f.id, competencia)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item is None:
        item = ComissaoFolha(loja_id=loja_id, funcionario_id=f.id, competencia=competencia,
                             origem="venda", papel="venda", ref_etapa=ref)
        db.add(item)
    if item.status == "confirmado":
        return
    base_ef = item.base_ajustada if item.base_ajustada is not None else base
    item.base = base; item.pct = pct; item.valor = round(base_ef * pct / 100.0, 2); item.status = "previsto"
    db.flush()
```
No corpo de `gerar_folha`, para cada funcionário ativo (folha não paga):
```python
        _upsert_item_venda(db, loja_id, f, competencia, cfg)
        c = calcular_folha(db, loja_id, f, competencia, cfg)   # fixa + benefícios (variável=0 aqui)
        variavel = _total_itens_comissao(db, loja_id, f.id, competencia)
        reg.parte_fixa = c["parte_fixa"]; reg.beneficios = c["beneficios"]
        reg.parte_variavel = variavel
        reg.total = round((c["parte_fixa"] or 0) + variavel + (c["beneficios"] or 0), 2)
        reg.status = "aberta"
```
Nota: `calcular_folha` continua retornando `parte_variavel`/`base_comissao` da Fase 3 (usado por testes unitários diretos), mas **`gerar_folha` passa a usar os itens** como fonte da variável. Ajustar os testes da Fase 3 que assumiam `gerar_folha` colocando a variável do consultor via `base_comissao` (agora vem do item `venda`).

- [ ] **Step 4: Ajustar testes da Fase 3 afetados**

Rodar `tests/test_folha.py`; onde um teste de `gerar_folha` esperava variável do consultor, o valor agora vem do item `venda` (mesmo número). Corrigir asserts que liam `reg.base_comissao` para lerem `reg.parte_variavel`/item. Manter os testes unitários de `calcular_folha` (fixa/benefícios) inalterados.

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py tests/test_comissao.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_folha.py tests/test_folha.py tests/test_comissao.py
git commit -m "feat(folha): parte variável = Σ itens comissao_folha; Consultor vira item 'venda'"
```

---

### Task 6: Editar item + `PATCH /api/comissao/<id>`

**Files:**
- Modify: `mod_comissao.py` (`editar_item`); `main.py` (rota PATCH em `do_PATCH`)
- Test: `tests/test_comissao.py`

- [ ] **Step 1: Escrever teste que falha (editar base recalcula valor)**

```python
def test_editar_item_recalcula_valor(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    it = app_db.ComissaoFolha(loja_id=loja, funcionario_id=1, competencia="2026-07",
         origem="papel", papel="montagem", base=10000.0, pct=2.0, valor=200.0,
         status="previsto", ref_etapa="Z:17:1")
    db.add(it); db.flush()
    ok, err = mod_comissao.editar_item(db, it, 15000.0)
    assert ok and it.base_ajustada == 15000.0 and it.valor == 300.0   # 15000 × 2%
    it.status = "confirmado"
    ok2, _ = mod_comissao.editar_item(db, it, 1.0)
    assert ok2 is False
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py::test_editar_item_recalcula_valor -q`
Expected: FAIL.

- [ ] **Step 3: Implementar `editar_item`**

Em `mod_comissao.py`:
```python
def editar_item(db, item, base_ajustada):
    """Override manual da base de um item (status != confirmado) e recalcula valor."""
    if item.status == "confirmado":
        return False, "comissão já confirmada"
    item.base_ajustada = float(base_ajustada)
    item.valor = round(float(base_ajustada) * float(item.pct or 0.0) / 100.0, 2)
    db.flush()
    return True, None
```

- [ ] **Step 4: Rota `PATCH /api/comissao/<id>` em `do_PATCH`**

Em `main.py`, no início de `do_PATCH` (junto à rota de folha da Fase 3):
```python
            m = re.match(r'^/api/comissao/(\d+)$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_comissao
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    it = db.query(ComissaoFolha).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                    if it is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    base = float((json.loads(body or b'{}')).get("base_ajustada") or 0.0)
                    ok, err = mod_comissao.editar_item(db, it, base)
                    if not ok:
                        self.send_json({"ok": False, "erro": err}, code=409); return
                    db.commit()
                    self.send_json({"ok": True, "id": it.id, "base_ajustada": it.base_ajustada, "valor": it.valor})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```
Importar `ComissaoFolha` no topo do `main.py` (junto aos demais imports de `database`).

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_comissao.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_comissao.py main.py tests/test_comissao.py
git commit -m "feat(comissao): editar_item + PATCH /api/comissao/<id> (base ajustável recalcula valor)"
```

---

### Task 7: Folha expõe itens de comissão (serialize/listar)

**Files:**
- Modify: `mod_folha.py` (`serialize` inclui `comissoes`)
- Test: `tests/test_comissao.py`

- [ ] **Step 1: Escrever teste que falha (serialize traz os itens)**

```python
def test_serialize_folha_inclui_comissoes(seed, app_db):
    import mod_folha
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Q", status="ativo"); db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
          parte_fixa=0.0, parte_variavel=200.0, total=200.0, status="aberta"); db.add(reg); db.flush()
    db.add(app_db.ComissaoFolha(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
           origem="papel", papel="montagem", projeto_nome="PX", etapa_codigo="17",
           base=10000.0, pct=2.0, valor=200.0, status="previsto", ref_etapa="PX:17:%d" % f.id))
    db.commit()
    d = mod_folha.serialize(db, reg)
    assert len(d["comissoes"]) == 1
    assert d["comissoes"][0]["papel"] == "montagem" and d["comissoes"][0]["valor"] == 200.0
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_comissao.py::test_serialize_folha_inclui_comissoes -q`
Expected: FAIL (sem `comissoes`).

- [ ] **Step 3: Incluir `comissoes` no `serialize`**

Em `mod_folha.serialize`, antes do `return`:
```python
    from database import ComissaoFolha
    itens_com = (db.query(ComissaoFolha)
                 .filter_by(funcionario_id=reg.funcionario_id, competencia=reg.competencia)
                 .filter(ComissaoFolha.status != "cancelado")
                 .order_by(ComissaoFolha.id.asc()).all())
    comissoes = [{"id": i.id, "origem": i.origem, "papel": i.papel, "projeto": i.projeto_nome,
                  "etapa": i.etapa_codigo, "base": i.base, "base_ajustada": i.base_ajustada,
                  "pct": i.pct, "valor": i.valor, "status": i.status} for i in itens_com]
```
E adicionar `"comissoes": comissoes,` ao dict retornado.

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_comissao.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_folha.py tests/test_comissao.py
git commit -m "feat(folha): serialize expõe itens de comissão (comissoes) por funcionário/competência"
```

---

### Task 8: Frontend — itens de comissão na folha do mês

**Files:**
- Modify: `static/index.html` (`folhaRender` — expandir linha para os itens; editar item via PATCH)

- [ ] **Step 1: Localizar `folhaRender` (Fase 3)**

Run (WSL): `grep -n "folhaRender\|folhaSalvarBase\|folha-mes-box" static/index.html`

- [ ] **Step 2: Substituir a edição da "Base comissão" única por lista de itens por funcionário**

Na linha de cada funcionário, quando houver `it.comissoes.length`, renderizar uma sublista (papel · projeto · base editável · valor), cada base com `onchange="comissaoSalvarBase(<id>, this.value)"`. A célula "Parte variável" mostra a soma (`it.parte_variavel`). Quando não houver itens, manter a variável em `_fBRL(it.parte_variavel||0)` (0). Remover o input de `base_comissao` único da Fase 3 (agora a edição é por item):
```javascript
const comiss = (it.comissoes||[]).map(cm =>
   '<div style="display:flex;gap:8px;align-items:center;font-size:11px;padding:2px 0">'
  +'<span style="color:var(--muted);min-width:90px">'+esc(cm.papel||cm.origem)+'</span>'
  +'<span style="color:var(--muted);min-width:80px">'+esc(cm.projeto||'—')+'</span>'
  +(it.status==='paga'
     ? '<span style="font-family:var(--font-mono)">'+_fBRL((cm.base_ajustada!=null?cm.base_ajustada:cm.base)||0)+'</span>'
     : '<input type="number" step="0.01" value="'+((cm.base_ajustada!=null?cm.base_ajustada:cm.base)||0)+'" class="inp" style="width:110px;text-align:right;font-family:var(--font-mono);padding:2px 5px" onchange="comissaoSalvarBase('+cm.id+',this.value)">')
  +'<span style="color:var(--muted)">× '+(cm.pct?Number(cm.pct).toFixed(2)+'%':'—')+'</span>'
  +'<span style="font-family:var(--font-mono);font-weight:600">'+_fBRL(cm.valor||0)+'</span></div>').join('');
```
Inserir `comiss` numa célula abaixo/expandida da linha (ou numa coluna "Comissões" que lista os itens). Ajustar `colspan` conforme necessário.

- [ ] **Step 3: Implementar `comissaoSalvarBase`**

```javascript
async function comissaoSalvarBase(id, valor){
  const r = await fetch('/api/comissao/'+id, {method:'PATCH', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify({base_ajustada: parseFloat(valor)||0})});
  const d = await r.json().catch(()=>({}));
  if(r.ok && !d.erro){ folhaMesCarregar(); }
  else { showToast((d&&d.erro)||'Erro ao salvar comissão.', true); }
}
```
Observação: após editar um item, a `parte_variavel`/`total` da folha só reflete após novo `Gerar folha` (que resoma) — para refletir na hora, `folhaMesCarregar()` relista; se o total exibido não recalcular sem regenerar, exibir a soma dos itens no frontend ou chamar `folhaGerar()` silenciosamente. Escolha: relistar e mostrar a soma dos itens como "Parte variável" no cliente (não depender de regenerar).

- [ ] **Step 4: Verificar sintaxe do frontend**

Extrair o maior `<script>` e `node --check` (WSL). Expected: `JS_OK`.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(folha/ui): itens de comissão por funcionário na folha do mês (base por item editável)"
```

---

## Verificação final
- [ ] `python3 -m pytest -q` (SQLite) — verde.
- [ ] Postgres: subir o app com `DATABASE_URL` de dev; confirmar `comissao_folha` criada (sem crash) e conclusão de etapa gerando item.
- [ ] Smoke: concluir uma etapa de montagem de um projeto com Mapa atribuído → conferir item na folha do mês; editar base do item; gerar folha e ver a variável somando; pagar.
- [ ] FF-merge para `main`. Não commitar `perfis_config.json`. Push só quando o usuário pedir.

## Self-Review (cobertura da spec — Frente A)
- Gatilho na conclusão de etapa → Task 4. ✅
- Competência = mês de conclusão → Task 3 (`concluido_em.strftime`). ✅
- Base = Σ order_total dos ambientes atribuídos (projeto inteiro se NULL) → Task 2. ✅
- % da Função (faixas/flat) → Task 3 (`_pct_funcao` reusa `_resolver_pct_funcao`). ✅
- Itens somados na parte variável; Consultor como item `venda` → Task 5. ✅
- Ajuste manual da base por item → Task 6. ✅
- Reversão na reabertura → Task 4. ✅
- UI dos itens → Task 8. ✅

**Fora de escopo (Frentes B/C e pendências):** adiantamentos/empréstimos + saldo (Fase 5); comissão fixa por função (Fase 6); executor **terceiro** (repasse, não folha); modelo contábil completo de matching (hoje simples + Provisões).
