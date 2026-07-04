# Deploy — Orizon Manager

---

## Ambientes

| Ambiente | URL | Servidor |
|---|---|---|
| Local (dev) | http://127.0.0.1:8765 | Máquina do desenvolvedor |
| DEV (nuvem) | http://167.88.33.121:8765 | Hostinger VPS |

---

## Fluxo de desenvolvimento

```
1. Desenvolver e testar localmente (http://127.0.0.1:8765)
2. git add . && git commit -m "descrição"
3. git push
4. SSH no servidor → git pull → restart
```

---

## Subir no servidor DEV

```bash
# 1. Conectar ao servidor
ssh root@167.88.33.121

# 2. Ir para o diretório do projeto
cd /root/orizon-manager

# 3. Descartar modificações locais (main.py tem 0.0.0.0)
git checkout main.py

# 4. Atualizar código
git pull

# 5. Ajustar bind para acesso externo
sed -i 's/127.0.0.1/0.0.0.0/g' main.py

# 6. Parar instância anterior
pkill -f "python3 main.py"

# 7. Subir em background com screen
screen -S omie
python3 main.py
# Ctrl+A, D para desanexar

# 8. Verificar
curl http://127.0.0.1:8765
```

---

## Comandos úteis no servidor

```bash
# Ver sessões screen ativas
screen -ls

# Reconectar ao app
screen -r omie

# Ver processos Python rodando
ps aux | grep python

# Matar todos os processos Python (se travado)
pkill -f python3

# Ver logs em tempo real
# (o app imprime no stdout — visível dentro do screen)
```

---

## Instalar dependências no servidor

```bash
pip3 install sqlalchemy --break-system-packages
pip3 install aiohttp --break-system-packages
```

---

## Banco de dados no servidor

```bash
# Criar usuários iniciais (primeira vez)
cd /root/orizon-manager
python3 seed.py

# O orizon.db é criado automaticamente ao subir o app
```

---

## Problemas comuns

### "Address already in use"
```bash
pkill -f "python3 main.py"
# Aguardar 2 segundos
python3 main.py
```

### "git pull" conflita com main.py
```bash
git checkout main.py
git pull
sed -i 's/127.0.0.1/0.0.0.0/g' main.py
```

### 404 em rotas que existem
Verificar se há múltiplas instâncias rodando:
```bash
ps aux | grep python3
# Se houver várias:
pkill -f python3
python3 main.py
```

---

## `[TODO]` Script deploy.sh

Criar script que automatiza todo o processo:

```bash
#!/bin/bash
# deploy.sh — executar no servidor
cd /root/orizon-manager
git checkout main.py
git pull
sed -i 's/127.0.0.1/0.0.0.0/g' main.py
pkill -f "python3 main.py" || true
sleep 2
python3 main.py &
echo "Deploy concluído — app rodando em http://167.88.33.121:8765"
```
