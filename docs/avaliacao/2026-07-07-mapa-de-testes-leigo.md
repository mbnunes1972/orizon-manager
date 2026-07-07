# Mapa de Testes — roteiro para conferência manual (linguagem simples)

> **Para quem vai testar:** você **não precisa saber programar**. Basta seguir os passos na ordem, olhar a tela
> e marcar se aconteceu o que está escrito em **"✅ Deve acontecer"**. Se algo diferente acontecer, anote em
> **"Se der errado"** e passe ao próximo. Cada teste é independente.
>
> **O que estamos conferindo:** as **telas** do sistema (o "miolo" já é testado automaticamente pelo computador;
> aqui olhamos o que só o olho humano pega: botões, avisos, telas e documentos).

## Antes de começar
1. Abra o sistema no navegador (peça o **endereço/URL** a quem cuida do sistema).
2. **Entrar (login).** Use um usuário e senha de exemplo abaixo (ambiente de teste). Em produção, use os
   credenciais reais que te passarem.

| Papel | Usuário | Senha (exemplo) |
|---|---|---|
| Diretor (vê tudo) | `pdm2026` | `teste123` |
| Gerente de Vendas | `lds2026` | `teste234` |
| Consultor (vê só o que criou) | `mds2026` | `teste345` |
| Gerente Adm/Financeiro | `gaf2026` | `teste456` |

> **Dica:** faça a maior parte dos testes como **Diretor** (`pdm2026`), que enxerga tudo. Alguns testes pedem
> outro usuário — está indicado no teste.

## Como marcar cada teste
- **[ ] OK** — aconteceu como o esperado.
- **[ ] Problema** — algo diferente. Anote o quê (print de tela ajuda muito).

## Documentos válidos e inválidos para os testes (CPF/CNPJ)
- **CPF válidos:** `111.444.777-35` · `390.533.447-05`
- **CPF falsos (devem ser recusados):** `111.111.111-11` · `123.123.123-00`
- **CNPJ válido:** `11.222.333/0001-81`
- **CNPJ falso (deve ser recusado):** `11.222.333/0001-00`

---

# Parte A — Cadastro de Cliente

### A1. Recusar CPF falso
**Passos:** Vá em **Clientes** → **Novo Cliente**. Preencha Nome, E-mail e Telefone. No campo **CPF**, digite um
**CPF falso** (`111.111.111-11`). Tente **Salvar**.
**✅ Deve acontecer:** o sistema **não salva** e mostra um aviso de **CPF inválido** (dígito verificador não confere).
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### A2. Aceitar CPF válido
**Passos:** No mesmo cadastro, troque o CPF por um **válido** (`111.444.777-35`) e **Salvar**.
**✅ Deve acontecer:** o cliente é **salvo** com sucesso (mensagem "Cliente cadastrado").
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### A3. Cliente sem CPF (opcional)
**Passos:** Cadastre um novo cliente **sem preencher CPF** (só Nome, E-mail, Telefone). **Salvar**.
**✅ Deve acontecer:** salva normalmente — **o CPF não é obrigatório** no cadastro.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### A4. CEP preenche endereço e "cidade/estado" sozinho
**Passos:** No cadastro, digite um **CEP válido** (ex.: um CEP real de São José dos Campos) no campo CEP.
**✅ Deve acontecer:** rua, bairro, cidade e estado são **preenchidos automaticamente** (via consulta de CEP).
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### A5. Tipo de cliente muda os campos (CPF vs CNPJ)
**Passos:** No cadastro, mude o **tipo de destinatário** para **contribuinte** (ou "empresa"/CNPJ).
**✅ Deve acontecer:** o campo **CNPJ** (e Inscrição Estadual) aparece no lugar do CPF. Ao voltar para
"não-contribuinte" (pessoa física), o **CPF** volta.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### A6. Recusar CNPJ falso
**Passos:** Com o tipo em **contribuinte**, digite um **CNPJ falso** (`11.222.333/0001-00`) e tente **Salvar**.
**✅ Deve acontecer:** **não salva**; aviso de **CNPJ inválido**. Trocando pelo válido (`11.222.333/0001-81`), salva.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

# Parte B — Projeto, Orçamento e Negociação

### B1. Criar projeto ligado a um cliente
**Passos:** Crie um **novo projeto** e ligue a um cliente existente.
**✅ Deve acontecer:** não deixa criar projeto **sem cliente**; com cliente, cria normalmente.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### B2. Consultor vê só os próprios projetos
**Passos:** Saia e **entre como Consultor** (`mds2026`). Olhe a lista de projetos.
**✅ Deve acontecer:** o Consultor vê **apenas os projetos que ele criou** — não os de outros.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### B3. Negociação — "Valor Total do Contrato" editável
**Passos:** Entre como Diretor, abra um projeto com orçamento e vá para a **Negociação**. Encontre o campo
**"Valor Total do Contrato"** e **digite um valor final** desejado (ex.: um valor redondo abaixo do cheio).
**✅ Deve acontecer:** o sistema recalcula sozinho o **desconto** para chegar exatamente naquele valor; os
números da tela batem com o valor que você digitou.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### B4. Desconto acima do limite é barrado
**Passos:** Ainda na negociação, tente aplicar um **desconto maior que o permitido** para o seu perfil.
**✅ Deve acontecer:** o sistema **não aceita** (ou pede autorização) e **não deixa** o desconto acima do limite.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

# Parte C — Contrato (PDF)

