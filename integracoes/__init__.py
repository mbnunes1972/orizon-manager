"""
integracoes/ — camada de integração com serviços externos.

Focus NF-e (emissor_fiscal/focus_client/focus_config), Omie (mod_omie) e
Promob (promob_grupos). Núcleo: pode ser importado por qualquer domínio.

Import de fora:      from integracoes import promob_grupos
Import entre irmãos: from . import focus_client

Ver fiscal/__init__.py para o padrão e o porquê do ratchet entrar no pacote.
"""
