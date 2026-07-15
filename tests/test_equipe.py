"""mod_equipe — Equipe do Projeto (roster papel → responsáveis). Automáticos DERIVAM da fonte
(Consultor = criado_por; Gerente Comercial/SAC/Supervisor = funcionário da loja com a função);
seletores (medidor/finalizador/montagem[N]) são escolhidos e guardados em projetos_meta.equipe_json."""
import mod_equipe as eq
from database import Projeto, Funcionario, Terceiro, Funcao, Usuario


def _mkfunc(db, loja, nome):
    f = Funcao(loja_id=loja, nome=nome, status="ativo"); db.add(f); db.flush(); return f.id


def _seed_eq(db, loja):
    gv = _mkfunc(db, loja, "Gerente de Vendas")
    sac = _mkfunc(db, loja, "SAC")
    sup = _mkfunc(db, loja, "Supervisor de Montagem")
    med = _mkfunc(db, loja, "Medidor")
    db.add(Funcionario(loja_id=loja, nome="Gerente Ger", funcao_id=gv, telefone="1"))
    db.add(Funcionario(loja_id=loja, nome="Sac Sac", funcao_id=sac))
    db.add(Funcionario(loja_id=loja, nome="Super Sup", funcao_id=sup))
    fm = Funcionario(loja_id=loja, nome="Med Func", funcao_id=med); db.add(fm)
    t1 = Terceiro(loja_id=loja, nome="Montador T1"); db.add(t1)
    t2 = Terceiro(loja_id=loja, nome="Montador T2"); db.add(t2)
    u = Usuario(nome="Consultor Criador", login="cc_eq_%d" % loja, senha_hash="x", nivel="operador")
    db.add(u); db.flush()
    db.add(Projeto(nome_safe="EQ_%d" % loja, status="quente", loja_id=loja, criado_por_id=u.id))
    db.commit()
    return {"fm": fm.id, "t1": t1.id, "t2": t2.id, "u": u.id}


def test_equipe_automaticos_resolvem(app_db):
    db = app_db.get_session()
    try:
        _seed_eq(db, 6001)
        by = {p["papel"]: p for p in eq.equipe(db, "EQ_6001", 6001)["papeis"]}
        assert [x["nome"] for x in by["gerente_comercial"]["pessoas"]] == ["Gerente Ger"]
        assert [x["nome"] for x in by["sac"]["pessoas"]] == ["Sac Sac"]
        assert [x["nome"] for x in by["supervisor_montagem"]["pessoas"]] == ["Super Sup"]
        assert [x["nome"] for x in by["consultor"]["pessoas"]] == ["Consultor Criador"]
        assert by["medidor"]["pessoas"] == [] and by["montagem"]["pessoas"] == []
        assert by["montagem"]["multi"] is True and by["gerente_comercial"]["auto"] is True
    finally:
        db.close()


def test_equipe_salva_seletores(app_db):
    db = app_db.get_session()
    try:
        ids = _seed_eq(db, 6002)
        ok, _ = eq.salvar(db, "EQ_6002", "medidor", {"tipo": "funcionario", "id": ids["fm"]}); db.commit()
        assert ok
        ok2, _ = eq.salvar(db, "EQ_6002", "montagem",
                           [{"tipo": "terceiro", "id": ids["t1"]}, {"tipo": "terceiro", "id": ids["t2"]}])
        db.commit(); assert ok2
        by = {p["papel"]: p for p in eq.equipe(db, "EQ_6002", 6002)["papeis"]}
        assert [x["nome"] for x in by["medidor"]["pessoas"]] == ["Med Func"]
        assert [x["nome"] for x in by["montagem"]["pessoas"]] == ["Montador T1", "Montador T2"]
    finally:
        db.close()


def test_equipe_salvar_rejeita_papel_automatico(app_db):
    db = app_db.get_session()
    try:
        _seed_eq(db, 6003)
        ok, _ = eq.salvar(db, "EQ_6003", "gerente_comercial", {"tipo": "funcionario", "id": 1})
        assert ok is False
    finally:
        db.close()


def test_endpoint_equipe_get_e_rejeita_automatico(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/%s/equipe" % seed["projeto_l1"])
    assert st == 200 and d["ok"], (st, d)
    papeis = {p["papel"] for p in d["equipe"]["papeis"]}
    assert {"gerente_comercial", "consultor", "sac", "medidor", "finalizador",
            "supervisor_montagem", "montagem"} <= papeis
    assert "candidatos" in d
    st2, d2 = c.post("/api/projetos/%s/equipe" % seed["projeto_l1"],
                     {"papel": "consultor", "selecao": {"tipo": "funcionario", "id": 1}})
    assert st2 == 400, (st2, d2)   # papel automático não é gravável


def test_candidatos_lista_funcionarios_e_terceiros(app_db):
    db = app_db.get_session()
    try:
        _seed_eq(db, 6004)
        c = eq.candidatos(db, 6004)
        assert any(x["nome"] == "Med Func" for x in c["funcionarios"])
        assert {x["nome"] for x in c["terceiros"]} == {"Montador T1", "Montador T2"}
    finally:
        db.close()
