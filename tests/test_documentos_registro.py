import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Banco isolado por teste."""
    import database
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "t.db"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///" + str(tmp_path / "t.db"))
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    s = S()
    yield s
    s.close()


def test_criar_versao_comeca_em_1(db):
    m = mod_documentos.criar_versao(db, loja_id=1, tipo="contrato",
                                    corpo_md="# CLÁUSULA\n1.1. Ok.\n",
                                    origem_nome="c.docx", usuario_id=1)
    assert m.versao == 1


def test_versoes_sao_sequenciais_por_loja_e_tipo(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    outra_loja = mod_documentos.criar_versao(db, 2, "contrato", "c", "c.docx", 1)
    outro_tipo = mod_documentos.criar_versao(db, 1, "proposta", "d", "p.docx", 1)
    assert m2.versao == 2
    assert outra_loja.versao == 1, "loja 2 tem sequência própria"
    assert outro_tipo.versao == 1, "proposta tem sequência própria"


def test_ativar_desliga_a_anterior(db):
    m1 = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    m2 = mod_documentos.criar_versao(db, 1, "contrato", "b", "c.docx", 1)
    mod_documentos.ativar(db, m1.id)
    mod_documentos.ativar(db, m2.id)
    db.refresh(m1)
    assert m1.ativo == 0
    assert m2.ativo == 1


def test_ativar_nao_mexe_em_outro_tipo(db):
    c = mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    p = mod_documentos.criar_versao(db, 1, "proposta", "b", "p.docx", 1)
    mod_documentos.ativar(db, c.id)
    mod_documentos.ativar(db, p.id)
    db.refresh(c)
    assert c.ativo == 1, "ativar proposta não pode desligar o contrato"


def test_resolver_modelo_devolve_a_versao_ativa(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "CORPO DA LOJA", "c.docx", 1)
    mod_documentos.ativar(db, m.id)
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == "CORPO DA LOJA"


def test_resolver_modelo_cai_no_global_quando_a_loja_nao_tem(db):
    """Loja sem modelo próprio continua igual a hoje — migração zero."""
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 99, "contrato") == mod_contrato._carregar_md()


def test_resolver_modelo_de_proposta_sem_modelo_e_vazio(db):
    """Proposta é capa-só hoje: sem modelo, corpo vazio."""
    assert mod_documentos.resolver_modelo(db, 99, "proposta") == ""


def test_resolver_modelo_ignora_versao_inativa(db):
    mod_documentos.criar_versao(db, 1, "contrato", "RASCUNHO", "c.docx", 1)
    import mod_contrato
    assert mod_documentos.resolver_modelo(db, 1, "contrato") == mod_contrato._carregar_md()


def test_listar_e_escopado_por_loja(db):
    mod_documentos.criar_versao(db, 1, "contrato", "a", "c.docx", 1)
    mod_documentos.criar_versao(db, 2, "contrato", "b", "c.docx", 1)
    assert len(mod_documentos.listar(db, 1)) == 1, "loja A não pode ver modelo da loja B"


def test_tipo_invalido_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "custom", "a", "x.docx", 1)


def test_corpo_vazio_e_recusado(db):
    with pytest.raises(ValueError):
        mod_documentos.criar_versao(db, 1, "contrato", "   ", "c.docx", 1)


def test_original_do_staging_e_promovido_para_a_versao(db, tmp_path, monkeypatch):
    """Auditoria: o arquivo subido tem que sobreviver ao lado da versão."""
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs"))
    caminho, sha = mod_documentos.guardar_staging(1, "contrato", "meu.docx", b"conteudo-x")
    assert os.path.exists(caminho)
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "meu.docx", 1,
                                    staging_path=caminho, origem_sha256=sha)
    assert m.origem_sha256 == sha
    assert m.origem_path and os.path.exists(m.origem_path)
    assert "v1" in m.origem_path
    assert not os.path.exists(caminho), "o staging foi movido, não copiado"
    assert open(m.origem_path, "rb").read() == b"conteudo-x"


def test_criar_versao_sem_staging_nao_explode(db):
    m = mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "c.docx", 1)
    assert m.origem_path is None


# ── Corrida em _proxima_versao: linha primeiro, arquivo depois ────────────────
# Dois uploads simultâneos leem o mesmo MAX(versao); a UniqueConstraint pega o
# perdedor. Estes testes forçam a colisão de forma DETERMINÍSTICA (monkeypatch em
# _proxima_versao) em vez de usar threads: com threads, quem colide e quantas
# vezes varia a cada execução — o teste ficaria flaky e não provaria nada de
# forma confiável na suíte.


def _colide_n_vezes(monkeypatch, n):
    """Faz _proxima_versao devolver um número já usado nas n primeiras chamadas."""
    real = mod_documentos._proxima_versao
    estado = {"i": 0}

    def fake(db_, loja_id, tipo):
        estado["i"] += 1
        if estado["i"] <= n:
            return 1                      # versão 1 já existe → UniqueConstraint dispara
        return real(db_, loja_id, tipo)

    monkeypatch.setattr(mod_documentos, "_proxima_versao", fake)


def test_corrida_de_versao_nao_deixa_arquivo_orfao(db, tmp_path, monkeypatch):
    """O perdedor da corrida não pode largar arquivo em v<N>/ sem linha apontando.

    É o teste que prova a ordem: linha primeiro, arquivo depois.
    """
    docs = str(tmp_path / "docs")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs)
    mod_documentos.criar_versao(db, 1, "contrato", "primeira", "a.docx", 1)   # ocupa a v1
    caminho, sha = mod_documentos.guardar_staging(1, "contrato", "meu.docx", b"bytes-x")

    _colide_n_vezes(monkeypatch, 1)
    m = mod_documentos.criar_versao(db, 1, "contrato", "segunda", "meu.docx", 1,
                                    staging_path=caminho, origem_sha256=sha)

    assert m.versao == 2, "o retry tem que pegar o próximo número livre"
    v1_dir = os.path.join(docs, "1", "contrato", "v1")
    assert not os.path.exists(os.path.join(v1_dir, "meu.docx")), \
        "arquivo órfão em v1/: o move aconteceu antes de a linha existir"
    assert m.origem_path and os.path.exists(m.origem_path)
    assert "v2" in m.origem_path


def test_corrida_de_versao_e_retentada_sem_vazar_integrityerror(db, monkeypatch):
    mod_documentos.criar_versao(db, 1, "contrato", "primeira", "a.docx", 1)
    _colide_n_vezes(monkeypatch, 3)
    m = mod_documentos.criar_versao(db, 1, "contrato", "segunda", "b.docx", 1)
    assert m.versao == 2, "IntegrityError da corrida não pode vazar para o chamador"


def test_retry_esgotado_vira_erro_claro(db, monkeypatch):
    mod_documentos.criar_versao(db, 1, "contrato", "primeira", "a.docx", 1)
    _colide_n_vezes(monkeypatch, 99)                 # nunca sai da colisão
    with pytest.raises(RuntimeError, match="versão"):
        mod_documentos.criar_versao(db, 1, "contrato", "segunda", "b.docx", 1)


def test_falha_ao_promover_original_preserva_versao_e_staging(db, tmp_path, monkeypatch):
    """Move quebrou DEPOIS do commit: a versão vale, o original fica no staging."""
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", str(tmp_path / "docs"))
    caminho, sha = mod_documentos.guardar_staging(1, "contrato", "meu.docx", b"bytes-y")

    def explode(*a, **k):
        raise OSError("disco cheio")
    monkeypatch.setattr(mod_documentos, "_promover_original", explode)

    with pytest.raises(OSError):
        mod_documentos.criar_versao(db, 1, "contrato", "# C\n1.1. Ok.\n", "meu.docx", 1,
                                    staging_path=caminho, origem_sha256=sha)

    modelos = mod_documentos.listar(db, 1)
    assert len(modelos) == 1, "a versão foi commitada antes do move — tem que existir"
    assert modelos[0].origem_path is None
    assert os.path.exists(caminho), "o original tem que continuar no staging (recuperável)"
