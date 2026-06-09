# Módulo de Parceiros — SPEC

**Status:** `[TODO]`

---

## Visão geral

Cadastro de parceiros comerciais que indicam ou participam de projetos. A comissão padrão do parceiro preenche automaticamente o campo de comissão no modal de parâmetros da negociação.

---

## Tipos de parceiro

- `arquiteto`
- `designer`
- `decorador`
- `corretor`
- `engenheiro`
- `indicador`

---

## Funcionalidades a implementar

### Lista de parceiros
- Exibição com nome, tipo, CPF/CNPJ e telefone
- Busca por nome ou CPF/CNPJ
- Botão "Novo parceiro"

### Cadastro/Edição
- Modal com todos os campos
- Tipo selecionável (dropdown)
- Comissão padrão (%)

### Vinculação com projeto
- Campo de busca de parceiro ao criar/abrir projeto
- Se não existir: botão "+ Cadastrar novo parceiro"
- `projeto.json` salva `parceiro_id`
- Ao selecionar parceiro: preenche automaticamente `comissao_arq_pct` no modal de parâmetros

### Regra de comissão automática
- Ao vincular parceiro ao projeto, o campo "Comissão do arquiteto" no modal de parâmetros é preenchido com `comissao_padrao_pct` do parceiro
- O consultor pode ajustar o valor manualmente para aquela negociação específica
- A alteração manual não altera o cadastro do parceiro

---

## Campos do cadastro

| Campo | Obrigatório | Formato | Observação |
|---|---|---|---|
| Nome completo | ✓ | Texto livre | |
| Tipo | ✓ | Dropdown | Ver tipos acima |
| CPF/CNPJ | | 000.000.000-00 ou 00.000.000/0001-00 | |
| E-mail | | email@dominio.com | |
| Telefone | | (12) 3811-5199 | Máscara automática |
| WhatsApp | | (12) 98115-1998 | Máscara automática |
| Comissão padrão (%) | | 0.0–30.0 | Preenchimento automático na negociação |

---

## Modelo de dados

```python
class Parceiro(Base):
    __tablename__ = "parceiros"
    id                  = Column(Integer, primary_key=True)
    nome                = Column(String(150), nullable=False)
    cpf_cnpj            = Column(String(18))
    tipo                = Column(String(30), nullable=False)
    email               = Column(String(120))
    telefone            = Column(String(20))
    whatsapp            = Column(String(20))
    comissao_padrao_pct = Column(Float, default=0.0)
    criado_em           = Column(DateTime, default=datetime.utcnow)
```

---

## Rotas a implementar

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/parceiros` | Lista todos |
| GET | `/api/parceiros/buscar?q=` | Busca por nome ou CPF/CNPJ |
| GET | `/api/parceiros/<id>` | Retorna um parceiro |
| POST | `/api/parceiros` | Cria novo |
| PUT | `/api/parceiros/<id>` | Atualiza |

---

## User Stories

**US-PAR-001** — Como consultor, quero cadastrar um parceiro com seu tipo e comissão padrão.

**US-PAR-002** — Como consultor, ao vincular um arquiteto a um projeto, quero que sua comissão padrão seja preenchida automaticamente no modal de parâmetros.

**US-PAR-003** — Como consultor, quero buscar um parceiro pelo nome ou CPF/CNPJ ao criar um projeto.

**US-PAR-004** — Como consultor, quero ajustar a comissão de um parceiro para uma negociação específica sem alterar seu cadastro.
