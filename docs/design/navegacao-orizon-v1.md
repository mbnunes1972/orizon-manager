# Diagramação e Navegação — Orizon (v1)

> Fonte: `Diagramacao_e_Navegacao_Orizon_v1.docx` (extraído automaticamente). **Especificação oficial de front-end.**

Diagramação e Navegação — Orizon Studio
v1 — 2026-07-08 · complementa Padrao_Design_Orizon_v2 (tokens e componentes)
## PARTE 1 — Diagramação de telas
Define como os componentes (já tokenizados no doc de design) se organizam no espaço, por tipo de tela.
## 1.1 Estrutura geral — vale para toda tela
Sidebar fixa, 170px de largura — sempre visível, nunca colapsa
Conteúdo com padding 22px 26px
Ação primária da página: sempre no canto superior direito do header — nunca solta no corpo da tela
Telas de Formulário/Detalhe: largura máxima de conteúdo 960px — não esticar até a borda da janela em monitores largos
## 1.2 Templates por tipo de tela
Cada aba de navegação (Parte 2) reaproveita um destes templates — nenhuma tela nova é um template do zero.
## PARTE 2 — Navegação
Define como o usuário se move entre telas. Modelo de 3 níveis, profundidade máxima fixa.
## 2.1 Os 3 níveis
Nível 1 — Hub: cards por faixa, tela de entrada pós-login
Nível 2 — Sidebar: sempre visível, 1 item por módulo de domínio, mais a seção Núcleo (Admin)
Nível 3 — Abas dentro do módulo: as seções do módulo (reaproveita o padrão "Projetos / Clientes" já existente)
Regra fixa: profundidade máxima = 3. Nunca aba dentro de aba; nunca sidebar que se expande por seção.
## 2.2 Composição da sidebar
## 2.3 Critério de admissão de um atalho
Só entra na seção Atalhos se: (a) consultado várias vezes ao dia por quase todo perfil de usuário, e (b) não puder simplesmente ser a aba padrão que abre ao clicar no módulo
Limite explícito: no máximo 2 atalhos. Um terceiro candidato é sinal de que falta um card/módulo no Hub — não de que cabe mais um atalho
## 2.4 Ação imediata — corrigir o estado atual
Remover Clientes e Parceiros da sidebar — já são abas dentro de Cadastro; hoje existem dois caminhos para o mesmo dado, o que precisa ser eliminado
Adicionar a seção Atalhos com Projetos como único item — não tem card próprio no Hub (vive dentro de Comercial), mas é o objeto mais consultado no dia a dia
## 2.5 Exemplo — abas do módulo Cadastro
Clientes · Fornecedores · Parceiros · Funcionários · Terceiros
Ordem sugerida por frequência de uso no dia a dia, não pela ordem do documento de módulos — ajustável por decisão de negócio, não de arquitetura.

### Tabela 1
| Tipo | Exemplo já existente | Regras |
|---|---|---|
| Hub | tela pós-login por módulos | cards agrupados por faixa com título de grupo; módulo sem tela própria mostra estado "em breve" |
| Lista / Tabela | Projetos, Cadastro (Clientes...) | filtro sempre acima da tabela; ação primária no header; altura de linha e paginação padronizadas |
| Detalhe / Formulário | abrir um projeto, cadastro de cliente | campos agrupados em seções com título; ações salvar/cancelar fixas (rodapé ou topo), nunca soltas no meio; respeita a largura máxima de 960px |
| Fluxo multi-etapa | negociação/orçamento (EP-07), gates financeiros | indicador de progresso sempre visível; painel de resumo/dossiê da IA em posição fixa, não muda de lugar entre etapas |

### Tabela 2
| Seção | Conteúdo |
|---|---|
| Módulos | sempre no topo — leva ao Hub |
| Atalhos | seção separada, visualmente distinta (label menor + divisor). Máximo 2 itens. |
| Admin (Núcleo) | sempre por último — Credenciais e Tokens vive aqui dentro, não na sidebar |
