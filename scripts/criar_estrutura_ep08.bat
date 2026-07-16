@echo off
chcp 65001 >nul
echo ============================================
echo  EP-08 - Secretaria Orizon
echo  Criando estrutura de repositorio...
echo ============================================
echo.

set BASE=E:\2026\ESTUDO_DE_IA\secretaria_orizon

mkdir "%BASE%" 2>nul
mkdir "%BASE%\static" 2>nul
mkdir "%BASE%\static\css" 2>nul
mkdir "%BASE%\static\js" 2>nul
mkdir "%BASE%\prompts" 2>nul
mkdir "%BASE%\docs" 2>nul
mkdir "%BASE%\docs\modulos" 2>nul
mkdir "%BASE%\docs\modulos\secretaria" 2>nul
mkdir "%BASE%\docs\historias" 2>nul

echo Criando arquivos Python...

type nul > "%BASE%\main.py"
type nul > "%BASE%\agent_core.py"
type nul > "%BASE%\db_reader.py"
type nul > "%BASE%\scheduler.py"
type nul > "%BASE%\notifier.py"
type nul > "%BASE%\auth.py"
type nul > "%BASE%\config.py"

echo Criando arquivos de configuracao...

(
echo # Claude API
echo ANTHROPIC_API_KEY=sk-ant-...
echo.
echo # Orizon Manager - leitura
echo ORIZON_MANAGER_BASE_URL=http://localhost:8765
echo ORIZON_MANAGER_JWT_SECRET=
echo.
echo # Evolution API - WhatsApp
echo EVOLUTION_API_URL=http://localhost:8080
echo EVOLUTION_API_KEY=
echo EVOLUTION_INSTANCE=orizon-central
echo.
echo # Scheduler
echo SCHEDULER_INTERVAL_HOURS=2
echo.
echo # Secretaria
echo PORT=8766
echo DEBUG=false
) > "%BASE%\.env.example"

(
echo anthropic^>=0.25.0
echo apscheduler^>=3.10.0
echo requests^>=2.31.0
echo pyjwt^>=2.8.0
echo python-dotenv^>=1.0.0
) > "%BASE%\requirements.txt"

(
echo .env
echo __pycache__/
echo *.pyc
echo secretaria.db
echo *.log
) > "%BASE%\.gitignore"

type nul > "%BASE%\static\index.html"
type nul > "%BASE%\static\css\style.css"
type nul > "%BASE%\static\js\app.js"
type nul > "%BASE%\static\js\chat.js"
type nul > "%BASE%\static\js\voice.js"
type nul > "%BASE%\static\js\alerts.js"
type nul > "%BASE%\prompts\system_prompt.txt"

echo Copiando documentacao...
echo ^(Copie manualmente os arquivos .md gerados para %BASE%\docs\^)

echo.
echo ============================================
echo  Estrutura criada em: %BASE%
echo.
echo  Proximos passos:
echo  1. Copiar arquivos .md para docs/
echo  2. cd %BASE% ^& git init
echo  3. Preencher .env com as credenciais
echo  4. Iniciar Passo 1 no Orizon Manager
echo ============================================
pause
