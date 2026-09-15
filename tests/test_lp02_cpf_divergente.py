# -*- coding: utf-8 -*-
"""LP-02 (docs/db/LISTA_PARALELA.md, decidido 15/09/2026): AVISAR, NÃO BLOQUEAR quando o CPF
digitado na assinatura não bate com o do cadastro (cliente do projeto, ou o usuário logado
assinando pela loja) — exige confirmação de um gerente (login+senha, ou sessão já com a
capacidade) para prosseguir, e registra quem autorizou em LogAcaoGerencial. Vale nos quatro
documentos (Contrato, Aditivo, Aprovação do PE, Solicitação de Medição).

CPF do cliente L1 no seed: "111.444.777-35" (ver tests/conftest.py) — CPF_DIVERGENTE abaixo é
estruturalmente válido mas de OUTRA pessoa, então nunca bate por acidente. `cons_l1` (operador)
não tem `confirmar_excecao_cpf`; `dir_l1` (master) tem — usado como "o gerente" que confirma."""
from datetime import datetime

from database import (Contrato, ContratoAssinatura, AprovacaoPE, SolicitacaoMedicao, Aditivo,
                      LogAcaoGerencial)

CPF_DIVERGENTE = "529.982.247-25"   # válido, mas não é o CPF de nenhum cliente/usuário do seed


def _login(f, who):
    c = f(); st, b = c.login(who, "senha123"); assert st == 200 and b["ok"]; return c


def _prep_contrato(app_db, seed):
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    p = db.get(app_db.Projeto, nome)
    p.previsao_medicao = datetime(2028, 1, 1)
    p.data_entrega = datetime(2028, 1, 10)
    p.folga_autorizada = 1
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    ct.assinatura_canal = "interno"
    db.query(ContratoAssinatura).filter_by(contrato_id=cid).delete()
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="Loja", cpf="111.444.777-35",
                              assinado_em=datetime.utcnow(), hash_sha256="x" * 64))
    db.commit(); db.close()
    return nome


def test_contrato_cliente_cpf_divergente_exige_gerente(app_db, seed, http_client_factory):
    nome = _prep_contrato(app_db, seed)
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE})
    assert st == 409 and d["precisa_confirmar_cpf"] is True, d
    db = app_db.get_session()
    ct = db.get(Contrato, seed["contrato_l1_id"])
    assert ct.status == "assinado_loja", "não avança sem a confirmação"
    assert not db.query(LogAcaoGerencial).filter_by(acao="confirmar_cpf_divergente").all()
    db.close()


def test_contrato_cliente_cpf_divergente_com_gerente_prossegue_e_loga(app_db, seed, http_client_factory):
    nome = _prep_contrato(app_db, seed)
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE,
                    "login_gerente": "dir_l1", "senha_gerente": "senha123"})
    assert st == 200 and d["ok"], d
    assert d["status"] == "assinado"
    db = app_db.get_session()
    log = db.query(LogAcaoGerencial).filter_by(acao="confirmar_cpf_divergente",
                                               projeto_nome=nome).first()
    assert log is not None
    assert log.autorizador_id == db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()


def test_contrato_cpf_divergente_sessao_ja_com_capacidade_nao_precisa_de_senha(app_db, seed, http_client_factory):
    """dir_l1 é master — já TEM confirmar_excecao_cpf. Assinando ele mesmo, sem
    login_gerente/senha_gerente, o atalho sessão-primeiro de _usuario_com_capacidade se aplica."""
    nome = _prep_contrato(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE})
    assert st == 200 and d["ok"], d


def test_contrato_cpf_confere_nao_pede_nada(app_db, seed, http_client_factory):
    nome = _prep_contrato(app_db, seed)
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "111.444.777-35"})
    assert st == 200 and d["ok"], d


