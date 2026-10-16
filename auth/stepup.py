# -*- coding: utf-8 -*-
"""stepup.py — janelas de step-up por senha (cadeado de módulo e aprovar_financeiro).

Mora aqui, e não em main.py, porque o servidor sobe com `python3 main.py`: main roda como
`__main__` e um `import main` vindo de auth/ criava uma SEGUNDA cópia do módulo, com outro dict.
A liberação gravava numa cópia e o gate lia a outra (16/10/2026). main.py e auth_routes.py
importam este módulo pelo mesmo nome, então só existe um GRANTS por processo.
"""
import time

GRANTS = {}   # {(token, recurso): expira_em_epoch}
TTL = 30 * 60


def purgar_expirados():
    """`GRANTS` é um dict de PROCESSO — sem isto, só cresce: `valido` limpa a
    própria chave quando ALGUÉM a consulta depois de expirada, mas uma janela que ninguém nunca
    mais consulta (ex.: a pessoa fechou a aba sem outra ação financeira) fica pra sempre. Chamado
    a cada `conceder` — concessões são raras (uma por aprovação financeira/step-up de
    módulo), então a varredura sai barata e o dict nunca acumula mais que o necessário."""
    agora = time.time()
    for chave, exp in list(GRANTS.items()):
        if exp <= agora:
            GRANTS.pop(chave, None)


def conceder(token, recurso, ttl=None):
    purgar_expirados()
    GRANTS[(token, recurso)] = time.time() + (ttl if ttl is not None else TTL)


def valido(token, recurso):
    exp = GRANTS.get((token, recurso))
    if exp and exp > time.time():
        return True
    if exp:
        GRANTS.pop((token, recurso), None)
    return False


def revogar_todos(token):
    """ACHADO-68: chamado no logout — nenhuma janela de step-up (nenhum recurso, não só
    aprovar_financeiro) sobrevive à sessão que a abriu."""
    if not token:
        return
    for chave in [k for k in GRANTS if k[0] == token]:
        GRANTS.pop(chave, None)
