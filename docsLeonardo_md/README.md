# Testes Unitários — Omie_V3

## Rodar todos os testes
```
cd E:\2026\ESTUDO_DE_IA\Omie_V3
pytest tests\ -v
```

## Rodar um módulo específico
```
pytest tests\test_aymore.py -v
pytest tests\test_cartao.py -v
pytest tests\test_margens.py -v
```

## Regra
Nenhum commit na branch `main` ou `develop` sem todos os testes passando.

## Fluxo de versionamento
```
git checkout -b feat/nome-da-feature   # 1. criar branch
# ... fazer alterações ...
pytest tests\ -v                       # 2. validar
git add .
git commit -m "tipo: descrição"        # 3. commit
git checkout develop
git merge feat/nome-da-feature         # 4. merge
```

### Tipos de commit
| Tipo | Quando usar |
|------|-------------|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `style` | visual/CSS |
| `test` | testes |
| `refactor` | refatoração sem mudança de comportamento |
