"""mod_nfe.py — parser + precificação do XML da NF-e da fábrica (Fase 1).
Puro: sem rede, sem banco. Produz a estrutura de preview consumida pelas fases seguintes."""
import re
import xml.etree.ElementTree as ET

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


def _strip_ns(xml_text):
    """Remove os atributos xmlns (default e prefixados) — a NF-e usa um único namespace
    default; sem ele os finds ficam simples (mesma tática usada ao inspecionar o XML real)."""
    return re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_text)


def _txt(el, path, default=None):
    if el is None:
        return default
    x = el.find(path)
    return x.text if (x is not None and x.text is not None) else default


def parse_nfe(xml):
    """XML (str|bytes) da NF-e da fábrica -> {'cabecalho': {...}, 'itens': [...]}.
    Namespace-aware (localiza infNFe sob nfeProc OU NFe puro). vIPI ausente -> 0.0."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    root = ET.fromstring(_strip_ns(xml))
    inf = root if root.tag == "infNFe" else root.find(".//infNFe")
    ide, emit, dest = inf.find("ide"), inf.find("emit"), inf.find("dest")
    cabecalho = {
        "nNF": _txt(ide, "nNF"), "serie": _txt(ide, "serie"),
        "dhEmi": _txt(ide, "dhEmi"), "natOp": _txt(ide, "natOp"),
        "emit": {"cnpj": _txt(emit, "CNPJ"), "nome": _txt(emit, "xNome"), "crt": _txt(emit, "CRT")},
        "dest": {"nome": _txt(dest, "xNome"), "doc": _txt(dest, "CNPJ") or _txt(dest, "CPF")},
    }
    itens = []
    for det in inf.findall("det"):
        prod, imp = det.find("prod"), det.find("imposto")
        vipi = imp.find(".//vIPI") if imp is not None else None
        infad = det.find("infAdProd")
        itens.append({
            "nItem": det.get("nItem"),
            "cProd": _txt(prod, "cProd"),
            "xProd": _txt(prod, "xProd"),
            "ncm": _txt(prod, "NCM"),
            "cfop": _txt(prod, "CFOP"),
            "uCom": _txt(prod, "uCom"),
            "qCom": float(_txt(prod, "qCom", "0") or 0),
            "vUnCom": float(_txt(prod, "vUnCom", "0") or 0),
            "vProd": float(_txt(prod, "vProd", "0") or 0),
            "vIPI": float(vipi.text) if (vipi is not None and vipi.text) else 0.0,
            "infAdProd": infad.text if infad is not None else None,
        })
    return {"cabecalho": cabecalho, "itens": itens}


def consolidar(itens):
    """Agrupa por cProd (na mesma NF-e), somando qCom/vProd/vIPI. Mantém os campos estáticos
    (xProd, ncm, cfop, uCom, vUnCom, infAdProd) da 1ª ocorrência. Preserva a ordem de aparição."""
    ordem, por_cod = [], {}
    for it in itens:
        cod = it["cProd"]
        if cod not in por_cod:
            por_cod[cod] = dict(it)
            ordem.append(cod)
        else:
            ac = por_cod[cod]
            ac["qCom"] += it["qCom"]
            ac["vProd"] += it["vProd"]
            ac["vIPI"] += it["vIPI"]
    return [por_cod[c] for c in ordem]


def precificar(itens_consolidados, markup_pct):
    """Custo unitário = (vProd + vIPI) / qCom; preco_venda_unit = round(custo * (1+pct/100), 2).
    Anexa base/id_peca/tipo (split_cprod) e cor/largura/altura (parse_infadprod)."""
    fator = 1 + (markup_pct / 100.0)
    out = []
    for it in itens_consolidados:
        base, id_peca, tipo = split_cprod(it["cProd"])
        q = it["qCom"] or 0
        custo = (it["vProd"] + it["vIPI"]) / q if q else 0.0
        dim = parse_infadprod(it.get("infAdProd"))
        out.append({
            "cProd": it["cProd"], "base": base, "id_peca": id_peca, "tipo": tipo,
            "xProd": it.get("xProd"), "ncm": it.get("ncm"), "cfop": it.get("cfop"), "uCom": it.get("uCom"),
            "qCom": it["qCom"], "vUnCom": it.get("vUnCom"), "vProd": it["vProd"], "vIPI": it["vIPI"],
            "custo_unit": round(custo, 2), "preco_venda_unit": round(custo * fator, 2),
            "cor": dim["cor"] if dim else None,
            "largura": dim["largura"] if dim else None,
            "altura": dim["altura"] if dim else None,
            "infAdProd": it.get("infAdProd"),
        })
    return out
