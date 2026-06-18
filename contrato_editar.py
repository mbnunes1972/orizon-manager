import os, time


def _lock_paths(docx_path):
    d = os.path.dirname(docx_path); b = os.path.basename(docx_path)
    return [os.path.join(d, "~$" + b), os.path.join(d, ".~lock." + b + "#")]


def arquivo_salvo_e_livre(docx_path, mtime_ref):
    """True se o docx foi modificado após mtime_ref E nenhum lock (~$ / .~lock) presente."""
    if not os.path.exists(docx_path):
        return False
    if os.path.getmtime(docx_path) <= mtime_ref:
        return False
    return not any(os.path.exists(l) for l in _lock_paths(docx_path))


def watcher_regerar_pdf(docx_path, on_save, *, poll=2.0, timeout=1800,
                        sleep=time.sleep, agora=time.monotonic, debounce=3.0,
                        mtime_ref=None):
    """Faz polling até timeout. A cada salvamento detectado (mtime cresceu + sem lock),
    aguarda o debounce, reconfirma e chama on_save(docx_path). Atualiza a referência de
    mtime para detectar salvamentos subsequentes. on_save não deve levantar (capturado).

    A referência inicial de mtime (mtime_ref) deve corresponder ao momento em que a
    edição começou — antes de o usuário salvar. Se não informada, captura o mtime atual
    (uso real: o watcher inicia logo após abrir o app, antes do primeiro salvamento)."""
    inicio = agora()
    if mtime_ref is not None:
        ref = mtime_ref
    else:
        ref = os.path.getmtime(docx_path) if os.path.exists(docx_path) else 0.0
    while agora() - inicio < timeout:
        sleep(poll)
        if arquivo_salvo_e_livre(docx_path, ref):
            sleep(debounce)
            if arquivo_salvo_e_livre(docx_path, ref):
                try:
                    on_save(docx_path)
                except Exception:
                    pass
                ref = os.path.getmtime(docx_path)


def abrir_no_app(docx_path, app):
    """Abre o .docx no app escolhido (máquina local Windows). Isolado p/ permitir mock."""
    import subprocess
    if app == "libreoffice":
        from mod_contrato import _libreoffice_cmd
        subprocess.Popen([_libreoffice_cmd(), docx_path])
    else:  # 'word' ou padrão
        os.startfile(docx_path)  # Windows: abre no app padrão do .docx


def validar_gerencial(db, login, senha):
    """Retorna (autorizador, None) se ok; (None, msg_erro) caso contrário. Reusa a regra gerencial."""
    from database import Usuario
    a = db.query(Usuario).filter_by(login=login, ativo=1).first()
    if not a or not a.check_senha(senha):
        return None, "Credenciais inválidas"
    if a.nivel not in ("gerente", "diretor", "admin"):
        return None, "Necessário nível Gerente ou Diretor"
    return a, None
