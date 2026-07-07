# Revisão por frente — o que foi feito (02/07 → 07/07/2026)

> Documento de **avaliação** para o Marcelo. Objetivo: dar um retrato preciso do que entrou na `main`
> nos últimos dias, com o **status de prova** de cada frente e **como conferir**. Companheiro deste
> arquivo: `2026-07-07-mapa-de-testes-leigo.md` (roteiro passo a passo para uma pessoa leiga testar as telas).

## Números do período
- **214 commits**, **12 sessões** (DEV_LOG 39 → 50).
- Suíte de testes automáticos: **414 → 632** (+218 testes; todos verdes).
- **2 documentos fiscais reais autorizados** em homologação: NF-e de **produto** (SEFAZ) e NFS-e de **serviço** (Prefeitura de SJC).

## Legenda de prova
- ✅ **Testes automáticos** — coberto por `pytest` (backend). Roda com `python3 -m pytest -q`.
- 🌐 **Smoke real** — testado de verdade contra o serviço externo (Focus NFe / SEFAZ / Prefeitura).
- 👁 **Precisa dos seus olhos** — sem teste automático de tela; exige conferência manual no navegador ou dado real.

---

## 1. Contrato em HTML/Markdown → PDF (WeasyPrint) — Sessões 39-40
**O quê:** aposentou o caminho antigo do contrato (`.docx` → LibreOffice) e passou a gerar o **PDF direto de
HTML+Markdown via WeasyPrint**. Capa em HTML, cláusulas em `contrato.md`, grade de parcelas e ambientes em HTML.
**Onde:** `mod_contrato.py`, `contrato_template/` (css/shell/logo), `contrato.md`.
**Testes:** ✅ montagem da capa, substituição de marcadores, grade de parcelas/ambientes, escape de valores.
**Fora / risco:** 👁 a **aparência final do PDF** (quebra de página, fontes, logo, assinaturas) não tem teste —
precisa abrir um contrato real e olhar. A **proposta** ainda usa o caminho `.docx`/LibreOffice (não foi tocada).

## 2. Negociação — UI padronizada + "Valor Total do Contrato" editável — Sessões 42-43
**O quê:** uniformizou o visual das modalidades de pagamento e adicionou o campo **"Valor Total do Contrato"**
editável, que faz o **cálculo reverso** (deriva o desconto a partir do valor final desejado).
**Onde:** frontend (`static/index.html`, tela de Negociação) + motor (`mod_negociacao.py`/`mod_provisoes.py`).
**Testes:** ✅ cálculo reverso e regras de persistência de parâmetros no backend.
**Fora / risco:** 👁 a **lógica financeira na tela** (o número que aparece após editar o valor) é o ponto mais
sensível do sistema — conferir com casos reais. Lembrete do projeto: `_negBaseValues` nunca é populado; a
verdade vem do motor/preview.

## 3. Escopo por projetista · parceiro na criação · elimina etapas 5/6 — Sessão ~42
**O quê:** Consultor passa a ver **apenas os projetos que criou** (`criado_por_id`); gerente+ veem todos.
Parceiro pode ser inserido já na etapa de Criação do Projeto. Etapas 5 (Revisão) e 6 (Aprovação do orçamento)
foram **eliminadas** (o ciclo encurtou: Orçamento 4 → Contrato 7).
**Onde:** `main.py` (visibilidade), `mod_ciclo.py`, frontend.
**Testes:** ✅ escopo de visibilidade por criador; trava do parceiro só com ambas as assinaturas.
**Fora / risco:** baixo. 👁 confirmar no navegador que o Consultor realmente não enxerga projeto de outro.

## 4. Subfases do Projeto Executivo (etapa 11) — Sessão 45
**O quê:** a etapa 11 ganhou **subfases** com upload de documentos (append-only), conclusão com guardas e
**revisão com reabertura em cascata**. Novas capabilities `executar_pe` e `revisar_pe`.
**Onde:** `mod_ciclo.py` (lógica pura), `main.py` (endpoints upload/conclusão/revisão), `database.py`
(`CicloDocumento`, `CicloRevisao`), frontend (painéis).
**Testes:** ✅ guardas, versão, upload/download, reabertura em cascata, casos negativos.
**Fora / risco:** 👁 os **painéis das subfases** no navegador (upload, botões de concluir/revisar).

