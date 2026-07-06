import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_arquivo_salvo_e_livre(tmp_path):
    from contrato_editar import arquivo_salvo_e_livre
    f = tmp_path / "contrato_1.docx"; f.write_text("x")
    m0 = f.stat().st_mtime
    assert arquivo_salvo_e_livre(str(f), m0) is False           # não mudou
    os.utime(str(f), (m0 + 100, m0 + 100))                      # mtime futuro
    assert arquivo_salvo_e_livre(str(f), m0) is True            # mudou, sem lock
    lock = tmp_path / "~$contrato_1.docx"; lock.write_text("")
    assert arquivo_salvo_e_livre(str(f), m0) is False           # lock Word presente
    lock.unlink()
    lock2 = tmp_path / ".~lock.contrato_1.docx#"; lock2.write_text("")
    assert arquivo_salvo_e_livre(str(f), m0) is False           # lock LibreOffice presente


def test_watcher_chama_on_save_em_cada_salvamento(tmp_path):
    from contrato_editar import watcher_regerar_pdf
    f = tmp_path / "contrato_1.docx"; f.write_text("x")
    base = f.stat().st_mtime
    chamadas = []
    # tempo simulado
    estado = {"t": 0.0}
    def fake_sleep(s): estado["t"] += s
    def fake_agora(): return estado["t"]
    # 1º on_save: simula que o usuário salvou (mtime futuro) ANTES do primeiro poll
    os.utime(str(f), (base + 10, base + 10))
    def on_save(p):
        chamadas.append(estado["t"])
        # após salvar, NÃO há novo salvamento -> não deve chamar de novo
    # mtime_ref = baseline ANTES do salvamento (como o endpoint faz ao iniciar o watcher)
    watcher_regerar_pdf(str(f), on_save, poll=1, timeout=5, sleep=fake_sleep,
                        agora=fake_agora, debounce=0, mtime_ref=base)
    assert len(chamadas) == 1   # exatamente um salvamento detectado


def test_watcher_respeita_timeout_sem_salvar(tmp_path):
    from contrato_editar import watcher_regerar_pdf
    f = tmp_path / "contrato_1.docx"; f.write_text("x")
    estado = {"t": 0.0}
    chamadas = []
    watcher_regerar_pdf(str(f), lambda p: chamadas.append(p), poll=1, timeout=3,
                        sleep=lambda s: estado.__setitem__("t", estado["t"]+s),
                        agora=lambda: estado["t"], debounce=0)
    assert chamadas == []   # nada salvo -> nada regerado


def test_validar_gerencial(tmp_path, monkeypatch):
    # usa um banco em memória/sqlite temporário com um gerente e um consultor
    from database import Base, Usuario
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng); db = S()
    g = Usuario(nome="Ger", login="ger", nivel="gerente"); g.set_senha("123"); g.ativo = 1
    c = Usuario(nome="Con", login="con", nivel="consultor"); c.set_senha("123"); c.ativo = 1
    db.add_all([g, c]); db.commit()
    from contrato_editar import validar_gerencial
    a, err = validar_gerencial(db, "ger", "123"); assert a is not None and err is None
    a, err = validar_gerencial(db, "ger", "errada"); assert a is None and "Credenciais" in err
    a, err = validar_gerencial(db, "con", "123"); assert a is None and "Gerente" in err
