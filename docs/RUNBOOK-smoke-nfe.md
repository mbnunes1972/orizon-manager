# Runbook — Smoke da NF-e (homologação) · etapa 15

> Preparado em 2026-07-06 para rodar em **2026-07-07**, após o certificado A1 entrar na Focus.
> Objetivo: emitir uma NF-e **real em homologação** da loja INSPIRIUM, ponta a ponta, pelo painel da etapa 15.

## ✅ Já preparado (não precisa refazer)
- **Chave de cripto** estável: `config/fiscal.key` criada (gitignored). Um token salvo hoje decripta amanhã.
- **PerfilFiscal da loja 1 (INSPIRIUM, CNPJ 19.152.134/0001-56):** criado, `ambiente_ativo=homologacao`,
  perfil-padrão (Simples, CSOSN 101, CFOP 5102/6102, ISS 5%). Placeholders presentes → **produção bloqueada**.
- **Token Focus (homologação)** salvo encriptado no perfil. **Validado hoje:** autentica na Focus
  (consulta de `ref` inexistente → 404 "Nota fiscal não encontrada"). A cadeia perfil→decrypt→FocusClient→auth
  funciona.
- **Projeto-alvo:** `Projeto_Teste_Neg` (loja INSPIRIUM, cliente **Marcelo Buonocore Nunes**, CPF preenchido).
  Ciclo concluído até a etapa 14 → **etapa 15 destravada**.
- **XMLs reais da fábrica:** `E:/2026/desenvolvimento/nfe-dalmobile/NFe-1709xx.xml` (5 arquivos).
- **Dry-run offline OK:** `NFe-170942.xml` + perfil INSPIRIUM + cliente 2 → preview (12 itens, custo 730,89 /
  venda 950,16) → `montar_nota` → `montar_payload` sem erro; item com CFOP/NCM/CSOSN 101/PIS-COFINS 49.

## ⚠️ Falta preencher (dado que só você tem) — antes ou durante o smoke
1. **Certificado A1 na Focus** (empresa 19.152.134/0001-56) — o bloqueio principal. Sem ele: "Empresa ainda
   não habilitada para emissão de NFe".
2. **Endereço da loja INSPIRIUM** (Loja: logradouro, número, bairro, cidade, **UF**, CEP) e **Inscrição
   Estadual** (perfil) — hoje estão **vazios**. O emitente do payload vem daí. Sem a **UF do emitente**, o
   CFOP sai como 6102 (interestadual) por padrão; com a UF certa (igual à do cliente) sai 5102 (dentro do
   estado). Preencher:
   - **Endereço** → painel de **dados da loja** (admin da loja INSPIRIUM).
   - **IE / município IBGE** → aba **Fiscal** do admin da loja.
   > Se a Focus reclamar de campo do emitente (endereço/IE/município) no smoke, preencha estes e re-emita.

## Passo a passo (após o certificado na Focus)
1. **Suba o servidor** com o interpretador real (o `python3` do PATH pode ser o stub do WindowsApps):
   `& "C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe" main.py`
   → `http://localhost:8765`. (Frontend é lido do disco a cada request — Ctrl+F5 basta; só Python exige restart.)
2. Faça login como usuário da INSPIRIUM com capacidade fiscal (`editar_dados_loja`: diretor / admin).
3. (Se ainda não preencheu) informe **endereço da loja** + **IE** — item ⚠️2 acima.
4. Abra o projeto **`Projeto_Teste_Neg`** → botão do **Ciclo** → card da **etapa 15 "Emissão da NFe do cliente"**.
5. **Carregar NF-e da Fábrica** → selecione `NFe-170942.xml`.
6. No item que aparecer, ajuste o **markup %** (default 30) e clique **Emitir NF-e da Loja**.
7. **Sucesso esperado:** status **autorizado** + **chave** de acesso; botões **Baixar XML / DANFE** aparecem;
   a etapa 15 fica **emitida** (verde). Use **Consultar** para reconsultar; **Cancelar** (justificativa 15-255
   chars) reverte a etapa.

## Como ler falhas
- **"Empresa ainda não habilitada…"** → certificado A1 ainda não processado na Focus (item ⚠️1).
- **"Configure o Perfil Fiscal…"** (400) → perfil sumiu (não deve — já criado); recriar pela aba Fiscal.
- **Rejeição de campo do emitente** (endereço/IE/UF/município) → preencher item ⚠️2 e re-emitir.
- **Erro de rede / stub** → subir o servidor com o interpretador real (passo 1); confirmar porta 8765.

## Alternativa sem UI (harness de teste, Fase 4)
`POST /api/admin/lojas/1/nfe/emitir-teste` (multipart: `arquivo`=XML da fábrica, `projeto_nome`=`Projeto_Teste_Neg`,
`markup_pct`=30), autenticado — mesma emissão sem depender do card do ciclo.
