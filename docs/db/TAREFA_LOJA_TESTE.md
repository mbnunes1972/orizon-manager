# TAREFA — Loja Teste: clonar configuração e limpar os projetos da Inspirium

Decisão do Marcelo, 11/09/2026. Duas etapas, **nesta ordem**: clonar primeiro, limpar depois.

**Por que essa ordem:** o clone só copia configuração, então a limpeza não o afetaria — mas se a
limpeza correr mal, ter clonado antes significa que a configuração afinada da Inspirium já existe
em outro lugar. Clonar é barato; refazer configuração perdida, não.

## O contexto, para quem pegar isto depois

A Loja Teste nasce para separar **teste de sistema** de **operação de loja**. Hoje a Inspirium
(`loja_id=1`, Homologação) mistura as duas coisas: 13 projetos que são um misto dos testes do
Marcelo (Teste_1..7, Projetos 8, 10, 11, 13) com o que deveria ser dado de loja.

Em paralelo, uma rede de lojas vai usar Homologação com **dados reais**, mantendo o Pontta em
funcionamento — ou seja, o Orizon não é sistema de registro para elas ainda, e **os dados do
piloto são descartáveis**. O que precisa sobreviver é a **configuração**, e os clientes virão
por importação do Pontta (frente própria, não coberta aqui).

**A regra que governa as duas etapas: configuração viaja, dado não.**

## A referência é HOMOLOGAÇÃO — medido em 11/09, não suposto

O banco `orizon` da bancada **não é referência de nada** — a `ESTEIRA.md` já diz isso do
ambiente (*"a bancada não é ambiente… é oficina"*), e vale igual para o banco de aplicação dela.
A borda de evolução é o **código**; a configuração real vive em Homologação, onde o Marcelo
clica e pede ajuste.

Medido exportando a configuração dos dois lados e comparando:

- **plano de contas e centro de custo**: idênticos ao gabarito **nos dois** — 168 contas, 16
  centros, zero divergência. Nada a promover;
- **funções**: divergem, e a divergência é o trabalho de 10/09 (benefícios, comissão por meta do
  Gerente de Vendas, comissão fixa do Supervisor) feito **só em Homologação**, como devia;
- **`config_financeira_json`**: `fuso_horario` existe só em Homologação;
- **`Emitente`**: o da bancada está **vazio** — sem inscrição estadual, sem CFOP, sem CSOSN, sem
  endereço. Não emitiria nota nenhuma. O de Homologação está completo.

**Consequência operacional: o clone de verdade sai de Homologação.** A rodada na bancada prova o
mecanismo, nunca a configuração.

Duas divergências anteriores a 10/09, registradas para decisão futura: a função **Diretor** tem
salário fixo 8.000 na bancada e 0 + comissão fixa 20.000 em Homologação (dois modelos de
remuneração para o mesmo cargo), e o **Projetista Executivo** tem `comissao_json` em Homologação
que o seed não gravou. Com a regra de remuneração acima, nenhuma das duas viaja no clone — mas
continuam divergindo entre os bancos.

A comissão fixa de **R$ 3.300** do Supervisor de Montagem, que eu havia sinalizado como provável
dígito a mais, **está correta** (confirmado pelo Marcelo em 11/09).

---

# Etapa 1 — Clonar a Inspirium na Loja Teste

Mecanismo novo, e o de maior valor a longo prazo: é o **perfil de implantação de loja** que vai
ser reusado quando abrir loja de verdade em Produção. Escreva-o como mecanismo, não como script
descartável.

## O que COPIA (decisão)

- **`Loja`**: `config_financeira_json` inteiro (faixas de comissão de vendas, fuso horário da
  competência — ACHADO-48), telefone, e-mail, responsável, endereço, `rede_id`.
- **`PerfilAcesso`**: todas as linhas da loja, **mesmos slugs** — a unicidade é
  `(loja_id, slug)` (`uq_perfil_loja_slug`), verificado no modelo; o comentário que diz "único
  globalmente" está desatualizado.
- **`Funcao`**: todas as funções da loja — **só a estrutura**: `nome`, `status`,
  `atribuicoes_json`, `perfil_padrao`, `remuneracao_padrao`, `regime_*`, `descricao`,
  `usa_comissao_vendas` e `comissao_json` (percentuais e faixas). **Valor em dinheiro NÃO viaja**
  — ver a seção própria abaixo.
