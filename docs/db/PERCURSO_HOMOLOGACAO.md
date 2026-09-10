# Percurso manual de homologação

O teste que a suíte não faz. Repete-se **inteiro** a cada candidato, não só
na parte que mudou — a razão está no ROTEIRO: a suíte prova o servidor, o
percurso prova o sistema.

**Candidato atual:** `v2026.09.09-beta1` (`871817b`) — Integração e
Homologação. **Produção não recebeu nada** desde 28/08 e segue fora da
esteira (`IMPLANTAR.md`, `### Produção — diagnóstico de 04/09`).

**Este documento substitui a versão de 01/09** (`v2026.09.01-beta1`, quatro
seções A-E sobre o fichário e a Conciliação Final). Aquele percurso continua
válido — está inteiro aqui dentro, nas etapas 11 e 21 — e o git guarda a
redação anterior. Desde então entraram **F2-8 a F2-42**: bloco fiscal,
fuso da competência, Item Especial, painel da Aprovação Financeira revisável,
o modelo contábil de reconhecimento na emissão, e a linha inteira do
Complemento de PE (F2-40/41/42, fechada ontem à noite).

**Como reportar:** defeito encontrado vira achado numerado, não vira recado.
Diga em que etapa, o que você esperava, o que apareceu. Print quando o
número estiver na tela.

---

## 0 · Antes de começar

### 0.1 Confirmar o que está rodando

Não olhar `git log` no servidor — perguntar direto:

    cd /root/orizon-manager && git describe --tags     # esperado: v2026.09.09-beta1
    cd /root/orizon-homolog && git describe --tags     # esperado: v2026.09.09-beta1

E a bancada, que não aparece no `git describe` de servidor nenhum e já ficou
duas migrations atrás sem ninguém notar:

    cd /mnt/e/2026/DESENVOLVIMENTO/orizon-manager
    set -a && . ./.env && set +a && python3 -m alembic current
    # esperado: 9a1b2c3d4e5f (head) — a MESMA dos servidores

Se a bancada não devolver `9a1b2c3d4e5f`, `alembic upgrade head` antes de
qualquer percurso. A suíte monta o próprio schema e não denuncia esse atraso;
o app aberto na tela, sim.

### 0.2 O interruptor de apoio

O F2-41 marcou (não apagou) os textos de diagnóstico do modal do complemento
com a classe `apoio-dev`, escondida por padrão. Para vê-los em Homologação,
ligue `data-apoio="on"` no `<body>` pelo console:

    document.body.dataset.apoio = 'on'

Faça o percurso **com o interruptor desligado** — é o que o cliente vê. Ligue
só quando quiser conferir uma divergência que apareceu.

### 0.3 O que o percurso precisa

- Uma conta **com** `pode_aprovar_financeiro` (para as etapas 8 e 11d).
- Uma conta **sem** ela (perfil "operador" ou "consultor") — a Fatia 3 do
  F2-40 esconde as etapas 8 e 11d por inteiro para essa conta, e isso se
  prova com um login, não com um clique.
- Um projeto novo, do zero, percorrido até o fim.
- O **Projeto 11** de Homologação intacto, para a conferência 11.5 abaixo.

### 0.4 Ler antes dos logs, quando algo divergir

    journalctl -u orizon-b --since today --no-pager | grep -E 'F2-41-SOMBRA|F2-42-FALLBACK'

`[F2-42-FALLBACK]` **não pode aparecer** num percurso normal — ele só dispara
quando o motor não alcança um ambiente. Se aparecer, é achado.

---

## 1 · Cadastro do cliente (etapa 1)

1.1 Cadastre um cliente novo. No campo de CPF/CNPJ, digite primeiro um
**CPF com dígito verificador errado** (ex.: `111.111.111-11`). Tem que
recusar — a validação entrou no F2-6 e cobre os três caminhos de assinatura
mais o webhook, mas o cadastro é onde o número nasce.

1.2 Corrija e salve.

## 2 · Criação do projeto (etapa 2)

2.1 Crie o projeto. Confira que ele aparece na lista **com o nome da etapa
correto** — a lista de Projetos e o diálogo de transferência mostram
"Logística e Expedição" para a posição 13, não "Produção" (dois dicionários
que já divergiram uma vez).

2.2 Faça login com a conta **Consultor** e confirme que ela vê só os projetos
que criou; com gerente+, todos.

## 3 · Briefing (etapa 3)

3.1 Preencha e conclua. Nada mudou aqui — a etapa entra no percurso porque é
o contêiner das seguintes, não porque tem conserto para provar.

