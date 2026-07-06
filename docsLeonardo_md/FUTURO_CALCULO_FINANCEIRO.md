# Fluxo de Cálculo Financeiro — Omie_V3

> Documento complementar ao SPEC.md do módulo financeiro  
> Criado em: 2026-06-10  
> Status: referência para revisões futuras — sistema atual está correto

---

## Visão geral

O cálculo financeiro do Omie_V3 segue 5 etapas sequenciais, cada uma com
uma origem de dados clara e um papel específico. Este documento formaliza
esse fluxo para orientar futuras manutenções e novas funcionalidades.

---

## Etapa 1 — Valor Bruto Base

**Origem:** XML do Promob (`BUDGET/@TOTAL` por ambiente)  
**Escopo:** Apenas os ambientes incluídos no orçamento ativo  

```
Valor Bruto Base = soma de budget_total dos ambientes do orçamento ativo
```

> Ambientes presentes no pool do projeto mas não incluídos no orçamento
> ativo NÃO entram neste cálculo.

---

## Etapa 2 — Valor Bruto Negociado (Modal de Parâmetros)

O modal de parâmetros é compartilhado entre todos os orçamentos do projeto
(alterar um parâmetro altera para todos), mas o cálculo é executado
exclusivamente sobre os ambientes do orçamento ativo.

### Toggle MARCADO — custos repassados ao cliente (gross-up)

Os custos adicionais são embutidos no Valor Bruto, majorando o preço
que o cliente vai pagar:

```
Valor Bruto Negociado = Valor Bruto Base
    + (comissão arquiteto %  × Valor Bruto Base)   [se ativo]
    + (programa fidelidade % × Valor Bruto Base)   [se ativo]
    + custo viagem R$                               [se ativo]
    + brinde R$                                     [se ativo]
    + (carga tributária %    × Valor Bruto Base)   [se ativo]
```

### Toggle DESMARCADO — custos absorvidos pela loja

O Valor Bruto não é alterado. Os custos adicionais existem mas serão
descontados do Valor Líquido Final — a loja os absorve:

```
Valor Bruto Negociado = Valor Bruto Base (inalterado)
```

### Parâmetros editáveis e padrões iniciais

| Parâmetro | Padrão | Toggle padrão | Observação |
|---|---|---|---|
| Comissão arquiteto | 10% | ✅ marcado | Consultor desmarca quando não houver |
| Programa fidelidade | 2% | ✅ marcado | Consultor desmarca quando não houver |
| Custo viagem | R$ 0 | ⬜ desmarcado | Consultor marca quando houver |
| Brinde | R$ 0 | ⬜ desmarcado | Consultor marca quando houver |
| Carga tributária | 0% | editável | Inicia em zero |
| Toggle majoração | — | ✅ marcado | Padrão: custos repassados ao cliente |

> Todos os parâmetros são editáveis. Os valores acima são apenas padrões iniciais.  
> Alterar um parâmetro em qualquer orçamento aplica a todos os orçamentos do projeto.

---

## Etapa 3 — Desconto Comercial → Valor à Vista

O desconto comercial é sempre aplicado sobre o Valor Bruto Negociado:

```
Valor à Vista = Valor Bruto Negociado × (1 - desconto%)
```

**Limites por perfil:**
- Consultor: até 10%
- Gerente: até 20%
- Diretor: até 50%
- Autorização delegada: permite exceder o limite com aprovação de superior

> Se toggle desmarcado: Valor Bruto Negociado = Valor Bruto Base,
> então o desconto incide sobre o valor original do XML.
> Se toggle marcado: o desconto incide sobre o valor já majorado.

---

## Etapa 4 — Valor Líquido Final

Exibido no painel de parâmetros. Representa o que a **loja efetivamente
recebe** após arcar com os custos adicionais internos:

```
Custos Adicionais = (comissão arquiteto × Valor Bruto Base)  [se ativo]
                  + (fidelidade × Valor Bruto Base)           [se ativo]
                  + custo viagem                              [se ativo]
                  + brinde                                    [se ativo]
                  + (tributação × Valor Bruto Base)           [se ativo]

Valor Líquido Final = Valor à Vista − Custos Adicionais
```