- **`DocumentoModelo`**: **só a versão ATIVA** de cada tipo, recriada com `versao=1` na loja nova
  (o unique é `(loja_id, tipo, versao)`). Não copiar o histórico — versão imutável é rastro do
  que assinou contrato, e contrato da Inspirium não é contrato da Teste.
- **`Emitente`**: copiar — **decisão do Marcelo (11/09)**, com a justificativa de que hoje só há
  token de homologação da Focus em uso.

## O que NÃO copia

- **Dado**: clientes, projetos, orçamentos, contratos, aditivos, lançamentos, provisões,
  comissões, folhas, agenda, documentos de ciclo.
- **Pessoas**: funcionários e usuários. A Loja Teste nasce sem equipe.
- **Identidade parcial**: `codigo` é **`TES`** (definido pelo Marcelo; o campo é `unique` no
  banco — são as três letras do número de contrato). `nome` novo.
- **`cnpj` e `razao_social`**: copiados, por decisão do Marcelo — ver a condição abaixo.

## Remuneração não viaja — DECIDIDO (Marcelo, 11/09)

**Salário não se copia entre lojas.** Remuneração é decisão trabalhista de cada loja, não
configuração de sistema. A linha: **a estrutura da função viaja; o valor em dinheiro não.**

**Fica de fora, sempre que a flag não estiver ligada:**

- `salario_fixo`
- `beneficios_json` (AT/VA/PS — são valores em R$)
- `comissao_fixa`

**Viaja:** `comissao_json` (percentuais e faixas) e `usa_comissao_vendas`. Percentual é **política
comercial da rede**; valor é contrato de trabalho. A loja nova herda a política e define os
valores.

### A exceção declarada: `--copiar-remuneracao`

Desligada por padrão. Ligada, copia também os três campos de dinheiro.

Existe por um motivo específico e datado: a **Loja Teste** deve receber a configuração de teste já
montada na Inspirium — inclusive a folha —, senão o Marcelo refaz o trabalho de 10/09 só para
continuar testando. Para loja real em Produção **ninguém liga essa flag**: a loja nasce sem
salário nenhum, e cada uma define o seu.

Mesmo padrão do `--permitir-identidade`: a regra padrão é a segura, a exceção é **declarada**,
nunca implícita.

**Quando a flag estiver desligada, diga isso na saída** — "N funções copiadas, remuneração NÃO
copiada; configure na tela de Funções". Senão a primeira folha da loja nova sai zerada e alguém
vai caçar defeito onde não há. (Foi exatamente o que aconteceu em 10/09, quando as funções
padrão nasciam vazias e a folha saía zerada sem ninguém entender.)


## A condição do Emitente — cumprir, não discutir de novo

Copiar o Emitente foi decidido porque **este ambiente só tem credencial de homologação**. A linha
`Emitente`, porém, tem campo para as duas: `focus_token_homolog_enc` **e**
`focus_token_prod_enc`, mais `ambiente_ativo`. Copiar a linha inteira faria o clone herdar o que
aparecesse ali depois.

Portanto, no clone:

- **`focus_token_prod_enc` NUNCA é copiado** — fica nulo, sempre;
- **`ambiente_ativo` é forçado a `'homologacao'`**, ignorando o valor da origem;
- o mesmo vale para `cert_validade`/`cert_cnpj`: copiar é inócuo hoje, mas o certificado em si não
  viaja — confira o que existe em `keys/` antes de assumir qualquer coisa.

**E escreva no código, em comentário, que esta decisão é condicional ao ambiente.** Quando este
mecanismo for reusado em Produção para abrir loja real, a regra **inverte**: identidade fiscal
(CNPJ, razão social, inscrições, tokens, certificado) **não** se copia, porque emitir nota no
CNPJ de outra empresa é o que essa cópia permitiria. Sem essa nota, o próximo a reusar herda a
premissa sem saber que ela tinha prazo.

## Plano de contas e centro de custo — semear, não copiar

**Não copie as árvores.** A loja nova nasce com `mod_contabil.aplicar_gabarito_completo` (o mesmo
que a criação de loja já usa — R15, uma implementação e dois pontos de entrada), e só **as
divergências** da Inspirium em relação ao gabarito são aplicadas por cima.

Copiar a árvore inteira é exatamente o que a R13 e a R14 registram como causa de divergência
congelada: gabarito é template de decisão deliberadamente mutável, e uma cópia trava no tempo.
Se houver divergência na Inspirium que o gabarito não produz, **liste-a antes de aplicar** — ela
pode ser configuração legítima ou resíduo, e isso é decisão do Marcelo, não do script.

