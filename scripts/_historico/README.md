# scripts/_historico/

Scripts que já cumpriram o papel: cutover do motor de negociação (jun/2026), template `.docx`
do contrato (aposentado — hoje o contrato é gerado pelo WeasyPrint), ajustes únicos no modelo de
contrato e criação pontual de um PDV. Nenhum teste, código ou runbook depende deles. Ficam como
registro de como algo foi feito. **Não rode sem ler o código antes.**

- Foram escritos para rodar de `scripts/`: os que montam o caminho da raiz com `__file__` sobem só
  um nível e, daqui, não acham a raiz. Ajuste o caminho antes de rodar.
- `reset_para_teste.py` é DESTRUTIVO e da época do SQLite — não rode contra Postgres.
- `ler_aymore.py` precisa das planilhas `tabelas_financeiras/xls/*.xlsx`, que não estão no git.
- `criar_docs.bat` e `criar_estrutura_ep08.bat` são de Windows e usam um caminho fixo de outra
  máquina (`E:\2026\...`); o segundo é de outro projeto (`secretaria_orizon`).

Separados de `scripts/` em 12/11/2026 (Fase 2 do plano de organização do repositório).
