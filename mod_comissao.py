# -*- coding: utf-8 -*-
"""Shim de compatibilidade (empacotamento 2026-11-13): o código vive em folha/mod_comissao.py.
`import mod_comissao` (main.py, testes, outros módulos) continua funcionando e devolve o MESMO objeto
de módulo — ver o comentário dos shims no topo do main.py e PLANO de organização, Fase 5."""
import sys as _sys
from folha import mod_comissao as _real
_sys.modules[__name__] = _real