---

## 4 · Orçamento e negociação (etapa 4) — o bloco que mais mudou

Suba os XMLs de pool e monte a negociação. Esta etapa acumula F2-11, F2-12,
F2-13, F2-32, F2-33, F2-35 a F2-38.

### 4.1 As recusas no upload

4.1.1 Suba um XML de **pool** com um item de markup ≤ 1. Tem que **recusar no
upload**, nomeando o item (`itens_com_markup_invalido`, F2-13). A regra é uma
só: markup > 1 **por item**.

4.1.2 Suba um XML que não fecha a conta consigo mesmo (soma dos itens ≠ total
do ambiente). Recusa no upload, pool e PE (`consistencia_interna`, F2-12).

4.1.3 Toda recusa tem que **se explicar sozinha** — dizer qual arquivo, qual
item, qual número. Recusa sem detalhe é achado (F2-23).

### 4.2 O Item Especial (F2-35 → F2-39) — conceito novo, nunca percorrido inteiro

O Item Especial é **mercadoria de terceiro vendida na venda, a custo, markup
1**. Não é "Outros Fornecedores" — esse só nasce na AF, por substituição do
Custo de Fábrica, e **nunca** na venda.

4.2.1 Clique em "Item Especial". O texto tem que ser exatamente: *"Produto ou
serviço negociado pelo valor de custo. Este item não tem aplicação de
descontos."* Sem menção a achado, sem jargão (C1 do F2-42).

4.2.2 O campo tem **máscara financeira** — digite `500000` e veja virar
`R$ 5.000,00` enquanto digita (F2-37/F2-39).

4.2.3 Salve com valor > 0. Confira que aparece **uma linha na tabela de
ambientes**, em itálico, com lápis, e que **clicar na linha inteira** reabre
a mesma caixa.

4.2.4 Zere o valor. A linha **some** — remover é editar para 0, não existe
checkbox de remoção nessa linha.

4.2.5 Com o item ativo, confira em Parâmetros/preview que ele **não infla**
comissão nem provisão operacional: as nove rubricas percentuais
(com_adm, com_venda, com_med, com_proj_exec, frete_loc, assist, ins_loc,
prov_mont, prov_gar) calculam sobre a base **menos** o Item Especial. O
**imposto continua incidindo** — o item sai na nota (F2-38).

4.2.6 Aceite valor **zero** sem erro (F2-38).

### 4.3 O desconto e o portão (F2-11, F2-32, F2-33)

4.3.1 Conceda um desconto e confira a identidade do F2-32/ACHADO-63:
**`Bruto × (1 − desconto) = Valor à Vista`**, sempre. Custo de viagem, brinde
e custo especial não podem inflar o Bruto — o preço de tabela não varia
conforme o desconto concedido.

4.3.2 Suba comissão de arquiteto / fidelidade além do limite. Tem que passar
pelo **mesmo portão** do desconto (autorização gerencial), com o composto
calculado **por ambiente**.

4.3.3 Leia a caixa de aviso. Dois textos, e só esses (F2-33):
- composto **cabe** no teto absoluto → *"Limite de desconto excedido.
  Autorização gerencial necessária."*
- composto **excede** o teto → *"Limite máximo de desconto excedido."*

Não pode citar comissão, fidelidade, "efeito composto" nem percentual
nenhum — o cliente está do outro lado da mesa.

4.3.4 Force `Val_Liq < 0`. É **recusa dura**: não existe credencial que
levante.

### 4.4 O card de ambientes com plano longo (ACHADO-27, regressão a vigiar)

4.4.1 Escolha **Cartão de Crédito 15x** ou Aymoré parcelado. O card de
ambientes **não pode colapsar** — Salvar / Aprovar / Imprimir continuam
clicáveis. Foi achado seu em 31/08 e tem E2E, mas é o tipo de coisa que
volta.

4.5 Salve, aprove e siga.

---

## 5 · Contrato (etapa 7) e o fechamento contábil

5.1 Gere o contrato. Confira a capa e as cláusulas (PDF via WeasyPrint).

5.2 Assine. Tente primeiro com **CPF de dígito inválido** — recusa (F2-6).

5.3 Depois da assinatura, abra o razão do projeto e confira o **lote do
fechamento do contrato**:

- venda cheia: `1.1.02 × 2.1.06` ("Receita a Realizar", Val_Cont);
- as rubricas constituídas como **ativo diferido** `1.1.06.0X × 2.1.04.0X`,
  **sem tocar a DRE**;
