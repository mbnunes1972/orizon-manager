"""
integracoes/ — camada de integração com serviços externos.

Focus NF-e (emissor_fiscal/focus_client/focus_config) e Promob (promob_grupos,
projetos_store). Núcleo: pode ser importado por qualquer domínio. A integração
Omie foi REMOVIDA (faxina 2026-07-23); o armazenamento local de projetos que
vivia em mod_omie.py está em projetos_store.py.

Import de fora:      from integracoes import promob_grupos
Import entre irmãos: from . import focus_client

Ver fiscal/__init__.py para o padrão e o porquê do ratchet entrar no pacote.
"""
