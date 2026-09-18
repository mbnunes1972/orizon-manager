# Tarefa — Limpar a base da Inspirium em Homologação

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-18
**Ambiente:** **Homologação apenas** (loja 1, Inspirium). Não tocar em Integração, não tocar na
bancada, não tocar em Produção.

**Decisão do Marcelo (18/09):** limpar a base da Inspirium para facilitar a transição de outubro.
A Loja Teste (id 15) passa a ser o lugar de brincar; a Inspirium fica limpa para receber operação
real. O que fica duplicado no Pontta não precisa sobreviver aqui.

**O que ele definiu, literalmente:**
- **Apagar** conversas e projetos.
- Base pode ficar **limpa**: sem agenda, sem contábil, sem financeiro — a operação inteira.
- **Usuários: DESATIVAR (`ativo=0`), não apagar.** Fica **um único master ativo**.

**Por que desativar e não apagar (decidido em 17/09, medido):** `pdm2026` era dono de centenas de
registros em seis tabelas, incluindo 330 linhas de `log_acoes_gerenciais`. Desativar bloqueia o
login por completo — provado — com risco zero de chave estrangeira e sem deixar auditoria sem
autor.

---

## Passo 0 — as duas coisas que dependem do Marcelo

**(a) A conta master que fica: a GABRIELA** — decidido pelo Marcelo em 18/09. Ela aparece como
"Gabriela Adm/Fin · MASTER" na Inspirium; o login é provavelmente `gaf2026`, mas **confirme no
banco antes de rodar** — dedução de iniciais não é medição.

Use `scripts/redefinir_senha.py` (Caminho 3, já no ar) para definir uma senha forte **antes** da
limpeza, e **entre com ela** para confirmar. **Não comece sem ter entrado.** Uma limpeza que deixa
ninguém dentro é um incidente, não uma limpeza.

**(a-bis) O nome dela vira a assinatura da loja — corrija ANTES.** Com a Gabriela como única conta
ativa, o `Usuario.nome` dela passa a assinar **toda** mensagem que sai para cliente pelo WhatsApp
(`espelhar_para_externos` monta `"💬 <nome>: <texto>"`). Hoje esse nome é **"Gabriela Adm/Fin"** —
a abreviação de função iria para o cliente em cada mensagem. Corrigir para só o nome próprio deixa
de ser cosmético e vira pré-requisito.

Atenção a onde editar: o prefixo vem do **`Usuario.nome`**, não do `Funcionario.nome`. Se os dois
não estiverem sincronizados, editar o funcionário muda a tela e não muda o WhatsApp. Prova simples:
entrar como ela e olhar o cabeçalho — o nome ali é o do `Usuario`, o mesmo que vai na mensagem.

**(b) Os dois contatos reais.** Entre as 8 conversas externas, duas são de **pessoas de verdade que
escreveram para o negócio**: **Felipe Guizalberte** (5512988056021, 17/09) e **5511952135165**
(18/09) — este último o Marcelo já respondeu pessoalmente. Apagar é perder o registro de um
prospecto real.

**Antes de apagar qualquer coisa, exporte.** Um arquivo simples (CSV ou JSON) com as 8 conversas
externas: telefone, nome, data, texto de cada mensagem, status dos envios. Guarde fora do banco.
Custa minutos e torna a decisão reversível. Depois disso, apagar é seguro e o Marcelo decide sem
medo.

---

## Passo 1 — backup com restauração TESTADA

Dump não é garantia; garantia é ter restaurado. Faça o dump de `orizon_homologacao`, restaure num
banco descartável e **confirme lá** que as 8 conversas externas e os 2 leads estão presentes.
Só então prossiga. Esta é a única rede de proteção de uma operação irreversível num banco que hoje
tem dado de pessoa real.

---

## Passo 2 — o script, com ensaio obrigatório

**Entrega:** `scripts/limpar_loja.py`, no padrão da casa (`clonar_loja.py`, `seed_loja15.py`):
**sem `--aplicar` ele NÃO apaga nada** — imprime uma tabela do que apagaria, por tabela, com
contagem. O Marcelo lê essa tabela e aprova antes da execução real.

Parâmetros: a loja alvo (nunca embutida no código) e o login do master que permanece ativo.

**O que SAI** — toda a operação da loja 1:
- Projetos e tudo que pende deles: orçamentos, ambientes, negociação, contratos, ciclo, etapas,
  documentos, medição, pool.
- Conversas **todas** — as de projeto e as externas — com mensagens, participantes, anexos.
- Leads, triagem, envios externos.
- Financeiro, contábil, folha, provisões, agenda.
- Clientes da loja 1.

**O que FICA** — a loja e a forma dela:
- A própria `Loja` (id 1) e sua configuração: funções, remuneração, parâmetros financeiros,
  segmentos, config do OrizonBot, emitente.
- **Funcionários e usuários** — todos preservados, todos com `ativo=0`, **exceto o master
  nomeado no Passo 0(a)**, que fica `ativo=1`.
- `rede_id` e vínculos de rede.

**Ordem de exclusão:** das folhas para a raiz — o que referencia antes do que é referenciado.
Erro de chave estrangeira aqui não é obstáculo a contornar com `CASCADE` improvisado; é sinal de
que a ordem está errada. **Se esbarrar, pare e reporte.**

**Tudo numa transação.** Ou a limpeza inteira acontece, ou nada acontece. Limpeza pela metade é
pior que nenhuma.

---

## Passo 3 — depois

1. `varrer_orfaos_gabarito` (R16) — obrigatório depois de mexer em massa no banco.
2. `bash docs/db/confirmar.sh` — 15 OK esperados.
3. Entrar na tela com o master que ficou: a loja abre, sem projeto, sem conversa, com as funções e
   a remuneração intactas.
4. Conferir que **a Loja Teste (15) não foi tocada** — nenhuma linha dela some.
5. Conferir que **nenhuma outra loja** foi afetada (Dalmóbile Recreio, Teste Funções).

---

## Regras deste lote

1. **Homologação apenas.** Confirme `\l` e o nome do banco antes de qualquer comando — já houve
   caso de comando rodado no ambiente errado nesta esteira.
2. **Sem `--aplicar` primeiro.** A tabela do ensaio vai para o Marcelo e espera o aval dele.
3. Não apagar usuário nenhum. Não apagar a loja. Não mexer em configuração.
4. Não abrir achado novo — reportar e seguir.
5. Se alguma medição contradisser este documento, **pare e reporte**: ele foi escrito a partir do
   que foi medido esta semana, não de execução própria.
