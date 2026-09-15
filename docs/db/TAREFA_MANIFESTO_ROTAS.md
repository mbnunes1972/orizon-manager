# Tarefa — corrigir `modulo_do_path()` para rotas com segmento variável (Fronteira 6.6)

Pacote de execução da Semana 2 (21–27/09), escrito pela Sessão B a partir da Seção 6.6 do
`docs/db/MAPA_MODULOS.md`. Quem executa é a Sessão A — este documento não contém código, só o
que medir, o que fazer, os limites e o critério de aceite. **A mais urgente das três fronteiras
desta rodada**, porque o defeito que ela fecha é o único das três que já existe hoje em produção
— só está dormente.

> **Por que isto muda a ORDEM de quem conserta o quê, não só o quê.** O endpoint que liga/desliga
> os módulos por loja — `/api/admin/lojas/<id>/modulos`, a tela que torna a venda por topologia
> possível — hoje **não** é protegido por `_bloqueio_modulo`, e por isso não há sintoma. Mas ele
> está sob o prefixo `/api/admin/lojas/` que o manifesto atribui inteiro a `fiscal`. Se, em
> qualquer trabalho futuro (inclusive dentro desta mesma Semana 2, se alguém decidir avançar rápido
> demais na topologia "loja avulsa"), esse guard for adicionado à rota de `modulos` **antes** deste
> pacote estar aplicado, o resultado é um **auto-bloqueio de inicialização**: desligar Fiscal numa
> loja trancaria o próprio painel que a religaria — sem rota de fuga pela UI, só mexendo direto no
> banco. Por isso este pacote **precisa ser o primeiro passo de qualquer frente que mexa em guard
> de topologia daqui pra frente**, não só mais uma correção de manifesto — quem for adicionar
> `_bloqueio_modulo` a uma rota nova de Comercial/Financeiro/Admin na Semana 2 ou depois deve
> confirmar que este pacote já foi aplicado antes de começar.

## O que está medido

**O sintoma original (Seção 5/Causa E do mapa):** o manifesto declara, para o domínio `fiscal`
(`modulos.py`), três prefixos:
```
"rotas": ["/api/projetos/", "/api/admin/lojas/", "/api/admin/redes/"]
```
`modulo_do_path()` (`modulos.py`) faz `path.startswith(prefixo)`, prefixo mais longo vence, e só
olha domínios (núcleo nunca aparece). Como os três prefixos de `fiscal` são exatamente os
prefixos FIXOS que antecedem o identificador variável (nome do projeto, id da loja, id da rede),
qualquer rota sob esses três caminhos — de QUALQUER domínio, ou do núcleo — cai em "fiscal" por
eliminação, a menos que outro domínio declare um prefixo mais longo (nenhum declara).

**Por que "completar a lista de rotas" (a formulação original da 6.6) não é suficiente
sozinha — medido nesta análise, é a causa raiz real:** o mecanismo de match é só `startswith`
sobre **string fixa**. Ele não sabe pular um segmento variável. Uma rota como
`/api/projetos/<nome>/equipe` não tem prefixo fixo possível que a identifique sem também casar
com `/api/projetos/<outro-nome>/nfe/emitir-teste` — o nome do projeto fica ENTRE o prefixo fixo e
o sufixo que diferencia o dono. **Prova de que essa armadilha já pegou alguém:** o manifesto de
`financeiro` já tenta ser mais específico com dois prefixos —
```python
"rotas": [..., "/api/projetos/<nome>/pe/conciliacao", "/api/projetos/<nome>/ciclo/11d/concluir"]
```
— usando `<nome>` como se fosse um curinga. Não é. `startswith()` compara caracteres literais:
`"/api/projetos/apartamento-silva/pe/conciliacao".startswith("/api/projetos/<nome>/pe/conciliacao")`
é `False`. **Essas duas entradas nunca casam com path nenhum — são mortas desde que foram
escritas**, e as duas rotas que deveriam proteger (conciliação de PE, conclusão do gate 11d) caem,
sem ninguém perceber, na regra de `fiscal` por eliminação, exatamente como todo o resto.

**Inventário do que hoje cai em "fiscal" por eliminação, sem ser fiscal** — levantado lendo as
rotas reais de `main.py` que começam pelos três prefixos:

- Sob `/api/admin/lojas/<id>/…`: `integracao-clicksign` (é Comercial —
  `modulos.MODULOS["comercial"]["arquivos"]` inclui `mod_clicksign.py`/`mod_assinatura.py`),
  `logo`, `logo/remover` e `pdvs` (Tenancy/Admin, não fiscal), `modulos` (o próprio endpoint de
  liga/desliga topologia — Tenancy/Admin). Só `perfil-fiscal`, `perfil-emissao` e
  `nfe/emitir-teste` são genuinamente Fiscal.
