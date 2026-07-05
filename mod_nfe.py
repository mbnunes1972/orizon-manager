"""mod_nfe.py — parser + precificação do XML da NF-e da fábrica (Fase 1).
Puro: sem rede, sem banco. Produz a estrutura de preview consumida pelas fases seguintes."""
import re

MARKUP_TESTE_PADRAO = 30.0   # % — valor de teste do CLI; a origem real do markup é config (fases 2+)

_RE_CPROD = re.compile(r'^(.+?)\[([^\]]+)\]$')


def split_cprod(cprod):
    """'50079[2131748]' -> ('50079','2131748','sob_medida'); '80070' -> ('80070', None, 'padrao')."""
    m = _RE_CPROD.match(cprod or "")
    if m:
        return (m.group(1), m.group(2), "sob_medida")
    return (cprod or "", None, "padrao")


def parse_infadprod(texto):
    """'COR LARGURA ALTURA' -> {cor,largura,altura} SÓ quando os 2 últimos tokens são inteiros.
    Caso contrário None (o campo é não-confiável na prática). Nunca levanta."""
    if not texto:
        return None
    toks = texto.split()
    if len(toks) >= 3 and toks[-1].isdigit() and toks[-2].isdigit():
        return {"cor": " ".join(toks[:-2]), "largura": int(toks[-2]), "altura": int(toks[-1])}
    return None
