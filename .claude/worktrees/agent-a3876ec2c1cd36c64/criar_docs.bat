@echo off
echo Criando estrutura de documentacao...

set BASE=E:\2026\ESTUDO_DE_IA\Omie_V3\docs

mkdir "%BASE%"
mkdir "%BASE%\arquitetura"
mkdir "%BASE%\modulos"
mkdir "%BASE%\modulos\autenticacao"
mkdir "%BASE%\modulos\clientes"
mkdir "%BASE%\modulos\parceiros"
mkdir "%BASE%\modulos\projetos"
mkdir "%BASE%\modulos\negociacao"
mkdir "%BASE%\modulos\financeiro"
mkdir "%BASE%\modulos\contratos"
mkdir "%BASE%\modulos\kanban"
mkdir "%BASE%\modulos\integracao_omie"
mkdir "%BASE%\modulos\pos_venda"
mkdir "%BASE%\processos"
mkdir "%BASE%\historias"

echo Estrutura criada com sucesso!
echo.
echo Agora coloque os arquivos baixados nas pastas corretas:
echo.
echo  README.md              -^> docs\
echo  STACK.md               -^> docs\arquitetura\
echo  BANCO_DE_DADOS.md      -^> docs\arquitetura\
echo  ROTAS.md               -^> docs\arquitetura\
echo  DECISOES.md            -^> docs\arquitetura\
echo  SPEC.md                -^> docs\modulos\autenticacao\
echo  SPEC_clientes.md       -^> docs\modulos\clientes\SPEC.md
echo  SPEC_parceiros.md      -^> docs\modulos\parceiros\SPEC.md
echo  SPEC_projetos.md       -^> docs\modulos\projetos\SPEC.md
echo  SPEC_negociacao.md     -^> docs\modulos\negociacao\SPEC.md
echo  SPEC_financeiro.md     -^> docs\modulos\financeiro\SPEC.md
echo  SPEC_contratos.md      -^> docs\modulos\contratos\SPEC.md
echo  SPEC_kanban.md         -^> docs\modulos\kanban\SPEC.md
echo  SPEC_integracao_omie.md-^> docs\modulos\integracao_omie\SPEC.md
echo  SPEC_pos_venda.md      -^> docs\modulos\pos_venda\SPEC.md
echo  MEDICAO.md             -^> docs\modulos\pos_venda\
echo  PROJETO_EXECUTIVO.md   -^> docs\modulos\pos_venda\
echo  IMPLANTACAO.md         -^> docs\modulos\pos_venda\
echo  PRODUCAO.md            -^> docs\modulos\pos_venda\
echo  TRANSPORTE_ENTREGA.md  -^> docs\modulos\pos_venda\
echo  MONTAGEM.md            -^> docs\modulos\pos_venda\
echo  ASSISTENCIA.md         -^> docs\modulos\pos_venda\
echo  TEMPLATE.md            -^> docs\historias\
echo  BACKLOG.md             -^> docs\historias\
echo  DEPLOY.md              -^> docs\processos\

pause