Depois de semear, rode `mod_contabil.varrer_orfaos_gabarito` (R16).

## Fronteiras

- Sem DDL (R1). Isto é dado e configuração, não schema.
- O script **afirma o nome do banco** antes de qualquer escrita, recusa qualquer banco com
  "produc" no nome, e só grava com `--aplicar` — mesmo padrão de
  `scripts/seed_funcionarios_homolog.py`.
- Idempotente: rodar duas vezes não duplica perfil, função nem modelo.
- `SimuladorAutorizacao` **não** se copia — o seed de boot (`_simulador_autorizacao_seed_v1`)
  cria a linha da loja nova sozinho.

## Aceite

1. Loja Teste existe com `codigo='TES'`, `ambiente_ativo='homologacao'` e
   `focus_token_prod_enc` nulo.
2. Perfis, funções e o modelo ativo de cada tipo existem na loja nova, com os mesmos valores.
3. Zero clientes, projetos, contratos, lançamentos, funcionários e usuários na loja nova.
4. Plano de contas e centro de custo **semeados**, com a lista de divergências da Inspirium
   mostrada e aplicada só depois de conferida.
5. Rodar o script duas vezes não duplica nada.
6. Um projeto novo criado na Loja Teste percorre a negociação com as faixas de comissão certas —
   prova de que `config_financeira_json` viajou de verdade.

---

# Etapa 2 — Limpar os projetos da Inspirium

Objetivo declarado: **deixar limpo o acesso da equipe**. Não é reset de loja — a Inspirium
preserva configuração, funções, funcionários, usuários, plano de contas e centro de custo.

## Antes de apagar qualquer coisa

**Backup**, no padrão que o `IMPLANTAR.md` já usa:

```
sudo -u postgres pg_dump orizon_homologacao > /root/backups/homolog_pre_limpeza_$(date +%Y%m%d_%H%M).sql
```

**Enumere os irmãos (ACHADO-26) antes de escrever o DELETE.** Liste toda tabela que referencia
projeto — por `projeto_nome`/`nome_safe`, por `projeto_id`, e por `orcamento_id`/`contrato_id`
descendentes. O grafo inclui, no mínimo: orçamentos e seus ambientes, contratos e assinaturas,
aditivos e assinaturas, aprovações de PE, solicitações de medição, documentos de ciclo, etapas
do ciclo, provisões e registros, comissões, recebíveis, NF-e/NFS-e emitidas, atribuições do
Mapa, conversas do chat vinculadas, retenções, cronogramas.

**`docs/db/limpar_base.sql` já existe** — parta dele, mas confira a lista contra o schema atual
antes de usar: ele foi escrito em 08/2026 e o sistema ganhou tabelas desde então.

## O que mais importa: o razão

Apagar projeto pela metade deixa **lançamento órfão**, e isso é pior que base suja — o razão
passa a somar dinheiro de projeto que não existe, e nenhuma tela denuncia.

Os lançamentos são presos a owner polimórfico (`owner_tipo`+`owner_id`, **sem FK** — R15), com
`projeto_id` próprio. Apague os do projeto **junto** com ele, e confira depois:

- nenhum `lancamento` com `projeto_id` que não existe mais;
- as contas de projeto (`1.1.02`, `2.1.06`, `1.1.06.*`, `2.1.04.*`) da Inspirium **zeradas**;
- `varrer_orfaos_gabarito` sem novidade.

## Fronteiras

- **Preserva**: `Loja` e sua configuração, `PerfilAcesso`, `Funcao`, `Funcionario`, `Usuario`,
  plano de contas, centro de custo, `DocumentoModelo`, `Emitente`.
- Mesmo padrão de guarda do script de seed: afirma o banco, recusa "produc", só grava com
  `--aplicar`, imprime o plano antes (quantas linhas de cada tabela sairiam).
- Sem DDL.

## Aceite

1. Zero projetos na Inspirium; a equipe entra e vê a lista vazia.
2. Configuração, funções, funcionários, usuários e as duas árvores contábeis **intactos** —
   compare antes e depois, contagem a contagem.
3. Razão sem órfão e contas de projeto zeradas (as três conferências acima).
4. Um projeto novo criado na Inspirium depois da limpeza percorre normalmente até o contrato —
   prova de que a limpeza não levou junto o que a loja precisa para operar.

---

---

# Etapa 1b — Fase 2 do clone: exportar para arquivo (implantação entre ambientes)

