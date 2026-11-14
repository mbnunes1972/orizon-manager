"""validacao_doc.py — validação de dígito verificador de CPF/CNPJ (offline, sem rede).
Aceita com ou sem pontuação. Não consulta a Receita — só rejeita número estruturalmente falso."""
import re


def _digitos(v):
    return re.sub(r"\D", "", v or "")


def valida_cpf(cpf) -> bool:
    d = _digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):
        s = sum(int(d[j]) * ((i + 1) - j) for j in range(i))
        dv = (s * 10) % 11 % 10
        if dv != int(d[i]):
            return False
    return True


def valida_cnpj(cnpj) -> bool:
    d = _digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, i in ((pesos1, 12), (pesos2, 13)):
        s = sum(int(d[j]) * pesos[j] for j in range(i))
        r = s % 11
        dv = 0 if r < 2 else 11 - r
        if dv != int(d[i]):
            return False
    return True


def doc_valido(doc) -> bool:
    """True se `doc` for um CPF (11 díg.) ou CNPJ (14 díg.) válido."""
    d = _digitos(doc)
    if len(d) == 11:
        return valida_cpf(d)
    if len(d) == 14:
        return valida_cnpj(d)
    return False


def erro_doc(valor, rotulo="Documento", tipo=None):
    """Mensagem de erro se `valor` (informado) for inválido; None se vazio ou válido.
    tipo: 'cpf' | 'cnpj' | None (auto por tamanho)."""
    if not (valor or "").strip():
        return None
    validador = {"cpf": valida_cpf, "cnpj": valida_cnpj}.get(tipo, doc_valido)
    return None if validador(valor) else "%s inválido (dígito verificador não confere)." % rotulo
