"""Núcleo Ciclo do projeto (manifesto: modulos.py → "ciclo"). Pacote desde 2026-11-13.
Os módulos da raiz com o mesmo nome são shims de compatibilidade (sys.modules).
Sem imports aqui de propósito: import ansioso no __init__ muda a ordem de carga e pode
disparar ciclo de import no boot."""