Escrever junto, porque custa pouco agora e evita reescrita depois. A Etapa 1 clona **loja → loja
no mesmo banco**; esta faz a **mesma coisa entre bancos diferentes**, que é o caso de Produção.

## A fatoração que torna as duas a mesma coisa

Uma função que APLICA, duas fontes que ALIMENTAM:

```
exportar_config_loja(loja_id) -> artefato            # lê do banco, devolve o artefato
aplicar_config_loja(destino, artefato, excecoes)     # escreve no banco, de onde quer que venha

clone (Etapa 1)  =  aplicar_config_loja(nova, exportar_config_loja(inspirium), excecoes)
implantação      =  aplicar_config_loja(nova, json.load(arquivo), excecoes)
```

O clone deixa de ser um caminho próprio e passa a ser **o caso em que a exportação não chega a
tocar o disco**. É o mesmo padrão do gabarito contábil (R15): uma implementação,
`aplicar_gabarito_completo`, chamada pela criação de loja e pela migration.

Se a Etapa 1 for escrita como script direto banco→banco, esta etapa vira reescrita. Se for escrita
assim, vira um `json.dump`.

## O artefato

JSON, com cabeçalho que responde de onde veio: `versao_formato`, ambiente e loja de origem,
data, e quem exportou. Sem cabeçalho, daqui a seis meses ninguém sabe se aquele arquivo é da
Inspirium de hoje ou de agosto.

**O que o artefato NUNCA carrega:**

- **segredo** — `focus_token_homolog_enc` e `focus_token_prod_enc`, os dois; certificado;
  qualquer credencial;
- **identidade** — CNPJ, razão social, inscrições: viajam só como campo marcado
  `identidade: true`, que `aplicar_config_loja` **recusa** aplicar salvo flag explícita. Em
  Produção essa flag não se liga: emitir nota no CNPJ de outra empresa é o que ela permitiria;
- **dado** — cliente, projeto, contrato, lançamento. Nunca.
- **as árvores contábeis** — o destino **semeia** (`aplicar_gabarito_completo`) e o artefato
  carrega só a **lista de divergências** em relação ao gabarito, como material de conferência
  humana. Mesma razão da Etapa 1: gabarito congelado em cópia é a R13/R14.

**Consequência que vale dizer em voz alta:** é justamente por não carregar segredo que o artefato
**pode ser versionado no git**. Configuração de loja vira configuração-como-código, com histórico
e diff — dá para ver o que mudou nas faixas de comissão entre março e setembro. A regra de tirar
o segredo deixa de ser precaução e vira o que habilita a coisa toda.

Isso o separa por inteiro do `config_*.sql` que hoje existe em `docs/db/` e está no `.gitignore`
**porque tem credencial** — e que, pela mesma razão, não pode ser lido nem diferenciado por
ninguém.

## Aceite adicional

7. `aplicar_config_loja(nova, exportar_config_loja(inspirium))` produz **exatamente** a mesma
   loja que o clone direto da Etapa 1 — prove comparando as duas, campo a campo.
8. O artefato exportado, lido como texto, **não contém** nenhum token, certificado ou dado de
   cliente. Teste que falha se contiver.
9. Aplicar o mesmo artefato duas vezes não muda nada na segunda.
10. Aplicar com identidade e **sem** a flag explícita: CNPJ e razão social do destino ficam
    **intocados**, e a operação diz o que recusou em vez de silenciar.


## Fora do escopo

- **Importação de clientes do Pontta** — frente própria. Vale desenhá-la como processo
  **repetível e idempotente**, com id de origem rastreável (`origem='pontta'` + id externo), não
  como carga única: assim o piloto em Homologação é descartável e a entrada real em Produção
  **re-roda a mesma importação**. Mesmo padrão do gabarito: uma implementação, dois pontos de
  entrada.
- **Higiene de credenciais antes de dado real entrar.** As dez contas de teste criadas em 10/09
  têm senha `orizon123` e `senha_provisoria=0`. Antes de existir cliente real nesta base, elas
  trocam de senha ou saem, e os usuários das lojas do piloto nascem com `senha_provisoria=1`.


## Etapa 1 EXECUTADA em Homologação (11/09) — o que a execução ensinou

Rodada em `orizon_homologacao`, servidor do serviço B, com o repositório na tag
`v2026.09.09-beta1` e os dois arquivos novos trazidos por `git show origin/main:<arquivo>` —
sem mover o servidor da tag.

