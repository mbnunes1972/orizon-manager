# Tarefa — A triagem que não responde, e o contador que mente

> **Camada 4 · TRABALHO EM ANDAMENTO.** Descartável quando fechar.

**Data:** 2026-09-21
**Origem:** as duas saíram das medições de 18/09, já feitas — nenhuma precisa ser remedida.
Prazo: antes de 01/10.

---

## Item 1 — Triagem: resposta fora do formato

**Medido em 18/09:** `chat/triagem.py::registrar_resposta_triagem` — quando não reconhece a
resposta, **anexa o texto à mesma entrada e não responde nada**. O docstring diz o porquê: *"sem
nova pergunta — evita loop de mensagens"*. A intenção era certa; o efeito é o contato ficar sem
resposta nenhuma. Aconteceu com o Felipe em 17/09 (respondeu texto livre) e com o contato de
18/09 (mandou mídia/vazio).

**Decisão do Marcelo (18/09):** **reformular a pergunta UMA vez.** Se a segunda resposta também
não casar, **encaminhar para a fila com o texto preservado** — nunca insistir uma terceira vez.

**O raciocínio, para não se perder:** alguém que escreve "quero fazer uma cozinha" deu uma resposta
ótima — para um humano. Insistir "responda com um número" transforma o primeiro contato numa
discussão com um robô, e lead perdido no primeiro contato não volta. O robô roteia; não ganha a
discussão. O medo de loop que está no docstring continua válido — por isso o limite é **uma**.

**O problema de implementação, e é o ponto que precisa de decisão sua:** para reformular *uma
vez* é preciso **lembrar que já reformulou**, e hoje não existe onde guardar isso em
`TriagemEntrada`. Duas saídas, e **meça antes de escolher**:

- **coluna nova** — explícito, mas é DDL e exige migração (R1: nenhum DDL fora de migração);
- **derivar do que já existe** — por exemplo, contar os envios de saída de triagem ligados àquela
  entrada em `envios_externos`. Sem migração, mas é inferência, e inferência quebra em silêncio
  quando o formato muda.

**Reporte a medição e a sua recomendação antes de implementar.** Não é decisão de conforto: a
primeira é mais honesta e mais cara; a segunda é mais barata e mais frágil.

**Dois casos que o conserto tem que cobrir:**

1. **Mídia e mensagem vazia.** Foi o caso real de 18/09. Não é resposta reconhecível, então
   dispara a reformulação — **mas a mídia é conteúdo valioso** (gente manda foto da cozinha antes
   de responder qualquer pergunta). Preserve, não descarte.
2. **A primeira mensagem não conta.** A reformulação vale para uma *resposta* que não casou, nunca
   para o contato inicial, que já recebe a pergunta original.

**Depois da segunda falha:** a entrada vai para a fila da Triagem com todo o texto preservado, e é
um humano que resolve em dois segundos o que o robô não conseguiu. Isso já funciona — a fila mostra
`TriagemEntrada` pendente — só confirme que o estado final cai lá.

---

## Item 2 — O contador do Chat Interno mente

**Medido em 18/09 e confirmado no código:** `ocAtualizarBadges` (`static/index.html`) particiona
o inbox **só por `tipo`**:

```js
const interno = (_ocInbox||[]).filter(c => _INT_TIPOS.includes(c.tipo) || c.tipo==='mural' || c.tipo==='publico');
const atend   = (_ocInbox||[]).filter(c => !interno.includes(c));
```

Mas as **listas de fato** particionam por `tipo` **e** `segmento`: Chat Interno = tipo ∈
(direct, grupo) **E sem segmento**; Atendimentos = tipo = projeto **OU** (grupo **E** com
segmento). Resultado: uma conversa `grupo` **com** segmento — ou seja, um atendimento — entra na
soma do Chat Interno, num contador que aponta para uma lista onde ela nunca aparece.

Ninguém vaza linha nenhuma: é número falso, não conversa no lugar errado. Mas é a mesma família da
semana — afirmação falsa na tela, do mesmo tipo do ADR-004, do "Venda até" e do subtítulo "só SAC".

**O conserto NÃO é acertar o filtro do badge.** Se ficarem dois lugares decidindo o que é interno,
eles voltam a divergir no dia em que alguém mexer num só — que é exatamente como este defeito
nasceu.

**Extraia um predicado único** — algo como `_ocEhInterno(c)` — e use **o mesmo** na filtragem das
listas e no contador. Uma fonte, dois consumidores. Mesma prática do `mod_assinatura`, do
`_rede_da_loja` e do gate da fila.

*De brinde:* `!interno.includes(c)` é busca linear dentro de um filtro (O(n²)); com o predicado
compartilhado isso some naturalmente.

---

## Regras deste lote

1. Item 1: **medir e reportar antes de implementar** a escolha entre coluna e inferência.
2. Não abrir achado novo — reportar ao Marcelo e seguir.
3. **Antes da suíte completa:** `ps -eo pid,etime,rss,args | grep -Ei 'chrom|playwright|claude'` —
   sessão-irmã com Chromium vivo conta como ocupada (`PLANO_SEMANA_1.md`, regra 2b).
4. Suíte verde antes da tag; Integração antes de Homologação; `git status --short` vazio antes do
   checkout; smoke em `172.19.0.1`.
5. **Script que executa contra dado real é commitado antes de rodar** (`IMPLANTAR.md`).
