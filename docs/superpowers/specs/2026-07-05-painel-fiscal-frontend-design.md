# Painel de Configuração Fiscal · Sub-frente II — Frontend — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (Sessão 47, direto na `main`)** — painel na aba Fiscal do admin da loja;
> checagem estrutural OK, backend 507 verde. **Verificação manual no navegador pendente** (do usuário).
> Frontend do `PerfilFiscal` (Sub-frente I). Sem teste JS (verificação manual + checagem estrutural).
> **[Gap para depois]** `cert_validade`/`cert_cnpj` são exibidos read-only — o PUT de config da Sub-frente
> I não os inclui na allowlist; torná-los editáveis é um ajuste pequeno no backend.

## 1. Contexto e recorte

A Sub-frente I entregou o backend do `PerfilFiscal` (modelo, cripto, endpoints GET/PUT
`config`/`segredos`/`ambiente`). Esta frente é o **painel no frontend** (`static/index.html`) que
consome esses endpoints — uma **nova aba "Fiscal"** na tela admin da loja (nível 3), espelhando o
padrão da aba "Financeiro" (`adminFinanceiroCarregar/Salvar`). Backend intocado.

## 2. Decisões (brainstorming)

- **Confirmar placeholder:** **checkbox "confirmado" por campo**. Cada campo em `placeholders` mostra um
  badge "valor de teste — confirmar com contabilidade" + um checkbox. Ao salvar, `placeholders` = os
  campos que seguem **não confirmados** (checkbox desmarcado).
- **NFS-e:** **incluir agora** como captura de dado (CNAE, código do serviço, ISS, município IBGE),
  marcado "NFS-e (emissão futura)". Só persiste dado; não emite serviço.
- **Guarda de produção (front):** o botão "Ativar Produção" fica **desabilitado** enquanto houver
  qualquer placeholder **OU** o token de produção não estiver definido (`token_prod_definido=false`),
  com dica explicando. Reforça o backend (que já rejeita produção com placeholder).
- **Segredos write-only:** tokens homolog/prod nunca pré-preenchidos; mostra "✓ definido" quando
  `token_*_definido`; salvos por `PUT …/segredos` (botão próprio). Certificado A1 **não** é enviado por
  aqui (aviso de que o `.pfx` vai no painel da Focus).
- Reusa os helpers existentes: `campo(id,label,val)`, `grid2`, `field-label`, `.sw`, `showToast`,
  `avisoPopup`, `confirmarPopup`, `esc`, botões `.btn btn-primary btn-sm`.

## 3. UI — aba "Fiscal" (em `adminRenderLoja`)

- **Aba:** `<button class="home-tab" id="loja-tab-fiscal" onclick="adminLojaTab('fiscal')">Fiscal</button>`
  + `<div id="loja-panel-fiscal">`; estender `adminLojaTab` para chamar `adminFiscalCarregar(lid)` em
  `'fiscal'`.
- **`adminFiscalCarregar(lid)`** → `GET /api/admin/lojas/<lid>/perfil-fiscal`; guarda o retorno em
  `_cfgFisc` (perfil, placeholders, ambiente_ativo, token_*_definido, cert_*). Renderiza as seções:
  1. **Identificação:** `razao_social`, `inscricao_estadual`, `inscricao_municipal`.
  2. **Regime:** `regime_tributario` (select: simples/simples_excesso/normal/mei), `csosn_padrao`.
  3. **NF-e produto:** `cfop_dentro_uf`, `cfop_fora_uf`, `serie_nfe`, `discrimina_impostos` (toggle `.sw`).
  4. **NFS-e (emissão futura):** `cnae_servico`, `cod_servico_municipio`, `aliquota_iss` (number %),
     `municipio_ibge`.
  5. **Certificado A1:** `cert_validade`, `cert_cnpj` (referência) + aviso "o .pfx fica no painel da
     Focus, não aqui".
  6. **Credenciais Focus:** dois campos password (homolog/prod) com rótulo "✓ definido" quando o
     respectivo `token_*_definido`; botão **"Salvar credenciais Focus"** (`PUT …/segredos`).
  7. **Perfil de emissão:** `papel_cnpj` (select: central_produto/loja_servico/loja_produto_servico/avulso).
  - **Badge + checkbox de placeholder:** cada campo cujo id está em `placeholders` recebe o badge e um
    checkbox "confirmado" (id `pf-conf-<campo>`), inicialmente desmarcado.
  - **Ambiente:** indicador do `ambiente_ativo` (homologação em cor neutra; produção em destaque/alerta)
    + botão **"Ativar Produção"** (desabilitado por placeholder pendente ou token de produção ausente) e
    **"Voltar para Homologação"**.
- **`adminFiscalSalvar(lid)`** → lê os campos não-secretos + recomputa `placeholders` (os campos
  originalmente placeholder cujo checkbox segue desmarcado) → `PUT …/perfil-fiscal`; `showToast` no ok,
  `avisoPopup` no erro; recarrega.
- **`adminFiscalSalvarSegredos(lid)`** → lê os dois campos password; envia só os não-vazios em
  `PUT …/segredos`; limpa os campos e recarrega (mostra "✓ definido").
- **`adminFiscalAtivarAmbiente(lid, ambiente)`** → `confirmarPopup(perigo)` (só para produção) →
  `PUT …/ambiente`; em erro (ex.: placeholder pendente no backend) mostra o motivo; recarrega.

## 4. Segurança / cuidados

- Token **nunca** exibido (o GET não devolve valor — só flags); campos password sempre vazios ao abrir.
- Troca para produção é ação explícita (confirm modal) + dupla guarda (placeholder + token de produção).
- `esc()` em todo valor dinâmico interpolado no HTML.

## 5. Testes / verificação

- **Sem teste JS.** Verificação: extrair o `<script>` e checar balanceamento (chaves/parênteses/backticks)
  — se `node` disponível, `node --check`. A suíte backend (`python3 -m pytest -q`, 507) deve permanecer
  verde (o frontend não é importado pelos testes).
- **Verificação manual no navegador** (pendente, do usuário): abrir Admin → Loja → aba Fiscal; editar e
  salvar config; badges nos campos placeholder + checkbox confirmando; salvar credenciais Focus (mostra
  "✓ definido", nunca ecoa o token); "Ativar Produção" bloqueado com placeholder/sem token e liberado
  quando ambos ok.

## 6. Fora de escopo

- Backend do `PerfilFiscal` (Sub-frente I — pronto). Mapa fiscal/emissão (Fases 3b/4).
- Upload do certificado (fluxo no painel da Focus).
- Máscaras de CNPJ/IE/CEP (o projeto não tem helper de máscara; inputs de texto simples, validação no
  backend).
