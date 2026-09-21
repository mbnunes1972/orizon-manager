# Tarefa — As lojas-piloto: três lojas, um PDV, e o que falta antes de clonar

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-21
**Prazo:** as lojas-piloto entram em **01/10**, em Homologação. Produção em 01/11.

**Decisão do Marcelo (21/09):** são **4 lojas + 1 ponto de venda**, todas na **rede Orizon**:
Inspirium (já existe), Dalmóbile Recreio, Dalmóbile Salinas, Dalmóbile Casa Shopping, e
**Caraguatatuba como PDV da Inspirium** — não como loja irmã.

**Consequência da rede única:** o ADR-028 passa a valer entre todas — cliente cadastrado numa
aparece para a outra puxar e confirmar, sem duplicar; histórico comercial continua isolado.

---

## BLOQUEADOR — o roteamento por número não existe (medido em 21/09)

**Leia isto antes de qualquer outra coisa.** `chat/externo.py::_loja_da_entrada` escolhe a loja de
uma entrada externa assim:

1. o remetente é um `Cliente` cadastrado → a loja dele;
2. existe **um único** `NumeroConectado` na instalação inteira → a loja daquele número;
3. senão → **a primeira loja**.

O próprio docstring diz: *"Multi-número por loja fica p/ quando o webhook repassar o
`phone_number_id` do payload."*

**O que isso significa para o piloto:** com quatro lojas, cada uma com seu WhatsApp, a regra (2)
deixa de valer (não há número único) e **todo lead novo de qualquer loja cai na primeira loja**.
Lead da Salinas aparece na Inspirium. Não é hipótese — é o que o código faz hoje.

**DECIDIDO em 21/09: hoje só a Inspirium tem número, e o chat é por loja.** Com um número só, a
regra (2) funciona e não há defeito. Portanto isto **sai do caminho crítico de 01/10** e vira
**pré-requisito para conectar o segundo número**: no dia em que a Salinas (ou qualquer outra)
ligar o WhatsApp dela, o roteamento por `phone_number_id` precisa estar pronto **antes** — senão
os leads dela caem na primeira loja, em silêncio, sem erro nenhum.

**Regra operacional até lá: não conecte um segundo `NumeroConectado` em Homologação.**

*Pergunta aberta para quando o roteamento for feito:* a regra (1) manda a entrada para a loja do
`Cliente` cadastrado. Com cadastro compartilhado na rede, um cliente da Salinas que escreva para o
número da Inspirium cairia na Salinas. Isso pode ser o certo (é a loja dele, ADR-030) ou o errado
(ele escreveu para a Inspirium). Medir e decidir junto com o roteamento, não antes.

**Referência antiga, mantida para contexto:**

- **(a) Piloto de chat só na Inspirium.** Uma loja, um número, regra (2) funciona. As outras três
  usam o resto do sistema sem o chat externo. Custo zero, escopo menor.
- **(b) Implementar roteamento por número.** O payload da Cloud API traz
  `metadata.phone_number_id`; `iter_mensagens_whatsapp` precisa expô-lo, `_loja_da_entrada` passa a
  usá-lo, e cada loja registra o seu `NumeroConectado`. Não é enorme, mas é código novo, com teste,
  numa semana que já tem outras coisas — e sem ele o item (2) acima é uma armadilha silenciosa.

**Enquanto isso não estiver decidido, não conecte um segundo número em Homologação.** Hoje há um
só, e é isso que faz o roteamento funcionar.

---

## Passo 0 — medir o estado atual (antes de criar qualquer coisa)

1. Quais lojas existem hoje em Homologação, com `id`, `nome`, `codigo`, `rede_id`, `loja_mae_id`,
   `ativo`. **A Dalmóbile Recreio parece já existir** (há uma conta master
   `carlar.dalmobile@gmail.com` ligada a ela) — confirme antes de clonar, para não criar
   duplicada.
2. Qual é o `id` da rede Orizon, e se a Inspirium está nela.
3. **A Inspirium ainda tem a função "Teste Novo"?** (LP-34). A limpeza de 19/09 preservou
   configuração, então provavelmente sim. Ela é a loja-fonte do clone: cada função de teste que
   sobrar lá nasce três vezes. Limpar antes é mais barato que limpar depois em cada filha.