- impostos em `1.1.05 × 2.1.04.13`;
- se houver **Item Especial**: `1.1.06.22 / 2.1.04.22` (contas novas do
  F2-36);
- **`2.1.04.14` (Outros Fornecedores) NÃO pode nascer aqui.** O F2-31 fez
  nascer e o F2-36 **reverteu de propósito** — Outros Fornecedores é
  substituição de Custo de Fábrica e só existe a partir da AF. Se aparecer no
  fechamento do contrato, é achado.

5.4 **Imutabilidade pós-assinatura:** volte à negociação. Os campos ficam
travados e o botão **Aprovar** some. Este é o comportamento do orçamento
normal — o do complemento é diferente e se testa em 11.4.

5.5 Confira a **data de competência** dos lançamentos (F2-14/ACHADO-48). Ela
sai do fuso configurado da loja (`config_financeira_json['fuso_horario']`),
não do relógio do servidor. Homologação roda em `Etc/UTC` de propósito: um
lançamento feito entre 21h e 00h (BRT) tem que ficar no **dia de São Paulo**,
não no dia UTC. É o teste mais fácil de esquecer e o mais barato de fazer —
basta rodar um passo do percurso nesse horário.

---

## 6 · Aprovação financeira I (etapa 8) — painel revisável

Esta é a etapa com mais consertos acumulados sem percurso completo depois:
F2-25, F2-28, F2-29 Fatia A, F2-30 Fatia 1, F2-34, F2-39.

6.1 **Visibilidade (F2-40 Fatia 3).** Entre com a conta **sem**
`pode_aprovar_financeiro`. As etapas **8 e 11d somem por inteiro** — nem
sub-aba, nem card, nem aviso de "sem permissão". A navegação entre as etapas
vizinhas continua normal. Volte para a conta com permissão.

6.2 **Máscara nos campos (F2-39).** Todos os campos do painel aceitam digitação
financeira (`R$ 1.234,56`) e são lidos com `parseMoeda`. Digite letra: a
máscara sanitiza. Perde a setinha de incremento — isso é assumido, não é
achado.

6.3 **A coluna "Atual" lê o razão (F2-28 + F2-29 Fatia A).** Três colunas:
Venda | Rev1 | Atual. Depois de qualquer movimento no razão (efetivação,
migração, conferência), **"Atual" tem que mudar** sem você reabrir a
negociação. Confira em pelo menos **três rubricas diferentes** — o conserto
original só cobria `custo_fabrica` e `out_forn`; as outras 17 só passaram a
ler o razão no F2-29 Fatia A e nunca foram percorridas.

6.4 **Custo de Fábrica é read-only**, com contrapartida automática.

6.5 **Duas revisões seguidas (F2-30 Fatia 1).** Faça uma migração de 3.000,
salve; depois 4.000, salve. O snapshot da **Rev1 tem que refletir a revisão
que está sendo feita**, não a contrapartida da anterior. Foi exatamente esse
o print que você mandou no beta5.

6.6 **Concordar não sobrescreve (F2-30 Fatia 1, correção).** Na branch
"concorda", o Custo de Fábrica gravado antes é **preservado** — o override só
vale na branch "revisa".

6.7 **Outros Fornecedores grava de verdade (F2-25/ACHADO-59).** Digite
`out_forn` na AF1 e confira o **lançamento** em `2.1.04.14` — não basta ficar
no `itens_json`.

6.8 **Reduzir Outros Fornecedores é RECUSADO (F2-34/ACHADO-62).** Com 4.000
gravados, tente salvar 2.000. A submissão **inteira** tem que ser rejeitada
(400), **antes de qualquer persistência** — nenhuma rubrica pode ter sido
gravada, nem `ProvisaoRegistro` criado. Recarregue e confirme que o painel
ainda mostra 4.000. Aumentar e repetir o mesmo valor continuam funcionando.

6.9 **Reabrir a AF1 (F2-29 Fatia B).** Com a conta `operador`, tente reabrir
a etapa 8. A recusa tem que dizer que **a conta não tem autoridade** — não
pode soar como "senha errada". A AF continua revisável até **Concluir
Contrato**; depois disso, não.

6.10 **Uma linha só na lista de provisões**, não uma por revisão (F2-28).

---

## 7 · Solicitação de medição (9) e Medição (10)

7.1 Solicite a medição. CPF com dígito inválido na assinatura → recusa (F2-6).

7.2 Registre a medição e conclua. As etapas 8 e 9 são **paralelas** dentro do
Contrato — nenhuma depende da outra; só a 10 depende da 9.

---

## 8 · Projeto Executivo (etapa 11) — o trecho mais pesado

