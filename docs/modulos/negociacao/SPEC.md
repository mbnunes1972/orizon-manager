# Módulo de Negociação — SPEC

**Status:** `[IMPLEMENTADO]` — atualizado 2026-06-12  
> Bug toggle "Incluir custos adicionais?" ainda pendente — ver [PENDENTE]

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
- Lista de ambientes com checkbox de seleção (legado) ou listagem fixa do orçamento (EP-07)
- **Desconto individual por ambiente** — coluna "Desc.%" com input numérico editável
  - Fórmula: `à vista = bruto × (1 − desc_global%) × (1 − desc_individual%)`
  - Chave EP-07: `'ep07_' + pool_ambiente_id`; legado: nome do arquivo
  - Revertido automaticamente se ultrapassar o limite total de 35%
- Valor por ambiente após desconto (e financiamento distribuído proporcionalmente para Aymoré/TF)

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

onde `bruto_original = Σ budget_total` dos XMLs (nunca o valor majorado pelo gross-up).

---

## Limite de Desconto Total

O sistema impõe um **teto absoluto de 35%** no desconto total, independente do nível do usuário.

- **Salvar parâmetros:** bloqueado se `desconto_total > 35%` com mensagem: *"Desconto total excede o limite máximo de descontos."*
- **Desconto individual:** revertido automaticamente para o valor anterior se ultrapassar o limite
- `_margemAtual` é atualizado em tempo real por `mpAtualizarApoio()` a cada mudança nos parâmetros
- O limite de nível do usuário (10/20/50%) e o teto de 35% são validações independentes e cumulativas

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

## Comportamento de Modais

Todos os modais do sistema respondem à tecla **Esc** como equivalente ao botão "Cancelar" / "Voltar" (sem salvar). Um listener global `keydown` percorre os modais do z-index mais alto ao mais baixo e fecha o primeiro visível.

Modais cobertos: `modal-autorizacao`, `modal-perfil`, `modal-exportar`, `modal-gerente-senha`, `modal-tf-aviso`, `modal-cli-encontrado`, `modal-parceiro`, `modal-cliente`, `modal-pool-sobrescrever`, `modal-pool-renomear`, `modal-remover-amb-orc`, `modal-pool-ambientes`, `modal-novo-orc`, `modal-novo-ambiente`, `modal-params`.

---

## Arquivos relevantes

- `static/index.html` — todo o frontend da negociação
- `mod_margens.py` — função `calcular_margens()`
- `mod_fin/` — módulos financeiros
- `storage.py` — persistência de margens
- `main.py` — `_enriquecer_projetos_com_pool()` corrige contadores de ambientes em listagens
