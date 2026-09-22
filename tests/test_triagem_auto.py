# -*- coding: utf-8 -*-
"""RF-08/09 — triagem AUTOMÁTICA (2026-08-04): contato novo no WhatsApp recebe a PERGUNTA de
triagem de volta (texto livre — janela de 24h recém-aberta; sem template) e a RESPOSTA dele
(número/nome do segmento) preenche `segmento_sugerido` + envia a confirmação. Sem credencial
Meta o envio nasce `pendente_config` (a rede nunca é tocada em teste). A resolução é sempre
AUTOMÁTICA (2026-08-05): resposta reconhecida materializa a conversa na hora
(chat.triagem.triagem_materializar) — não fica mais esperando humano na fila."""
import ast
import inspect

import mod_chat_externo as wa
from chat import triagem as tri
from database import EnvioExterno, TriagemEntrada


# ── puros ────────────────────────────────────────────────────────────────────────

def test_interpretar_resposta():
    ops = [{"segmento": "comercial", "rotulo": "Comercial"},
           {"segmento": "financeiro", "rotulo": "Financeiro"},
           {"segmento": "suporte_tecnico", "rotulo": "Suporte Técnico"}]
    assert tri.interpretar_resposta_triagem("2", ops) == "financeiro"
    assert tri.interpretar_resposta_triagem(" 3. ", ops) == "suporte_tecnico"
    assert tri.interpretar_resposta_triagem("Financeiro", ops) == "financeiro"
    assert tri.interpretar_resposta_triagem("suporte tecnico", ops) == "suporte_tecnico"
    assert tri.interpretar_resposta_triagem("9", ops) is None
    assert tri.interpretar_resposta_triagem("quero comprar um armário", ops) is None
    assert tri.interpretar_resposta_triagem("", ops) is None


def test_montar_pergunta_lista(app_db, seed):
    db = app_db.get_session()
    try:
        texto, ops = tri.montar_pergunta_triagem(db, seed["loja1_id"])
        assert "NÚMERO" in texto and "1. " in texto
        assert ops and ops[0]["segmento"] == "comercial"
    finally:
        db.close()


# ── fluxo completo (sem credencial: pendente_config) ─────────────────────────────

def _limpar(app_db, remetente):
    db = app_db.get_session()
    try:
        for e in db.query(TriagemEntrada).filter_by(remetente=remetente).all():
            db.query(EnvioExterno).filter_by(triagem_id=e.id).delete()
            db.delete(e)
        db.commit()
    finally:
        db.close()


def test_contato_novo_recebe_pergunta_e_resposta_materializa_conversa(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)      # hermético: sem transporte real
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999990001"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        # 1ª mensagem: cai no buffer E dispara a pergunta (pendente_config sem credencial)
        r1 = wa.processar_entrada(db, "whatsapp", tel, "Oi, preciso de um orçamento",
                                  id_externo="wamid.auto.1")
        db.commit()
        assert r1["status"] == "triagem" and r1["triagem_id"]
        envs = db.query(EnvioExterno).filter_by(triagem_id=r1["triagem_id"],
                                                direcao="saida").all()
        assert len(envs) == 1
        assert envs[0].status == "pendente_config"      # sem ORIZON_WA_* no teste
        assert envs[0].mensagem_id is None              # ainda não há conversa
        # 2ª mensagem: escolha "1" → segmento reconhecido MATERIALIZA a conversa na hora
        r2 = wa.processar_entrada(db, "whatsapp", tel, "1", id_externo="wamid.auto.2")
        db.commit()
        assert r2["status"] == "roteado" and r2["conversa_id"]
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert ent.status == "resolvido" and ent.conversa_id == r2["conversa_id"]
        from database import Conversa
        conv = db.get(Conversa, r2["conversa_id"])
        assert conv.segmento == "comercial"
        # 3ª mensagem: já roteia normal pra conversa materializada (não é mais "anexa no buffer")
        r3 = wa.processar_entrada(db, "whatsapp", tel, "é para uma cozinha",
                                  id_externo="wamid.auto.3")
        db.commit()
        assert r3["status"] == "roteado" and r3["conversa_id"] == conv.id
    finally:
        db.close()


def test_resposta_nao_reconhecida_reformula_uma_vez_depois_some(app_db, seed, monkeypatch):
    """Decisão 18/09/2026 (TAREFA_TRIAGEM_E_CONTADOR.md, Item 1): a 1ª resposta que não casa
    reformula a pergunta (nunca a mensagem inicial em si, que já recebeu a pergunta original);
    a 2ª que também não casa não reenvia — some, com o texto preservado e a entrada pendente
    na fila pra um humano."""
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999990002"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        r1 = wa.processar_entrada(db, "whatsapp", tel, "olá", id_externo="wamid.auto.4")
        db.commit()
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert not tri.ja_reformulou(db, ent)            # só a pergunta original até aqui

        # 1ª resposta que não casa (inclui o caso de mídia/mensagem vazia — mesmo texto
        # "(mensagem sem texto)" da Meta, que também não reconhece nenhum segmento)
        r2 = wa.processar_entrada(db, "whatsapp", tel, "quero falar com alguém",
                                  id_externo="wamid.auto.5")
        db.commit()
        assert r2["triagem_id"] == r1["triagem_id"]
        assert r2["segmento_sugerido"] is None
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert "falar com alguém" in ent.texto           # nada se descarta
        envs = db.query(EnvioExterno).filter_by(triagem_id=ent.id, direcao="saida").all()
        assert len(envs) == 2                             # pergunta original + reformulação
        assert tri.ja_reformulou(db, ent)

        # 2ª resposta que também não casa: robô some — sem 3ª pergunta, texto preservado
        r3 = wa.processar_entrada(db, "whatsapp", tel, "ainda não entendi o que vocês fazem",
                                  id_externo="wamid.auto.6")
        db.commit()
        assert r3["triagem_id"] == r1["triagem_id"]
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert "ainda não entendi" in ent.texto
        assert ent.status == "pendente"                   # segue na fila (listar_fila)
        assert db.query(EnvioExterno).filter_by(triagem_id=ent.id,
                                                direcao="saida").count() == 2   # nenhuma 3ª
    finally:
        db.close()


def test_ja_reformulou_escritores_fixos():
    """Fixa a premissa do docstring de `ja_reformulou`: hoje só DUAS funções deste módulo
    levam a um `EnvioExterno.triagem_id` gravado (as duas chamam `_enviar_texto_triagem`,
    que é o ÚNICO ponto que constrói `EnvioExterno(triagem_id=...)`). Uma terceira função
    passando a chamar o escritor, OU um segundo ponto de construção direta, tem que estourar
    AQUI — vermelho no teste — nunca virar contagem errada em produção."""
    arvore = ast.parse(inspect.getsource(tri))

    def chama_o_escritor(no):
        return any(isinstance(f, ast.Call) and isinstance(f.func, ast.Name)
                   and f.func.id == "_enviar_texto_triagem" for f in ast.walk(no))

    # ast.walk (e não arvore.body): um escritor novo escondido dentro de uma classe ou de uma
    # função aninhada tem que aparecer aqui do mesmo jeito.
    chamadores = {no.name for no in ast.walk(arvore)
                  if isinstance(no, ast.FunctionDef) and no.name != "_enviar_texto_triagem"
                  and chama_o_escritor(no)}
    assert chamadores == {"enviar_pergunta_triagem", "registrar_resposta_triagem"}

    construtores = [no for no in ast.walk(arvore)
                    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                    and no.func.id == "EnvioExterno"
                    and any(kw.arg == "triagem_id" for kw in no.keywords)]
    assert len(construtores) == 1