Ordem obrigatória: **11a → 11b → 11c → 11d → 11e**.

### 8.1 · 11a Planta de pontos, 11b Reunião de alinhamento

8.1.1 Suba o arquivo de medição (11a) e o relatório da reunião (11b).

8.1.2 **Remover documento (F2-15/ACHADO-30).** Remova um documento de subfase
e confira: ele some da tela, mas o registro e o arquivo **continuam
existindo** (marcado com `removido_em`/`removido_por_id`, append-only de pé).
A remoção do PE tem que ser **tão exigente quanto o upload** (F2-22/ACHADO-52)
— se o upload pedia permissão que a remoção não pede, é achado.

### 8.2 · 11c Revisão de PE — o upload e a decisão

8.2.1 Suba o XML do Projeto Executivo. As mesmas recusas de 4.1 valem aqui
(`consistencia_interna`, `venda_maior_que_cfo`).

8.2.2 Abra a tela **Comparação de Valores**. Confira, por ambiente, os três
números (custo, venda, à vista) e que eles fecham entre si.

8.2.3 **Marque os ambientes** que vão para renegociação. A marcação é o que a
11e vai usar depois — não existe botão de complemento nesta subfase, só a
marcação (medido no F2-40; se aparecer botão aqui, é achado).

8.2.4 **A decisão de cobrar / absorver / manter (F2-24/ACHADO-55).** Dê a
decisão e confira que ela **grava dinheiro** de verdade. Confira também o
ACHADO-56, que ficou só registrado: a Revisão de PE **fecha verde antes do
veredito**. Se você conseguir concluir a 11c sem ter decidido tudo, isso é
o achado conhecido — anote a ocorrência, não abra achado novo.

8.2.5 **Valor estourando a coluna (LP-19).** Se um valor longo/negativo
quebrar o layout da tabela de decisão, é conhecido, ergonomia, não bloqueia.

### 8.3 · 11d Aprovação financeira II

8.3.1 Com a conta sem permissão: a sub-aba **não existe** (mesmo teste de
6.1). Tentar forçar a seleção redireciona para a etapa mãe.

8.3.2 Com a conta com permissão: aprove. O estado é conferido **antes** de
pedir a credencial (F2-9/ACHADO-38) — não pode pedir senha para depois dizer
que a etapa já estava concluída.

8.3.3 A decisão da AF2 usa a **mesma fonte** do Complemento
(`diferenca_valor_contrato_estimada`, agora pelo motor — F2-42). Anote a
magnitude que ela mostra; ela tem que ser coerente com o que o modal do
complemento vai mostrar em 8.4.

### 8.4 · 11e Aprovação do PE e o Complemento — a frente de ontem

Este é o bloco novo. Foi fechado às 00h40 de hoje e **nenhum ser humano
percorreu a versão final**.

8.4.1 **Onde está o botão.** "Negociar Complemento" está no **cabeçalho do
card "Aprovação do Projeto Executivo"**, não dentro do bloco de upload de XML
(F2-40 Fatia 1). Ele aparece **só quando há ambiente marcado** na 11c. Com
zero ambientes marcados, não aparece.

8.4.2 **O modal.** Clique. Tem que abrir a tela do mockup:
- tabela por ambiente com **Desc.%** e **A cobrar**;
- linha de diferença zero **esmaecida, sem input**, fora dos totais;
- **sem** campo de desconto global;
- rodapé com **uma linha só**: "Diferença" — ou "Diferença (com desconto)" se
  algum ambiente tiver Desc.% ≠ 0 (C3 do F2-42). Não pode aparecer
  "Diferença bruta", nem o valor repetido, nem três linhas.

8.4.3 **A forma de pagamento não pode dumpar JSON (C2 do F2-42).** O modal
mostra **uma linha**: `{nome da forma} — {parcelamento}`. Se aparecer um
bloco de 6 linhas com o JSON cru das parcelas, o conserto não pegou. Era esse
dump que empurrava o botão de troca para fora da vista e dava a impressão de
que ele "sumia".

8.4.4 **O botão de definir/alterar pagamento nunca some (C5 do F2-42).** Sua
hipótese de trava invertida foi medida e **não bateu com o código** — não
existe trava, só um toggle de rótulo (Definir ↔ Alterar). Entre, defina,
volte, reabra: o controle tem que estar sempre lá, só mudando o texto.

8.4.5 **O handoff.** "Definir forma de pagamento" leva à tela de negociação
com o **mesmo orçamento ativo** (o complemento). Escolha a condição.


