"""
storage.py — Camada de armazenamento, configuração, perfis e sessão.
Para migrar para nuvem: substituir apenas as funções storage_*() e session_*().
"""
import os, json, re, hashlib, unicodedata
import sys
from auth import perfis   # fonte única dos perfis de acesso (Regras_Funcoes_Perfis_Atribuicoes §8)

# == CONSTANTES E CAMINHOS ==
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJETOS_DIR      = os.path.join(_BASE_DIR, "PROJETOS")
PERFIS_FILE       = os.path.join(_BASE_DIR, "perfis_config.json")

# == STORAGE LAYER ==
# Camada de abstração de armazenamento.
# Backend local: lê/escreve em disco.
# Para nuvem: substituir apenas estas funções por S3/GCS/Supabase Storage.
# NUNCA usar open(), os.makedirs() ou shutil fora desta seção.

STORAGE_BACKEND = "local"

def storage_ler_json(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)

def storage_salvar_json(caminho: str, dados: dict) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def storage_salvar_texto(caminho: str, conteudo: str) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

def storage_salvar_binario(caminho: str, conteudo: bytes) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)

def storage_ler_texto(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as f:
        return f.read()

def storage_ler_binario(caminho: str) -> bytes:
    with open(caminho, "rb") as f:
        return f.read()

def storage_deletar(caminho: str) -> None:
    if os.path.exists(caminho):
        os.remove(caminho)

def storage_listar(pasta: str) -> list:
    """Retorna lista de nomes de itens (pastas ou arquivos) diretos em pasta."""
    if not os.path.isdir(pasta):
        return []
    return sorted(os.listdir(pasta))

def storage_existe(caminho: str) -> bool:
    return os.path.exists(caminho)

# == PERFIS DE ACESSO E LIMITES ==
# Controle de permissões por perfil de usuário.
# Local: arquivo perfis_config.json em disco.
# Para nuvem: substituir por banco de dados com autenticação JWT/OAuth.
# Os perfis definem limites máximos de desconto por nível hierárquico.
# Estrutura preparada para multi-usuário em nuvem — cada sessão terá
# um perfil associado via token de autenticação.

PERFIS_FILE = os.path.join(_BASE_DIR, "perfis_config.json")

PERFIS_PADRAO = {
    "perfil_ativo": "consultor",   # perfil em uso (local: único usuário)
    "perfis": {
        "consultor": {
            "nome":              "Consultor de Vendas",
            "desconto_max_pct":  10.0,   # desconto máximo permitido (global + individual)
            "pode_editar_total": True,   # pode editar o Total do Contrato diretamente
            "pode_ver_margens":  False,  # vê o painel de apoio (margens internas)
            "cor":               "#19c9a0"
        },
        "gerente": {
            "nome":              "Gerente de Vendas",
            "desconto_max_pct":  20.0,
            "pode_editar_total": True,
            "pode_ver_margens":  True,
            "cor":               "#f0a500",
            "senha_gerente":     "1234"
        },
        "diretoria": {
            "nome":              "Diretoria",
            "desconto_max_pct":  100.0,  # sem limite prático
            "pode_editar_total": True,
            "pode_ver_margens":  True,
            "cor":               "#e8611a"
        }
    }
}

# Chaves legadas da UI (perfil "ativo" simulado) → slug real de perfis.py (fonte única). O legado
# perfis_config.json deixa de ser fonte de verdade: as DEFINIÇÕES vêm de perfis.py; só o `perfil_ativo`
# (estado de UI) é lido do arquivo, se existir. Sem senha embutida.
_PERFIL_LEGADO_SLUG = {"consultor": "consultor", "gerente": "gerente_vendas", "diretoria": "diretor"}
_PERFIL_LEGADO_COR  = {"consultor": "#19c9a0", "gerente": "#f0a500", "diretoria": "#e8611a"}


def _perfis_derivado() -> dict:
    out = {}
    for leg, slug in _PERFIL_LEGADO_SLUG.items():
        out[leg] = {
            "nome":              perfis.rotulo(slug),
            "desconto_max_pct":  perfis.desconto_max(slug),
            "pode_editar_total": True,
            "pode_ver_margens":  perfis.pode(slug, "ver_parametros"),
            "cor":               _PERFIL_LEGADO_COR[leg],
        }
    return out


def perfis_carregar() -> dict:
    ativo = "consultor"
    if storage_existe(PERFIS_FILE):
        try:
            ativo = (storage_ler_json(PERFIS_FILE) or {}).get("perfil_ativo", "consultor")
        except Exception:
            pass
    if ativo not in _PERFIL_LEGADO_SLUG:
        ativo = "consultor"
    return {"perfil_ativo": ativo, "perfis": _perfis_derivado()}

def perfis_salvar(dados: dict) -> None:
    storage_salvar_json(PERFIS_FILE, dados)

def perfil_ativo_get() -> dict:
    dados = perfis_carregar()
    nome_perfil = dados.get("perfil_ativo", "consultor")
    return dados["perfis"].get(nome_perfil, PERFIS_PADRAO["perfis"]["consultor"])

def perfil_desconto_max() -> float:
    return float(perfil_ativo_get().get("desconto_max_pct", 10.0))

# == SESSION LAYER ==
# Estado da sessão do usuário.
# Local: dicionário Python em memória (um usuário por vez).
# Para nuvem: substituir por Redis ou cookies assinados.
# NUNCA acessar _session diretamente fora desta seção.

_session: dict = {
    "dados_carregados": None,
    "xmls_carregados": None,
    "nome_cliente": None,
    "idx_negociacao": None,
    "projeto_ativo": None,
}

def session_get(chave: str, padrao=None):
    return _session.get(chave, padrao)

def session_set(chave: str, valor) -> None:
    _session[chave] = valor

# -- Helpers basicos ------------------------------------------------------------
def _sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def normalizar(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").upper().strip()

def so_digitos(s):
    return re.sub(r"[^0-9]", "", s or "")

