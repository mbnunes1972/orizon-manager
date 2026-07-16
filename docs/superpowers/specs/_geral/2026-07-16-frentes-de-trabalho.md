# Frentes de Trabalho — Orizon Manager | Dalmóbile

**Data:** 2026-07-16

Segmenta o trabalho para que **devs descentralizados (locais físicos diferentes) atuem em paralelo sem
colidir nos commits**. As frentes se apoiam no manifesto de domínios já existente (`modulos.py`), que
declara o dono de cada arquivo/tabela/rota e um ratchet de dependência (`test_arquitetura_modulos`).
Documento irmão: `2026-07-16-plano-de-testes.md` (ambientes e disciplina de git).

---

## 1. Frentes (faixas de titularidade)

Cada frente é um conjunto de domínios do `modulos.py` escolhido para ser **independente** — dois devs em
frentes diferentes quase nunca tocam o mesmo arquivo. A **frente é a unidade de branch** (`feat/A-…`).
Um dev pode assumir mais de uma frente.

| Frente | Domínios (donos no `modulos.py`) | Dependência | Observação |
|--------|----------------------------------|-------------|------------|
| **A — Comercial/Vendas** | `captacao`, `cadastro`, `comercial` | base | Coração do sistema; **todos dependem dela**. Mudança de interface pública aqui **exige aviso** às outras frentes. |
| **B — Fiscal & Expedição** | `fiscal`, `estoque`, `expedicao` | → A | `fiscal` já é pacote. |
| **C — Financeiro & Folha** | `financeiro`, `folha` | → A | Motor contábil de partida dobrada; alto rigor. |
| **D — Pós-venda** | `montagem`, `assistencias` | → A | Stubs hoje, baixo conflito. |
| **E — Plataforma/Núcleo** | `auth`, `tenancy`, `escopo`, `ciclo`, `integracoes`, `plataforma` | base | Infra compartilhada; mudança sensível → **PR obrigatório**. `auth`/`integracoes` já são pacote. |

> Direção das dependências (do `modulos.py`): `fiscal → cadastro, comercial`; `financeiro → comercial`;
> `folha → cadastro, comercial, financeiro`; `expedicao → comercial, estoque, fiscal`. **A é upstream de
> quase tudo** → é a frente que mais precisa de coordenação ao mudar assinatura de função/rota.

---

## 2. Arquivos compartilhados (regra de convivência)

Colisão nos arquivos de módulo é rara (dono limpo no `modulos.py`). Os ímãs de conflito reais são os
dois monolitos que sobraram e os arquivos de infra transversal.

| Arquivo | Tamanho | Risco | Regra |
|---------|---------|-------|-------|
| **`main.py`** | ~9.100 linhas | Alto — roteador com `do_GET`/`do_POST` inline; todo domínio mexe aqui | Ver **Frente R** (extração por domínio). Enquanto não extraído: edição **coordenada**, commits pequenos e cirúrgicos na própria faixa de rotas. |
| **`static/index.html`** | ~14.300 linhas | **O pior** — frontend inteiro (HTML+CSS+JS) num arquivo só | Precisa de **spec próprio** para quebra por domínio (parciais/JS por módulo). Interino: **marcadores de seção por frente** + dono declarado, para reduzir colisão. |
| **`modulos.py`, `database.py`** | — | Médio — tocados por várias frentes | Mudança sempre em **PR isolado**. O `test_arquitetura_modulos` é o guarda-fronteira automático. |

---

## 3. Frente R — Refatoração do roteador `main.py` (pré-go-live, fatiada)

Objetivo: transformar `main.py` num **despachante fino**, com **um handler de rotas por domínio**
(`<dominio>_routes.py`), seguindo o padrão que o `auth` já inaugurou (`auth.auth_routes` →
`handle_auth_get/post`). Isso é o que **destrava o trabalho paralelo**: cada frente passa a editar o
arquivo de rotas do seu domínio, não o `main.py` compartilhado.

### Método (dois painéis em paralelo)
- **Painel 1 — "Estudo" (nós dois no terminal):** lemos `main.py` + a documentação **linha a linha**,
  isolamos as rotas de **um** domínio por fatia e extraímos para `<dominio>_routes.py`.
- **Painel 2 — "Desenvolvimento monitorado":** features seguem em suas branches, com a **Vera**
  validando. As duas frentes não se atropelam porque a extração mexe só na fatia de rotas do domínio-alvo.

### Garantia de não-regressão
Cada fatia é acompanhada de **testes de caracterização** (capturam a resposta atual da rota antes de
mover o código) → o comportamento tem de ficar **idêntico**. Suíte verde + `test_arquitetura_modulos`
antes de cada merge.

### Ordem sugerida das fatias
1. `financeiro` — conjunto de rotas coeso e bem delimitado; bom primeiro caso.
2. `fiscal` — já é pacote; encaixe natural.
3. `comercial` — o **maior**, por último, já com o padrão maduro.
4. Núcleo (`ciclo`, `tenancy`) — ao fim.

Cada fatia é uma branch (`refactor/R-routes-<dominio>`), mergeada no `main` de forma independente. É
seguro fatiar ao longo de vários dias: entre fatias o sistema fica sempre verde e deployável.

---

## 4. Regras de convivência (resumo)

1. Cada frente na **sua branch**; a frente nomeia o prefixo (`feat/A-…`, `refactor/R-…`).
2. Tocar arquivo compartilhado (`main.py`, `static/index.html`, `modulos.py`, `database.py`) → **PR**.
3. Mudança na **interface pública da Frente A** (assinatura de função/rota da qual outros dependem) →
   avisar as frentes dependentes antes do merge.
4. Antes de merge no `main`: suíte verde + `test_arquitetura_modulos` + Vera em área sensível.
5. Sem `git add .`; commitar só os arquivos da mudança.

---

## Rastreabilidade
- Manifesto de domínios (fonte da titularidade): `modulos.py`.
- Ambientes e disciplina de promoção: `2026-07-16-plano-de-testes.md`.
- Reorganização monolito → pacotes (em andamento): `CLAUDE.md` (seção "Layout do código").