8.4.5-bis **O plano de pagamento na PRIMEIRA renderização (ACHADO-67 / F2-43).**
No instante em que a tela de negociação abre pelo handoff, **antes de tocar em
qualquer coisa**, olhe o plano. Ele tem que ser o do **complemento** — não o do
contratado, não um plano com juros numa condição à vista.

O defeito original (09/09) sumia ao trocar de modalidade e voltar; se você
precisar fazer isso para ver o número certo, **o achado voltou**. O conserto
do F2-43 fechou a classe (painel à vista recalculando por visibilidade), mas
a instância não está confirmada: mediu-se uma janela real de ~2,5s em que a
tela exibia o valor do contratado, e não se sabe se o conserto a cobre.

Faça esta entrada **duas ou três vezes**, com a captura armada. Cole no console
ANTES de clicar em "Definir forma de pagamento":

```js
window._F43 = [];
window._f43 = setInterval(() => {
  const t = id => { const e = document.getElementById(id); return e ? (e.value ?? e.textContent ?? '').trim() : null; };
  _F43.push({
    hora:      new Date().toISOString().slice(11, 23),
    orcAtivo:  (typeof _orcamentoAtivoId !== 'undefined') ? _orcamentoAtivoId : null,
    pagDoOrc:  (typeof _pagamentoDoOrc   !== 'undefined') ? _pagamentoDoOrc   : null,
    tipo:      (typeof _tipoAtivo        !== 'undefined') ? _tipoAtivo        : null,
    plano:     window._planoPagamento ? JSON.parse(JSON.stringify(window._planoPagamento)) : null,
    avLiq:     t('av-liq-valor'), totalFinal: t('neg-total-final'), avista: t('neg-avista'),
  });
}, 250);
// ao terminar: clearInterval(_f43); copy(JSON.stringify(_F43, null, 1))
```

Note que **`#neg-parcelado` não entra na captura**: é gêmeo morto, apagado do
DOM no ACHADO-64. A caixa viva é `#neg-total-final`.

Se em três entradas o plano estranho não aparecer, o ACHADO-67 vira RESOLVIDO.
Se aparecer, o alvo passa a ser o **handoff** — `carregarOrcamentos()` reativa
o orçamento anterior antes do `ativarOrcamento` do complemento — e não mais o
painel à vista.


8.4.6 **Salvar devolve à 11e sozinho (C4 do F2-42).** Clique Salvar na
negociação do complemento. Você tem que **voltar à 11e automaticamente**, sem
ação manual. Na negociação normal, Salvar continua se comportando como sempre
— confira os dois.

8.4.7 **O botão Salvar existe no complemento (achado de 08/09).** Depois do
contrato assinado, o complemento continua **editável e salvável** — cinco
lugares decidem esse lock e um deles divergia. Confira a ida e volta: abra o
contratado (campos travados, sem Salvar), troque para o complemento (campos
livres, **com** Salvar), volte ao contratado (travado de novo).
**Aprovar continua escondido nos dois** — complemento não se aprova, vira
Termo Aditivo. `btn-pool`, `btn-novo-ambiente`, `btn-item-especial` e
`btn-novo-orc` **continuam escondidos** no complemento; se algum aparecer, é
achado.

8.4.8 **O número — a conferência que substituiu o gabarito.** Esta é a razão
principal deste percurso existir hoje.

Abra, lado a lado:
- a tela **Comparação de Valores** (11c) — coluna "À vista (PE)";
- o modal do **Complemento** (11e) — coluna "À vista (complemento)".

**Ambiente a ambiente, os dois têm que bater exato.** Antes do F2-42 eles
divergiam (você mediu +52,07 e −5,66 no primeiro teste; parcela fixa
implícita de ≈R$66,40 nos oito ambientes do Projeto 11). A causa é o
**brinde**, dividido em partes iguais por ambiente enquanto a viagem é
rateada proporcionalmente. A troca de fonte foi feita: agora os dois lados
falam com o motor.

Faça a conferência **com brinde ativo** — é o único caso em que divergiam.

8.4.9 **A conferência do Projeto 11.** Abra o Projeto 11 (o dos 8 ambientes)
e confira os valores contra a medição de ontem:

| ambiente | À vista (complemento) |
|---|---|
| Área Gourmet | 9.546,52 |
| Despensa | 15.237,98 |
| Lavanderia | 15.814,03 |
| Quarto Filho | 58.968,39 |
| Sala TV Térreo | 18.717,78 |
| Sala superior | 26.645,93 |
| Suite Master closet | 61.388,66 |
| Suite Master painéis | 32.331,52 |
| **total** | **−3.118,72** |

