# Módulo de Negociação — SPEC

**Status:** `[IMPLEMENTADO]` (com bug pendente — ver [PENDENTE])

---

## Visão geral

O módulo de negociação é o coração comercial do sistema. Permite ao consultor apresentar ao cliente o valor final do projeto com desconto, forma de pagamento e custos adicionais, respeitando os limites de cada perfil de acesso.

---

## Fluxo principal

```
Projeto carregado
    → Ambientes selecionados
    → Desconto aplicado (respeitando limite do perfil)
    → Forma de pagamento selecionada
    → Simulação financeira calculada
    → Orçamento salvo ou aprovado
```

---

## Tela de negociação (page-02)

### Cabeçalho
- Valor bruto total (soma dos XMLs selecionados)
- Desconto aplicado (R$ e %)
- Valor à vista

### Tabela de ambientes
- Lista de ambientes com checkbox de seleção
- Desconto individual por ambiente (opcional)
- Valor por ambiente após desconto

### Sidebar — Parâmetros visíveis
- Campo de desconto (%) com validação de limite
- Botão "✓ OK" quando desconto excede limite
- Select de modalidade de pagamento
- Select de parcelas
- Painel de simulação financeira

### Botões de ação
- "Salvar orçamento" — salva estado sem avançar
- "Aprovar orçamento →" — bloqueia o projeto e avança para exportação
- "⚙ Parâmetros" — abre modal de parâmetros internos

---

## Modal de parâmetros

Acessível apenas para gerentes e diretores (consultor não vê).

### Campos
| Campo | Tipo | Descrição |
|---|---|---|
| Incluir custos adicionais? | Toggle | Gross-up dos custos no valor bruto |
| Desconto de venda | % | Mesmo campo da sidebar |
| Comissão do arquiteto | Toggle + % | Custo interno |
| Programa de fidelidade | Toggle + % | Custo interno |
| Custo Viagem | Toggle + R$ | Custo interno |
| Brinde | Toggle + R$ | Custo interno |

### Painel de apoio à negociação
Visível somente no modal. Mostra ao consultor a margem interna:
- Valor bruto total
- Desconto
- Valor à vista
- − Comissão arquiteto
- − Programa de fidelidade
- − Custo de viagem
- − Brinde
- **Valor líquido final** (margem da loja)
- **Desconto Total** (calculado sempre sobre bruto original dos XMLs)

---

## Regras de desconto

### Limites por perfil
- Consultor: máximo 10%
- Gerente: máximo 20%
- Diretor: máximo 50%

### Autorização delegada
- Desconto acima do limite → solicita credenciais de gerente ou diretor
- O limite autorizado é o desconto específico aprovado (não o limite do autorizador)
- Ex: gerente autoriza 15% → novo limite é 15%, não 20%
- Persiste durante a negociação, reseta ao trocar de projeto
- Desconto salvo no projeto vira limite ao reabrir

### Toggle "Incluir custos adicionais?"
- Desligado (padrão): valor bruto = valor original dos XMLs
- Ligado: gross-up aplicado na seguinte ordem:
  1. `bruto_arq = bruto / (1 − arq%)` (se arquiteto ativo)
  2. `bruto_fid = bruto_arq / (1 − fid%)` (se fidelidade ativa)
  3. `bruto_viagem = bruto_fid + custo_viagem` (se fora da sede)
  4. `bruto_cliente = bruto_viagem + brinde` (se brinde ativo)

---

## Cálculo do Desconto Total

O "Desconto Total" no painel de apoio é calculado **sempre** sobre o valor bruto original dos XMLs, independente do toggle "Incluir custos adicionais?":

```
Desconto Total % = (bruto_original − valor_liquido_final) / bruto_original × 100
```

---

## Salvar vs Aprovar

| Ação | Efeito |
|---|---|
| Salvar orçamento | Salva estado atual no projeto.json — pode continuar editando |
| Aprovar orçamento | Bloqueia o projeto — não permite mais alterações — avança para exportação Omie |

---

## [PENDENTE] Bug — Toggle "Incluir custos adicionais?"

**Descrição:** O toggle não persiste corretamente entre aberturas do modal.

**Fluxo do bug:**
1. Marcar toggle → Salvar → ok ✓
2. Entrar/sair sem salvar → ok ✓
3. Entrar novamente → toggle aparece desmarcado ✗

**Causa identificada:** `carregarMargensSalvas` recarrega do servidor após fechar o modal sem salvar, e o servidor retorna o JSON onde `incluir_custos` pode estar desatualizado.

**Arquivos:** `static/index.html` — funções `fecharModalParams`, `carregarMargensSalvas`, `abrirModalParams`.

---

## Arquivos relevantes

- `static/index.html` — todo o frontend da negociação
- `mod_margens.py` — função `calcular_margens()`
- `mod_fin/` — módulos financeiros
- `storage.py` — persistência de margens