## 5. Etapas operacionais 12/13/14 (Implantação · Produção · Entrega) — Sessão 46
**O quê:** painéis e **guardas operacionais** para concluir as etapas 12/13/14, com upload/listagem de XML na 12.
**Onde:** `mod_ciclo.py` (guardas puras), `main.py` (upload + PATCH `/ciclo`), frontend (painéis).
**Testes:** ✅ guardas puras, upload append-only, casos de erro.
**Fora / risco:** 👁 os painéis no navegador; o encaminhamento entre etapas.

## 6. Módulo Fiscal NF-e (Focus NFe) — Fases 1→5 — Sessões 47-48
**O quê:** pipeline completo de emissão da **NF-e de produto** da loja: lê o XML da fábrica → consolida →
precifica (markup) → monta o bloco fiscal → emite via **Focus NFe** → acompanha (polling) → guarda XML/DANFE.
Orquestrado na **etapa 15** do ciclo (upload, emitir, consultar, cancelar, baixar).
**Onde:** `mod_nfe.py`, `emissor_fiscal.py`, `focus_client.py`, `focus_config.py`, `mapa_fiscal.py`,
`emissor_focus.py`, `nfe_emissao.py`, `fiscal_cripto.py`, `mod_fiscal.py`, endpoints em `main.py`.
**Testes:** ✅ ampla cobertura offline (parser, precificação, montagem, emissão mockada, idempotência).
🌐 **Smoke real AUTORIZADO**: NF-e de produto da INSPIRIUM emitida pela SEFAZ (chave + XML + DANFE).
**Fora / risco:** 👁 o **painel da etapa 15** no navegador (fluxo pelo botão, não por script). Segurança:
segredos criptografados (Fernet, chave fora do git); o certificado A1 **nunca** é guardado por nós (vai ao painel
da Focus); o token nunca vai ao git. Corrigido no smoke: `modalidade_frete` obrigatório, CPF/CNPJ/CEP só-dígitos,
e uma falha de **cross-tenant** (consultar/cancelar exigem que o `ref` pertença ao projeto da URL).

## 7. Multi-CNPJ — Emitente como 1ª classe — Sessão 49
**O quê:** desacoplou **"quem vende"** de **"quem emite"**. Nasce o `Emitente` (CNPJ + config fiscal + tokens +
endereço), `PerfilEmissao` (política por loja/rede) e `DocumentoFiscal` (emitente pode diferir da loja).
Uma venda pode gerar 0, 1 ou 2 documentos por CNPJs diferentes.
**Onde:** `database.py` (Emitente/PerfilEmissao/DocumentoFiscal + migração), `mod_fiscal.resolver_emitente`.
**Testes:** ✅ resolução de emitente (override loja → default rede → self), migração idempotente com fix crítico
(rename da tabela **antes** do `create_all`, senão o upgrade perderia dados). 🌐 provado: emissão sob o CNPJ da
central da rede (≠ loja vendedora).
**Fora / risco:** baixo no backend. 👁 a configuração pela tela (ver frente 9).

## 8. Destinatário — 3 tipos (contribuinte / isento / não-contribuinte) — 06/07
**O quê:** o cliente ganhou `tipo_dest`, `cnpj`, `inscricao_estadual`. A emissão ramifica indicador de IE, CSOSN,
`consumidor_final`, e pede a IE do contribuinte na hora da emissão. O contrato passa a exigir CPF **ou** CNPJ
conforme o tipo.
**Onde:** `database.py` (Cliente), `mapa_fiscal.py`, `main.py`, frontend (modal do cliente).
**Testes:** ✅ ramificação por tipo, CSOSN, indicador; contrato exige o documento certo.
**Fora / risco:** 👁 o modal de cliente (campos que aparecem/somem conforme o tipo).