Estes números **não viraram teste** de propósito (decisão de hoje): fixar
dados reais de uma loja num teste unitário quebraria por mudança de
configuração, não de código. A propriedade que importa virou teste sintético;
estes oito ficam como **conferência de percurso**, aqui.

8.4.10 **Gerar Termo Aditivo.** Só libera depois que a forma de pagamento
existe. Gere e confira que o aditivo sai com **todas as linhas**, inclusive as
de diferença zero — a cifra fica de fora dos totais, mas o **vínculo**
continua no aditivo.

8.4.11 **Reabrir não apaga o plano (F2-40, decisão do reset).** Feche o modal
e reabra. A forma de pagamento salva **tem que continuar lá**. O resync dos
vínculos (marcas ↔ ambientes) continua acontecendo sempre; só o apagar do
plano virou condicional.

8.4.12 **Marcar um ambiente depois de criado o complemento.** Volte à 11c,
marque mais um ambiente, volte à 11e e reabra o modal. O ambiente novo tem
que **entrar na cobrança**. Cobrar a menos em silêncio aqui é da família do
ACHADO-16.

8.4.13 **Assine o aditivo.** O CPF passa pela validação de dígito (F2-6), e a
assinatura tem que **funcionar** — foi ela que ficou quebrada em produção por
uma rodada inteira com 2466 testes verdes (ACHADO-25).

8.4.14 Complemento **pós-aditivo assinado**, sem mudar o XML, tem que dar
**zero** (ACHADO-21).

8.4.15 Conclua o PE (11e).

---

## 9 · Conferência e Implantação do Pedido (etapa 12)

9.1 Suba os XMLs dos pedidos.

9.2 **Remover na etapa 12 (F2-20/ACHADO-49).** A remoção existe e funciona —
foi a única etapa que caía no `else` sem ser subfase do PE. Remova e confira
que a tela **conta o que o servidor fez** (nada de "removido" na tela e
presente no banco, ou o contrário).

9.3 **Pendente não é falha (F2-20/ACHADO-50).** Um pedido em estado pendente
não pode ser reportado como falha.

9.4 **NF-e da fábrica em duplicata (F2-20/F2-22/ACHADO-51).** Suba a mesma
NF-e da fábrica duas vezes — recusa, explicando. Suba a mesma chave em
**outro projeto** — recusa também (extensão do F2-22). Cancele uma NF-e e
confira que a chave **volta a ser aceita** (F2-23).

9.5 **XML da fábrica validado no upload (F2-16/ACHADO-31).** Suba um XML
malformado, sem `<infNFe>`, sem item, ou com item sem NCM/CFOP/unidade. Tem
que recusar **na porta**, com 400, **antes de gravar o documento**.

9.6 **Despesa avulsa com vínculo de projeto (F2-30 Fatia 2).** Lance uma
despesa avulsa vinculada ao projeto e confira que ela **entra na margem**.

---

## 10 · Logística e Expedição (13 → 14 → 15 → 16)

O fichário mostra um grupo só; por baixo são quatro etapas sequenciais.

10.1 **Produção (13)** — conclua com os números.

10.2 **Recebimento do Pedido (14)** — conclua o relatório de entrega.

10.3 **Emissão da NF-e do cliente (15)** — o bloco fiscal inteiro:

10.3.1 **O selo de prontidão (F2-18).** Antes do botão de emitir, a etapa
avisa o que falta. Com o emitente incompleto, tem que **BARRAR e AVISAR**,
listando os campos **nomeados** (identificação + endereço), e o mesmo para o
**destinatário** (função irmã, nova). Homologação é regime "simples" — o
**CSOSN** é o bloqueio ativo, não secundário.

10.3.2 **Erro da SEFAZ item a item (F2-17).** Force uma rejeição. A tela tem
que mostrar a lista da SEFAZ **item a item**, não "erro ao emitir". Vale nas
duas rotas com tela (`ciclo/15/emitir-nfe` e `ciclo/15/emitir-nfse`).

10.3.3 **Rejeitada não é beco sem saída (F2-23/ACHADO-54).** Depois de uma
rejeição, **retente**. Não pode voltar "Duplicidade de NF-e com diferença na
Chave de Acesso" — cada tentativa pede `ref` novo; só a autorizada fixa.

10.3.4 **O reconhecimento na emissão (F2-27) — o modelo contábil novo.** Este
é o item que mais mudou o livro e que menos foi percorrido. Ao emitir,
confira no razão:
- as **17 rubricas de despesa** reconhecidas pelo **provisionado integral**,
  em tempo real, segmentadas Mercadoria/Serviço;