- Sob `/api/admin/redes/<id>/…`: o CRUD de rede (`GET /api/admin/redes/<id>` puro) e
  `integracao-clicksign` (Comercial) também não são Fiscal — só `perfil-fiscal` e
  `perfil-emissao`.
- Sob `/api/projetos/<nome>/…`: a MAIORIA das ~70 sub-rotas existentes (contrato, aditivo,
  aprovação de PE, medição, equipe, briefing, parcelas, retenção, conversa, PE/comparação,
  data-entrega, status, editar…) é Comercial; as de `/ciclo`, `/ciclo/<codigo>`,
  `/ciclo/<codigo>/reabrir` etc. são do **Ciclo — núcleo**, que nunca deveria aparecer aqui (núcleo
  não é desligável, `modulo_do_path()` só olha domínio — o comportamento correto para uma rota do
  Ciclo é `None`, nunca "fiscal"). Só o grupo `ciclo/15/nfe*` (emissão/consulta/cancelamento de
  NF-e) é genuinamente Fiscal.

**Por que está adormecido hoje, e por que não vai continuar assim:** medi os seis pontos reais do
código que chamam `_bloqueio_modulo(path, loja)` (`main.py`) — todos os seis protegem rotas que
IMPORTAM `from fiscal import ...` logo acima, ou seja, são genuinamente Fiscal (`ciclo/15/nfe`,
`ciclo/15/emitir-nfe`, `ciclo/15/emitir-nfse`, `ciclo/15/nfe/consultar`, `ciclo/15/nfe/cancelar`,
`admin/lojas/<id>/nfe/emitir-teste`). Por coincidência, os seis lugares onde o guard já é chamado
hoje são exatamente os lugares onde a resposta errada e a certa colidem — **por isso não há
sintoma visível ainda**. O padrão natural da Fase 2 (extrair o Fiscal, que o próprio
`ARQUITETURA-MODULOS.md` já elege como piloto) é adicionar o MESMO guard `_bloqueio_modulo` às
rotas de Comercial/Financeiro/Ciclo conforme a topologia "loja avulsa" amadurecer — no instante em
que isso acontecer, qualquer rota nova sob `/api/projetos/`, `/api/admin/lojas/` ou
`/api/admin/redes/` herda a classificação errada por padrão, silenciosamente.

**Confirmado por leitura — o `/api/admin/lojas/<id>/modulos` (o próprio endpoint que liga/desliga
os domínios) não é hoje protegido por `_bloqueio_modulo`.** Não há risco de auto-bloqueio (desligar
Fiscal não pode travar o próprio painel que religaria Fiscal) — mas também não há NADA que impeça
alguém de adicionar esse guard a ele no futuro por engano, e aí o auto-bloqueio passaria a existir.
Vale um teste de regressão negativo explícito para isto (ver Aceite).

**O teste existente já teria pego só metade do problema.** `tests/test_modulos.py::
test_modulo_do_path` afirma `modulo_do_path("/api/projetos/X/ciclo/15/emitir-nfe") == "fiscal"` —
correto, continua correto depois do conserto. Mas não existe nenhuma asserção negativa (uma rota
de Comercial ou do Ciclo que NÃO deveria virar "fiscal") — é essa lacuna que escondeu o problema.

## O que fazer

**1. Ensinar `modulo_do_path()` a pular o segmento variável, em vez de tentar mais prefixos
fixos.** O problema não é falta de entradas na lista — é que a lista, do jeito que o mecanismo
funciona hoje, não TEM como expressar "depois do nome do projeto". A correção mínima: antes de
comparar, normalizar os três formatos de "contêiner com id/nome no meio" para a forma
`<prefixo-fixo><placeholder>/`, e casar as `rotas` do manifesto contra o que sobra DEPOIS do
placeholder, não contra o path inteiro. Os três contêineres conhecidos hoje:
   - `/api/projetos/<nome>/…` (nome do projeto)
   - `/api/admin/lojas/<id>/…` (id numérico da loja)
   - `/api/admin/redes/<id>/…` (id numérico da rede)

   Path que não casa com nenhum dos três continua sendo comparado como está hoje (`startswith`
   direto) — isso preserva `/api/clientes`, `/api/orcamentos/9/margens`, `/api/expedicao` etc.
   sem mudança de comportamento (são prefixos verdadeiramente fixos, sem id no meio).

