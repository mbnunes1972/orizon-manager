# Validação de CPF/CNPJ nos cadastros — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Rejeita **CPF/CNPJ falso** (dígito verificador) em
> todos os cadastros. O documento **segue opcional** no cadastro (cliente/parceiro etc.) — valida-se **só se
> informado**; obrigatório mesmo só na geração do contrato (já existente).

## 1. Motivação

Hoje nenhum cadastro valida o **dígito verificador** de CPF/CNPJ — o cadastro de cliente só checa
**unicidade** do CPF (`main.py`), então números falsos (ex.: `123.123.123-00`, o placeholder `012.021.345-01`
do Marcelo) entram e só quebram lá na SEFAZ (o smoke da NF-e revelou "CPF inválido"). Validar no cadastro
barra o dado ruim na origem.

## 2. Decisões (brainstorming)

- **Escopo:** **todos** os cadastros com documento — **Cliente** (`cpf`/`cnpj`), **Parceiro** (`cpf_cnpj`),
  **Usuário** (`cpf`), **Rede** (`cnpj`), **Loja** (`cnpj`).
- **Opcional, mas não-falso:** valida **apenas se o campo for informado** (não torna obrigatório); vazio é OK.
- **Backend autoritativo** (rejeita 400 com mensagem clara) + **frontend inline** (UX no modal de cliente; os
  demais mostram o erro do backend).
- **Não retroativo:** vale para cadastros novos/editados; placeholders atuais só somem via edição.

## 3. Util — `validacao_doc.py` (novo, puro, testável)

```python
def _digitos(v): return re.sub(r"\D", "", v or "")

def valida_cpf(cpf) -> bool:
    d = _digitos(cpf)
    if len(d) != 11 or d == d[0]*11: return False
    for i in (9, 10):
        s = sum(int(d[j]) * ((i+1)-j) for j in range(i))
        dv = (s*10) % 11 % 10
        if dv != int(d[i]): return False
    return True

def valida_cnpj(cnpj) -> bool:
    d = _digitos(cnpj)
    if len(d) != 14 or d == d[0]*14: return False
    pesos1 = [5,4,3,2,9,8,7,6,5,4,3,2]; pesos2 = [6]+pesos1
    for pesos, i in ((pesos1, 12), (pesos2, 13)):
        s = sum(int(d[j]) * pesos[j] for j in range(i))
        r = s % 11; dv = 0 if r < 2 else 11 - r
        if dv != int(d[i]): return False
    return True

def doc_valido(doc) -> bool:
    d = _digitos(doc)
    if len(d) == 11: return valida_cpf(d)
    if len(d) == 14: return valida_cnpj(d)
    return False

def erro_doc(valor, rotulo="Documento", tipo=None):
    """Retorna a mensagem de erro se `valor` (informado) for inválido, ou None se vazio/válido.
    tipo: 'cpf' | 'cnpj' | None (auto por tamanho)."""
    if not (valor or "").strip(): return None
    ok = {"cpf": valida_cpf, "cnpj": valida_cnpj}.get(tipo, doc_valido)(valor)
    return None if ok else "%s inválido (dígito verificador não confere)." % rotulo
```

## 4. Backend — aplicar nos handlers (`main.py`)

Em cada create/edit, **antes de persistir**, validar o(s) campo(s) de documento com `validacao_doc.erro_doc`;
se retornar mensagem → responder `{"ok": False, "erro": <msg>}` code **400**. Sempre **só se informado**.

- **Cliente** `POST /api/clientes` + `POST /api/clientes/<id>/editar`: valida `cpf` (tipo "cpf") **e** `cnpj`
  (tipo "cnpj"). *(A checagem de unicidade de CPF existente permanece.)*
- **Parceiro** create/edit: valida `cpf_cnpj` (tipo None → auto: 11=CPF, 14=CNPJ; comprimento diferente e
  não-vazio → inválido).
- **Usuário** create/edit: valida `cpf` (tipo "cpf").
- **Rede** create/edit: valida `cnpj` (tipo "cnpj").
- **Loja** create/edit: valida `cnpj` (tipo "cnpj").

## 5. Frontend (`static/index.html`)

- **Modal de cliente** (`cli-cpf`/`cli-cnpj`): validação **inline** ao sair do campo — reusar/estender o
  `cli-aviso-cpf` (já existe) e um aviso análogo para CNPJ; bloquear o "Salvar" com aviso claro se inválido
  (o backend também barra). `esc()` no dinâmico.
- **Demais cadastros** (parceiro/usuário/rede/loja): mostram o **erro do backend** (400 → `avisoPopup`) —
  sem inline dedicado (menor superfície; o backend é a trava).

## 6. Testes

- **`tests/test_validacao_doc.py`:** `valida_cpf` (válido; DV errado; repetido `111...`; com/sem pontuação;
  tamanho errado), `valida_cnpj` (idem), `doc_valido` (11→CPF, 14→CNPJ, outro→False), `erro_doc` (vazio→None,
  válido→None, inválido→msg; tipo cpf/cnpj/auto). CPFs/CNPJs de teste **válidos** conhecidos.
- **e2e:** `POST /api/clientes` com `cpf` inválido → 400; com CPF válido → 200; **sem** cpf → 200 (opcional);
  com `cnpj` inválido (contribuinte) → 400. Um caso por cadastro (parceiro/usuário/rede/loja) — inválido→400,
  válido→200.
- Suíte verde (baseline 601). **Nota:** o `seed`/fixtures usam CPFs placeholder (`111.111.111-11` etc.) —
  se algum teste existente criar cadastro via endpoint com CPF inválido, **trocar para um CPF válido** (ou
  omitir o CPF). Levantar esses no plano.

## 7. Fora de escopo

- Correção retroativa dos cadastros já inválidos (é edição manual pelo usuário).
- Validação de outros documentos (IE, inscrição municipal) — formatos municipais/estaduais variados.
- Consulta de existência real na Receita (só dígito verificador, offline).