- a baixa do ativo diferido `1.1.06.0X`;
- a **provisão `2.1.04.0X` sobrevive** (é paga/reconciliada depois);
- `5.1.01` para a fábrica.

10.3.5 **Os dois segmentos.** Confira que **mercadoria E serviço** foram
faturados. O F2-26 mediu dois projetos ("fechados") com `2.1.06` aberto de
R$63k e R$69k porque só o segmento mercadoria tinha saído. Se ao fim do
faturamento sobrar `2.1.06` deste projeto, é achado.

10.4 **Entrega no cliente (16)** — conclua.

---

## 11 · Montagem (17), pendências (17a) e pós-montagem (18)

11.1 Conclua a Montagem. **Ela não se conclui sozinha** — o F2-24/ACHADO-57
consertou isso; se voltar a fechar sem ação, é regressão.

11.2 Abra **pendências de montagem (17a)** e resolva.

11.3 Registre uma **assistência pós-montagem (18)**. Confira que a
transferência de responsabilidade oferece as funções certas — "Projetista"
com papel `projeto_executivo` declarado tem que aparecer (F2-13/ACHADO-46).

---

## 12 · Vistoria final (19) e Aprovação final (20)

12.1 Conclua as duas. Confira que a etapa **20** não libera a 21 antes de
estar concluída.

---

## 13 · Conciliação Final (etapa 21) — o fechamento

Este bloco é o percurso de 01/09 inteiro, mais o que entrou depois (F2-8,
F2-10).

### 13.1 · Os selos, antes de clicar em nada

13.1.1 Rubrica que **nunca teve movimento** neste projeto mostra **—**, não
"Resolvida". Uma tela toda verde em rubricas que nunca aconteceram significa
que o conserto não pegou.

13.1.2 Rubrica com efetivação parcial mostra **Parcialmente Efetivada** —
inclusive sendo rubrica de veredito nomeado. **O selo fala do dinheiro, não
de onde se age.**

### 13.2 · Efetivar

13.2.1 Na linha de **Provisão de Montagem**: o botão **Efetivar** existe e
está habilitado; **Resolver não existe** — no lugar dele, o link "Dar
veredito na Fila de Provisões".

13.2.2 Digite um valor e efetive. Três conferências: o toast diz
**"Efetivado R$ <valor>"**, a linha **realça** por um instante, e a coluna
**Efetivado** muda.

13.2.3 **Clique de novo, mesmo valor, mesmo dia.** Tem que dizer **"Já
efetivado hoje"** e a coluna Efetivado **não pode dobrar** — o total do dia
vem do **razão** (`efetivado_no_dia`), não do que foi digitado (F2-9/ACHADO-35).

13.2.4 Passe o mouse nos botões. O tooltip explica **o efeito no livro**
(despesa na competência, ativo diferido, destino da sobra), não o nome do
botão.

### 13.3 · A Fila de Provisões

13.3.1 Pelo link da linha, chegue à Fila (Financeiro → Fila de Provisões).

13.3.2 **A Fila mostra todas as provisões, agrupadas (F2-25).** Confira a
contagem: 21 contas `2.1.04.%` no plano, **19** elegíveis ao painel, **17**
elegíveis à fila. As telas têm que **rotular o que contam** — se alguma
mostrar um número sem dizer de quê, é o defeito que o F2-25 identificou.

13.3.3 **A Fila só oferece veredito que o sinal permite (F2-10/ACHADO-41).**
Numa rubrica com saldo de um sinal, os vereditos incompatíveis **não podem
aparecer** — a tela desenha só o que o servidor aceitaria. Se ela oferecer e
o servidor recusar, é a família ACHADO-32/33/39/41 de novo.

13.3.4 Dê os vereditos. Use pelo menos um de cada:
- **encerrada_valor_menor** com um valor efetivado real;
- **nao_se_aplica** — **exige motivo escrito**; tente sem motivo primeiro e
  confirme a recusa;
- **ainda_vai_chegar** numa rubrica, e então volte e tente concluir a
  Conciliação Final: **tem que recusar, dizendo qual rubrica**. Depois troque
  o veredito para seguir.

13.3.5 **O veredito da folha (F2-8/ACHADO-34).** Se a comissão deste projeto
já passou por **folha paga**, ela chega aqui **sem rubrica em aberto** — e
isso é esperado, não é defeito. O que mudou: a folha agora **grava um
`VeredictoProvisao`** em vez de ser reconhecida por escrito. Confira que o
projeto **aparece** no relatório de encerrados por reversão (ele é o
contra-controle do ACHADO-16); antes ficaria cego para sempre.