def _prep_aprovacao_pe(app_db, seed, tmp_path):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    pdf = tmp_path / "aprovacao_pe.pdf"
    pdf.write_bytes(b"%PDF-fake")
    ap = AprovacaoPE(projeto_nome=nome, contrato_id=seed["contrato_l1_id"],
                     status="para_assinatura", pdf_path=str(pdf), assinatura_canal="interno")
    db.add(ap); db.commit()
    db.close()
    return nome


def test_aprovacao_pe_loja_cpf_divergente_exige_gerente(app_db, seed, http_client_factory, tmp_path):
    """`parte='loja'` compara contra o Usuario.cpf de quem assina — cons_l1 não tem CPF
    cadastrado, então definimos um antes do teste pra ter algo pra divergir."""
    nome = _prep_aprovacao_pe(app_db, seed, tmp_path)
    db = app_db.get_session()
    db.query(app_db.Usuario).filter_by(login="cons_l1").first().cpf = "111.444.777-35"
    db.commit(); db.close()
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/aprovacao-pe/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_DIVERGENTE})
    assert st == 409 and d["precisa_confirmar_cpf"] is True, d
    st, d = c.post("/api/projetos/%s/aprovacao-pe/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": CPF_DIVERGENTE,
                    "login_gerente": "dir_l1", "senha_gerente": "senha123"})
    assert st == 200 and d["ok"], d


def _prep_solicitacao_medicao(app_db, seed, tmp_path):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    db.get(Contrato, seed["contrato_l1_id"]).status = "assinado"
    for sol in db.query(SolicitacaoMedicao).filter_by(projeto_nome=nome).all():
        for a in list(sol.assinaturas):
            db.delete(a)
        db.delete(sol)
    pdf = tmp_path / "solicitacao_medicao.pdf"
    pdf.write_bytes(b"%PDF-fake")
    sol = SolicitacaoMedicao(projeto_nome=nome, loja_id=seed["loja1_id"],
                             status="para_assinatura", pdf_path=str(pdf), assinatura_canal="interno")
    db.add(sol); db.commit()
    db.close()
    return nome


def test_solicitacao_medicao_cliente_cpf_divergente_exige_gerente(app_db, seed, http_client_factory, tmp_path):
    nome = _prep_solicitacao_medicao(app_db, seed, tmp_path)
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/medicao/solicitacao/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE})
    assert st == 409 and d["precisa_confirmar_cpf"] is True, d
    st, d = c.post("/api/projetos/%s/medicao/solicitacao/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE,
                    "login_gerente": "dir_l1", "senha_gerente": "senha123"})
    assert st == 200 and d["ok"], d


def _prep_aditivo(app_db, seed):
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    ct = (db.query(Contrato).filter_by(projeto_nome=nome).order_by(Contrato.id.desc()).first())
    orc = app_db.Orcamento(projeto_id=nome, nome="Complemento LP-02", ordem=99,
                           loja_id=seed["loja1_id"])
    db.add(orc); db.flush()
    ad = Aditivo(projeto_nome=nome, contrato_id=ct.id, orcamento_complemento_id=orc.id,
                status="para_assinatura", pdf_path="/tmp/fake_aditivo.pdf",
                assinatura_canal="interno")
    db.add(ad); db.commit()
    db.close()
    return nome


def test_aditivo_cliente_cpf_divergente_exige_gerente(app_db, seed, http_client_factory):
    nome = _prep_aditivo(app_db, seed)
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/projetos/%s/aditivo/assinar" % nome,
                   {"parte": "loja", "nome": "Loja", "cpf": "111.444.777-35"})
    assert st == 200 and d["ok"], d   # 1ª parte (loja) — CPF só compara pra 'cliente' aqui
    import json as _json
    st, d = c.post("/api/projetos/%s/aditivo/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": CPF_DIVERGENTE,
                    "forma_pagamento": _json.dumps({"tipo": "avista", "entrada_valor": 1.0})})
    assert st == 409 and d["precisa_confirmar_cpf"] is True, d