**Desconto Total %** — representa a perda real da loja para alcançar
o Valor Líquido Final partindo do Valor Bruto Base:

```
Desconto Total % = 1 − (Valor Líquido Final / Valor Bruto Base)
```

---

## Etapa 5 — Condição Financeira → Valor Final ao Cliente

**Entrada:** Valor à Vista  
**Saída:** Valor que o cliente paga na modalidade escolhida

```
Valor Final ao Cliente = modalidade.calcular(Valor à Vista)
```

### Modalidades atuais

| Modalidade | Função | Status |
|---|---|---|
| À vista / 1x | Passthrough — sem alteração | ✅ implementado |
| Cartão de crédito | `calcular_cartao(valor_avista, parcelas)` | ✅ implementado |
| Aymoré | `calcular_aymore(valor_avista, entrada, parcelas, prazo)` | ✅ implementado |
| Total Flex | `calcular_total_flex(valor_avista, parcelas_custom)` | 🔲 planejado |

### Arquitetura para novas modalidades

As condições financeiras são registradas em tabela no banco, permitindo
configuração sem alterar o código principal:

```sql
CREATE TABLE condicoes_financeiras (
    id          INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL,      -- ex: "Cartão 6x Cielo"
    tipo        TEXT NOT NULL,      -- 'cartao' | 'aymore' | 'total_flex' | 'custom'
    parametros  TEXT NOT NULL,      -- JSON com taxas, parcelas, etc.
    ativo       BOOLEAN DEFAULT 1,
    ordem       INTEGER DEFAULT 0   -- ordem de exibição na interface
);
```

Cada `tipo` mapeia para uma função de cálculo em `mod_fin/`:

```python
CALCULADORAS = {
    'cartao':     calcular_cartao,
    'aymore':     calcular_aymore,
    'total_flex': calcular_total_flex,
    # adicionar nova modalidade: nova função + nova entrada aqui
}

def aplicar_condicao(condicao, valor_avista):
    fn = CALCULADORAS[condicao.tipo]
    return fn(valor_avista, json.loads(condicao.parametros))
```

**Para adicionar nova modalidade no futuro:**
1. Criar `mod_fin/nova_modalidade.py` com a função de cálculo
2. Registrar em `CALCULADORAS` em `mod_fin/__init__.py`
3. Inserir linha na tabela `condicoes_financeiras`
4. Interface de configuração exibe automaticamente

> **Planejado (v0.3.0):** painel de administração para inserir e editar
> condições financeiras sem precisar de deploy.

---

## Fluxo completo

```
XML Promob (budget_total por ambiente)
            ↓
[1] Valor Bruto Base
    soma dos ambientes DO ORÇAMENTO ATIVO
            ↓
[2] Modal de Parâmetros (compartilhado, calcula por orçamento)
    ├── Toggle marcado   → Valor Bruto Negociado (majorado com custos)
    └── Toggle desmarcado → Valor Bruto Negociado = Valor Bruto Base
            ↓
[3] Desconto Comercial (% sobre Valor Bruto Negociado)
            ↓
        Valor à Vista
            ↓
[4] Valor Líquido Final = Valor à Vista − Custos Adicionais
    Desconto Total %    = perda real da loja
            ↓
[5] Condição Financeira (modalidade escolhida pelo consultor)
            ↓
    Valor Final ao Cliente
```

---

## Observações para revisões futuras

- O cálculo atual está correto e validado
- Este documento serve como referência para manutenção e novas features
- Ao implementar Total Flex, seguir o padrão de `CALCULADORAS` acima
- Ao implementar o painel de condições financeiras (v0.3.0), usar a
  tabela `condicoes_financeiras` já especificada aqui
- O modal de parâmetros sempre recalcula sobre `_orcAmbientesAtivos`
  (ambientes do orçamento ativo), nunca sobre `projetoAtivo.ambientes`

---

*Documento: `docs/modulos/financeiro/CALCULO_FINANCEIRO.md`*