13.3.6 **O que a Conciliação Final exige é o SALDO, não a decisão** (F2-8). Uma
rubrica com saldo aberto trava mesmo que alguém tenha "decidido" fora dela.

### 13.4 · Fechar

13.4.1 Concluir Conciliação Final. O projeto vira **Concluído**, com data —
distinto de "fechado".

13.4.2 Reabra o projeto concluído: a etapa mostra o estado final, **sem
oferecer ação nenhuma**.

13.4.3 **O projeto se identifica (F2-29 Fatia C).** Todos os painéis do ciclo
mostram de que projeto se trata. Painel sem identificação é achado.

---

## 14 · Transversal — conferir uma vez, em qualquer ponto

14.1 **Avisos são `avisoPopup`, não `showToast(..., true)`** no módulo
financeiro/provisões (F2-9/ACHADO-36). Os 164 restantes no resto do sistema
são higiene conhecida, não achado.

14.2 **Nenhuma tela oferece ação que o servidor recusa.** É a família mais
recorrente deste projeto (ACHADOS 32, 33, 38, 39, 41, 49, 50, 51). Se você
clicar em algo e receber 409/400, o achado é **da tela**, não do servidor.

14.3 **Toda recusa se explica sozinha** (F2-23): qual arquivo, qual item,
qual número, o que fazer.

14.4 **Abrir Parâmetros não pode salvar nada** (F2-23/ACHADO-53) — não existe
autosave ao abrir.

---

## O que este percurso NÃO cobre, e por quê

**F2-21 — NF-e H e NF-e P: SUSPENSO.** O item pressupunha que a emissão é um
evento do projeto; o seu percurso de 04/09 redesenhou isso (entrada fiscal no
recebimento, emissão **por fase**, escolha entre NF-e de origem e "Estoque").
Não está neste candidato e não é achado.

**Complemento por FASE.** Existem dois mecanismos: complemento por
**ambiente** (`parcela_id=None`, o que a 11e gerencia — é o que este percurso
testa) e complemento por **fase** (`parcela_id=<fase>`, criado pela
Conciliação/AF2). O segundo tem porta medida mas **não ligada** no modal;
o caminho real é a tela de orçamentos comum. Inventário de 08/09: **zero**
complementos por fase em Homologação — desenho nunca operado. Fica a pergunta
aberta para você: é desenho que ninguém precisou ainda, ou desenho que
deveria sair?

**A DRE `competencia_estimada`.** Mistura receita realizada com custo
estimado. **Não decidir por ela** — sai na Fase 4. A visão `real` (futura
Diferida) é o livro e está correta.

**Trava de período fechado.** Não existe (Fase 3). Relatório impresso hoje
pode não bater com o mesmo relatório amanhã.

**Ramo financeira, ACHADO-01.** O gatilho automático da conferência do
extrato não existe. O saldo fica aberto esperando alguém conferir.

**`/api/financeiro/lancamentos` (ACHADO-07)** ainda lança contra conta de
provisão sem passar por veredito. Caminho manual e deliberado, mas contorna
a Fila.

**`2.1.04.12 "Retenção de Comissão de Vendas"` não retém nada** (ACHADO-17,
decisão de produto pendente). Quem lê o plano de contas acredita que existe.

**Markup de ajuste (LP-15)** — a metade não implementada do ACHADO-31.

**Os cinco flakes da suíte.** `test_aceite_achado12`, `test_bateria_ciclo`
(LP-21), LP-16, `test_achado_c4_reaprovar_af_silenciosa`,
`test_e2e_browser_conciliacao_final`. Mesma assinatura nos cinco: timeout sob
carga paralela, nunca falha de lógica, sempre verde isolado. Provavelmente o
timeout fixo de 5s do cliente HTTP de teste, dimensionado para máquina
ociosa. **Sem dono** — candidato a uma rodada curta agora que a linha do
complemento fechou.

---

## Ao terminar

Se passou inteiro: escreva a lista de **defeitos conhecidos** deste candidato
(o modelo é `DEFEITOS_CONHECIDOS_beta1.md`) e decida se sobe. A `ESTEIRA.md`
é explícita: *"um fluxo quebrado conhecido não impede a subida, mas não pode
subir sem alguém ter decidido que sobe."*

Lembre que **Produção está fora da esteira desde 28/08** e precisa do rebuild
descrito em `IMPLANTAR.md` — não é um `checkout` a mais.
