# Tarefa — Admin e Config como chaves de primeira classe no manifesto (Fronteira 6.5)

Pacote de execução da Semana 2 (21–27/09), escrito pela Sessão B a partir da Seção 6.5 do
`docs/db/MAPA_MODULOS.md`. Quem executa é a Sessão A. **Faz-se na MESMA sessão de trabalho que
`docs/db/TAREFA_MANIFESTO_ROTAS.md` (6.6), depois dela** — os dois pacotes editam `modulos.py`, e
a 6.6 muda o mecanismo de match que este pacote não deve ter que reconciliar duas vezes.

**Escopo honesto, antes de começar:** este pacote é menor e mais barato do que a 6.6. Ele não
conserta um defeito ativo nem dormente — é fechar uma lacuna de taxonomia que, medida com cuidado,
tem um efeito concreto pequeno e um efeito de prevenção maior. Os dois estão descritos abaixo.

## O que está medido

**Admin e Config não têm chave em `modulos.py` hoje.** O manifesto tem 8 entradas de núcleo (auth,
tenancy, escopo, auditoria, ciclo, integracoes, plataforma, chat) e 10 de domínio — nenhuma se
chama `admin` ou `config`, embora o `Módulos_Orizon_v12.docx` (o papel) seja explícito: "Núcleo,
sempre presente, nunca desligável" para os dois, "dois itens distintos" um do outro.

**Consequência medida — três lugares diferentes já tratam "admin"/"config" como conceito, sem
nenhum consultar `modulos.py`:**
1. **Frontend** (`static/index.html`): a visibilidade dos nav-items `nav-07`/`nav-cfg` é decidida
   por dois campos que vêm de `/api/auth/me` — `usuario.acessa_admin`/`usuario.acessa_config`.
2. **`auth/perfis.py`**: as capacidades `acesso_admin`/`acesso_config` (dicionário `CAPACIDADES`,
   com `rotulo`/`descricao` próprios) e a função `acessa_painel(slug, painel)` — que, quando um
   perfil tem registro customizado em `perfil_acesso` (banco), decide checando
   `painel in info["modulos"]`. Ou seja: no banco, "admin" e "config" já são tratados como se
   fossem ids de módulo dentro da lista `modulos` de um perfil — misturados com `cadastro`,
   `comercial` etc. — mas só o registro em `perfil_acesso` sabe disso; `modulos.py` não.
3. **`main.py` (`mod_perfis_opcoes()`)**: monta a lista de opções da tela Admin › Perfis de Usuário
   concatenando os domínios de `modulos.dominios_com_rotulo()` com dois itens **hardcoded**:
   `{"id": "admin", "rotulo": "Painel Administração"}` e `{"id": "config", "rotulo": "Painel
   Config"}`. É a MESMA forma do defeito que o candidato 3 do mapa achou para Montagem
   (`rotulo` duplicado fora do manifesto, um "Operacional" desatualizado) — só que aqui o
   `rotulo` nunca esteve no manifesto, então não há divergência ainda, mas o padrão "rótulo
   hardcoded fora de `modulos.py`" é exatamente o que já causou aquele achado uma vez.

**Efeito prático de NÃO ter a chave:** `tests/test_arquitetura_modulos.py::
test_todo_py_esta_classificado` só cobre `.py` da raiz — como o código de Admin/Config vive
disperso em `main.py` (que já está em `SHELL`, isento), a ausência da chave não deixa nenhum
arquivo hoje sem dono. O gap é mais estreito do que o candidato 1 do mapa sugeria: não é uma
enforcement quebrada, é a MESMA informação (rótulo, "isto é núcleo, nunca desligável") vivendo
em três lugares que não se falam, com um deles (`main.py`) já tendo o hábito de hardcodar rótulo
por fora — o hábito que gerou o achado da Montagem.

**O que este pacote NÃO muda:** a lógica de permissão em si (`auth/perfis.py`,
`acessa_painel`/`acessa_painel_usuario`, os capability slugs `acesso_admin`/`acesso_config`) fica
exatamente como está — funciona, é testada, não é o problema. `modulo_do_path()` continua
ignorando núcleo (`if v["camada"] != "dominio": continue`) — Admin e Config não vão ficar
desligáveis nem bloqueáveis por rota, porque não são domínio. **Sem mudança de comportamento
visível a usuário nenhum.**

## O que fazer

