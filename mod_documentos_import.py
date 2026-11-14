# -*- coding: utf-8 -*-
"""Shim de compatibilidade (empacotamento 2026-11-14): o código vive em comercial/mod_documentos_import.py.
`import mod_documentos_import` (main.py, testes, outros módulos) continua funcionando e devolve o MESMO objeto
de módulo — ver o comentário dos shims no topo do main.py e PLANO de organização, Fase 4."""
import sys as _sys
from comercial import mod_documentos_import as _real
_sys.modules[__name__] = _real