## 9. Painel Fiscal → Emitente (US-36) · UI do Perfil de Emissão (US-37) · NFS-e de serviço (US-38) — 06/07
**O quê:** o painel de config fiscal passou a operar o **Emitente** (não o antigo `PerfilFiscal`, removido; tabela
vira legado), com endereço + CSOSN. Surge o **painel Fiscal da rede** (Emitente central) e a **política de emissão
em 2 níveis** (default da rede + override da loja, produto/serviço → self|central). E a emissão da **NFS-e de
serviço** (montagem) via `/v2/nfse`, com valor manual, no painel da etapa 15.
**Onde:** `main.py` (endpoints perfil-fiscal/perfil-emissao/emitir-nfse), frontend (painéis).
**Testes:** ✅ endpoints e política; montagem da NFS-e.
**Fora / risco:** 👁 **três painéis** que nunca tiveram conferência manual: Fiscal da loja, Fiscal da rede, e
Perfil de Emissão. Marcados como "verificação manual PENDENTE" no DEV_LOG.

## 10. Omie desligado + painel "Fila Omie" removido — 06/07
**O quê:** a auto-sincronização de cliente com o Omie foi **desligada** (novo cliente sai `omie_sync_status =
'dispensado'`); o painel "Fila Omie" (clientes pendentes/erro) foi **removido** do admin.
**Onde:** `main.py` (flag `_OMIE_AUTO_SYNC` off), frontend (remoção do painel).
**Testes:** ✅ suíte segue verde. Código Omie residual (`_tentar_sync_omie`) está **morto mas inócuo**.
**Fora / risco:** baixo.

## 11. Validação de CPF/CNPJ nos cadastros — Sessão 50
**O quê:** **rejeita CPF/CNPJ falso** (dígito verificador) em **todos** os cadastros (Cliente, Parceiro, Usuário,
Rede, Loja). O documento **segue opcional** — valida-se só se informado. Backend autoritativo (400) + validação
inline no modal de cliente.
**Onde:** `validacao_doc.py` (novo), `main.py` (5 cadastros), `static/index.html` (inline).
**Testes:** ✅ util (DV, repetidos, com/sem pontuação) + e2e por cadastro (inválido→400, válido→200, sem doc→200).
**Fora / risco:** 👁 o aviso inline no modal (bloquear "Salvar" com número falso). **Não retroativo:** cadastros
já gravados com número falso só somem via edição.

## 12. US-39 — payload NFS-e completo — 07/07
**O quê:** completou o payload da NFS-e com `optante_simples_nacional` + `regime_especial_tributacao` +
`natureza_operacao` (derivados do regime do Emitente) e o **IBGE do tomador**. O cliente ganhou `municipio_ibge`
(capturado via ViaCEP no modal; backfill best-effort por CEP na emissão para clientes antigos).
**Onde:** `mapa_fiscal.py`, `database.py` (Cliente), `main.py`, `static/index.html`.
**Testes:** ✅ Simples→optante/RET, não-Simples→sem RET, tomador com/sem IBGE; regressão do `_ibge_por_cep`
(offline-safe). 🌐 **Smoke real: NFS-e AUTORIZADA** por SJC pelo caminho de código.
**Fora / risco:** 👁 re-emitir **pelo botão da etapa 15** (servidor+login+projeto de serviço) — o caminho de
código já está provado, falta a UI. RET=6/natureza=1 são **defaults documentados** (MEI seria 5).

## 13. Docs de arquitetura e processo — 06/07
**O quê:** mapa lógico de módulos (Núcleo/Plataforma + domínios), governança do ciclo (faixas de titularidade,
gates financeiros, papel da IA), reconciliação do fluxo canônico de **38 etapas** com o ciclo implementado (18+6),
e backlog EP-10/EP-11.
**Onde:** `docs/ARQUITETURA-MODULOS.md`, `docs/referencia/`, `docs/processos/`, `docs/historias/BACKLOG.md`.
**Testes:** — (documentação).

---

## Onde concentrar sua avaliação (resumo do risco)
1. **Frontend não tem teste automático** — todo 👁 acima é tela. Use o `mapa-de-testes-leigo.md`.
2. **NFS-e pela UI real** — provada por código, falta o botão da etapa 15 ponta a ponta.
3. **Dados de teste** — muitos clientes têm CPF/CEP placeholder (inválidos, sem IBGE) — corrigir para emitir de verdade.
4. **Contrato PDF** — conferência visual do documento final.

O **núcleo lógico está sólido** (632 testes verdes; 2 emissões fiscais reais autorizadas). O risco remanescente
está no **frontend não-testado** e em **dados**, não na lógica.