**1. Adicionar duas entradas de núcleo em `modulos.py`**, seguindo o padrão exato das oito já
existentes (`"rotas": []` como todas as outras de núcleo — `modulo_do_path()` nunca olha para lá,
popular a lista seria simetria falsa):
```python
"admin":  {"camada": "nucleo", "depende_de": [], "rotulo": "Painel Administração",
           "arquivos": [], "tabelas": [], "rotas": []},
"config": {"camada": "nucleo", "depende_de": [], "rotulo": "Painel Config",
           "arquivos": [], "tabelas": [], "rotas": []},
```
Confirmar que `dominios_com_rotulo()`/`DOMINIOS_ORDEM`/`FAIXAS`/`hub_layout()` **não** citam essas
duas chaves em lugar nenhum — são núcleo, não entram no hub de domínios. Rodar
`tests/test_modulos.py` inteiro depois de adicionar: `test_rotulo_e_ordem_dos_dominios` e
`test_hub_layout_agrupa_por_faixa` não podem mudar de resultado (continuam vendo só os 10
domínios).

**2. Trocar o hardcode de `mod_perfis_opcoes()` (`main.py`) pela leitura do manifesto**, para que
o rótulo tenha uma fonte só:
```python
def mod_perfis_opcoes():
    import modulos
    doms = [{"id": d["id"], "rotulo": d["rotulo"]} for d in modulos.dominios_com_rotulo()]
    paineis = [{"id": "admin",  "rotulo": modulos.MODULOS["admin"]["rotulo"]},
               {"id": "config", "rotulo": modulos.MODULOS["config"]["rotulo"]}]
    return {"dominios": doms, "paineis": paineis}
```
(Pseudocódigo — a Sessão A decide a forma exata; o ponto é eliminar as duas strings literais.)

**3. Não mexer em `auth/perfis.py`.** A tentação natural é "já que estou aqui, ligar
`acessa_painel` no manifesto também" — não faça. `acessa_painel`/`acesso_admin`/`acesso_config`
são sobre QUEM pode ver o painel (permissão), o manifesto é sobre O QUE o painel é (taxonomia).
Misturar os dois nesta rodada troca um pacote pequeno e seguro por um que mexe em controle de
acesso — fora do escopo que o Marcelo definiu para esta Semana 2.

## Fronteiras — o que este pacote toca, e o que não

**Toca:** `modulos.py` (duas entradas novas) e `mod_perfis_opcoes()` em `main.py` (troca hardcode
por leitura do manifesto).

**Não toca:**
- `auth/perfis.py` — capability slugs, `PERFIS`, `acessa_painel`, `CAPACIDADES` continuam como
  estão.
- `static/index.html` — a lógica de mostrar/esconder `nav-07`/`nav-cfg` por
  `acessa_admin`/`acessa_config` não muda; ela já funciona (confirmado pelo Marcelo em bancada e
  Homologação com o perfil `pdm2026`) e não depende do manifesto.
- Qualquer rota de `main.py` — Admin/Config continuam sem `rotas` no manifesto, exatamente como os
  outros oito módulos de núcleo.
- A Fronteira 6.6 (`docs/db/TAREFA_MANIFESTO_ROTAS.md`) — os dois pacotes tocam `modulos.py`, mas
  em partes diferentes (6.6 mexe no mecanismo de match e nas `rotas` de `fiscal`/`financeiro`; 6.5
  só adiciona duas entradas de núcleo). Fazer 6.6 primeiro evita qualquer conflito de merge dentro
  do mesmo arquivo.

## Aceite

1. `modulos.MODULOS["admin"]["camada"] == "nucleo"` e `modulos.MODULOS["config"]["camada"] ==
   "nucleo"`; `modulos.desligavel("admin") is False` e `modulos.desligavel("config") is False`.
2. `modulos.NUCLEO` passa a ter 10 elementos (era 8); `modulos.DOMINIOS` continua com 10 — teste
   novo em `tests/test_modulos.py` fixando os dois números, para que uma reclassificação acidental
   futura quebre um teste, não passe despercebida.
3. `tests/test_modulos.py::test_rotulo_e_ordem_dos_dominios` e `::test_hub_layout_agrupa_por_faixa`
   continuam passando sem alteração — prova de que Admin/Config não vazaram para o hub de domínio.
4. `tests/test_arquitetura_modulos.py` inteiro continua verde.
5. `GET /api/admin/perfis` (a rota que `mod_perfis_opcoes()` alimenta) devolve exatamente os mesmos
   dois rótulos de antes ("Painel Administração", "Painel Config") — teste de regressão de
   conteúdo, não só de status 200. Prova que a troca de fonte não mudou o que a tela mostra.
6. `grep -n '"Painel Administração"\|"Painel Config"' main.py` devolve zero ocorrências fora de
   `modulos.py` — a string para de existir em dois lugares.