**2. Corrigir os prefixos de `fiscal` no manifesto para os sufixos reais**, usando o inventário
acima: `ciclo/15/nfe`, `ciclo/15/emitir-nfe`, `ciclo/15/emitir-nfse`, `ciclo/15/nfe-fabrica`,
`ciclo/15/nfe/consultar`, `ciclo/15/nfe/cancelar` (sob o contêiner de projeto);
`nfe/emitir-teste`, `perfil-fiscal`, `perfil-emissao` (sob o contêiner de loja E de rede). Isso
troca os três prefixos largos por uma lista de sufixos precisos — mais entradas, mas cada uma
correta.

**3. Consertar as duas entradas mortas de `financeiro`** (`/api/projetos/<nome>/pe/conciliacao` e
`/api/projetos/<nome>/ciclo/11d/concluir`) para a forma de sufixo que o novo mecanismo espera
(`pe/conciliacao`, `ciclo/11d/concluir`).

**4. NÃO tentar classificar as ~70 sub-rotas de `/api/projetos/<nome>/…` de uma vez.** Depois do
passo 1 e 2, qualquer sufixo que nenhum domínio reivindicar cai em `None` (hoje ninguém é
bloqueado — comportamento idêntico ao atual "tudo ligado", só que sem a classificação errada). Isso
é seguro E suficiente para esta rodada: o defeito que importa (Fiscal engolindo rota alheia) já
está fechado; classificar CADA sub-rota de Comercial e do Ciclo é auditoria maior, correta como
follow-up, não como parte deste pacote.

## Fronteiras — o que este pacote toca, e o que não

**Toca:** só `modulos.py` (a função `modulo_do_path` e as entradas `rotas` de `fiscal` e
`financeiro`) e `tests/test_modulos.py`/`tests/test_arquitetura_modulos.py` (novos casos). **Não
toca nenhuma rota de `main.py`** — este pacote não muda comportamento de nenhum endpoint, só a
classificação usada pelo guard de topologia.

**Não faz parte deste pacote:**
- Classificar as sub-rotas de Comercial (`equipe`, `briefing`, `contrato`, `medicao`, `aditivo`,
  `aprovacao-pe`, `parcelas`, `retido`, `retencoes`, `conversa`, `pe/*` exceto `pe/conciliacao`,
  etc.) — ficam `None` (não bloqueáveis) até alguém precisar de fato desligar Comercial numa loja
  avulsa. Quando isso vier, é outro pacote, sobre a base que este conserta.
- Adicionar o guard `_bloqueio_modulo` a rotas novas — este pacote só impede que o guard, quando
  for chamado no futuro, erre. Não decide onde ele passa a ser chamado.
- Qualquer mudança na Fronteira 6.5 (Admin/Config no manifesto) — os dois pacotes tocam o mesmo
  arquivo (`modulos.py`) e por isso **devem ser feitos na mesma sessão de trabalho**, nesta ordem
  (6.6 primeiro, 6.5 depois) — ver `docs/db/TAREFA_MANIFESTO_ADMIN_CONFIG.md`.

## Aceite

1. `tests/test_modulos.py::test_modulo_do_path` continua passando com a asserção existente
   (`ciclo/15/emitir-nfe` → `fiscal`) **e** ganha casos novos, negativos:
   - `modulo_do_path("/api/projetos/X/equipe")` não é `"fiscal"` (hoje é; depois, `None` ou
     `"comercial"` se o passo 4 for estendido — mas nunca fiscal).
   - `modulo_do_path("/api/projetos/X/ciclo/8")` (PATCH genérico de etapa, núcleo) não é
     `"fiscal"` — é `None`.
   - `modulo_do_path("/api/admin/lojas/1/integracao-clicksign")` não é `"fiscal"`.
   - `modulo_do_path("/api/admin/lojas/1/modulos")` não é `"fiscal"` — confirma que o próprio
     endpoint de topologia nunca seria auto-bloqueado se alguém adicionasse o guard a ele amanhã.
   - `modulo_do_path("/api/admin/redes/3")` (CRUD de rede) não é `"fiscal"`.
   - As seis rotas reais que hoje chamam `_bloqueio_modulo` continuam `"fiscal"` depois do
     conserto — teste de não-regressão explícito, um `assert` por rota.
2. `tests/test_arquitetura_modulos.py` continua verde sem exceção nova.
3. Nenhuma rota de `main.py` muda de comportamento — só rodar a suíte completa de Fiscal/ClickSign
   e confirmar zero diferença (a Sessão A decide o comando; não é escopo da Sessão B sugerir
   invocação de `pytest`).
4. `financeiro["rotas"]` não tem mais nenhuma entrada com `<` literal — `grep -n '"<'
   modulos.py` não retorna nada dentro do bloco de `rotas`.