### C1. Gerar o contrato e conferir o PDF
**Passos:** Com o orçamento aprovado, gere o **contrato** e **abra o PDF**.
**✅ Deve acontecer:** o PDF abre com **capa**, cláusulas, **grade de parcelas** (valores e datas) e o bloco de
**assinaturas** (empresa INSPIRIUM fixa; o cliente como 2º signatário). Confira visualmente:
- [ ] logo e capa aparecem certos
- [ ] valores e datas das parcelas corretos
- [ ] nome/CPF do cliente no lugar certo
- [ ] nada cortado/quebrado feio entre páginas

**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### C2. Documento do cliente aparece conforme o tipo
**Passos:** Gere contrato para um cliente **pessoa física** (CPF) e outro **empresa** (CNPJ).
**✅ Deve acontecer:** no contrato aparece **CPF** para pessoa física e **CNPJ** para empresa.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

# Parte D — Ciclo do Projeto (etapas)

### D1. Projeto Executivo (etapa 11) — subfases e anexos
**Passos:** Num projeto avançado, abra o **Ciclo** e vá à etapa **Projeto Executivo (11)**. Faça **upload de um
arquivo** numa subfase e **conclua** a subfase.
**✅ Deve acontecer:** o arquivo aparece na lista; a subfase fica concluída; dá para **baixar** o arquivo.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### D2. Revisão reabre etapas seguintes
**Passos:** Ainda no Projeto Executivo, use a opção de **Revisão** de uma subfase já concluída.
**✅ Deve acontecer:** a revisão **reabre** a subfase (e as seguintes, em cascata), pedindo refazer.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### D3. Etapas operacionais 12/13/14 (Implantação, Produção, Entrega)
**Passos:** Avance o ciclo pelas etapas **12, 13 e 14**, concluindo cada uma.
**✅ Deve acontecer:** cada etapa só conclui quando as condições estão atendidas; o painel mostra o avanço.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

# Parte E — Fiscal (NF-e e NFS-e) — **a área mais nova, olhar com atenção**

> Estes testes mexem com emissão de nota fiscal. Faça em **ambiente de homologação (teste)**, nunca produção,
> a não ser que quem cuida do sistema autorize.

### E1. Painel de configuração fiscal da loja
**Passos:** Entre como **Diretor**. Vá no **Admin da loja** → aba **Fiscal**. Confira os campos do **Emitente**:
CNPJ, razão social, endereço, Inscrição Estadual, Inscrição Municipal, código de serviço, ISS, ambiente.
**✅ Deve acontecer:** os dados aparecem e podem ser **editados e salvos**; ao reabrir, **continuam salvos**
(não somem). Os **segredos/tokens** aparecem como "preenchido" (não mostram o valor).
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### E2. Painel fiscal da rede (Emitente central) e política de emissão
**Passos:** Ainda no Admin, procure o painel **Fiscal da rede** e a configuração de **Perfil de Emissão**
(quem emite produto e quem emite serviço: a própria loja ou a central).
**✅ Deve acontecer:** dá para escolher, por **produto** e por **serviço**, se emite a **própria loja** ou a
**central da rede**; a escolha salva.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### E3. Emitir NF-e de produto (etapa 15)
**Passos:** Num projeto que chegou à **etapa 15 ("Emissão da NFe do cliente")**: clique em **Carregar NF-e da
Fábrica** e selecione o XML; ajuste o **markup %**; clique **Emitir NF-e da Loja**.
**✅ Deve acontecer:** aparece status **autorizado** + uma **chave de acesso**; surgem botões **Baixar XML /
DANFE**; a etapa fica marcada como emitida (verde). *(Isso já foi provado uma vez de verdade na SEFAZ.)*
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### E4. Emitir NFS-e de serviço/montagem (etapa 15)
**Passos:** No painel da etapa 15, use a opção de **NFS-e de serviço**, informe o **valor do serviço** e emita.
**⚠️ Importante:** o **cliente** dessa nota precisa ter **CPF/CNPJ válido** e **endereço com CEP válido** (senão a
prefeitura recusa). Use um cliente cadastrado corretamente (o CEP preenche o código do município automaticamente).
**✅ Deve acontecer:** a nota é **autorizada** pela prefeitura (número + código de verificação; XML/PDF).
*(Já foi provado de verdade na Prefeitura de São José dos Campos.)*
**Se der errado (anote o código do erro que aparecer):** _______________________  → **[ ] OK  [ ] Problema**

### E5. Consultar e cancelar (segurança entre lojas)
**Passos:** Após emitir, use **Consultar** para reconsultar o status. Se for testar **Cancelar**, informe uma
justificativa (entre 15 e 255 caracteres).
**✅ Deve acontecer:** consultar mostra o status atual; cancelar (quando permitido) reverte a etapa. Você **nunca**
consegue mexer numa nota de **outra loja/projeto**.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

# Parte F — Administração e cadastros

### F1. Validação de CPF/CNPJ nos outros cadastros
**Passos:** Em **Parceiros** (e, como Diretor, em **Usuários**), tente cadastrar com um **documento falso**.
**✅ Deve acontecer:** o sistema **recusa** o documento falso (mesma regra do cliente); com documento válido, aceita.
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

### F2. Painel "Fila Omie" foi removido
**Passos:** No Admin, procure o antigo painel **"Fila Omie — Clientes pendentes / com erro"**.
**✅ Deve acontecer:** **não existe mais** — foi retirado de propósito (a integração Omie está desligada).
**Se der errado:** _______________________  → **[ ] OK  [ ] Problema**

---

## Como me devolver o resultado
Para cada teste, marque **OK** ou **Problema**. Nos que deram **Problema**, descreva em uma frase o que aconteceu
e, se possível, anexe um **print da tela**. Não precisa saber o motivo técnico — a descrição do que você viu já basta.

## Resumo rápido (preencha no fim)
- Testes com **OK**: ____ de 22
- Testes com **Problema**: ____  → quais números: ____________________
- Observações gerais: ________________________________________________
