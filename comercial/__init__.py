"""Domínio Comercial (manifesto: modulos.py → "comercial"). Pacote desde 2026-11-14.
Os mod_*.py da raiz com o mesmo nome são shims de compatibilidade (sys.modules).
Sem imports aqui de propósito: import ansioso no __init__ muda a ordem de carga e pode
disparar o ciclo mod_contrato ↔ mod_documentos no boot."""
