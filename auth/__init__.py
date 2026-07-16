"""
auth/ — identidade e acesso: sessão, autorização, perfis e usuários.

Núcleo: pode ser importado por qualquer domínio.

Import de fora:      from auth import perfis
Import entre irmãos: from . import perfis

__init__ DELIBERADAMENTE VAZIO. A tentação era transformar o antigo auth.py neste
__init__ (assim `import auth` seguiria idêntico), mas ele faz `from database import
...` — e aí todo `from auth import perfis` passaria a arrastar o database junto, nos
17 arquivos que importam perfis e hoje não tocam o banco. Acoplamento novo escondido
numa mudança de pasta. O preço de não fazer isso é o `from auth import auth`, que é
feio mas é o idioma do próprio Python (from datetime import datetime).
"""
