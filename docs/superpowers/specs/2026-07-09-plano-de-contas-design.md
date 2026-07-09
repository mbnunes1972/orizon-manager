# Plano de Contas — Design (Módulo Financeiro, sub-projeto #1)

> **Status: ✅ IMPLEMENTADO (2026-07-09)** — branch `feat/financeiro-plano-contas`, suíte 687→699. Modelo `Conta`
> (99 contas no seed padrão: 78 analíticas + 21 sintéticas), CRUD por owner (inativar-não-apagar), API
> `/api/financeiro/contas`, aba na page-12. **Corte consciente:** "mover conta" (reparent/recodificar subárvore) **não**
> entrou no #1 — `editar_conta` cobre **nome + ordem**; reparent fica para o #2/futuro (evita recodificar subárvores agora).

> **Fonte de verdade:** `Especificacao_Financeiro_Orizon_v2.docx` (§2 Plano de Contas e §2.1 contas analíticas).
> Este documento é o **design derivado** do 1º sub-projeto. Se a regra de negócio mudar, a alteração volta primeiro
> para o `.docx`. Tratamento contábil/tributário exige validação de contador antes de produção (aviso do `.docx`).

## 0. Contexto e escopo

O módulo Financeiro será construído em **6 sub-projetos** (Plano de Contas → Livro de Lançamentos → Motor
evento→lançamento → DRE societário → DRE por projeto → Auditoria/Reconciliação). Este é o **#1 — Plano de Contas**,
a fundação que todos referenciam. O financeiro atual (`mod_provisoes.py` + `ProvisaoRegistro`, config de provisões/
custos que alimenta o orçamento) **não é tocado**; o Plano de Contas é uma camada **nova**.

