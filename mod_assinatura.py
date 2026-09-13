# -*- coding: utf-8 -*-
"""mod_assinatura.py — ACHADO-69 (docs/db/TAREFA_ACHADO69_ASSINATURA_UNIFICADA.md), Passo 1.

Registro único dos documentos que oferecem assinatura por ClickSign — hoje: Contrato, Aprovação
do PE e Solicitação de medição. `main.py` tinha essa lista repetida em dois lugares (o webhook e
o job `/internal/clicksign/reconciliar`), cada um com um bloco quase idêntico por classe — a
duplicação que o pacote nomeou pra unificar.

Passo 1 NÃO muda comportamento nenhum: cada entrada aqui só referencia as funções
`_enviar_*_para_clicksign`/`_reconciliar_*_clicksign` que já existiam em `main.py`, intocadas —
o que muda é o DESPACHO (qual classe, para qual envelope; quais linhas entram na varredura do
job), nunca a lógica de enviar/reconciliar em si. `main.py` popula o registro (nunca o contrário
— `mod_assinatura` não importa `main`, pra não criar import circular); só ele conhece as funções
concretas de cada documento.

Cancelamento de envelope (ACHADO-70, `docs/db/ACHADOS_CONTABEIS.md`): só o Contrato tem hoje.
`cancelar=None` em Aprovação do PE e Solicitação de medição é DELIBERADO — ligar isso nelas é
mudança de comportamento em produção, não extração de mecanismo; entra em commit próprio, depois
que o Passo 2 tiver migrado cada documento com a suíte verde. O campo existe no registro desde já
(é uma das cinco capacidades que o pacote pede: envio, verificação, reenvio, cancelamento,
reconciliação) mas nenhum chamador deste módulo o consome ainda."""

from collections import namedtuple

RegistroDocumento = namedtuple("RegistroDocumento", [
    "nome",          # rótulo curto (logs/erros) — "contrato", "aprovacao_pe", "solicitacao_medicao"
    "modelo",        # classe SQLAlchemy (ex.: Contrato) — precisa ter assinatura_canal, status,
                     # clicksign_envelope_id, clicksign_enviado_em com esses nomes exatos
    "enviar",        # função(db, doc, cfg, **kwargs) -> None (não commita — igual às atuais)
    "reconciliar",   # função(db, doc, cfg) -> None (não commita — igual às atuais)
    "cancelar",      # função(db, doc, loja_id, status_final) -> None, ou None (não suportado hoje)
])

STATUS_PENDENTES_CLICKSIGN = ("para_assinatura", "assinado_loja", "assinado_cliente")

_registro = []


def registrar(nome, modelo, enviar, reconciliar, cancelar=None):
    """Chamado por `main.py` (nunca por este módulo) — uma vez por classe, no import."""
    _registro.append(RegistroDocumento(nome, modelo, enviar, reconciliar, cancelar))


def documentos():
    """Cópia da lista — iterar à vontade, nunca mutar o registro por fora de `registrar`."""
    return list(_registro)


def achar_por_envelope(db, envelope_id):
    """(doc, registro) do primeiro documento conhecido com este `clicksign_envelope_id`, na
    ordem de registro (hoje: Contrato, Aprovação do PE, Solicitação de medição — mesma ordem que
    o webhook original consultava em série). `(None, None)` se nenhuma classe conhecida bater —
    o chamador decide o que fazer (o webhook de hoje faz ack sem processar)."""
    for reg in _registro:
        doc = db.query(reg.modelo).filter_by(clicksign_envelope_id=envelope_id).first()
        if doc is not None:
            return doc, reg
    return None, None


def pendentes_para_reconciliar(db, reg, limite):
    """Linhas de `reg.modelo` prontas pra reconciliação: canal ClickSign, status ainda não
    terminal, enviadas há mais que a carência (`limite` = agora − carência, calculado pelo
    chamador). Mesmo filtro que os três blocos de `/internal/clicksign/reconciliar` já faziam,
    um por um."""
    m = reg.modelo
    return (db.query(m)
            .filter(m.assinatura_canal == "clicksign",
                    m.status.in_(STATUS_PENDENTES_CLICKSIGN),
                    m.clicksign_enviado_em.isnot(None),
                    m.clicksign_enviado_em <= limite)
            .all())
