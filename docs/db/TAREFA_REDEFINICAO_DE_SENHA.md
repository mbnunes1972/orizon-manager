# Tarefa — Redefinição de senha: três caminhos, por natureza da conta

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-18
**Origem:** o Marcelo ficou preso fora de duas contas em dois dias (`sad2026`, `lds2026`). Hoje
resolve porque existe uma sessão com acesso ao banco. **Em outubro serão cinco lojas com gente de
verdade**, e alguém esquece senha toda semana — sem redefinição pela tela, cada esquecimento vira
um pedido ao Marcelo.

**Decisão do Marcelo (18/09):** implementar os três caminhos abaixo, nesta ordem. O ideal seria
e-mail ou SMS; para estes usuários, criados pelo próprio sistema, vale um mecanismo diferente.

**O que já existe e deve ser reusado (não reinventar):**
- `auth/auth.py::trocar_senha(usuario_id, nova_senha)` — define a senha e **limpa** a flag
  `senha_provisoria`. É a primitiva.
- `senha_provisoria` → `precisa_trocar_senha` no login (`auth/auth.py:93` e `:296`) → a tela
  bloqueia até trocar (`_forcarTrocaSenha`). Provado ao vivo em 17/09.
- `mod_cadastro.func_sync_acesso` já **gera senha inicial** (dígitos do CPF; token aleatório quando
  não há CPF — conserto da auditoria de 13/08, que achou `orizon123` previsível). **Regra dos
  irmãos: reuse esse gerador**, não escreva um segundo.

---

## Caminho 3 — PRIMEIRO: contas sem gestor e sem telefone (script, fora de banda)

`sad2026`, super_admin, e as contas que a tela Admin › Usuários cria soltas (ela não tem campo de
Função — medido em 17/09). Não têm gestor acima nem funcionário com celular, então nenhum dos
outros caminhos as alcança.

Para elas o caminho certo é **linha de comando no servidor**, de propósito: é a conta que pode
tudo, e o acesso a ela deve exigir acesso à máquina. Precedente da casa: `scripts/criar_primeiro_admin.py`.

**Entrega:** `scripts/redefinir_senha.py` — recebe o login, gera senha forte pelo gerador já
existente, chama `trocar_senha`, **marca `senha_provisoria=1` em seguida** (a primitiva limpa a
flag; aqui a gente quer o contrário) e imprime o valor uma vez. Recusa login inexistente ou
inativo com mensagem clara. É o menor dos três e resolve o problema de hoje — pode sair junto com
a próxima tag.

---

## Caminho 1 — contas de funcionário: redefinição pelo gestor

**O mecanismo principal, e o que tira o Marcelo do caminho crítico.**

Master ou gerencial da loja abre Admin › Usuários, clica **"Redefinir senha"** no funcionário: o
sistema gera senha provisória, marca `senha_provisoria=1` e **mostra o valor uma vez na tela**,
para o gestor entregar em mãos.

**Por que é adequado a este público, e não é preguiça:** são funcionários de loja, fisicamente ao
lado de quem os cadastrou. Não exige e-mail, SMS nem fornecedor novo. O gestor pode tomar a conta
do funcionário — mas ele já podia, porque foi ele quem a criou; o que muda é **ficar registrado**.

**Requisitos:**
- Endpoint novo, perto de `PUT /api/admin/usuarios/<id>` (`main.py`). **Tenancy obrigatória:** só
  redefine conta de usuário da própria loja. `admin_rede`/`super_admin` seguem suas próprias
  regras de alcance — **meça, não assuma**.
- Um gestor **não** redefine a senha de quem é de nível igual ou superior ao dele. Sem isso, um
  gerencial toma a conta do master.
- Registra `LogAcaoGerencial` com ator, alvo e data. É o que torna o risco aceitável.
- O valor aparece **uma vez**, na resposta da ação; nunca é relido depois, nunca vai para log.
- **Regra dos irmãos:** enumere todo ponto que já define ou gera senha (`func_sync_acesso`,
  `criar_primeiro_admin.py`, a criação em `main.py`, o Caminho 3 acima) antes de acrescentar mais
  um. Reuse o gerador; se achar divergência entre eles, reporte.

---

## Caminho 2 — DEPOIS DE 01/10: autoatendimento por WhatsApp

**Não é para esta rodada.** Está escrito aqui para quando chegar a vez, e para as ressalvas não
precisarem ser redescobertas.

"Esqueci minha senha" → digita o login → o sistema envia um código de 6 dígitos ao **WhatsApp
cadastrado do funcionário** → código de uso único e validade curta → define senha provisória.

Melhor que e-mail **para este público**: o canal já está de pé e provado (`envios_externos`,
saída, `status=enviado`), o celular do funcionário já está no cadastro (é assim que
`processar_entrada_usuario` reconhece funcionário hoje), e vendedor de loja lê WhatsApp, não
e-mail — montar SMTP entregaria numa caixa que muitos não abrem.

**Três ressalvas, e a terceira tem prazo de fora:**

1. **A resposta tem que ser idêntica exista ou não o login.** Senão a tela vira um oráculo que
   confirma quem tem conta no sistema — e o login de vários é o e-mail da pessoa.
2. Limite de tentativas por login e por origem; código guardado **como hash**, uso único,
   expiração curta. Um código de 6 dígitos sem limite de tentativas é adivinhável.
3. **A Meta exige template aprovado** para mensagem iniciada pelo negócio fora da janela de 24 h —
   e um código de redefinição é exatamente isso. Depende de submeter e ter aprovação, com prazo
   que não controlamos. É o motivo prático de este caminho vir por último.

---

## Ordem e regras

1. Caminho 3 (script) — cabe na próxima tag.
2. Caminho 1 (gestor) — antes de 01/10; é o que faz a loja operar sem depender do Marcelo.
3. Caminho 2 (WhatsApp) — depois de 01/10.

Regras de sempre: não abrir achado novo (reportar e seguir); suíte verde antes da tag; Integração
antes de Homologação; **confira `ps aux` por outras sessões antes de rodar a suíte** (18/09:
sessões concorrentes foram a causa das três mortes por memória).