Reporte o Passo 0 antes de seguir.

---

## Passo 1 — LP-31: o `--rede-id` do clone é letra morta

Está registrado: `aplicar_config_loja` (`mod_implantacao_loja.py`) reaplica `_LOJA_CONFIG`
**incluindo `rede_id`** por cima do que o parâmetro pediu. Como todas as lojas ficam na mesma rede
da Inspirium, o resultado hoje sairia **certo por acidente**.

Depender de acidente numa implantação é o mesmo que não ter a opção. Conserte: `rede_id` do
destino tem que ser decisão explícita de quem chama, com gate próprio — mesmo padrão já usado para
`cnpj`/`razao_social` (`_EMITENTE_IDENTIDADE`, gated por `permitir_identidade`). O LP-31 tem o
detalhe.

---

## Passo 2 — o clone não sabe criar PDV

`scripts/clonar_loja.py` tem `--rede-id`, `--codigo`, `--permitir-identidade`,
`--copiar-remuneracao` — e **nenhum `--loja-mae-id`**. Caraguatatuba nasceria como loja avulsa, e
a regra do PDV não se aplicaria a ela.

A regra existe e é real, espalhada por vários pontos: `database.py` (`loja_mae_id`, e
`lojas_acessiveis` filtrando por mãe), `auth/auth_routes.py` (loja ativa), `main.py` (lista de PDVs
da mãe), e **`fiscal/mod_fiscal.py`: PDV sem emitente próprio herda o emitente da mãe.**

Acrescente o parâmetro e faça o PDV nascer certo. **Decidido em 21/09 (ADR-030):** Caraguatatuba **herda o emitente da
Inspirium**. Ponto de venda é, por definição, a condição em que o tratamento fiscal é feito pela
loja mãe; quando houver CNPJ próprio, deixa de ser PDV e vira loja nova.

---

## Passo 3 — clonar, com ensaio

Padrão da casa: **sem `--aplicar` não cria nada**; o plano vai para o Marcelo antes.

Ordem: as duas (ou três) Dalmóbile primeiro, Caraguatatuba por último — PDV depois que a mãe está
confirmada.

Para cada loja nova, depois do clone:
1. **Uma conta master**, com senha definida por `scripts/redefinir_senha.py` e
   `senha_provisoria=1`. **Reporte o valor ao Marcelo** — conta criada sem a senha relatada nasce
   inacessível (aconteceu com o `sac.inspirium` em 17/09).
2. **Um funcionário na função SAC, com login.** Sem isso, `triagem_materializar` não acha
   `_sac_usuario_id`, a conversa nasce sem dono e o lead fica invisível — **foi exatamente o que
   custou dezessete dias na Inspirium (31/08 a 17/09)**. Cada loja precisa do seu.
3. Conferir na tela: nome da loja no cabeçalho, funções e remuneração vieram, e **salários por
   função conferidos** (a implantação verifica os valores — decisão de 16/09; o clone traz os da
   fonte e cada praça paga o que paga).

---

## Passo 4 — verificação

- `varrer_orfaos_gabarito` (R16) depois de tudo.
- `bash docs/db/confirmar.sh` — 15 OK.
- Caraguatatuba aparece como PDV **da Inspirium** (não como loja avulsa) na tela que lista PDVs.
- A Loja Teste (15) e a Inspirium não foram alteradas.
- Um cliente cadastrado numa Dalmóbile é **encontrado** pela outra (ADR-028), e o histórico
  comercial **não** atravessa.

---

## Regras deste lote

1. **Homologação apenas.** Confirme o banco antes de cada comando.
2. Ensaio antes de aplicar, em tudo.
3. Não abrir achado novo — reportar e seguir.
4. Suíte verde antes da tag; **Sessão B parada enquanto a suíte roda** (`PLANO_SEMANA_1.md`,
   regra 2b); Integração antes de Homologação; smoke em `172.19.0.1`.
5. Se alguma medição contradisser este documento, **pare e reporte**.
