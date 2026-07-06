# docs/referencia/ — documentos de referência editáveis pelo usuário

Este diretório guarda **a fonte da verdade organizacional/processual** da Dalmóbile/Inspirium,
transcrita em **markdown** para o Claude conseguir **ler e diferenciar** (o original costuma ser `.docx`,
que não é diffável).

## Contrato de uso

- **Dono:** o **usuário** edita estes arquivos. São a referência conceitual do negócio (fluxo, papéis,
  documentos, políticas), não código.
- **O Claude NÃO edita** arquivos deste diretório sem pedido explícito. Ele **lê** e usa como fonte para
  reconciliar.
- **Ao editar, o usuário avisa o Claude.** O Claude então **reconcilia** a mudança contra:
  - o **código** (ex.: `mod_ciclo.py`/`ciclo_etapas`, endpoints),
  - os **docs gerados** (`docs/ARQUITETURA-MODULOS.md`, `docs/processos/*`, `DEV_LOG.md`, specs),
  - o **grafo MCP** (requisitos/decisões),
  e **reporta conflitos** (divergência de numeração, etapa sem implementação, papel/documento novo, etc.).
- **Não é lido automaticamente pelo servidor** — é documentação. Vai para o git (referência versionada).

## Convenções

- Nome: `NN-nome-kebab.md` (ordem estável).
- Cabeçalho de cada doc: **fonte** (caminho do `.docx`/original), **data da última edição**, e um resumo de 1 linha.
- Transcrição fiel: se divergir do original, o **original manda** — avise para eu corrigir a transcrição.

## Índice

| Arquivo | O quê | Fonte original |
|---|---|---|
| `01-fluxo-de-processos.md` | Fluxo comercial completo — 38 etapas / 6 fases, papéis e documentos (D1–D45) | `E:\2026\dalmobile inspirium\ESTRUTURA ORGANIZACIONAL\1.FLUXO_DE_PROCESSOS.docx` |

> Reconciliação **38 etapas ↔ ciclo implementado (18 principais + 6 sub)**: ver
> `docs/processos/FLUXO_38_ETAPAS.md` (doc **gerado** pelo Claude, derivado desta referência + do código).
