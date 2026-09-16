# Documentação do Orizon One — por onde começar

> Substitui o índice de 04/07/2026, que apontava para os `modulos/*/SPEC.md` (anteriores ao
> Módulos v12) e ainda chamava o sistema de "Dalmóbile | Sistema de Gestão Comercial". O nome
> mudou para **Orizon One** em agosto; aqueles SPECs viraram histórico (Camada 5).

**Esta é a porta de entrada.** Se você chegou aqui sem contexto — funcionário novo, o Marcelo
depois de um fim de semana, uma sessão de Claude depois de um resumo — comece por este arquivo.

São 365 arquivos de documentação. Eles não estão organizados por assunto, e sim por **compromisso
com a verdade** — que é o que realmente os distingue. Um diário de bordo e um registro de decisão
podem falar do mesmo assunto; a diferença é que o registro de decisão *tem que continuar
verdadeiro*, e o diário não: ele registra o que se sabia naquele dia, e continua certo mesmo
quando envelhece.

Cinco camadas. Cada uma com uma regra diferente sobre verdade.

---

## Camada 1 · O QUE O SISTEMA DEVE SER
### A especificação · **tem que ser verdade sempre**

O que o negócio decidiu que o sistema é. Muda raramente. Se estiver errado, constrói-se a coisa
errada.

| documento | onde |
|---|---|
| Módulos do sistema (v12) | `especificacoes/Modulos_Orizon_v12.docx` |
| Especificação Financeiro (v7) | `especificacoes/Especificacao_Financeiro_Orizon_v7.docx` |
| Provisões, custo de fábrica e margem (rev6) | `especificacoes/Provisoes_Custo_Fabrica_Margem_Orizon_v1_rev6.docx` |
| Regras de funções, perfis e atribuições (rev3) | `especificacoes/Regras_Funcoes_Perfis_Atribuicoes_Orizon_v1_rev3.docx` |
| Diagramação e navegação (v8) | `especificacoes/Diagramacao_e_Navegacao_Orizon_v8.docx` |
| Padrão de design (v10) | `especificacoes/Padrao_Design_Orizon_v10.docx` |
| Controle de entrega de material (v1) | `especificacoes/Controle_Entrega_Material_Orizon_v1.docx` |
| O processo comercial em 38 etapas | `processos/FLUXO_38_ETAPAS.md` |
| Nomenclatura — os nomes que o negócio usa | `referencia/NOMENCLATURA.md` |

**São nove documentos, cerca de 160 KB. Uma tarde de leitura, e tudo o mais deriva daí.**

> **Atenção às versões.** O diretório `especificacoes/` guarda revisões antigas ao lado das
> atuais (Provisões tem rev1 a rev6; Regras de Funções tem rev2 e rev3). **Só a última de cada
> vale.** As anteriores são histórico — Camada 5 — e não deveriam ser lidas como especificação.

> **Dívida conhecida:** esta camada está em `.docx`. São justamente os documentos que mais
> precisam ser verdade, e os únicos que o git não consegue comparar entre versões nem as sessões
> de Claude conseguem ler bem. Converter os principais para Markdown faria o "v12" virar histórico
> de commits em vez de nome de arquivo.

---

## Camada 2 · POR QUE ESTÁ ASSIM
### As decisões · **tem que ser verdade sempre**

Toda escolha importante e o motivo dela. Técnicas **e de negócio** — as duas moram aqui.

| documento | onde |
|---|---|
| Registro de decisões (ADR) | `arquitetura/DECISOES.md` |

**A regra desta camada:** decisão revista **não se apaga**. Marca-se como superada, dizendo o que
a substituiu e quando. Quem lê precisa conseguir reconstruir não só o que vale hoje, mas por que
mudou.

**Por que isso importa mais do que parece:** em 15/09 descobrimos que o ADR-004 ainda dizia
*"sistema interno, não exposto publicamente"* — enquanto o sistema estava escutando na internet
sem firewall. Um registro de decisão desatualizado é pior que nenhum: alguém lê, confia, e decide
errado com confiança.

---

## Camada 3 · COMO SE TRABALHA
### As regras operacionais · **tem que ser verdade hoje**

Como se desenvolve, testa e implanta. Mudou o procedimento, muda o documento no mesmo dia.