```
python3 scripts/clonar_loja.py --banco-esperado orizon_homologacao clone --origem-loja 1 \
    --nome "Loja Teste" --codigo TES --permitir-identidade --copiar-remuneracao --aplicar
```

Resultado: **Loja Teste = id 15**, rede_id 1 (a mesma da Inspirium). O relatório trouxe
`divergências contra o gabarito: NENHUMA`, 3 perfis, 15 funções, 4 documentos-modelo,
emitente aplicado, `remuneracao: copiada (--copiar-remuneracao)`.

**Idempotência provada sem querer.** A segunda execução do `--aplicar` disse
`loja já existe (id=15) — reaplicando config por cima` e devolveu `criados: 0` em tudo, com os
4 documentos-modelo `pulados_ja_iguais`. Não foi um teste planejado; foi uma repetição acidental
que virou evidência.

**R16 satisfeita depois da gravação:** `varrer_orfaos_gabarito` devolveu zero em todos os
campos — `encontrados_conta`, `encontrados_centro_custo`, `retidos_*`.

**A configuração financeira chegou inteira.** `config_financeira_json` da loja 15 traz as faixas
da Inspirium (3% até 100k, 4% até 150k, 5% até 200k, 6% até 300k), `meta_mensal` 500.000 e o
`limitador_desconto` com os dois degraus (30% → −1pp, 35% → −2pp). A função Consultor de Vendas
chegou com `usa_comissao_vendas=1` e `salario_fixo=2000.0` — este último só porque a flag foi
passada.

### O achado da execução: o clone leva FUNÇÕES, não FUNCIONÁRIOS

A Loja Teste nasceu com **15 funções e zero pessoas** — `Funcionario` e `Usuario` deram 0 na
consulta. Isso não estava escrito em lugar nenhum do plano, e não é detalhe de teste: **numa
implantação real é um passo a mais**, entre "a loja existe configurada" e "alguém consegue
entrar nela".

Duas consequências para quando este mecanismo virar atalho de implantação:

1. O relatório do `clone` deveria **dizer** que a loja destino ficou sem usuário — hoje ele
   informa o que copiou e cala sobre o que a loja ainda não tem para funcionar. Mesmo espírito
   da linha da remuneração não copiada: uma exceção que se anuncia vale mais que uma que só
   existe no código.
2. Não adianta procurar um usuário de rede para contornar: as duas lojas estão na rede 1 e
   **nenhum usuário do banco tem `rede_id` preenchido**. Foi medido, não suposto.

O contorno usado foi `scripts/seed_loja15.py` — irmão do `seed_funcionarios_homolog.py`, que não
serve para uma segunda loja porque checa `login` **globalmente** e pularia os dez. O novo usa
sufixo `15` nos logins e a faixa 910.xxx de CPF (o outro usa 900.xxx), e é idempotente por login
e por CPF-dentro-da-loja. Semeou 11 contas: 1 `master` (`admtes`), 2 `gerencial`
(`rvieira15`, `alopes15`) e 8 `operador`, cobrindo os dez papéis. Amarração 1:1
`Funcionario.usuario_id` ↔ `Usuario.funcionario_id` conferida nos dois sentidos — é o que
`mod_folha._upsert_itens_venda` exige.

**Higiene:** essas 11 entram na mesma dívida já registrada no "Fora do escopo" — senha
`orizon123`, `senha_provisoria=0`. São 21 contas nessa condição em Homologação agora.

### O que ainda falta para fechar a Etapa 1

O **aceite 6** continua aberto: criar um projeto na Loja Teste (entrar como `cantunes15`) e ver
as faixas de comissão aparecerem na negociação. O lado do dado está provado acima; falta a tela.
Três coisas a conferir lá: a faixa muda de degrau ao cruzar 100k/150k/200k/300k; o limitador de
desconto morde acima de 30% e de 35%; e o cabeçalho mostra "Loja Teste", não Inspirium — este
último é onde a identidade herdada pelo `--permitir-identidade` apareceria.

**A Etapa 2 (limpar os projetos da Inspirium) segue bloqueada** até o aceite 6 passar: enquanto
a tela não confirmar, a Inspirium é a única cópia boa da configuração.

**Dívida de identidade, a não esquecer:** a Loja Teste carrega hoje o CNPJ e a razão social da
Inspirium. Inofensivo em Homologação — o token da Focus é de homologação. Mas esta loja **não
viaja para Produção** com a identidade herdada.
