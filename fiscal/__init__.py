"""
fiscal/ — módulo Fiscal (NF-e/NFS-e): parser, precificação, emissão e mapa fiscal.

Pacote piloto da reorganização de 2026-07-15. Segue o precedente do mod_fin/:
pacote na raiz, registrado em modulos.py pelo nome do diretório (sem .py).

Import de fora:      from fiscal import mod_nfe
Import entre irmãos: from . import mod_fiscal   (relativo — não cria dependência
                     cruzada aos olhos do ratchet de arquitetura)

O ratchet (tests/test_arquitetura_modulos.py) ENTRA neste pacote: _arquivos_do_modulo
expande diretório em .py. Antes disso, empacotar equivalia a sair da verificação.
"""