| documento | onde |
|---|---|
| Regras de banco, convenções e o que está congelado | `../CLAUDE.md` |
| A esteira: bancada → integração → homologação → produção | `db/ESTEIRA.md` |
| O procedimento de deploy, passo a passo | `db/IMPLANTAR.md` |
| Regras de desenvolvimento | `../DEV_RULES.md` |
| Rotas e banco (precisam de revisão — ver Camada 2) | `arquitetura/ROTAS.md`, `arquitetura/BANCO_DE_DADOS.md`, `arquitetura/STACK.md` |

---

## Camada 4 · O QUE ESTÁ ACONTECENDO
### O trabalho em curso · **verdade enquanto o trabalho existe**

Some quando o trabalho termina — ou melhor, vira Camada 5.

| documento | onde |
|---|---|
| A fila de trabalho, organizada por destino | `db/LISTA_PARALELA.md` |
| O mapa dos módulos: papel × código, duplicações, fronteiras | `db/MAPA_MODULOS.md` |
| Os planos de semana | `db/PLANO_SEMANA_*.md` |
| Os pacotes de tarefa | `db/TAREFA_*.md` |
| O percurso manual de homologação | `db/PERCURSO_HOMOLOGACAO.md` |

**A regra dos destinos** (decidida em 15/09): todo item da fila tem um destino, e só um —
**BETA** (conserto agora), **FRONTEIRA** (morre quando a fronteira for construída), **HIGIENE**
(lote único), **PRODUTO** (decisão do Marcelo), **INFRA** (teste, congelado), **DECIDIDO** (regra
escrita, implementação agendada). **Nada entra sem destino.** É isso que impede a fila de crescer
para sempre.

---

## Camada 5 · O QUE JÁ ACONTECEU
### O histórico · **nunca se corrige**

Registro do que foi encontrado, decidido e feito, com data. **Não se conserta um documento desta
camada** — ele está certo sobre o que se sabia naquele dia. Só cresce.

| documento | onde |
|---|---|
| Os achados, um a um, com medição e desfecho | `db/ACHADOS_CONTABEIS.md` |
| O diário de bordo — viradas de rumo e o porquê | `db/CADERNO_DE_BORDO.md` |
| O log de desenvolvimento | `../DEV_LOG.md` |
| Planos de implementação de jun–ago/2026 (~60 arquivos) | `superpowers/plans/` |
| Desenhos de funcionalidade de jun–ago/2026 (~100 arquivos) | `superpowers/specs/` |
| A auditoria de julho/2026 | `audit/` |
| Especificações de módulo anteriores ao Módulos v12 | `modulos/*/SPEC.md` |

> **`ACHADOS_CONTABEIS.md` é histórico, não fila.** Foi essa confusão — ser as duas coisas ao
> mesmo tempo — que fez a lista de achados parecer infinita. A fila vive na Camada 4.

---

## Como usar isto no dia a dia

**Procurando o que o sistema deve fazer?** Camada 1.
**Perguntando por que está assim?** Camada 2.
**Vai implantar, testar ou desenvolver?** Camada 3.
**Quer saber o que está sendo feito agora?** Camada 4.
**Quer saber o que aconteceu e quando?** Camada 5.

**Ao criar documento novo:** decida a camada **antes** de escrever, e diga isso na primeira linha
do arquivo. Documento sem camada declarada é como achado sem destino — vira acúmulo.

**Ao mudar o sistema:** se a mudança altera o que está na Camada 1, 2 ou 3, o documento muda **no
mesmo commit**. As três camadas de cima não podem ficar para depois.

---

## A separação que resolve a confusão

Nem todo documento precisa ser verdade. Alguns só precisam ser **encontráveis**.

- **Precisa ser verdade:** as camadas 1, 2 e 3 — cerca de **doze documentos**.
- **Precisa ser encontrável:** as camadas 4 e 5 — os outros trezentos e tantos.

Confundir as duas coisas é o que produz documento desatualizado com cara de válido. Foi assim que
o ADR-004 ficou dizendo que o sistema não estava na internet enquanto ele estava.

---

## Convenções de marcação

Usadas dentro dos documentos, em qualquer camada:

| marca | significa |
|---|---|
| `[VALIDAR]` | ponto que precisa de confirmação do Marcelo |
| `[TODO]` | planejado, não implementado |
| `[IMPLEMENTADO]` | concluído e testado |
| `[BUG]` | comportamento incorreto conhecido |

E duas que este documento acrescenta, para a Camada 2:

| marca | significa |
|---|---|
| `[SUPERADA POR ...]` | decisão substituída; diz por qual e quando |
| `[REVISTA EM ...]` | decisão mantida, mas com o contexto atualizado |