**Escopo deste sub-projeto:** modelo `Conta` (árvore hierárquica), CRUD editável com **inativar-não-apagar**, seed do
plano-padrão completo (grupos + analíticas nível 3), API e uma aba **Plano de Contas** na tela Financeiro.
**Fora de escopo (sub-projetos futuros):** lançamentos, DRE, rateio/reconciliação, `projeto_id`. A checagem
"conta tem lançamento?" já é **estruturada** aqui (para o #2 plugar), mas hoje sempre retorna falso (não há livro).

## 1. Decisões de arquitetura (fechadas com o usuário)

- **Tenancy = por owner.** A contabilidade pertence a um **owner** `(owner_tipo, owner_id)` onde `owner_tipo ∈
  {rede, loja}` — espelhando o modelo do `PerfilEmissao`/Emitente. Resolução: se a loja do usuário tem `rede_id`,
  o owner é a **rede**; senão, a **loja avulsa** (ex.: INSPIRIUM, `rede_id=None`). Assim uma rede tem **uma**
  contabilidade compartilhada; loja avulsa tem a sua.
- **Seed completo.** O owner sem plano recebe o **plano-padrão** (grupos 1–5 + subgrupos + ~70 analíticas nível 3
  do Pontta), tudo **editável/renomeável/inativável**. É ponto de partida, ajustável com o contador.

## 2. Modelo de dados — `Conta` (novo, em `database.py`)

```python
class Conta(Base):
    """Conta do Plano de Contas (árvore hierárquica), por owner (rede|loja)."""
    __tablename__ = "conta"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(String(10), nullable=False)   # 'rede' | 'loja'
    owner_id   = Column(Integer,    nullable=False)
    codigo     = Column(String(20), nullable=False)   # hierárquico: '5', '5.4', '5.4.01'
    nome       = Column(Text,       nullable=False)    # editável
    grupo      = Column(Integer,    nullable=False)    # 1..5 (Ativo/Passivo/PL/Receita/Despesa)
    tipo       = Column(String(10), nullable=False)    # 'sintetica' (agrupa) | 'analitica' (folha, recebe lançamento)
    natureza   = Column(String(8),  nullable=False)    # 'devedora' | 'credora' (derivada do grupo no seed)
    pai_id     = Column(Integer, ForeignKey("conta.id"), nullable=True)   # árvore
    ativa      = Column(Integer, default=1)            # inativar-não-apagar
    ordem      = Column(Integer, default=0)            # ordenação entre irmãos (default: por codigo)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_conta_owner_codigo"),)
```

- **`natureza` por grupo:** grupo 1 (Ativo) e 5 (Despesa) → `devedora`; grupos 2 (Passivo), 3 (PL), 4 (Receita) →
  `credora`. (Deduções 4.3 são redutoras de receita — o **sinal na DRE** é tratado no sub-projeto de DRE; aqui a
  `natureza` segue o grupo.)
- **`tipo`:** conta **com filhos = sintética** (só agrupa); **folha = analítica** (recebe lançamento no #2). Uma
  sintética nunca recebe lançamento. Ao criar um filho sob uma analítica, ela **vira sintética** (regra no motor).
- Migração idempotente em `_migrar_colunas` (cria a tabela via `create_all`; sem ALTER retroativo, pois é tabela nova).

## 3. Plano-padrão (seed) — do `.docx` §2 + §2.1 (Pontta)

Estrutura codificada (└ = analítica/folha; demais = sintética). **Editável após o seed.**

```
1  ATIVO
  1.1  Circulante
    └ 1.1.01 Caixa/Bancos
    └ 1.1.02 Contas a Receber (Clientes)
    └ 1.1.03 Estoques
    └ 1.1.04 Adiantamentos a Fornecedores
  1.2  Não Circulante
    1.2.1 Imobilizado
      └ 1.2.1.01 Itens de Informática
      └ 1.2.1.02 Veículos
      └ 1.2.1.03 Obras/Reforma de Loja
      └ 1.2.1.04 Show Room
    └ 1.2.2 Intangível
2  PASSIVO
  2.1  Circulante
    └ 2.1.01 Fornecedores a Pagar
    └ 2.1.02 Obrigações Trabalhistas
    └ 2.1.03 Obrigações Tributárias
    2.1.04 Provisões
      └ 2.1.04.01 Provisão de Comissão
      └ 2.1.04.02 Provisão de Montagem
      └ 2.1.04.03 Provisão de Garantia Técnica
      └ 2.1.04.04 Provisão de Devolução
    └ 2.1.05 Financiamento Total Flex a Pagar
  2.2  Não Circulante
    └ 2.2.01 Financiamentos de Longo Prazo (Empréstimos e Dívidas — principal)
3  PATRIMÔNIO LÍQUIDO
  └ 3.1 Capital Social
  └ 3.2 Reservas
  └ 3.3 Lucros/Prejuízos Acumulados
  └ 3.4 Distribuição de Lucros
4  RECEITAS
  4.1 Vendas de Produtos
    └ 4.1.01 Receitas com Vendas
    └ 4.1.02 Receita com Vendas de Assistência
  4.2 Serviços
    └ 4.2.01 Receita de Serviços
    └ 4.2.02 Prestação de Serviços para Terceiros
  4.3 Deduções
    └ 4.3.01 Simples Nacional s/ Vendas
    └ 4.3.02 Devolução de Vendas
  4.4 Outras Receitas Não Operacionais
    └ 4.4.01 Receita de Aluguéis
5  DESPESAS / CUSTOS
  5.1 CMV
    └ 5.1.01 CMV Fábrica (Dal Mobile)
    └ 5.1.02 Frete Fábrica
  5.2 Custo de Serviço (inclui operacional-logístico)
    └ 5.2.01 Montagem
    └ 5.2.02 Comissão Executivo de Montagem
    └ 5.2.03 Viagens de Pedido
    └ 5.2.04 Salários Operacionais
    └ 5.2.05 Ajudante Semanal
    └ 5.2.06 Combustível de Depósito
    └ 5.2.07 Pedágio
    └ 5.2.08 Frete Local
    └ 5.2.09 Insumos
    └ 5.2.10 Manutenção de Veículos
    └ 5.2.11 Viagens de Supervisão
  5.3 Despesas Comerciais
    └ 5.3.01 Comissão de Vendedor
    └ 5.3.02 Comissão de Indicador
    └ 5.3.03 Comissão Administrativa
    └ 5.3.04 Pontos Programa de Indicação
    └ 5.3.05 Premiação de Vendedores
    └ 5.3.06 Salários de Vendas
    └ 5.3.07 Marketing/Campanhas de Divulgação
    └ 5.3.08 Salário Marketing
    └ 5.3.09 Site e Hospedagem
    └ 5.3.10 Combustível de Venda
    └ 5.3.11 Uniformes
    └ 5.3.12 Brindes
    └ 5.3.13 Suprimento a Cliente
    └ 5.3.14 Viagens de Especificador
  5.4 Despesas Administrativas
    └ 5.4.01 Aluguel
    └ 5.4.02 Energia Elétrica
    └ 5.4.03 Água
    └ 5.4.04 Telefonia Fixa/Móvel e Internet
    └ 5.4.05 Contabilidade
    └ 5.4.06 Assessoria Jurídica
    └ 5.4.07 Consultoria
    └ 5.4.08 Segurança e Seguros
    └ 5.4.09 Material de Limpeza/Expediente
    └ 5.4.10 Sistemas (ERP, CRM, assinatura digital)
    └ 5.4.11 Salários Administrativos
    └ 5.4.12 Pró-labore
    └ 5.4.13 Encargos sobre Folha
    └ 5.4.14 Vale-Transporte
    └ 5.4.15 Sindicato
    └ 5.4.16 Rescisões
    └ 5.4.17 IPVA/IPTU/Licenciamentos
    └ 5.4.18 Manutenção (loja, veículos, informática)
  5.5 Despesas Financeiras
    └ 5.5.01 Tarifas Bancárias
    └ 5.5.02 Juros de Empréstimos (só o juro, não o principal)
    └ 5.5.03 Custo de Antecipação de Recebíveis
  5.6 Constituição de Provisões
    └ 5.6.01 Constituição de Provisão (contrapartida do 2.1.04)
```

> **Nota:** o grupo "operacional-logístico" do Pontta (5.2/5.4) foi alocado em **5.2 (Custo de Serviço)** por padrão;
> como tudo é editável, o contador reorganiza para 5.4 o que for despesa fixa. Codificação `NN.NN.NN` com zero à
> esquerda no nível 3 (ordenação lexicográfica = ordem contábil).

O seed vive em `mod_contabil.py` como estrutura de dados (lista/árvore de `(codigo, nome)`), materializada por owner
na primeira vez (idempotente: não duplica se já existir plano para o owner).

## 4. Regras de negócio

- **Criar:** conta nova sob um pai (ou raiz de grupo). Herda `owner`, `grupo` (do pai/código), `natureza` (do grupo).
  Ao criar filho de uma conta **analítica**, o pai **vira sintética**.
- **Renomear / reorganizar:** `nome`, `ordem` e `pai_id`/`codigo` são editáveis livremente (é a "Restrição única"
  do `.docx`: só não se apaga conta com lançamento).
- **Inativar-não-apagar:** `DELETE` só é permitido se a conta for **folha** (sem filhos) **e sem lançamentos**
  (checagem `_tem_lancamentos(conta_id)` — hoje sempre `False`, o #2 implementa de verdade). Caso contrário → **inativa**
  (`ativa=0`). Conta inativa some da árvore por padrão (flag `?incluir_inativas=1` mostra).
- **Sintética não recebe lançamento** (validado no #2; aqui só marca `tipo`).
- **Escopo/acesso:** editar o plano exige capability financeira (reuso de `pode_editar_dados_loja`/perfil financeiro;
  definido no plano de implementação conforme as capabilities existentes). Gate do domínio `financeiro` (módulo ativo).

## 5. API — `/api/financeiro/contas` (em `mod_contabil.py`, roteado no dispatch)

- `GET  /api/financeiro/contas[?incluir_inativas=1]` → **árvore** do owner do usuário (seed-on-first-access se vazio).
- `POST /api/financeiro/contas` `{pai_id, nome}` → cria conta (código gerado no próximo nível do pai) → 201 + conta.
- `PUT  /api/financeiro/contas/<id>` `{nome?, pai_id?, ordem?}` → renomeia/reorganiza.
- `DELETE /api/financeiro/contas/<id>` → apaga se folha+sem-lançamento; senão inativa (resposta indica qual ocorreu).
- Todos resolvem o **owner** do usuário e barram cross-owner (uma loja/rede não vê/edita o plano de outra).

## 6. UI — aba "Plano de Contas" na tela Financeiro (page-12)

- A page-12 (hoje "Provisões e custos-padrão") ganha **abas**: **Provisões** (conteúdo atual) e **Plano de Contas** (novo).
- Plano de Contas: **árvore expansível** (grupos → subgrupos → analíticas), com badge de código, nome editável inline,
  botão **+ conta** (sob o nó), **renomear**, **inativar/apagar** (mostra qual aconteceu), toggle "mostrar inativas".
- Segue os tokens do design (sem cores hardcoded; usa `--accent`, `--muted`, etc.). Sintética vs analítica com peso/ícone.

## 7. Manifesto de módulos (`modulos.py`)

Domínio `financeiro` passa a declarar: `arquivos += ["mod_contabil.py"]`, `tabelas += ["conta"]`,
`rotas += ["/api/financeiro/contas"]`. Mantém `depende_de: ["comercial"]` (o Plano de Contas em si não depende de
comercial, mas o domínio já depende; sem mudança). O teste de arquitetura (`test_arquitetura_modulos`) deve seguir verde.

## 8. Testes (TDD no backend)

- Seed: materializa o plano-padrão para um owner; **idempotente** (rodar 2× não duplica); conta raiz de cada grupo
  1–5 existe; total de analíticas == esperado; naturezas corretas por grupo.
- CRUD: criar filho vira pai sintético; renomear/mover; **inativar-não-apagar** (folha sem lançamento → apaga;
  com filhos → inativa); código único por owner.
- Tenancy: owner resolvido de loja→rede; loja avulsa = próprio owner; cross-owner barrado (não vê plano alheio).
- Árvore: `GET` monta hierarquia correta; `incluir_inativas` respeita a flag.
- Frontend: sem teste JS → verificação manual (árvore, add/editar/inativar).

## 9. Fora de escopo (próximos sub-projetos)
Livro de Lançamentos (#2), motor evento→lançamento (#3), DRE societário (#4), DRE por projeto (#5),
Auditoria/Reconciliação (#6). A dimensão `projeto_id` entra no #2.

## 10. Self-review
- **Cobertura do .docx §2/§2.1:** todos os grupos 1–5, subgrupos e as ~70 analíticas do Pontta estão no seed (§3);
  regra "editável / inativar-não-apagar" = §4; hierarquia em árvore = modelo §2.
- **Consistência:** `Conta` (owner, codigo, grupo, tipo, natureza, pai_id, ativa) usada igual em API/UI/testes;
  tenancy espelha `PerfilEmissao` (owner_tipo loja|rede). Sem `projeto_id`/lançamento aqui (declarado fora de escopo).
- **Ambiguidade resolvida:** "2.1.x/2.1.y" do `.docx` viraram códigos concretos (2.1.04 Provisões, 2.1.05 Total Flex);
  operacional-logístico alocado em 5.2 por padrão (editável).
