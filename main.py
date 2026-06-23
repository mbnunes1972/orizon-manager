"""
main.py — Servidor HTTP, rotas e inicialização.
Ponto de entrada da aplicação: python main.py
"""
import os, io, json, time, re, threading, webbrowser, hashlib
import sys
import email
from email import policy as _email_policy
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
from database import (init_db, get_session, Cliente, Parceiro, Orcamento,
                       PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status,
                       CicloEtapa, Contrato, ContratoAssinatura, Usuario, Briefing,
                       LogAcaoGerencial, Medicao, Rede, Loja, ParceiroLoja)
from urllib.parse import urlparse, unquote

from storage import (
    _BASE_DIR, PROJETOS_DIR, CPF_CORINGA,
    PERFIS_PADRAO, PERFIS_FILE,
    storage_ler_json, storage_salvar_json, storage_salvar_binario,
    storage_salvar_texto, storage_ler_texto, storage_ler_binario,
    storage_existe, storage_listar, storage_deletar,
    config_carregar, config_salvar,
    perfis_carregar, perfis_salvar,
    session_get, session_set, session_reset_exportacao,
    _set_credenciais, _sleep_interval, _omie_key,
    get_omie_key, get_omie_secret,
    so_digitos, normalizar
)
from mod_omie import (
    omie_post, buscar_cliente_cpf, pesquisar_clientes, criar_cliente,
    garantir_conta_corrente, buscar_categoria, criar_pedido,
    garantir_grupos_omie, exportar_ambientes, gerar_excel,
    _listar_projetos, _buscar_projetos, _carregar_projeto, _salvar_projeto,
    _criar_projeto, _adicionar_ambientes, _arquivar_xmls,
    _buscar_projetos_omie, _projeto_path, carregar_xmls,
    bloquear_projeto, verificar_integridade_xmls
)
from mod_margens import calcular_margens, _normalizar_faixas
from mod_fin import calcular_aymore, calcular_cartao, calcular_venda_programada, calcular_total_flex
from mod_contrato import (calcular_hash_assinatura, montar_variaveis_contrato,
                          gerar_pdf_contrato, LibreOfficeIndisponivel,
                          construir_contexto, _formatar_valor)
import mod_ciclo
import mod_medicao
import perfis
import mod_usuarios
import mod_tenancy
from mod_qualidade_xml import avaliar_qualidade_xml

def _enriquecer_projetos_com_status(projetos):
    """Adiciona status e ultimo_orcamento_valor a cada projeto da lista."""
    if not projetos:
        return
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        metas = db.query(Projeto).filter(Projeto.nome_safe.in_(nomes)).all()
        meta_map = {m.nome_safe: m for m in metas}

        # Pega o orçamento mais recente por projeto (desempate por id desc)
        orc_map = {}
        for nome in nomes:
            orc = (db.query(Orcamento)
                     .filter(Orcamento.projeto_id == nome)
                     .order_by(Orcamento.updated_at.desc(), Orcamento.id.desc())
                     .first())
            if orc:
                orc_map[nome] = orc.valor_total

        for p in projetos:
            ns = p.get('nome_safe')
            if not ns:
                continue
            meta = meta_map.get(ns)
            p['status']                 = meta.status     if meta else None
            p['status_at']              = meta.status_at.isoformat() if meta and meta.status_at else None
            p['perdido_em']             = meta.perdido_em.isoformat() if meta and meta.perdido_em else None
            p['ultimo_orcamento_valor'] = orc_map.get(ns)
    finally:
        db.close()

def _enriquecer_projetos_com_pool(projetos):
    """Para projetos EP-07, sobrescreve n_ambientes/n_selecionados com contagens do pool."""
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        contagens = {}
        for pa in db.query(PoolAmbiente).filter(PoolAmbiente.projeto_id.in_(nomes)).all():
            contagens[pa.projeto_id] = contagens.get(pa.projeto_id, 0) + 1
        for p in projetos:
            n = contagens.get(p.get('nome_safe'), 0)
            if n > 0:
                p['n_ambientes']    = n
                p['n_selecionados'] = n
    finally:
        db.close()

# HTML servido como arquivo estático
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

def _serve_html():
    path = os.path.join(_STATIC_DIR, "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()

def _tentar_sync_omie(c, db):
    """Tenta criar cliente no Omie. Atualiza omie_sync_* em c e faz db.commit()."""
    from datetime import datetime as _dt
    if not c.cpf:
        c.omie_sync_status = "pendente"
        c.omie_sync_erro   = "CPF não informado — necessário para registro no Omie"
        c.omie_sync_at     = _dt.utcnow()
        db.commit()
        return

    cfg = config_carregar()
    key    = cfg.get("app_key", "")
    secret = cfg.get("app_secret", "")
    if not key or not secret:
        c.omie_sync_status = "pendente"
        c.omie_sync_erro   = "Credenciais Omie não configuradas"
        c.omie_sync_at     = _dt.utcnow()
        db.commit()
        return

    _set_credenciais(key, secret)
    try:
        codigo = criar_cliente(c.nome, c.cpf, lambda msg, tipo="info": None)
        c.omie_codigo      = str(codigo)
        c.omie_sync_status = "ok"
        c.omie_sync_erro   = None
        c.omie_sync_at     = _dt.utcnow()
    except Exception as e:
        c.omie_sync_status = "erro"
        c.omie_sync_erro   = str(e)
        c.omie_sync_at     = _dt.utcnow()
    db.commit()


# == HANDLERS HTTP ==
# == HANDLERS HTTP ==
# -- Multipart -----------------------------------------------------------------
def _parse_multipart(body, ct):
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = [], {}
    for part in msg.walk():
        cd = part.get("Content-Disposition", "")
        if not cd:
            continue
        params = {}
        for seg in cd.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        nome    = params.get("name", "")
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if nome == "xmls" and params.get("filename"):
            arquivos.append((params["filename"], payload.decode("utf-8", "ignore")))
        elif nome and not params.get("filename"):
            campos[nome] = payload.decode("utf-8", "ignore").strip()
    return arquivos, campos

def _parse_multipart_arquivos(body, ct):
    """Multipart binário: retorna (arquivos, campos) onde arquivos[name] = (filename, bytes)
    e campos[name] = texto. (O _parse_multipart é específico p/ XML texto.)"""
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = {}, {}
    for part in msg.walk():
        cd = part.get("Content-Disposition", "")
        if not cd:
            continue
        params = {}
        for seg in cd.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        nome = params.get("name", "")
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if params.get("filename"):
            arquivos[nome] = (params["filename"], payload)
        elif nome:
            campos[nome] = payload.decode("utf-8", "ignore").strip()
    return arquivos, campos


def _usuario_com_capacidade(db, login, senha, capacidade):
    """Usuario ativo com senha correta e a capacidade dada (perfis), ou None."""
    u = db.query(Usuario).filter_by(login=(login or "").strip()).first()
    if not u or not u.ativo or not u.check_senha(senha or ""):
        return None
    if not perfis.pode(u.nivel, capacidade):
        return None
    return u


def _set_etapa_status(db, nome_safe, codigo, status, responsavel_id):
    etapa = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
    if not etapa:
        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=codigo)
        db.add(etapa)
    if etapa.status == "pendente" and status != "pendente":
        etapa.iniciado_em = datetime.utcnow()
    etapa.status = status
    if status in mod_ciclo.STATUS_CONCLUSIVOS:
        etapa.concluido_em = datetime.utcnow()
        etapa.responsavel_id = responsavel_id
    return etapa


def _get_or_create_medicao(db, nome_safe):
    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
    if not md:
        md = Medicao(projeto_nome=nome_safe)
        db.add(md)
    return md


def _aprovador_financeiro(db, login, senha):
    """Retorna o Usuario apto a aprovar financeiro (ativo, senha correta e perfil com
    'aprovar_financeiro') ou None."""
    u = db.query(Usuario).filter_by(login=(login or "").strip()).first()
    if not u or not u.ativo or not u.check_senha(senha or ""):
        return None
    if not perfis.pode(u.nivel, "aprovar_financeiro"):
        return None
    return u

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if handle_auth_get(self, path): return
        if path == "/":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            body = _serve_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        elif path == "/config":
            self.send_json(config_carregar())

        elif path == "/perfis":
            self.send_json(perfis_carregar())

        elif path == "/perfis/ativo":
            dados = perfis_carregar()
            nome  = dados.get("perfil_ativo", "consultor")
            cfg   = dados["perfis"].get(nome, PERFIS_PADRAO["perfis"]["consultor"])
            self.send_json({"perfil_ativo": nome, "config": cfg})

        elif path == "/logs":
            logs_limpos = [l for l in (session_get("logs") or []) if l["msg"] != "__DONE__"]
            done = not session_get("running") and len(logs_limpos) > 0
            self.send_json({
                "logs":         logs_limpos,
                "done":         done,
                "confirm":      session_get("confirm_pending"),
                "pedidos":      session_get("pedidos", []),
                "pode_aprovar": session_get("idx_negociacao") is not None,
                "nome_cliente": session_get("nome_cliente", ""),
            })

        elif path == "/pagamentos":
            # Lista modalidades do mod_fin.py para popular o dropdown
            try:
                import mod_fin as _mf
                mods = _mf.listar_modalidades()
            except Exception:
                mods = [{"codigo": "a_vista", "descricao": "A Vista"}]
            self.send_json({"ok": True, "modalidades": mods})

        elif path == "/projetos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                projetos = _listar_projetos()
                projetos = _filtrar_projetos_por_loja(projetos, db, loja_id)
                _enriquecer_projetos_com_pool(projetos)
                _enriquecer_projetos_com_status(projetos)
                self.send_json({"ok": True, "projetos": projetos})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path == "/projetos/buscar":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from urllib.parse import parse_qs
                q = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip()
                locais = _buscar_projetos(q)
                locais = _filtrar_projetos_por_loja(locais, db, loja_id)
                for p in locais: p['origem'] = 'local'
                _enriquecer_projetos_com_pool(locais)
                _enriquecer_projetos_com_status(locais)
                omie_res = _buscar_projetos_omie(q)
                nomes_locais = {p['nome_projeto'].lower() for p in locais}
                omie_unicos = [p for p in omie_res if p['nome_projeto'].lower() not in nomes_locais]
                self.send_json({'ok': True, 'projetos': locais + omie_unicos})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        m = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                if c is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(cliente_id=c.id)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        m = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m:
            nome_safe = unquote(m.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        elif path == "/api/clientes":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                query = db.query(Cliente).filter(Cliente.loja_id == loja_id).order_by(Cliente.nome)
                if q:
                    query = query.filter(
                        (Cliente.nome.ilike(f"%{q}%")) |
                        (Cliente.cpf.ilike(f"%{q}%"))
                    )
                all_clientes = query.all()
                # IDs com briefing completo
                cli_ids = [c.id for c in all_clientes]
                briefings_ok = set()
                if cli_ids:
                    bfs = db.query(Briefing.cliente_id).filter(
                        Briefing.cliente_id.in_(cli_ids),
                        Briefing.tipo_imovel != None,
                        Briefing.tipo_imovel != "",
                        Briefing.budget_declarado != None,
                        Briefing.budget_declarado != 0,
                        Briefing.categoria_proposta != None,
                        Briefing.categoria_proposta != "",
                        Briefing.data_entrega_desejada != None,
                        Briefing.data_entrega_desejada != "",
                        Briefing.flexibilidade_prazo != None,
                        Briefing.flexibilidade_prazo != "",
                    ).all()
                    briefings_ok = {b[0] for b in bfs}
                clientes = []
                for c in all_clientes:
                    cd = _cliente_dict(c)
                    cd["tem_briefing"] = c.id in briefings_ok
                    clientes.append(cd)
                self.send_json({"ok": True, "clientes": clientes})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "clientes": []})
            finally:
                db.close()

        elif path == "/api/parceiros":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                query = db.query(Parceiro).order_by(Parceiro.nome)
                if q:
                    query = query.filter(
                        (Parceiro.nome.ilike(f"%{q}%")) |
                        (Parceiro.cpf_cnpj.ilike(f"%{q}%"))
                    )
                todos = query.all()
                todos = [p for p in todos if _parceiro_visivel_loja(db, p, loja_id)]
                parceiros = [_parceiro_dict(p, db) for p in todos]
                self.send_json({"ok": True, "parceiros": parceiros})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "parceiros": []})
            finally:
                db.close()

        elif path == "/api/admin/omie-sync":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"})
                return
            db2 = get_session()
            try:
                from sqlalchemy import or_
                clientes = db2.query(Cliente).filter(
                    or_(
                        Cliente.omie_sync_status.in_(["erro", "pendente"]),
                        Cliente.omie_sync_status.is_(None)
                    )
                ).order_by(Cliente.omie_sync_at.desc()).all()
                self.send_json({"ok": True, "clientes": [_cliente_dict(c) for c in clientes]})
            finally:
                db2.close()

        elif path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                us = db.query(Usuario).order_by(Usuario.nome).all()
                # pré-carrega rede_id de cada loja referenciada (evita N+1 no loop de escopo)
                loja_ids = {u.loja_id for u in us if u.loja_id is not None}
                rede_de_loja = {l.id: l.rede_id for l in
                                db.query(Loja).filter(Loja.id.in_(loja_ids)).all()} if loja_ids else {}
                visiveis = []
                for u in us:
                    if mod_tenancy._eh_super_admin(ator):
                        ok = True
                    elif mod_tenancy._eh_admin_rede(ator):
                        ok = (u.rede_id == ator["rede_id"]) or (
                            u.loja_id is not None and mod_tenancy.pode_ver_loja(
                                ator, {"id": u.loja_id, "rede_id": rede_de_loja.get(u.loja_id)}))
                    else:
                        ok = (u.loja_id is not None and u.loja_id == ator.get("loja_id"))
                    if ok:
                        visiveis.append(u)
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                escopo = (qs.get("escopo") or [""])[0].strip()
                if escopo == "loja":
                    fl = (qs.get("loja_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.loja_id is not None and str(u.loja_id) == fl]
                elif escopo == "rede":
                    fr = (qs.get("rede_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.nivel == "admin_rede" and str(u.rede_id) == fr]
                elif escopo == "plataforma":
                    visiveis = [u for u in visiveis
                                if u.nivel == "super_admin"
                                and u.loja_id is None and u.rede_id is None]
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "whatsapp": u.whatsapp or "", "email": u.email or "", "cpf": u.cpf or "",
                     "loja_id": u.loja_id, "rede_id": u.rede_id,
                     "ativo": bool(u.ativo)} for u in visiveis]})
            finally:
                db.close()

        elif path == "/api/admin/usuarios/perfis-permitidos":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(self.path).query)
            escopo = (qs.get("escopo") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                slugs = mod_tenancy.perfis_atribuiveis(ator, escopo)
                self.send_json({"ok": True, "perfis": [
                    {"slug": s, "rotulo": perfis.rotulo(s)} for s in slugs]})
            finally:
                db.close()

        elif path == "/api/admin/redes":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                redes = db.query(Rede).order_by(Rede.nome).all()
                self.send_json({"ok": True, "redes": [_rede_dict(r) for r in redes]})
            finally:
                db.close()
        elif path == "/api/admin/lojas":
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_lojas")
                                   or perfis.pode(usuario.get("nivel"), "editar_dados_loja")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs
            rede_q = (parse_qs(urlparse(self.path).query).get("rede_id") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                q = db.query(Loja)
                if rede_q == "avulsas":
                    q = q.filter(Loja.rede_id.is_(None))
                elif rede_q:
                    if not rede_q.isdigit():
                        self.send_json({"ok": False, "erro": "rede_id inválido"}, code=400)
                        return
                    q = q.filter(Loja.rede_id == int(rede_q))
                lojas = [l for l in q.order_by(Loja.nome).all()
                         if mod_tenancy.pode_ver_loja(
                             ator, {"id": l.id, "rede_id": l.rede_id})]
                self.send_json({"ok": True, "lojas": [_loja_dict(l) for l in lojas]})
            finally:
                db.close()

        elif path.endswith(".html") and path != "/":
            nome    = path.lstrip("/")
            caminho = os.path.join(_BASE_DIR, nome)
            if os.path.exists(caminho):
                with open(caminho, encoding="utf-8") as f:
                    body = f.read().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
            return

        else:
            import re as _re
            # GET /pagamentos/<codigo>/faixas
            m_pf = _re.match(r"^/pagamentos/([^/]+)/faixas$", path)
            if m_pf:
                codigo = m_pf.group(1)
                try:
                    import mod_fin as _mf
                    tab    = _mf._carregar(codigo)
                    tipo   = tab.get("tipo", "")
                    faixas = _normalizar_faixas(tab)
                    desconto_avista = float(tab.get("desconto_pct", 0)) if tipo == "avista" else 0.0
                except Exception as e:
                    print("[FAIXAS] Erro ao carregar %s: %s" % (codigo, e))
                    faixas = [{"parcelas": 1, "custo_pct": 0.0, "label": "A Vista"}]
                    tipo = "avista"; desconto_avista = 0.0
                self.send_json({"ok": True, "faixas": faixas, "tipo": tipo,
                                "desconto_avista": desconto_avista})
                return

            # ── GET /projetos/<nome>/pool?orcamento_id=<id> ───────────────────────────
            m = _re.match(r"^/projetos/([^/]+)/pool$", path)
            if m:
                from urllib.parse import parse_qs
                nome_safe    = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                qs           = parse_qs(urlparse(self.path).query)
                orcamento_id = qs.get("orcamento_id", [None])[0]
                orcamento_id = int(orcamento_id) if orcamento_id else None
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    ambientes = (db.query(PoolAmbiente)
                                   .filter_by(projeto_id=nome_safe)
                                   .order_by(PoolAmbiente.nome, PoolAmbiente.versao)
                                   .all())
                    incluidos = set()
                    if orcamento_id:
                        links = (db.query(OrcamentoAmbiente)
                                   .filter_by(orcamento_id=orcamento_id)
                                   .all())
                        incluidos = {lk.pool_ambiente_id for lk in links}
                    pool = []
                    for pa in ambientes:
                        d = _pool_ambiente_dict(pa)
                        d["incluido"] = pa.id in incluidos
                        pool.append(d)
                    self.send_json({"ok": True, "pool": pool})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── GET /orcamentos/<oid>/ambientes — listar ambientes do orçamento ─────
            m = _re.match(r"^/orcamentos/(\d+)/ambientes$", path)
            if m:
                oid = int(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    links = (db.query(OrcamentoAmbiente)
                               .filter_by(orcamento_id=oid)
                               .order_by(OrcamentoAmbiente.ordem)
                               .all())
                    ambientes = []
                    for lk in links:
                        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                        if pa:
                            d = _pool_ambiente_dict(pa)
                            d["ordem"] = lk.ordem
                            d["desconto_individual_pct"] = lk.desconto_individual_pct or 0.0
                            ambientes.append(d)
                    margens = json.loads(orc.margens) if (orc and orc.margens) else {}
                    negociacao = json.loads(orc.negociacao_json) if (orc and orc.negociacao_json) else None
                    parametros = {}
                    if orc:
                        from mod_orcamento_params import PARAMETROS_DEFAULT
                        _p = db.get(Projeto, orc.projeto_id)
                        parametros = json.loads(_p.parametros_json) if (_p and _p.parametros_json) else dict(PARAMETROS_DEFAULT)
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "margens": margens, "negociacao": negociacao,
                                    "parametros": parametros, "ambientes": ambientes})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m:
                nome_safe = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                print("[ORC] GET orcamentos para projeto_id=%r" % nome_safe)
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    orcs = (db.query(Orcamento)
                              .filter_by(projeto_id=nome_safe)
                              .order_by(Orcamento.ordem)
                              .all())
                    print("[ORC] encontrados %d orcamento(s)" % len(orcs))
                    self.send_json({"ok": True, "orcamentos": [_orcamento_dict(o) for o in orcs]})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)$", path)
            if m:
                nome_safe = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                    return
                finally:
                    db.close()
                proj = _carregar_projeto(nome_safe)
                if proj:
                    session_set("projeto_ativo", nome_safe)
                    self.send_json({"ok": True, "projeto": proj})
                else:
                    self.send_json({"ok": False, "erro": "Projeto nao encontrado"}, code=404)
                return

            m = _re.match(r"^/api/clientes/(\d+)$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                    if c:
                        self.send_json({"ok": True, "cliente": _cliente_dict(c)})
                    else:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/parceiros/(\d+)$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    p = db.get(Parceiro, int(m.group(1)))
                    if p is None or not _parceiro_visivel_loja(db, p, loja_id):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/clientes/(\d+)/projetos$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                    if not c:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    nome_lower = c.nome.lower()
                    projetos = [
                        p for p in _listar_projetos()
                        if p.get("cliente_id") == c.id
                        or p.get("cliente_nome", "").lower() == nome_lower
                    ]
                    _enriquecer_projetos_com_pool(projetos)
                    self.send_json({"ok": True, "projetos": projetos, "cliente": _cliente_dict(c)})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/parametros$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                from mod_orcamento_params import PARAMETROS_DEFAULT
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    p = _projeto_da_loja(db, nome_safe, loja_id)
                    if p is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    par = json.loads(p.parametros_json) if p.parametros_json else dict(PARAMETROS_DEFAULT)
                    self.send_json({"ok": True, "parametros": par})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/ciclo$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    etapas = db.query(CicloEtapa)\
                               .filter_by(projeto_nome=nome_safe)\
                               .all()
                    codigos_existentes = {e.etapa_codigo for e in etapas}
                    # Auto-completar etapas 1-5 para projetos que já têm negociação
                    ETAPAS_PRE = ["1","2","3","4","5"]
                    if not any(c in codigos_existentes for c in ETAPAS_PRE):
                        p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                        eh_legado = (p_meta is None) or (p_meta.cliente_id is None)
                        tem_negociacao = db.query(Orcamento).filter(
                            Orcamento.projeto_id == nome_safe,
                        ).count() > 0
                        if tem_negociacao and eh_legado:
                            agora = datetime.utcnow()
                            for cod in ETAPAS_PRE:
                                nova = CicloEtapa(
                                    projeto_nome=nome_safe,
                                    etapa_codigo=cod,
                                    status="concluido",
                                    concluido_em=agora,
                                )
                                db.add(nova)
                                etapas.append(nova)
                            db.commit()
                    etapas_sorted = sorted(etapas, key=lambda e: mod_ciclo.chave_ordenacao(e.etapa_codigo))
                    resultado = [{
                        "etapa_codigo":  e.etapa_codigo,
                        "status":        e.status,
                        "responsavel_id": e.responsavel_id,
                        "iniciado_em":   e.iniciado_em.isoformat() if e.iniciado_em else None,
                        "concluido_em":  e.concluido_em.isoformat() if e.concluido_em else None,
                        "observacoes":   e.observacoes or "",
                    } for e in etapas_sorted]
                    assinado = _contrato_assinado(nome_safe, db)
                    total_assinado = _contrato_totalmente_assinado(nome_safe, db)
                    self.send_json({"ok": True, "ciclo": resultado,
                                    "contrato_assinado": assinado,
                                    "contrato_totalmente_assinado": total_assinado})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/arquivo/(solicitacao|planta|doc_cliente)$', path)
            if m:
                nome_safe = unquote(m.group(1)); tipo = m.group(2)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    fname = md and getattr(md, tipo + "_arquivo", None)
                finally:
                    db.close()
                if not fname:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                caminho = os.path.join(_projeto_path(nome_safe), "medicao", fname)
                try:
                    data = storage_ler_binario(caminho)
                except Exception:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", len(data))
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % fname)
                self.end_headers()
                self.wfile.write(data)
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    if not md:
                        self.send_json({"ok": True, "medicao": None})
                        return
                    self.send_json({"ok": True, "medicao": {
                        "parecer": md.parecer,
                        "ambientes_aprovados": md.ambientes_aprovados or "",
                        "tem_solicitacao": bool(md.solicitacao_arquivo),
                        "tem_planta": bool(md.planta_arquivo),
                        "tem_doc_cliente": bool(md.doc_cliente_arquivo),
                    }})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    if not contrato or not contrato.pdf_path or not os.path.exists(contrato.pdf_path):
                        self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404)
                        return
                    eh_pdf  = contrato.pdf_path.endswith(".pdf")
                    ct      = "application/pdf" if eh_pdf else \
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ext     = "pdf" if eh_pdf else "docx"
                    with open(contrato.pdf_path, 'rb') as f:
                        arq_data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", len(arq_data))
                    disp = "inline" if eh_pdf else "attachment"
                    self.send_header("Content-Disposition",
                                     f'{disp}; filename="contrato_{nome_safe}.{ext}"')
                    self.end_headers()
                    self.wfile.write(arq_data)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    if not contrato:
                        self.send_json({"ok": True, "contrato": None})
                        return
                    assinaturas = [{
                        "parte":       a.parte,
                        "nome":        a.nome,
                        "assinado_em": a.assinado_em.isoformat(),
                    } for a in contrato.assinaturas]
                    tem_arquivo = bool(contrato.pdf_path and os.path.exists(contrato.pdf_path))
                    arquivo_tipo = ""
                    if tem_arquivo:
                        arquivo_tipo = "pdf" if contrato.pdf_path.endswith(".pdf") else "docx"
                    self.send_json({"ok": True, "contrato": {
                        "id":                   contrato.id,
                        "status":               contrato.status,
                        "endereco_instalacao":  contrato.endereco_instalacao or "",
                        "adendo":               contrato.adendo or "",
                        "gerado_em":            contrato.gerado_em.isoformat() if contrato.gerado_em else None,
                        "tem_pdf":              tem_arquivo,
                        "arquivo_tipo":         arquivo_tipo,
                        "assinaturas":          assinaturas,
                    }})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b'{}'

        if handle_auth_post(self, path, body): return
        if path == "/config":
            config_salvar(json.loads(body))
            self.send_json({"ok": True})

        elif path == "/perfis":
            dados = json.loads(body)
            perfis_salvar(dados)
            self.send_json({"ok": True})

        elif path == "/perfis/ativo":
            dados = json.loads(body)
            cfg   = perfis_carregar()
            cfg["perfil_ativo"] = dados.get("perfil", "consultor")
            perfis_salvar(cfg)
            self.send_json({"ok": True, "perfil_ativo": cfg["perfil_ativo"]})

        elif path == "/cancel":
            session_set("cancel", True)
            session_set("running", False)
            self.send_json({"ok": True})

        elif path == "/confirm":
            data = json.loads(body)
            session_set("confirm_result", data["resp"])
            session_set("confirm_pending", None)
            if session_get("confirm_event"):
                session_get("confirm_event").set()
            self.send_json({"ok": True})

        elif path == "/carregar":
            ct               = self.headers.get("Content-Type", "")
            arquivos, campos = _parse_multipart(body, ct)
            if not arquivos:
                self.send_json({"ok": False, "erro": "Nenhum arquivo XML recebido"})
                return
            try:
                dados        = carregar_xmls(arquivos)
                nome_cliente = dados.get("cliente", {}).get("nome", "").strip()
                cpf          = dados.get("cliente", {}).get("cpf", "").strip()
                if not nome_cliente:
                    nome_cliente = re.sub(r"\.xml$", "", arquivos[0][0], flags=re.IGNORECASE).strip() or "PROJETO"
                session_set("dados_carregados", dados)
                session_set("xmls_carregados", arquivos)
                session_set("nome_cliente", nome_cliente)
                session_set("excel_atual_caminho", None)
                session_set("idx_negociacao", None)
                dados["nome_cliente"] = nome_cliente
                self.send_json(dados)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})

        elif path == "/exportar":
            req        = json.loads(body)
            cfg_salvo  = config_carregar()
            app_key    = req.get("app_key", "")    or cfg_salvo.get("app_key", "")
            app_secret = req.get("app_secret", "") or cfg_salvo.get("app_secret", "")
            intervalo  = float(req.get("intervalo") or cfg_salvo.get("intervalo", 0.5))
            ambientes_sel = req.get("ambientes", "todos")
            dados = session_get("dados_carregados")
            nome_safe_para_bloquear = None
            if not dados:
                # Fluxo v3: usa o projeto ativo carregado na sessão
                nome_safe = session_get("projeto_ativo")
                if not nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum projeto ativo. Abra um projeto primeiro."})
                    return
                proj = _carregar_projeto(nome_safe)
                if not proj:
                    self.send_json({"ok": False, "erro": "Projeto nao encontrado."})
                    return
                if proj.get("bloqueado"):
                    self.send_json({"ok": False, "erro": "Projeto ja aprovado e bloqueado em %s." % proj.get("bloqueado_em", "—")})
                    return
                ambs_selecionados = [a for a in proj.get("ambientes", []) if a.get("selecionado", True)]
                if not ambs_selecionados:
                    self.send_json({"ok": False, "erro": "Nenhum ambiente selecionado no projeto."})
                    return
                dados = {
                    "ok":            True,
                    "cliente":       proj.get("cliente", {}),
                    "ambientes":     ambs_selecionados,
                    "grupos_ref":    {},
                }
                ambientes_sel = "todos"
                nome_safe_para_bloquear = nome_safe
            session_set("running", True)
            session_set("logs", [])
            session_set("pedidos", [])
            session_set("confirm_pending", None)
            session_set("confirm_result", None)
            session_set("confirm_event", None)
            session_set("cancel", False)
            session_set("idx_negociacao", None)

            def log_cb(msg, tipo="info"):
                if msg == "__DONE__":
                    session_set("running", False)
                    return
                session_get("logs").append({"msg": msg, "tipo": tipo})

            def confirm_cb(tipo, dados_modal):
                evt = threading.Event()
                session_set("confirm_event", evt)
                if tipo == "sem_cpf":
                    session_set("confirm_pending", {
                        "tipo": "sem_cpf", "titulo": "CPF nao informado",
                        "corpo": "O cliente <span class='highlight'>%s</span> nao tem CPF no XML." % dados_modal["nome"],
                    })
                elif tipo == "nome_diferente":
                    session_set("confirm_pending", {
                        "tipo": "nome_diferente", "titulo": "Nome diferente",
                        "corpo": "XML: <span class='highlight'>%s</span><br>Omie: <span class='highlight'>%s</span>" % (dados_modal["nome_xml"], dados_modal["nome_omie"]),
                    })
                elif tipo == "sem_uf":
                    session_set("confirm_pending", {
                        "tipo": "sem_uf", "titulo": "Estado (UF) nao informado",
                        "corpo": "O cliente <span class='highlight'>%s</span> nao tem UF no cadastro." % dados_modal["nome"],
                    })
                evt.wait(timeout=120)
                return session_get("confirm_result", "")

            def run():
                try:
                    pedidos = exportar_ambientes(
                        app_key, app_secret, dados, ambientes_sel,
                        log_cb, confirm_cb, intervalo=intervalo,
                    )
                    session_set("pedidos", pedidos)
                    if nome_safe_para_bloquear:
                        try:
                            bloquear_projeto(nome_safe_para_bloquear)
                            log_cb("Projeto bloqueado — XMLs travados com hash SHA-256.", "ok")
                            session_set("projeto_bloqueado", True)
                            try:
                                upsert_projeto_status(nome_safe_para_bloquear, "convertido")
                            except Exception as e_st:
                                log_cb(f"Aviso: status convertido não pôde ser salvo: {e_st}", "warn")
                        except Exception as e_lock:
                            log_cb("Aviso: nao foi possivel bloquear o projeto: %s" % e_lock, "warn")
                except Exception as e:
                    log_cb("ERRO: %s" % e, "err")
                finally:
                    session_set("running", False)

            _set_credenciais(app_key, app_secret)
            threading.Thread(target=run, daemon=True).start()
            self.send_json({"ok": True})

        elif path == "/buscar_cliente":
            req   = json.loads(body)
            query = req.get("query", "").strip()
            if not query:
                self.send_json({"ok": False, "erro": "Informe nome ou CPF para buscar"})
                return
            cfg = config_carregar()
            _set_credenciais(cfg.get("app_key", ""), cfg.get("app_secret", ""))
            try:
                clientes  = pesquisar_clientes(query)
                resultado = [
                    {"codigo": c.get("codigo_cliente_omie"), "nome": c.get("razao_social", ""),
                     "cpf": c.get("cnpj_cpf", ""), "cidade": c.get("cidade", ""),
                     "uf": c.get("estado", ""), "email": c.get("email", "")}
                    for c in clientes
                ]
                self.send_json({"ok": True, "clientes": resultado})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})

        elif path == "/vincular_cliente":
            req = json.loads(body)
            session_set("cliente_selecionado", {
                "codigo": req["codigo"], "nome": req["nome"],
                "cpf": req.get("cpf", ""), "uf": req.get("uf", ""),
            })
            self.send_json({"ok": True})

        elif path == "/limpar_cliente":
            session_set("cliente_selecionado", None)
            self.send_json({"ok": True})

        # == ROTAS DE NEGOCIAÇÃO ==
        # Stateless: recebem todos os dados no payload e devolvem resultado.
        # Pronto para nuvem sem alteração de assinatura.
        elif path == "/calcular_aymore":
            req = json.loads(body)
            from mod_fin import calcular_aymore as _calc_ay
            resultado = _calc_ay(
                valor_avista  = float(req.get("valor_avista",  req.get("valor_venda", 0))),
                entrada       = float(req.get("entrada", 0)),
                n_parcelas    = int(req.get("n_parcelas", 8)),
                carencia_dias = int(req.get("carencia_dias", 30)),
                data_contrato = req.get("data_contrato", ""),
            )
            self.send_json(resultado)

        elif path == "/calcular_cartao":
            req = json.loads(body)
            from mod_fin import calcular_cartao as _calc_cc
            resultado = _calc_cc(
                valor_avista  = float(req.get("valor_avista",  req.get("valor_venda", 0))),
                entrada       = float(req.get("entrada", 0)),
                n_parcelas    = int(req.get("n_parcelas", 1)),
                data_contrato = req.get("data_contrato", ""),
                codigo        = req.get("codigo", "cartao_credito"),
            )
            self.send_json(resultado)

        elif path == "/calcular_venda_programada":
            req = json.loads(body)
            from mod_fin import calcular_venda_programada as _calc_vp
            resultado = _calc_vp(
                valor_avista   = float(req.get("valor_avista", 0)),
                entrada        = float(req.get("entrada", 0)),
                n_parcelas     = int(req.get("n_parcelas", 1)),
                data_contrato  = req.get("data_contrato", ""),
                datas_parcelas = req.get("datas_parcelas", []),
            )
            self.send_json(resultado)

        elif path == "/api/gerente/verificar":
            req   = json.loads(body)
            senha = req.get("senha", "")
            _perfis_cfg = perfis_carregar()
            senha_correta = _perfis_cfg.get("perfis", {}).get("gerente", {}).get("senha_gerente", "1234")
            if senha == senha_correta:
                taxa_cfg = None
                try:
                    import mod_fin.total_flex as _tf_mod
                    c = _tf_mod._cfg()
                    taxa_cfg = round(c["taxa_juros_mensal"] * 100, 4)
                except Exception:
                    pass
                self.send_json({"ok": True, "taxa_juros_pct": taxa_cfg})
            else:
                self.send_json({"ok": False, "erro": "Senha incorreta"})

        elif path == "/api/fin/total_flex/inicializar":
            req = json.loads(body)
            from mod_fin import tf_inicializar as _tf_ini
            taxa_ov = req.get("taxa_override")
            resultado = _tf_ini(
                valor_financiado = float(req.get("valor_financiado", 0)),
                n_parcelas       = int(req.get("n_parcelas", 2)),
                prazo_meses      = int(req.get("prazo_meses", 6)),
                data_contrato    = req.get("data_contrato", ""),
                taxa_override    = float(taxa_ov) / 100 if taxa_ov is not None else None,
            )
            self.send_json(resultado)

        elif path == "/api/fin/total_flex/recalcular":
            req = json.loads(body)
            from mod_fin import tf_recalcular as _tf_rec
            taxa_ov = req.get("taxa_override")
            resultado = _tf_rec(
                valor_financiado   = float(req.get("valor_financiado", 0)),
                data_contrato      = req.get("data_contrato", ""),
                prazo_maximo_meses = int(req.get("prazo_maximo_meses", 12)),
                parcelas_input     = req.get("parcelas", []),
                taxa_override      = float(taxa_ov) / 100 if taxa_ov is not None else None,
            )
            self.send_json(resultado)

        elif path == "/calcular_total_flex":
            req = json.loads(body)
            from mod_fin import calcular_total_flex as _calc_tf
            resultado = _calc_tf(
                valor_avista     = float(req.get("valor_avista", 0)),
                entrada          = float(req.get("entrada", 0)),
                n_parcelas       = int(req.get("n_parcelas", 2)),
                taxa_mensal_pct  = 0,
                data_contrato    = req.get("data_contrato", ""),
                valores_parcelas = req.get("valores_parcelas", []),
                datas_parcelas   = req.get("datas_parcelas",   []),
            )
            self.send_json(resultado)

        elif path == "/calcular_margens":
            req = json.loads(body)
            fin_pct = req.get("custo_financeiro_pct", 0)
            bruto   = req.get("valor_bruto", 0)
            desc    = req.get("desconto_pct", 0)
            print("[CALC] bruto=%.2f desc=%.2f fin_pct=%.4f" % (bruto, desc, fin_pct))
            resultado = calcular_margens(
                valor_bruto              = bruto,
                desconto_pct             = desc,
                fora_da_sede             = req.get("fora_da_sede", False),
                custo_viagem             = req.get("custo_viagem", 0),
                comissao_arq_pct         = req.get("comissao_arq_pct", 0),
                comissao_arq_ativa       = req.get("comissao_arq_ativa", False),
                fidelidade_pct           = req.get("fidelidade_pct", 0),
                fidelidade_ativa         = req.get("fidelidade_ativa", False),
                custo_financeiro_pct     = fin_pct,
                brinde                   = req.get("brinde", 0),
                brinde_ativo             = req.get("brinde_ativo", False),
            )
            print("[CALC] saldo_desc=%.2f saldo_fin=%.2f acrescimo=%.2f final=%.2f" % (
                resultado["saldo_apos_desconto"], resultado["saldo_apos_financeiro"],
                resultado["acrescimo_financeiro"], resultado["valor_final"]))
            self.send_json({"ok": True, "resultado": resultado})

        elif path == "/projetos/novo":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req = json.loads(body)
            nome_proj   = req.get('nome_projeto', '').strip()
            cliente_id  = req.get('cliente_id')
            parceiro_id = req.get('parceiro_id')
            if not nome_proj:
                self.send_json({'ok': False, 'erro': 'nome_projeto é obrigatório'})
                return
            if not cliente_id:
                self.send_json({'ok': False, 'erro': 'cliente_id é obrigatório — selecione ou cadastre um cliente'})
                return
            # Carrega dados do cliente do banco para garantir consistência + escopo de loja
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(cliente_id), loja_id)
                if not c:
                    self.send_json({'ok': False, 'erro': 'Cliente não encontrado'}, code=404)
                    return
                cli_nome     = c.nome
                cli_cpf      = c.cpf      or ''
                cli_email    = c.email    or ''
                cli_telefone = c.telefone or ''
            except Exception as e:
                self.send_json({'ok': False, 'erro': str(e)})
                return
            finally:
                db.close()
            try:
                proj = _criar_projeto(nome_proj, cli_nome, cli_cpf, cli_email, cli_telefone,
                                      cliente_id=int(cliente_id),
                                      parceiro_id=int(parceiro_id) if parceiro_id else None)

                # Cria Orçamento 1 automaticamente
                _usuario = get_usuario_sessao(self)
                _db_orc = get_session()
                try:
                    _pid = proj['nome_safe']
                    print("[ORC] criando Orcamento 1 para projeto_id=%r" % _pid)
                    _orc = Orcamento(
                        projeto_id=_pid,
                        nome="Orçamento 1",
                        ordem=1,
                        loja_id=loja_id,
                        created_by=_usuario['id'] if _usuario else None,
                    )
                    _db_orc.add(_orc)
                    _db_orc.commit()
                    _db_orc.refresh(_orc)
                    proj['orcamento_ativo_id'] = _orc.id
                    print("[ORC] commit OK — id=%d projeto_id=%r" % (_orc.id, _orc.projeto_id))
                    _salvar_projeto(proj)
                except Exception as _e_orc:
                    print("[ORC] ERRO ao criar orcamento: %s" % _e_orc)
                    raise
                finally:
                    _db_orc.close()

                # Link cliente_id no projetos_meta e marcar etapas 1 e 2 (Briefing fica pendente)
                _db_ciclo = get_session()
                try:
                    p_meta = _db_ciclo.get(Projeto, proj['nome_safe'])
                    if not p_meta:
                        p_meta = Projeto(nome_safe=proj['nome_safe'])
                        _db_ciclo.add(p_meta)
                    p_meta.cliente_id = int(cliente_id)
                    p_meta.loja_id = loja_id
                    _db_ciclo.commit()

                    agora = datetime.utcnow()
                    uid_ciclo = _usuario['id'] if _usuario else None
                    # Marca apenas Captação(1) e Criação do projeto(2). Briefing(3) fica
                    # pendente — vira a "etapa corrente" e deve ser preenchido (sub-projeto D).
                    for cod in ["1", "2"]:
                        etapa = _db_ciclo.query(CicloEtapa).filter_by(
                            projeto_nome=proj['nome_safe'], etapa_codigo=cod
                        ).first()
                        if not etapa:
                            etapa = CicloEtapa(
                                projeto_nome=proj['nome_safe'],
                                etapa_codigo=cod,
                                status="concluido",
                                concluido_em=agora,
                                responsavel_id=uid_ciclo,
                            )
                            _db_ciclo.add(etapa)
                        elif etapa.status != "concluido":
                            etapa.status         = "concluido"
                            etapa.concluido_em   = agora
                            etapa.responsavel_id = uid_ciclo
                    _db_ciclo.commit()
                except Exception as _e_ciclo:
                    print("[CICLO] Erro ao marcar etapas iniciais: %s" % _e_ciclo)
                finally:
                    _db_ciclo.close()

                # Garante credenciais carregadas (main() já carrega, mas reforça)
                if not get_omie_key():
                    cfg = config_carregar()
                    if cfg.get('app_key'):
                        _set_credenciais(cfg['app_key'], cfg['app_secret'])

                # Diagnóstico sempre visível no terminal
                print("[OMIE] Tentando criar projeto: %r" % nome_proj)
                print("[OMIE] app_key: %s" % (get_omie_key()[:8] + "..." if get_omie_key() else "VAZIA"))

                # Tenta criar no Omie
                if get_omie_key():
                    try:
                        cod_int = (re.sub(r"[^A-Z0-9]", "", normalizar(nome_proj))[:9]
                                   + datetime.now().strftime("%y%m%d%H%M"))[:20]
                        r_omie = omie_post(
                            "/geral/projetos/", "IncluirProjeto",
                            {"nome": nome_proj, "inativo": "N", "codInt": cod_int},
                            lambda *_: None, no_rotate=True, timeout=10
                        )
                        print("[OMIE] Resposta bruta: %s" % r_omie)
                        cod = (r_omie.get("codigo") or r_omie.get("nCodProj")
                               or r_omie.get("nCod") or r_omie.get("codigo_projeto"))
                        proj["codigo_projeto_omie"] = cod
                        print("[OMIE] Projeto criado — codigo_projeto_omie: %s" % cod)
                    except Exception as e_omie:
                        proj["codigo_projeto_omie"] = None
                        proj["codigo_projeto_omie_erro"] = str(e_omie)
                        print("[OMIE] ERRO ao criar projeto: %s" % e_omie)
                    _salvar_projeto(proj)
                else:
                    print("[OMIE] Credenciais não configuradas — projeto criado apenas localmente.")

                session_set('projeto_ativo', proj['nome_safe'])
                self.send_json({'ok': True, 'projeto': proj})
            except Exception as e:
                self.send_json({'ok': False, 'erro': str(e)})

        elif path == "/api/clientes":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req  = json.loads(body) if body else {}
            faltando = validar_cadastro_minimo(req)
            if faltando:
                self.send_json({"ok": False,
                                "erro": "Campos obrigatórios faltando: " + ", ".join(faltando)})
                return
            nome = (req.get("nome") or "").strip()
            cpf = (req.get("cpf") or "").strip() or None
            db  = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if cpf:
                    existente = db.query(Cliente).filter_by(cpf=cpf).first()
                    if existente:
                        if getattr(existente, "loja_id", None) == loja_id:
                            self.send_json({"ok": False, "erro": "CPF já cadastrado",
                                            "cliente": _cliente_dict(existente)}, code=409)
                        else:
                            self.send_json({"ok": False,
                                            "erro": "CPF já cadastrado em outra unidade."}, code=409)
                        return
                c = Cliente(
                    nome       =nome, cpf=cpf,
                    loja_id    =loja_id,
                    email      =(req.get("email")       or "").strip() or None,
                    telefone   =(req.get("telefone")    or "").strip() or None,
                    whatsapp   =(req.get("whatsapp")    or "").strip() or None,
                    cep        =(req.get("cep")         or "").strip() or None,
                    logradouro =(req.get("logradouro")  or "").strip() or None,
                    numero     =(req.get("numero")      or "").strip() or None,
                    complemento=(req.get("complemento") or "").strip() or None,
                    bairro     =(req.get("bairro")      or "").strip() or None,
                    cidade     =(req.get("cidade")      or "").strip() or None,
                    estado     =(req.get("estado")      or "").strip() or None,
                    observacoes=(req.get("observacoes") or "").strip() or None,
                )
                db.add(c)
                db.commit()
                db.refresh(c)
                cliente_id = c.id
                self.send_json({"ok": True, "cliente": _cliente_dict(c)})

                def _sync_bg():
                    db2 = get_session()
                    try:
                        c2 = db2.get(Cliente, cliente_id)
                        if c2:
                            _tentar_sync_omie(c2, db2)
                    except Exception:
                        pass
                    finally:
                        db2.close()

                threading.Thread(target=_sync_bg, daemon=True).start()
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        m_bp = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m_bp:
            nome_safe = unquote(m_bp.group(1))
            usuario   = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req       = json.loads(body) if body else {}
            db        = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                cliente_id = p_meta.cliente_id if p_meta else None
                if not cliente_id:
                    self.send_json({"ok": False, "erro": "Projeto sem cliente vinculado"})
                    return
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        projeto_nome=nome_safe,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                if bd["completo"]:
                    etapa3 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="3"
                    ).first()
                    if not etapa3:
                        etapa3 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="3")
                        db.add(etapa3)
                    etapa3.status        = "concluido"
                    etapa3.concluido_em  = datetime.utcnow()
                    etapa3.responsavel_id = usuario["id"] if usuario else None
                    db.commit()
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        m_bf = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m_bf:
            cliente_id = int(m_bf.group(1))
            usuario    = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req        = json.loads(body) if body else {}
            db         = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, cliente_id, loja_id)
                if c is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(cliente_id=cliente_id)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        elif re.match(r"^/api/clientes/(\d+)/editar$", path):
            m_cli = re.match(r"^/api/clientes/(\d+)/editar$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(m_cli.group(1)), loja_id)
                if not c:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                campos = ["nome","cpf","email","telefone","whatsapp",
                          "cep","logradouro","numero","complemento",
                          "bairro","cidade","estado","observacoes",
                          "inst_logradouro","inst_numero","inst_complemento",
                          "inst_bairro","inst_cidade","inst_cep","inst_uf"]
                for f in campos:
                    if f in req:
                        setattr(c, f, (req[f] or "").strip() or None)
                if "inst_mesmo_residencial" in req:
                    c.inst_mesmo_residencial = 1 if req["inst_mesmo_residencial"] else 0
                if "nome" in req and not c.nome:
                    self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                    return
                from datetime import datetime as _dt
                c.atualizado_em = _dt.utcnow()
                db.commit()
                db.refresh(c)
                self.send_json({"ok": True, "cliente": _cliente_dict(c)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif path == "/api/parceiros":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req  = json.loads(body) if body else {}
            nome = (req.get("nome") or "").strip()
            if not nome:
                self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                return
            db = get_session()
            try:
                p = Parceiro(
                    nome                =nome,
                    cpf_cnpj            =(req.get("cpf_cnpj")            or "").strip() or None,
                    tipo                =(req.get("tipo")                 or "").strip() or None,
                    email               =(req.get("email")                or "").strip() or None,
                    telefone            =(req.get("telefone")             or "").strip() or None,
                    whatsapp            =(req.get("whatsapp")             or "").strip() or None,
                    comissao_padrao_pct =float(req.get("comissao_padrao_pct") or 0),
                    observacoes         =(req.get("observacoes")          or "").strip() or None,
                )
                db.add(p)
                db.flush()        # atribui p.id sem efetivar — transação única e atômica
                if "abrangencia" in req:
                    ator = _ator_dict(db, usuario) if usuario else {"nivel": "", "loja_id": None, "rede_id": None}
                    erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                    if erros:
                        db.rollback()    # desfaz tudo, inclusive o INSERT do parceiro
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif re.match(r"^/api/parceiros/(\d+)/editar$", path):
            m_par = re.match(r"^/api/parceiros/(\d+)/editar$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                p = db.get(Parceiro, int(m_par.group(1)))
                if p is None or not _parceiro_visivel_loja(db, p, loja_id):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                for f in ["nome","cpf_cnpj","tipo","email","telefone","whatsapp","observacoes"]:
                    if f in req:
                        setattr(p, f, (req[f] or "").strip() or None)
                if "comissao_padrao_pct" in req:
                    p.comissao_padrao_pct = float(req["comissao_padrao_pct"] or 0)
                if "nome" in req and not p.nome:
                    self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                    return
                if "abrangencia" in req:
                    erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                    if erros:
                        db.rollback()
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif re.match(r"^/api/projetos/([^/]+)/parametros$", path):
            m_par = re.match(r"^/api/projetos/([^/]+)/parametros$", path)
            nome_safe = unquote(m_par.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from mod_orcamento_params import merge_parametros
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                p = _projeto_da_loja(db, nome_safe, loja_id)
                if p is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _projeto_esta_bloqueado(nome_safe):
                    self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."}, code=400)
                    return
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
                    return
                atual = json.loads(p.parametros_json) if p.parametros_json else {}
                novos = merge_parametros(atual, req)
                p.parametros_json = json.dumps(novos, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True, "parametros": novos})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif re.match(r"^/api/orcamentos/(\d+)/margens$", path):
            # ── POST /api/orcamentos/<id>/margens — salva margens do orçamento ─────
            m_orc_mar = re.match(r"^/api/orcamentos/(\d+)/margens$", path)
            oid = int(m_orc_mar.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _projeto_esta_bloqueado(orc.projeto_id):
                    self.send_json({"ok": False,
                                    "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                   code=400)
                    return
                if orc and _contrato_assinado(orc.projeto_id, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                atual = json.loads(orc.margens) if orc.margens else {}
                if "desconto_pct" in req:
                    atual["desconto_pct"] = float(req["desconto_pct"])
                    orc.desconto_pct = float(req["desconto_pct"])
                orc.margens = json.dumps(atual, ensure_ascii=False)
                db.commit()
                # ── modo sombra: materializa derivados do motor de negociação ──
                # Bloco NÃO-INTRUSIVO: falhas aqui não afetam o save legado nem a resposta.
                # Roda ANTES do send_json — quando a resposta chega ao cliente os derivados
                # já estão gravados (o servidor é single-thread).
                try:
                    import mod_negociacao
                    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
                    params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
                    ambs = []
                    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
                        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                        if pa:
                            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                                         "desc_amb_pct": lk.desconto_individual_pct or 0.0})
                    # Padrão de duas chamadas: 1ª para obter VAVO, 2ª com cust_fin real
                    d0 = mod_negociacao.calcular_orcamento(ambs, params, orc.desconto_pct or 0.0)
                    cust_fin = max(0.0, (orc.valor_total or 0.0) - d0["VAVO"])
                    d = mod_negociacao.calcular_orcamento(ambs, params, orc.desconto_pct or 0.0, cust_fin=cust_fin)
                    orc.vbvo, orc.cfo, orc.vbno, orc.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
                    orc.cust_ad, orc.val_liq = d["Cust_Ad"], d["Val_Liq"]
                    orc.com_arq_orc, orc.pro_fid_orc = d["Com_Arq"], d["Pro_Fid"]
                    orc.desc_tot_pct, orc.markup = d["Desc_Tot"], d["Markup"]
                    orc.prov_imp = d["Prov_Imp"]
                    orc.cust_fin = d["Cust_Fin"]
                    orc.val_cont = d["Val_Cont"]
                    db.commit()
                except Exception as _e:
                    db.rollback()
                    print("[SOMBRA] falha ao materializar derivados:", _e)
                self.send_json({"ok": True, "margens": atual,
                                "sombra": _sombra_dict(orc)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif re.match(r"^/api/orcamentos/(\d+)/negociacao-preview$", path):
            # ── POST /api/orcamentos/<id>/negociacao-preview — preview do motor (sem gravar) ──
            m_prev = re.match(r"^/api/orcamentos/(\d+)/negociacao-preview$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                orc = _obj_da_loja(db, Orcamento, int(m_prev.group(1)), loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                pag = req.get("pagamento") or {}
                d = _negociacao_breakdown(
                    orc, db,
                    params=req.get("params"), desc_orc=req.get("desc_orc"),
                    descontos_amb=req.get("descontos_amb"),
                    total_cliente=pag.get("total_cliente"))
                self.send_json({"ok": True, "sombra": d, "ambientes": d.get("ambientes", [])})
            finally:
                db.close()
            return

        else:
            import re as _re

            # ── POST /projetos/<nome_safe>/orcamentos — criar novo orçamento ─────────
            m_novo_orc = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m_novo_orc:
                nome_safe = m_novo_orc.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    db.close()
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    db.close()
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _contrato_assinado(nome_safe, db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                if not _briefing_projeto_completo(unquote(nome_safe), db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de iniciar a negociação."},
                                   code=400)
                    return
                _orc_dict = None
                try:
                    req      = json.loads(body.decode("utf-8", "replace")) if body else {}
                    nome_orc = (req.get("nome") or "").strip()
                    if not nome_orc:
                        self.send_json({"ok": False, "erro": "nome é obrigatório"})
                        return
                    ultimo = (db.query(Orcamento)
                                .filter_by(projeto_id=nome_safe)
                                .order_by(Orcamento.ordem.desc())
                                .first())
                    proxima_ordem = (ultimo.ordem + 1) if ultimo else 1
                    _origem_id = req.get("origem_id")
                    _margens_novo = None
                    if _origem_id:
                        _origem = _obj_da_loja(db, Orcamento, int(_origem_id), loja_id)
                        if _origem and _origem.margens:
                            _margens_novo = _origem.margens
                    orc = Orcamento(
                        projeto_id=nome_safe,
                        nome=      nome_orc,
                        ordem=     proxima_ordem,
                        margens=   _margens_novo,
                        loja_id=   loja_id,
                        created_by=usuario['id'] if usuario else None,
                    )
                    db.add(orc)
                    db.commit()
                    db.refresh(orc)
                    _orc_dict = _orcamento_dict(orc)
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                    return
                finally:
                    db.close()
                # print fora do try para não capturar erros de encoding do terminal
                print("[ORC] novo orcamento: id=%d ordem=%d projeto=%r"
                      % (_orc_dict["id"], _orc_dict["ordem"], nome_safe))
                self.send_json({"ok": True, "orcamento": _orc_dict})
                return

            # ── POST /projetos/<nome_safe>/pool — carregar XML com detecção de duplicata ──
            m_pool = _re.match(r"^/projetos/([^/]+)/pool$", path)
            if m_pool:
                nome_safe = m_pool.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_bf = get_session()
                try:
                    ator = _ator_dict(_db_bf, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_bf, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _bf_ok = _briefing_projeto_completo(unquote(nome_safe), _db_bf)
                finally:
                    _db_bf.close()
                if not _bf_ok:
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de subir XML."},
                                   code=400)
                    return
                ct = self.headers.get("Content-Type", "")
                arquivos, _ = _parse_multipart(body, ct)
                if not arquivos:
                    self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                    return
                arq_nome, arq_conteudo = arquivos[0]
                nome_base = re.sub(r"\.xml$", "", arq_nome, flags=re.IGNORECASE).strip()

                from promob_grupos import ler_xml_str
                try:
                    amb = ler_xml_str(arq_nome, arq_conteudo)
                except Exception as e:
                    self.send_json({"ok": False, "erro": "XML inválido: %s" % e})
                    return

                budget_total = amb.get("total", 0.0)
                order_total  = sum(
                    item.get("order_total", 0.0)
                    for grupo in amb.get("grupos", [])
                    for item in grupo.get("itens", [])
                )
                _qa = avaliar_qualidade_xml(
                    [it for g in amb.get("grupos", []) for it in g.get("itens", [])])

                # Hash do conteúdo (ignora campos derivados do nome do arquivo)
                def _content_hash(a):
                    c = {"total": a.get("total"), "grupos": a.get("grupos", [])}
                    return hashlib.sha256(
                        json.dumps(c, sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                hash_novo = _content_hash(amb)

                db = get_session()
                if _contrato_assinado(nome_safe, db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                try:
                    # Busca por nome
                    por_nome = db.query(PoolAmbiente).filter_by(
                        projeto_id=nome_safe, nome=nome_base
                    ).first()

                    # Busca por conteúdo (compara hash contra todos do projeto)
                    por_hash = None
                    for pa_c in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe).all():
                        try:
                            h = _content_hash(json.loads(pa_c.ambientes_json))
                            if h == hash_novo:
                                por_hash = pa_c
                                break
                        except Exception:
                            continue

                    temp_base = {
                        "nome_safe":    nome_safe,
                        "nome_base":    nome_base,
                        "arq_nome":     arq_nome,
                        "arq_conteudo": arq_conteudo,
                        "amb":          amb,
                        "budget_total": budget_total,
                        "order_total":  order_total,
                        "qa":           _qa,
                    }

                    if por_nome and por_hash and por_nome.id == por_hash.id:
                        # Caso A: nome igual + conteúdo igual → já está no projeto
                        print("[POOL] ja_existe: id=%d nome=%r projeto=%r"
                              % (por_nome.id, por_nome.nome_exibicao, nome_safe))
                        self.send_json({
                            "ok":  True,
                            "acao": "ja_existe",
                            "ambiente_existente": {
                                "id":           por_nome.id,
                                "nome_exibicao": por_nome.nome_exibicao,
                            },
                        })

                    elif por_nome and (not por_hash or por_hash.id != por_nome.id):
                        # Caso B: nome igual + conteúdo diferente → perguntar sobrescrever
                        n_afetados = db.query(OrcamentoAmbiente).filter_by(
                            pool_ambiente_id=por_nome.id
                        ).count()
                        session_set("pool_xml_temp", temp_base)
                        print("[POOL] perguntar_sobrescrever: nome=%r orcamentos=%d"
                              % (nome_base, n_afetados))
                        self.send_json({
                            "ok":  True,
                            "acao": "perguntar_sobrescrever",
                            "ambiente_existente": {
                                "id":                  por_nome.id,
                                "nome_exibicao":       por_nome.nome_exibicao,
                                "orcamentos_afetados": n_afetados,
                            },
                        })

                    elif not por_nome and por_hash:
                        # Caso C: nome diferente + conteúdo igual → perguntar renomear
                        session_set("pool_xml_temp", temp_base)
                        print("[POOL] perguntar_renomear: nome_existente=%r nome_novo=%r"
                              % (por_hash.nome_exibicao, nome_base))
                        self.send_json({
                            "ok":  True,
                            "acao": "perguntar_renomear",
                            "ambiente_existente": {
                                "id":           por_hash.id,
                                "nome_exibicao": por_hash.nome_exibicao,
                            },
                            "nome_novo": nome_base,
                        })

                    else:
                        # Novo ambiente
                        pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                        os.makedirs(pasta_xmls, exist_ok=True)
                        _usuario = get_usuario_sessao(self)
                        pa = PoolAmbiente(
                            projeto_id=    nome_safe,
                            nome=          nome_base,
                            versao=        1,
                            nome_exibicao= nome_base,
                            xml_path=      os.path.join("xmls", arq_nome),
                            ambientes_json=json.dumps(amb),
                            budget_total=              budget_total,
                            order_total=               order_total,
                            qa_selo=                   _qa["qa_selo"],
                            qa_pct_sem_acrescimo=      _qa["qa_pct_sem_acrescimo"],
                            qa_markup_xml=             _qa["qa_markup_xml"],
                            qa_custo_sem_venda=        _qa["qa_custo_sem_venda"],
                            created_by=    _usuario['id'] if _usuario else None,
                        )
                        db.add(pa)
                        db.commit()
                        db.refresh(pa)
                        storage_salvar_texto(os.path.join(pasta_xmls, arq_nome), arq_conteudo)
                        print("[POOL] criado: id=%d nome_exibicao=%r projeto=%r budget=%.2f"
                              % (pa.id, pa.nome_exibicao, pa.projeto_id, pa.budget_total))
                        self.send_json({"ok": True, "acao": "criado",
                                        "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/sobrescrever ────────────────────
            m_sobr = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/sobrescrever$", path)
            if m_sobr:
                nome_safe = m_sobr.group(1)
                pid       = int(m_sobr.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para sobrescrita"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    # Atualiza o registro no pool
                    pa.xml_path               = os.path.join("xmls", temp["arq_nome"])
                    pa.ambientes_json          = json.dumps(temp["amb"])
                    pa.budget_total            = temp["budget_total"]
                    pa.order_total             = temp["order_total"]
                    _qa_s = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa.qa_selo                 = _qa_s["qa_selo"]
                    pa.qa_pct_sem_acrescimo    = _qa_s["qa_pct_sem_acrescimo"]
                    pa.qa_markup_xml           = _qa_s["qa_markup_xml"]
                    pa.qa_custo_sem_venda      = _qa_s["qa_custo_sem_venda"]
                    # Passo 12: recalcula todos os orçamentos que referenciam este ambiente
                    links_afetados = db.query(OrcamentoAmbiente).filter_by(pool_ambiente_id=pid).all()
                    recalculados = []
                    for lk in links_afetados:
                        orc = db.get(Orcamento, lk.orcamento_id)
                        if orc:
                            todos = db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all()
                            orc.valor_total = round(
                                sum(db.get(PoolAmbiente, t.pool_ambiente_id).budget_total
                                    for t in todos), 2
                            )
                            orc.updated_at = datetime.now()
                            recalculados.append(orc.id)
                    db.commit()
                    # Salva o arquivo no disco somente após commit bem-sucedido
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, temp["arq_nome"]), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] sobrescrito: id=%d nome=%r budget=%.2f orcamentos_recalc=%s"
                          % (pa.id, pa.nome_exibicao, pa.budget_total, recalculados))
                    self.send_json({
                        "ok": True, "acao": "sobrescrito",
                        "ambiente": _pool_ambiente_dict(pa),
                        "orcamentos_recalculados": recalculados,
                        "orcamentos_afetados": len(recalculados),
                    })
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/nova-versao ─────────────────────
            m_nova = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/nova-versao$", path)
            if m_nova:
                nome_safe = m_nova.group(1)
                pid       = int(m_nova.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para nova versão"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa_orig = db.get(PoolAmbiente, pid)
                    if not pa_orig or pa_orig.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    nova_versao      = pa_orig.versao + 1
                    # versao=2 → "_v1", versao=3 → "_v2" ...
                    nome_exib_novo   = "%s_v%d" % (pa_orig.nome, nova_versao - 1)
                    arq_nome_novo    = "%s.xml" % nome_exib_novo
                    _usuario = usuario
                    _qa_nv = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa_novo = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          pa_orig.nome,
                        versao=        nova_versao,
                        nome_exibicao= nome_exib_novo,
                        xml_path=      os.path.join("xmls", arq_nome_novo),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=              temp["budget_total"],
                        order_total=               temp["order_total"],
                        qa_selo=                   _qa_nv["qa_selo"],
                        qa_pct_sem_acrescimo=      _qa_nv["qa_pct_sem_acrescimo"],
                        qa_markup_xml=             _qa_nv["qa_markup_xml"],
                        qa_custo_sem_venda=        _qa_nv["qa_custo_sem_venda"],
                        created_by=    _usuario['id'] if _usuario else None,
                    )
                    db.add(pa_novo)
                    db.commit()
                    db.refresh(pa_novo)
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, arq_nome_novo), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] nova versao: id=%d nome_exibicao=%r versao=%d budget=%.2f"
                          % (pa_novo.id, pa_novo.nome_exibicao, pa_novo.versao, pa_novo.budget_total))
                    self.send_json({"ok": True, "acao": "nova_versao",
                                    "ambiente": _pool_ambiente_dict(pa_novo)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/renomear ────────────────────────
            m_ren = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/renomear$", path)
            if m_ren:
                nome_safe = m_ren.group(1)
                pid       = int(m_ren.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                try:
                    req = json.loads(body)
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"})
                    return
                novo_nome = (req.get("novo_nome") or "").strip()
                if not novo_nome:
                    self.send_json({"ok": False, "erro": "Nome não pode ser vazio"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa.nome          = novo_nome
                    pa.nome_exibicao = novo_nome
                    db.commit()
                    db.refresh(pa)
                    session_set("pool_xml_temp", None)
                    print("[POOL] renomeado: id=%d novo_nome=%r" % (pa.id, novo_nome))
                    self.send_json({"ok": True, "acao": "renomeado",
                                    "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/criar_forcado — mesmo conteúdo, nome novo ─
            m_forc = _re.match(r"^/projetos/([^/]+)/pool/criar_forcado$", path)
            if m_forc:
                nome_safe = m_forc.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    _qa_cf = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          temp["nome_base"],
                        versao=        1,
                        nome_exibicao= temp["nome_base"],
                        xml_path=      os.path.join("xmls", temp["arq_nome"]),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=              temp["budget_total"],
                        order_total=               temp["order_total"],
                        qa_selo=                   _qa_cf["qa_selo"],
                        qa_pct_sem_acrescimo=      _qa_cf["qa_pct_sem_acrescimo"],
                        qa_markup_xml=             _qa_cf["qa_markup_xml"],
                        qa_custo_sem_venda=        _qa_cf["qa_custo_sem_venda"],
                        created_by=    usuario['id'] if usuario else None,
                    )
                    db.add(pa)
                    db.commit()
                    db.refresh(pa)
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, temp["arq_nome"]), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] criado_forcado: id=%d nome=%r" % (pa.id, pa.nome_exibicao))
                    self.send_json({"ok": True, "acao": "criado",
                                    "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /orcamentos/<oid>/ambientes/<pid>/remover — remover ambiente ─────
            m_rem = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)/remover$", path)
            if m_rem:
                oid = int(m_rem.group(1))
                pid = int(m_rem.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if pa is None or pa.projeto_id != orc.projeto_id:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    link = db.query(OrcamentoAmbiente).filter_by(
                        orcamento_id=oid, pool_ambiente_id=pid
                    ).first()
                    if not link:
                        self.send_json({"ok": False, "erro": "Ambiente não está neste orçamento"})
                        return
                    db.delete(link)
                    db.flush()
                    # Recálculo simples — Passo 8 implementa versão completa com margens
                    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                    orc.valor_total = round(
                        sum(db.get(PoolAmbiente, lk.pool_ambiente_id).budget_total for lk in links), 2
                    )
                    orc.updated_at = datetime.now()
                    db.commit()
                    print("[ORC-AMB] removido: orcamento_id=%d pool_ambiente_id=%d valor_total=%.2f"
                          % (oid, pid, orc.valor_total))
                    self.send_json({"ok": True,
                                    "orcamento":        _orcamento_dict(orc),
                                    "ambiente_removido": _pool_ambiente_dict(pa) if pa else {"id": pid}})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /api/pool/<pid>/qa-override — liberar ambiente bloqueado ──────
            m_qaov = _re.match(r"^/api/pool/(\d+)/qa-override$", path)
            if m_qaov:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                motivo = (req.get("motivo") or "").strip()
                if not motivo:
                    self.send_json({"ok": False, "erro": "Justificativa é obrigatória."})
                    return
                db = get_session()
                try:
                    pa = db.get(PoolAmbiente, int(m_qaov.group(1)))
                    if not pa:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"}, code=404)
                        return
                    pa.qa_override_por_id = usuario["id"]
                    pa.qa_override_motivo = motivo
                    db.add(LogAcaoGerencial(
                        autorizador_id=usuario["id"], acao="qa_override",
                        projeto_nome=pa.projeto_id,
                        contexto=json.dumps({"pool_ambiente_id": pa.id, "motivo": motivo})))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            # ── POST /orcamentos/<oid>/ambientes/<pid> — adicionar ambiente ──────────
            m_add = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)$", path)
            if m_add:
                oid = int(m_add.group(1))
                pid = int(m_add.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if pa is None or pa.projeto_id != orc.projeto_id:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if pa.qa_selo == "bloqueado" and pa.qa_override_por_id is None:
                        self.send_json({"ok": False, "erro":
                            "Ambiente bloqueado por qualidade do XML (acréscimo zerado). "
                            "Re-exporte o XML ou solicite liberação ao Diretor/Gerente."}, code=409)
                        return
                    ja_existe = db.query(OrcamentoAmbiente).filter_by(
                        orcamento_id=oid, pool_ambiente_id=pid
                    ).first()
                    if ja_existe:
                        self.send_json({"ok": False, "erro": "Ambiente já está neste orçamento"})
                        return
                    ordem = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).count() + 1
                    db.add(OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=ordem))
                    db.flush()
                    # Recálculo simples — Passo 8 implementa versão completa com margens
                    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                    orc.valor_total = round(
                        sum(db.get(PoolAmbiente, lk.pool_ambiente_id).budget_total for lk in links), 2
                    )
                    orc.updated_at = datetime.now()
                    db.commit()
                    print("[ORC-AMB] adicionado: orcamento_id=%d pool_ambiente_id=%d valor_total=%.2f"
                          % (oid, pid, orc.valor_total))
                    self.send_json({"ok": True,
                                    "orcamento": _orcamento_dict(orc),
                                    "ambiente":  _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            if path == "/api/admin/usuarios":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db  = get_session()
                try:
                    logins = [u.login for u in db.query(Usuario.login).all()]
                    erros  = mod_usuarios.validar_novo_usuario(req, logins)
                    ator   = _ator_dict(db, usuario)
                    loja_id, rede_id, erros_tenant = mod_tenancy.atribuir_tenant_usuario(ator, req)
                    erros = erros + erros_tenant
                    if not erros and loja_id is not None and not mod_tenancy._eh_super_admin(ator):
                        loja = db.get(Loja, loja_id)
                        if not loja or not mod_tenancy.pode_ver_loja(
                                ator, {"id": loja.id, "rede_id": loja.rede_id}):
                            erros = erros + ["Loja fora do seu escopo."]
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                                nivel=req["nivel"].strip(),
                                telefone=(req.get("telefone") or "").strip(),
                                whatsapp=(req.get("whatsapp") or "").strip(),
                                email=(req.get("email") or "").strip(),
                                cpf=(req.get("cpf") or "").strip(),
                                loja_id=loja_id, rede_id=rede_id)
                    u.set_senha(req["senha"])
                    db.add(u); db.commit()
                    self.send_json({"ok": True, "id": u.id})
                finally:
                    db.close()
                return

            if path == "/api/admin/redes":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                erros = mod_tenancy.validar_rede(req)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                db = get_session()
                try:
                    r = Rede(nome=req["nome"].strip(),
                             cnpj=(req.get("cnpj") or "").strip() or None)
                    db.add(r); db.commit()
                    self.send_json({"ok": True, "rede": _rede_dict(r)})
                finally:
                    db.close()
                return

            if path == "/api/admin/lojas":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_lojas"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    codigos = [c for (c,) in db.query(Loja.codigo).all() if c]
                    erros = mod_tenancy.validar_loja(req, codigos)
                    rede_id = req.get("rede_id")
                    if not mod_tenancy._eh_super_admin(ator):
                        rede_id = ator.get("rede_id")
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    l = Loja(
                        nome=req["nome"].strip(),
                        codigo=req["codigo"].strip().upper(),
                        rede_id=rede_id,
                        cnpj=(req.get("cnpj") or "").strip() or None,
                        telefone=(req.get("telefone") or "").strip() or None,
                        email=(req.get("email") or "").strip() or None,
                    )
                    db.add(l); db.commit()
                    self.send_json({"ok": True, "loja": _loja_dict(l)})
                finally:
                    db.close()
                return

            m_sync = _re.match(r"^/api/admin/omie-sync/(\d+)/retry$", path)
            if m_sync:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                    self.send_json({"ok": False, "erro": "Acesso negado"})
                    return
                db2 = get_session()
                try:
                    c = db2.get(Cliente, int(m_sync.group(1)))
                    if not c:
                        self.send_json({"ok": False, "erro": "Cliente não encontrado"})
                        return
                    _tentar_sync_omie(c, db2)
                    self.send_json({"ok": True, "cliente": _cliente_dict(c)})
                finally:
                    db2.close()
                return

            m = _re.match(r"^/projetos/([^/]+)/ambientes/(adicionar|remover|atualizar|selecao)$", path)
            if m:
                nome_safe = m.group(1)
                acao = m.group(2)

                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_scope = get_session()
                try:
                    ator = _ator_dict(_db_scope, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_scope, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                finally:
                    _db_scope.close()

                # Rotas de escrita bloqueadas após aprovação
                if acao in ("adicionar", "remover", "atualizar"):
                    _proj_chk = _carregar_projeto(nome_safe)
                    if _proj_chk and _proj_chk.get("bloqueado"):
                        self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."})
                        return

                if acao == "adicionar":
                    ct = self.headers.get("Content-Type", "")
                    arquivos, _ = _parse_multipart(body, ct)
                    if not arquivos:
                        self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                        return
                    try:
                        proj = _adicionar_ambientes(nome_safe, arquivos)
                        session_set("projeto_ativo", nome_safe)
                        self.send_json({"ok": True, "projeto": proj})
                    except Exception as e:
                        self.send_json({"ok": False, "erro": str(e)})

                elif acao == "remover":
                    req = json.loads(body)
                    arquivo = req.get("arquivo", "").strip()
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    proj["ambientes"] = [a for a in proj["ambientes"] if a["arquivo"] != arquivo]
                    xml_path = os.path.join(_projeto_path(nome_safe), "xmls", arquivo)
                    storage_deletar(xml_path)
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "projeto": proj})

                elif acao == "atualizar":
                    ct = self.headers.get("Content-Type", "")
                    arquivos, campos = _parse_multipart(body, ct)
                    arquivo_sub = campos.get("arquivo_substituir", "").strip()
                    if not arquivos:
                        self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    sel_anterior = True
                    for a in proj["ambientes"]:
                        if a["arquivo"] == arquivo_sub:
                            sel_anterior = a.get("selecionado", True)
                    proj["ambientes"] = [a for a in proj["ambientes"] if a["arquivo"] != arquivo_sub]
                    old_xml = os.path.join(pasta_xmls, arquivo_sub)
                    if arquivo_sub:
                        storage_deletar(old_xml)
                    for nome_arq, conteudo in arquivos:
                        storage_salvar_texto(os.path.join(pasta_xmls, nome_arq), conteudo)
                    dados = carregar_xmls(arquivos)
                    for amb in dados.get("ambientes", []):
                        amb["selecionado"] = sel_anterior
                        amb["arquivo_path"] = os.path.join(pasta_xmls, amb["arquivo"])
                        proj["ambientes"].append(amb)
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "projeto": proj})

                elif acao == "selecao":
                    req = json.loads(body)
                    selecoes = req.get("selecoes", {})
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    for amb in proj["ambientes"]:
                        if amb["arquivo"] in selecoes:
                            amb["selecionado"] = selecoes[amb["arquivo"]]
                    _salvar_projeto(proj)
                    self.send_json({"ok": True})

            # POST /api/projetos/<nome>/ciclo/desfazer_aprovacao — volta ao orçamento (requer gerente)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/desfazer_aprovacao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                    if not autorizador or not autorizador.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Credenciais inválidas"})
                        return
                    if not perfis.pode(autorizador.nivel, "autorizar"):
                        self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"})
                        return
                    # Verifica se contrato está assinado — nesse caso não pode voltar
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if contrato and contrato.status in ("assinado", "vigente"):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível voltar ao orçamento"})
                        return
                    # Resetar etapas 5, 6 e 7 (a aprovação concluiu 5+6 e iniciou a 7)
                    e5 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="5").first()
                    if e5: db.delete(e5)
                    e6 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="6").first()
                    if e6: db.delete(e6)
                    e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="7").first()
                    if e7: db.delete(e7)
                    # Resetar contrato para rascunho
                    if contrato:
                        contrato.status = "rascunho"
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/reabrir — reabre em cascata (requer gerente)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/reabrir$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                    if not autorizador or not autorizador.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Credenciais inválidas"}, code=403)
                        return
                    if not perfis.pode(autorizador.nivel, "autorizar"):
                        self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"}, code=403)
                        return
                    todas    = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos  = [e.etapa_codigo for e in todas]
                    resetar  = mod_ciclo.codigos_a_resetar(etapa_cod, codigos)
                    # Trava: não reabrir se desfaz contrato assinado/vigente
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    cstatus  = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível reabrir esta etapa"},
                                       code=400)
                        return
                    resetar_set = set(resetar)
                    status_anterior = {e.etapa_codigo: e.status for e in todas
                                       if e.etapa_codigo in resetar_set}
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status         = "pendente"
                            e.iniciado_em    = None
                            e.concluido_em   = None
                            e.responsavel_id = None
                    log = LogAcaoGerencial(
                        solicitante_id=solicitante["id"],
                        autorizador_id=autorizador.id,
                        acao="reabrir_cascata",
                        projeto_nome=nome_safe,
                        etapa_alvo=etapa_cod,
                        contexto=json.dumps({"resetadas": sorted(resetar_set),
                                             "status_anterior": status_anterior}),
                    )
                    db.add(log)
                    db.commit()
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato/assinar — registra assinatura
            m = _re.match(r'^/api/projetos/([^/]+)/contrato/assinar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req   = json.loads(body)
                parte = (req.get("parte") or "").strip()
                nome  = (req.get("nome")  or "").strip()
                cpf   = (req.get("cpf")   or "").strip()
                if parte not in ("loja", "cliente"):
                    self.send_json({"ok": False, "erro": "parte deve ser 'loja' ou 'cliente'"}, code=400)
                    return
                if not nome or not cpf:
                    self.send_json({"ok": False, "erro": "nome e cpf são obrigatórios"}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status in ("vigente", "assinado"):
                        self.send_json({"ok": False, "erro": "Contrato já está vigente"}, code=400)
                        return
                    ja_assinou = any(a.parte == parte for a in contrato.assinaturas)
                    if ja_assinou:
                        self.send_json({"ok": False, "erro": f"Parte '{parte}' já assinou"}, code=400)
                        return
                    timestamp = datetime.utcnow().isoformat()
                    ip        = self.client_address[0] if self.client_address else ""
                    hash_sig  = calcular_hash_assinatura(nome, cpf, contrato.id, timestamp)
                    assinatura = ContratoAssinatura(
                        contrato_id=contrato.id,
                        parte=parte,
                        nome=nome,
                        cpf=cpf,
                        assinado_em=datetime.utcnow(),
                        ip_origem=ip,
                        hash_sha256=hash_sig,
                    )
                    db.add(assinatura)
                    partes_assinadas = {a.parte for a in contrato.assinaturas} | {parte}
                    if "loja" in partes_assinadas and "cliente" in partes_assinadas:
                        contrato.status = "assinado_loja"
                    elif parte == "loja":
                        contrato.status = "assinado_loja"
                    else:
                        contrato.status = "assinado_cliente"
                    db.commit()
                    # Verificar se ambas as partes assinaram → fechar etapa 7
                    assinaturas = db.query(ContratoAssinatura)\
                                    .filter_by(contrato_id=contrato.id).all()
                    partes_assinadas = {a.parte for a in assinaturas}
                    if {"loja", "cliente"}.issubset(partes_assinadas):
                        contrato.status = "assinado"
                        etapa7 = db.query(CicloEtapa).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="7"
                        ).first()
                        if not etapa7:
                            etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                            db.add(etapa7)
                        etapa7.status        = "concluido"
                        etapa7.concluido_em  = datetime.utcnow()
                        etapa7.responsavel_id = usuario["id"]
                        db.commit()
                        try:
                            upsert_projeto_status(nome_safe, "fechado")
                        except Exception as _e:
                            print("[FECHADO] upsert_projeto_status falhou:", _e)
                    self.send_json({"ok": True, "status": contrato.status, "parte": parte})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato/editar — abre o .docx (protegido) no
            # Word/LibreOffice local e regenera o PDF a cada salvamento (gate gerencial).
            m = _re.match(r'^/api/projetos/([^/]+)/contrato/editar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
                    req   = json.loads(body or b'{}')
                    app   = (req.get("app") or "word").strip().lower()
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    from contrato_editar import validar_gerencial
                    autorizador, erro = validar_gerencial(db, login, senha)
                    if erro:
                        self.send_json({"ok": False, "erro": erro}, code=403)
                        return
                    ator_ed = {"nivel": autorizador.nivel, "loja_id": autorizador.loja_id, "rede_id": autorizador.rede_id}
                    loja_id_ed, _err_ed = mod_tenancy.escopo_operacional(ator_ed)
                    if _err_ed:
                        self.send_json({"ok": False, "erro": _err_ed}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id_ed) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    from mod_contrato import CONTRATOS_DIR
                    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato.id}.docx")
                    if not os.path.exists(docx_path):
                        self.send_json({"ok": False,
                                        "erro": "Arquivo do contrato (.docx) não encontrado"}, code=404)
                        return
                    # auditoria
                    db.add(LogAcaoGerencial(
                        autorizador_id=autorizador.id,
                        acao="editar_contrato",
                        projeto_nome=nome_safe,
                        contexto=json.dumps({"app": app, "contrato_id": contrato.id}),
                    ))
                    db.commit()
                    contrato_id = contrato.id
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                    return
                finally:
                    db.close()
                # abrir o app + iniciar watcher (fora da sessão db)
                from contrato_editar import abrir_no_app, watcher_regerar_pdf
                import mod_contrato
                def _on_save(p):
                    try:
                        mod_contrato._converter_pdf(p)
                        s = get_session()
                        try:
                            c = s.query(Contrato).get(contrato_id)
                            if c:
                                c.pdf_path = os.path.join(CONTRATOS_DIR,
                                                          f"contrato_{contrato_id}.pdf")
                                s.commit()
                        finally:
                            s.close()
                    except Exception:
                        pass
                # snapshot do mtime ANTES de abrir o app (referência de edição iniciada)
                mtime_ini = os.path.getmtime(docx_path) if os.path.exists(docx_path) else 0.0
                try:
                    abrir_no_app(docx_path, app)
                except Exception as e:
                    self.send_json({"ok": False, "erro": f"Falha ao abrir o app: {e}"}, code=500)
                    return
                threading.Thread(
                    target=watcher_regerar_pdf,
                    args=(docx_path, _on_save),
                    kwargs={"mtime_ref": mtime_ini},
                    daemon=True,
                ).start()
                self.send_json({"ok": True, "editando": True, "app": app})
                return

            # POST /api/projetos/<nome>/contrato — gera PDF do contrato
            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                # A validação completa do cadastro do cliente (identificação +
                # endereço) ocorre mais abaixo, após montar cliente_dict, via
                # validar_cliente_para_contrato() — valida o dado realmente renderizado.
                req                  = json.loads(body)
                orcamento_id         = req.get("orcamento_id")
                endereco_instalacao  = (req.get("endereco_instalacao") or "").strip()
                entrada_valor        = float(req.get("entrada_valor") or 0)
                parcelas_descricao   = req.get("parcelas_descricao") or ""
                adendo               = req.get("adendo") or ""
                forma_entrada        = req.get("forma_entrada", "pix")
                forma_parcelas       = req.get("forma_parcelas", "boleto")
                pagamento_json_str   = req.get("pagamento_json", "")
                if not orcamento_id:
                    self.send_json({"ok": False, "erro": "orcamento_id obrigatório"}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)
                    # Gate: orçamento precisa ter ao menos um ambiente (1º orçamento concluído).
                    if not orcamento_dict.get("ambientes"):
                        self.send_json({
                            "ok": False,
                            "erro": "O orçamento não tem ambientes. Conclua o primeiro orçamento "
                                    "(com ambientes) antes de aprovar.",
                        }, code=400)
                        return
                    # Signatário alternativo: substitui o cadastro só para este contrato.
                    _override = req.get("signatario_override")
                    if isinstance(_override, dict) and _override.get("nome"):
                        cliente_dict = {**cliente_dict, **{k: v for k, v in _override.items() if v not in (None, "")}}
                    from mod_contrato import construir_contexto
                    from mod_contrato import _formatar_valor
                    from mod_contrato import validar_cliente_para_contrato
                    # Valida os dados que serão de fato renderizados no documento.
                    # Impede gerar contrato com endereço/contato em branco.
                    faltando = validar_cliente_para_contrato(cliente_dict)
                    if faltando:
                        self.send_json({
                            "ok": False,
                            "erro": "Cadastro do cliente incompleto — preencha antes de gerar o contrato. "
                                    "Campos faltando: " + ", ".join(faltando),
                            "campos_faltando": faltando,
                        }, code=400)
                        return
                    from mod_contrato import validar_loja_para_contrato
                    ator = _ator_dict(db, usuario)
                    loja_dict = _loja_dict_para_contrato(db, ator.get("loja_id"))
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
                    usuario_ctx = {
                        "nome":     usuario.get("nome", ""),
                        "telefone": _get_usuario_telefone(usuario["id"], db),
                        "email":    usuario.get("email", "") or "",
                    }
                    # pagamento_json_str = JSON completo enviado pela aprovação (prioridade)
                    # fallback: forma_pagamento do orçamento (texto curto ou JSON salvo)
                    pag_json = pagamento_json_str or orcamento_dict.get("forma_pagamento", "") or ""
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
                    variaveis.update({
                        "projeto_nome":    projeto_dict.get("nome_projeto", ""),
                        "orcamento_nome":  orcamento_dict.get("nome", ""),
                        "valor_total":     _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_negociado": _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_liquido":   _formatar_valor(orcamento_dict.get("valor_liquido", 0)),
                        "ambientes_lista": "\n".join(orcamento_dict.get("ambientes", [])),
                        "tem_adendo":      bool(req.get("adendo")),
                        "adendo":          req.get("adendo") or "",
                        "consultor_nome":  usuario.get("nome", ""),
                    })
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        contrato = Contrato(projeto_nome=nome_safe, orcamento_id=orcamento_id)
                        db.add(contrato)
                        db.flush()
                    contrato.endereco_instalacao = endereco_instalacao
                    contrato.pagamento_json      = pagamento_json_str
                    contrato.adendo              = adendo
                    contrato.gerado_em           = datetime.utcnow()
                    contrato.gerado_por_id       = usuario["id"]
                    contrato.status              = "rascunho"
                    if not contrato.loja_id:
                        contrato.loja_id = ator.get("loja_id")
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    # Número do contrato (gerado uma vez; mantido em regerações).
                    if not contrato.num_contrato:
                        from mod_contrato import gerar_num_contrato
                        _existing = [c.num_contrato for c in db.query(Contrato)
                                     .filter(Contrato.num_contrato.isnot(None)).all()]
                        contrato.num_contrato = gerar_num_contrato(_existing, loja_dict.get("codigo", ""))
                    variaveis["num_contrato"] = contrato.num_contrato
                    db.commit()
                    aviso = None
                    try:
                        pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                        contrato.pdf_path = pdf_path
                    except LibreOfficeIndisponivel as lo:
                        # Salva o .docx e avança mesmo sem PDF
                        contrato.pdf_path = lo.docx_path
                        aviso = str(lo)
                    contrato.status = "para_assinatura"
                    # Marcar etapa 5 (Revisão de projeto) como concluída — a aprovação
                    # conclui Revisão e Aprovação juntas.
                    etapa5 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="5"
                    ).first()
                    if not etapa5:
                        etapa5 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="5")
                        db.add(etapa5)
                    etapa5.status         = "concluido"
                    etapa5.concluido_em   = datetime.utcnow()
                    etapa5.responsavel_id = usuario["id"]
                    # Marcar etapa 6 (Aprovação do orçamento) como concluída
                    etapa6 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="6"
                    ).first()
                    if not etapa6:
                        etapa6 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="6")
                        db.add(etapa6)
                    etapa6.status       = "concluido"
                    etapa6.concluido_em = datetime.utcnow()
                    etapa6.responsavel_id = usuario["id"]
                    db.commit()
                    # Marcar etapa 7 como "em_andamento" (contrato gerado, aguardando assinatura)
                    etapa7 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="7"
                    ).first()
                    if not etapa7:
                        etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                        db.add(etapa7)
                    etapa7.status = "em_andamento"
                    db.commit()
                    resp = {"ok": True, "contrato_id": contrato.id, "status": "para_assinatura"}
                    if aviso:
                        resp["aviso"] = aviso
                    self.send_json(resp)
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/solicitacao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao")
                    if not u:
                        self.send_json({"ok": False, "erro": "Confirmação exige login+senha do Medidor (ou Diretor)."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo de solicitação de medição."}); return
                    fname, data = arquivos["arquivo"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "solicitacao_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md = _get_or_create_medicao(db, nome_safe)
                    md.solicitacao_arquivo = os.path.basename(destino)
                    md.solicitacao_por = u.id
                    md.solicitacao_em = datetime.utcnow()
                    _set_etapa_status(db, nome_safe, "9", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="medicao_solicitacao", projeto_nome=nome_safe, etapa_alvo="9"))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/parecer$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                parecer = (campos.get("parecer","") or "").strip().lower()
                ambientes = campos.get("ambientes_aprovados","")
                erros = mod_medicao.validar_parecer(parecer, ambientes)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)}); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao")
                    if not u:
                        self.send_json({"ok": False, "erro": "Registro exige login+senha do Medidor (ou Diretor)."}, code=403); return
                    if "planta" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo promob da Planta de Pontos Medidos."}); return
                    fname, data = arquivos["planta"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "planta_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md = _get_or_create_medicao(db, nome_safe)
                    md.planta_arquivo = os.path.basename(destino)
                    md.parecer = parecer
                    md.ambientes_aprovados = ambientes.strip() if parecer == "parcial" else None
                    md.medidor_id = u.id
                    md.medicao_em = datetime.utcnow()
                    if parecer in ("aprovado", "parcial"):
                        _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                    else:
                        _set_etapa_status(db, nome_safe, "10", "em_andamento", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="medicao_parecer_" + parecer, projeto_nome=nome_safe, etapa_alvo="10"))
                    db.commit()
                    self.send_json({"ok": True, "parecer": parecer})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/decisao-reprovado$', path)
            if m:
                nome_safe = unquote(m.group(1))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    if not md or md.parecer != "reprovado":
                        self.send_json({"ok": False, "erro": "Só aplicável a uma medição com parecer Reprovado."}); return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "aprovar_medicao_reprovada")
                    if not u:
                        self.send_json({"ok": False, "erro": "Liberação exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                    if "doc_cliente" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o documento de aprovação do cliente."}); return
                    fname, data = arquivos["doc_cliente"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "doc_cliente_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md.doc_cliente_arquivo = os.path.basename(destino)
                    md.excecao_por = u.id
                    md.excecao_em = datetime.utcnow()
                    _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                            acao="medicao_excecao_reprovado", projeto_nome=nome_safe, etapa_alvo="10"))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            else:
                self.send_response(404)
                self.end_headers()

    def do_PUT(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        # ── PUT /projetos/<nome_safe>/orcamentos/<oid> — renomear orçamento ───
        m = re.match(r"^/projetos/([^/]+)/orcamentos/(\d+)$", path)
        if m:
            nome_safe = m.group(1)
            oid       = int(m.group(2))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            try:
                req = json.loads(body)
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"})
                return
            novo_nome = (req.get("nome") or "").strip()
            if not novo_nome:
                self.send_json({"ok": False, "erro": "Nome não pode ser vazio"})
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None or orc.projeto_id != nome_safe:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                orc.nome       = novo_nome
                orc.updated_at = datetime.now()
                db.commit()
                db.refresh(orc)
                self.send_json({"ok": True, "orcamento": _orcamento_dict(orc)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        # ── PUT /api/orcamentos/<id>/descontos — descontos individuais em lote ──
        m_desc = re.match(r"^/api/orcamentos/(\d+)/descontos$", path)
        if m_desc:
            oid = int(m_desc.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from mod_orcamento_params import sanear_descontos
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                pares = req.get("descontos", req)   # aceita {"descontos":{...}} ou {...}
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _projeto_esta_bloqueado(orc.projeto_id):
                    self.send_json({"ok": False,
                                    "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                   code=400)
                    return
                if orc and _contrato_assinado(orc.projeto_id, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                ids_validos = {lk.pool_ambiente_id for lk in links}
                limpos = sanear_descontos(pares, ids_validos)
                by_id = {lk.pool_ambiente_id: lk for lk in links}
                for pid, pct in limpos.items():
                    by_id[pid].desconto_individual_pct = pct
                db.commit()
                self.send_json({"ok": True, "descontos": {str(k): v for k, v in limpos.items()}})
            except ValueError as ve:
                db.rollback()
                self.send_json({"ok": False, "erro": str(ve)}, code=400)
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        try:
            path = urlparse(self.path).path
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b'{}'

            m = re.match(r'^/orcamentos/(\d+)/valor$', path)
            if m:
                oid = int(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body)
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if orc and _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    if "valor_total" in req:
                        orc.valor_total = float(req["valor_total"] or 0)
                    if "valor_liquido" in req:
                        orc.valor_liquido = float(req["valor_liquido"] or 0)
                    if "forma_pagamento" in req:
                        orc.forma_pagamento = req["forma_pagamento"] or None
                    if "negociacao_json" in req:
                        orc.negociacao_json = req["negociacao_json"] or None
                    orc.updated_at = datetime.utcnow()
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = re.match(r'^/api/projetos/([^/]+)/status$', path)
            if m:
                nome_safe = unquote(m.group(1))
                req = json.loads(body)
                novo_status = (req.get('status') or '').strip().lower()
                VALIDOS = {'quente', 'morno', 'frio', 'perdido'}
                if novo_status not in VALIDOS:
                    self.send_json({"ok": False, "erro": f"Status inválido. Use: {', '.join(sorted(VALIDOS))}"})
                    return
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_scope = get_session()
                try:
                    ator = _ator_dict(_db_scope, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_scope, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _assinado = _contrato_assinado(nome_safe, _db_scope)
                finally:
                    _db_scope.close()
                if _assinado:
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                upsert_projeto_status(nome_safe, novo_status)
                self.send_json({"ok": True, "status": novo_status})
                return

            m = re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                usuario     = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body)
                novo_status = req.get("status", "").strip()
                obs         = req.get("observacoes")
                if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in ("9", "10"):
                    self.send_json({"ok": False, "erro": "Use o fluxo de Medição para concluir esta etapa."}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod
                    ).first()
                    if not etapa:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    # Gating sequencial: etapa principal só avança se a anterior está concluída.
                    if novo_status and novo_status != "pendente":
                        todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                        status_por_codigo = {e.etapa_codigo: e.status for e in todas}
                        if not mod_ciclo.pode_avancar(etapa_cod, status_por_codigo):
                            ant = mod_ciclo.etapa_anterior(etapa_cod)
                            nome_ant = mod_ciclo.ETAPA_NOME.get(ant, ant)
                            self.send_json({
                                "ok": False,
                                "erro": f"Conclua a etapa anterior ({nome_ant}) antes de iniciar esta.",
                            }, code=400)
                            return
                    # Aprovação financeira (8/11d): exige login+senha de quem pode aprovar.
                    aprovador = None
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and mod_ciclo.exige_aprovacao_financeira(etapa_cod):
                        aprovador = _aprovador_financeiro(db, req.get("login", ""), req.get("senha", ""))
                        if not aprovador:
                            self.send_json({
                                "ok": False,
                                "erro": "Apenas Gerente Administrativo/Financeiro ou Diretor podem "
                                        "aprovar a etapa financeira (login/senha inválidos ou sem permissão).",
                            }, code=403)
                            return
                    if novo_status:
                        if etapa.status == "pendente" and novo_status != "pendente":
                            etapa.iniciado_em = datetime.utcnow()
                        etapa.status = novo_status
                        if novo_status in mod_ciclo.STATUS_CONCLUSIVOS:
                            etapa.concluido_em  = datetime.utcnow()
                            etapa.responsavel_id = aprovador.id if aprovador else usuario["id"]
                    if obs is not None:
                        etapa.observacoes = obs
                    if aprovador is not None:
                        db.add(LogAcaoGerencial(
                            solicitante_id=usuario["id"],
                            autorizador_id=aprovador.id,
                            acao="aprovar_financeiro",
                            projeto_nome=nome_safe,
                            etapa_alvo=etapa_cod,
                        ))
                    db.commit()
                    self.send_json({"ok": True, "etapa_codigo": etapa_cod, "status": etapa.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req    = json.loads(body)
                adendo = req.get("adendo") or ""
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status in ("vigente", "assinado"):
                        self.send_json({"ok": False,
                                        "erro": "Contrato vigente não pode ser editado"}, code=400)
                        return
                    contrato.adendo = adendo
                    db.commit()
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, contrato.orcamento_id, db)
                    from mod_contrato import construir_contexto
                    from mod_contrato import _formatar_valor
                    from mod_contrato import validar_loja_para_contrato
                    ator = _ator_dict(db, usuario)
                    loja_dict = _loja_dict_para_contrato(db, contrato.loja_id or ator.get("loja_id"))
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
                    usuario_ctx = {
                        "nome":     usuario.get("nome", ""),
                        "telefone": _get_usuario_telefone(usuario["id"], db),
                        "email":    usuario.get("email", "") or "",
                    }
                    pag_json = contrato.pagamento_json or orcamento_dict.get("forma_pagamento", "") or ""
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
                    variaveis.update({
                        "projeto_nome":    projeto_dict.get("nome_projeto", ""),
                        "orcamento_nome":  orcamento_dict.get("nome", ""),
                        "valor_total":     _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_negociado": _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_liquido":   _formatar_valor(orcamento_dict.get("valor_liquido", 0)),
                        "ambientes_lista": "\n".join(orcamento_dict.get("ambientes", [])),
                        "tem_adendo":      bool(adendo),
                        "adendo":          adendo or "",
                        "consultor_nome":  usuario.get("nome", ""),
                    })
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    if not contrato.loja_id:
                        contrato.loja_id = ator.get("loja_id")
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m_user = re.match(r"^/api/admin/usuarios/(\d+)$", path)
            if m_user:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                erros = mod_usuarios.validar_edicao_usuario(req)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                db = get_session()
                try:
                    u = db.query(Usuario).filter_by(id=int(m_user.group(1))).first()
                    if not u:
                        self.send_json({"ok": False, "erro": "Usuário não encontrado"})
                        return
                    ator = _ator_dict(db, usuario)
                    # escopo: o ator precisa enxergar o usuário-alvo (mesma regra da listagem)
                    if mod_tenancy._eh_super_admin(ator):
                        visivel = True
                    elif mod_tenancy._eh_admin_rede(ator):
                        rede_alvo = u.rede_id
                        if rede_alvo is None and u.loja_id is not None:
                            la = db.get(Loja, u.loja_id)
                            rede_alvo = la.rede_id if la else None
                        visivel = (rede_alvo == ator.get("rede_id"))
                    else:
                        visivel = (u.loja_id is not None and u.loja_id == ator.get("loja_id"))
                    if not visivel:
                        self.send_json({"ok": False, "erro": "Usuário fora do seu escopo."}, code=403)
                        return
                    # anti-lockout: o ator não altera o próprio perfil nem se inativa
                    eh_proprio = (u.id == usuario.get("id"))
                    if eh_proprio and "nivel" in req and req["nivel"].strip() != u.nivel:
                        self.send_json({"ok": False,
                            "erro": "Não é possível alterar o próprio perfil."}, code=403)
                        return
                    if eh_proprio and "ativo" in req and not req["ativo"]:
                        self.send_json({"ok": False,
                            "erro": "Não é possível inativar a si mesmo."}, code=403)
                        return
                    # anti-escalonamento: super_admin só por super_admin;
                    # admin_rede por super_admin ou admin_rede
                    novo_nivel = req["nivel"].strip() if "nivel" in req else None
                    if novo_nivel == "super_admin" and not mod_tenancy._eh_super_admin(ator):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if novo_nivel == "admin_rede" and not (
                            mod_tenancy._eh_super_admin(ator) or mod_tenancy._eh_admin_rede(ator)):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if "nome" in req:     u.nome     = req["nome"].strip()
                    if "nivel" in req:    u.nivel    = req["nivel"].strip()
                    if "telefone" in req: u.telefone = (req.get("telefone") or "").strip()
                    if "whatsapp" in req: u.whatsapp = (req.get("whatsapp") or "").strip()
                    if "email" in req:    u.email    = (req.get("email") or "").strip()
                    if "cpf" in req:      u.cpf      = (req.get("cpf") or "").strip()
                    if "ativo" in req:    u.ativo    = 1 if req["ativo"] else 0
                    if req.get("senha"):  u.set_senha(req["senha"])
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            m_rede = re.match(r"^/api/admin/redes/(\d+)$", path)
            if m_rede:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    r = db.get(Rede, int(m_rede.group(1)))
                    if not r:
                        self.send_json({"ok": False, "erro": "Rede não encontrada"}, code=404)
                        return
                    if "nome" in req:
                        nome = (req["nome"] or "").strip()
                        if not nome:
                            self.send_json({"ok": False, "erro": "Nome da rede é obrigatório."})
                            return
                        r.nome = nome
                    if "cnpj" in req:  r.cnpj  = (req["cnpj"] or "").strip() or None
                    if "ativo" in req: r.ativo = 1 if req["ativo"] else 0
                    db.commit()
                    self.send_json({"ok": True, "rede": _rede_dict(r)})
                finally:
                    db.close()
                return

            m_loja = re.match(r"^/api/admin/lojas/(\d+)$", path)
            if m_loja:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    l = db.get(Loja, int(m_loja.group(1)))
                    if not l:
                        self.send_json({"ok": False, "erro": "Loja não encontrada"}, code=404)
                        return
                    ator = _ator_dict(db, usuario)
                    loja_d = {"id": l.id, "rede_id": l.rede_id}
                    if not mod_tenancy.pode_editar_dados_loja(ator, loja_d):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                        return
                    if "codigo" in req:
                        outros = [c for (c,) in db.query(Loja.codigo)
                                                .filter(Loja.id != l.id).all() if c]
                        erros = mod_tenancy.validar_loja(
                            {"nome": req.get("nome", l.nome), "codigo": req["codigo"]}, outros)
                        if erros:
                            self.send_json({"ok": False, "erro": " ".join(erros)})
                            return
                        l.codigo = req["codigo"].strip().upper()
                    for campo in ("nome", "cnpj", "telefone", "email", "cep", "logradouro",
                                  "numero", "complemento", "bairro", "cidade", "estado",
                                  "testemunha1_nome", "testemunha1_cpf",
                                  "testemunha2_nome", "testemunha2_cpf"):
                        if campo in req:
                            val = (req[campo] or "").strip() or None
                            if campo == "nome" and not val:
                                self.send_json({"ok": False, "erro": "Nome da loja é obrigatório."})
                                return
                            setattr(l, campo, val)
                    if perfis.pode(ator.get("nivel"), "gerir_lojas"):
                        if "ativo" in req:   l.ativo = 1 if req["ativo"] else 0
                        if "rede_id" in req and mod_tenancy._eh_super_admin(ator):
                            l.rede_id = req["rede_id"]
                    db.commit()
                    self.send_json({"ok": True, "loja": _loja_dict(l)})
                finally:
                    db.close()
                return

            self.send_json({"ok": False, "erro": "Rota não encontrada"})
        except Exception as e:
            self.send_json({"ok": False, "erro": str(e)})


# ── Helper ────────────────────────────────────────────────────────────────────
def validar_cadastro_minimo(req: dict) -> list:
    """Campos mínimos obrigatórios para criar um cliente: nome, e-mail, telefone.
    Retorna a lista de rótulos faltando (vazia se ok). CPF/endereço são opcionais
    na criação — a completude para o contrato é cobrada na aprovação."""
    faltando = []
    for campo, rotulo in [("nome", "Nome"), ("email", "E-mail"), ("telefone", "Telefone")]:
        if not (req.get(campo) or "").strip():
            faltando.append(rotulo)
    return faltando


def _cliente_dict(c) -> dict:
    return {
        "id":          c.id,
        "nome":        c.nome,
        "cpf":         c.cpf         or "",
        "email":       c.email       or "",
        "telefone":    c.telefone    or "",
        "whatsapp":    c.whatsapp    or "",
        "cep":         c.cep         or "",
        "logradouro":  c.logradouro  or "",
        "numero":      c.numero      or "",
        "complemento": c.complemento or "",
        "bairro":      c.bairro      or "",
        "cidade":      c.cidade      or "",
        "estado":      c.estado      or "",
        "observacoes": c.observacoes or "",
        "inst_mesmo_residencial": bool(c.inst_mesmo_residencial if c.inst_mesmo_residencial is not None else 1),
        "inst_logradouro":  c.inst_logradouro  or "",
        "inst_numero":      c.inst_numero      or "",
        "inst_complemento": c.inst_complemento or "",
        "inst_bairro":      c.inst_bairro      or "",
        "inst_cidade":      c.inst_cidade      or "",
        "inst_cep":         c.inst_cep         or "",
        "inst_uf":          c.inst_uf          or "",
        "omie_codigo":       c.omie_codigo or "",
        "omie_sync_status":  c.omie_sync_status or "",
        "omie_sync_erro":    c.omie_sync_erro   or "",
        "omie_sync_at":      c.omie_sync_at.isoformat() if c.omie_sync_at else "",
        "criado_em":   c.criado_em.strftime("%Y-%m-%d") if c.criado_em else "",
    }


_BRIEFING_OBRIGATORIOS = [
    "tipo_imovel", "budget_declarado", "categoria_proposta",
    "data_entrega_desejada", "flexibilidade_prazo",
]

def _briefing_dict(b) -> dict:
    d = {
        "id":                    b.id,
        "cliente_id":            b.cliente_id,
        "projeto_nome":          b.projeto_nome or "",
        "data_atendimento":      b.data_atendimento.isoformat() if b.data_atendimento else "",
        "consultor_id":          b.consultor_id,
        "tipo_imovel":           b.tipo_imovel           or "",
        "budget_declarado":      b.budget_declarado       or 0.0,
        "categoria_proposta":    b.categoria_proposta     or "",
        "data_entrega_desejada": b.data_entrega_desejada  or "",
        "flexibilidade_prazo":   b.flexibilidade_prazo    or "",
        "condicao_imovel":       b.condicao_imovel        or "",
        "metragem_m2":           b.metragem_m2,
        "num_ambientes":         b.num_ambientes,
        "ambientes_prioritarios":b.ambientes_prioritarios or "",
        "tem_arquiteto":         b.tem_arquiteto          or "",
        "nome_arquiteto":        b.nome_arquiteto         or "",
        "tem_gerente_obra":      bool(b.tem_gerente_obra),
        "end_empreendimento":    b.end_empreendimento     or "",
        "estilo_decisao":        b.estilo_decisao         or "[]",
        "estilo_vida":           b.estilo_vida            or "[]",
        "relacao_projeto":       b.relacao_projeto        or "[]",
        "decisor":               b.decisor                or "",
        "referencias_visuais":   b.referencias_visuais    or "[]",
        "obs_referencias":       b.obs_referencias        or "",
        "experiencia_anterior":  b.experiencia_anterior   or "",
        "obs_experiencia":       b.obs_experiencia        or "",
        "tem_budget":            b.tem_budget             or "",
        "forma_pagamento_pref":  b.forma_pagamento_pref   or "",
        "data_entrega_limite":   b.data_entrega_limite    or "",
        "motivo_prazo":          b.motivo_prazo           or "[]",
        "nao_abre_mao":          b.nao_abre_mao           or "",
        "restricoes":            b.restricoes             or "",
        "obs_livres":            b.obs_livres             or "",
    }
    d["completo"] = all(d.get(f) for f in _BRIEFING_OBRIGATORIOS)
    # locked é calculado dinamicamente pelo endpoint GET (não aqui)
    d["locked"] = False
    return d


def _briefing_projeto_completo(nome_safe, db) -> bool:
    """True se o projeto tem um briefing POR-PROJETO com todos os obrigatórios
    preenchidos. Briefings legados (projeto_nome NULL) não são considerados."""
    b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
          .order_by(Briefing.id.desc()).first()
    if not b:
        return False
    return _briefing_dict(b)["completo"]


def _briefing_locked(cliente_id: int, briefing_completo: bool, db) -> bool:
    """
    Retorna True se o briefing deve ser somente-leitura.
    Regra: briefing COMPLETO + pelo menos um projeto novo do cliente com etapa 4 concluída.
    Projetos legados (sem cliente_id em projetos_meta) não bloqueiam o briefing.
    """
    if not briefing_completo:
        return False   # briefing incompleto → sempre editável (precisa ser preenchido)
    projetos = db.query(Projeto).filter_by(cliente_id=cliente_id).all()
    if not projetos:
        return False   # nenhum projeto novo → não bloqueia
    for p in projetos:
        etapa4 = db.query(CicloEtapa).filter_by(
            projeto_nome=p.nome_safe, etapa_codigo="4", status="concluido"
        ).first()
        if etapa4:
            return True
    return False


def _marcar_etapa_cliente(cliente_id: int, etapa_codigo: str, db, usuario):
    """Marca uma etapa do ciclo como concluída em todos os projetos vinculados ao cliente."""
    from datetime import datetime as _dt
    projetos = db.query(Projeto).filter_by(cliente_id=cliente_id).all()
    agora = _dt.utcnow()
    uid = usuario["id"] if usuario else None
    for p in projetos:
        etapa = db.query(CicloEtapa).filter_by(
            projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo
        ).first()
        if not etapa:
            etapa = CicloEtapa(projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo)
            db.add(etapa)
        if etapa.status != "concluido":
            etapa.status         = "concluido"
            etapa.concluido_em   = agora
            etapa.responsavel_id = uid
    db.commit()


def _projeto_esta_bloqueado(nome_safe) -> bool:
    """True se o projeto foi aprovado/bloqueado (PROJETOS/<nome>/projeto.json -> 'bloqueado').
    Centraliza o gate pos-aprovacao usado pelos handlers de margens/descontos por orcamento."""
    proj = _carregar_projeto(nome_safe)
    return bool(proj and proj.get("bloqueado"))


def _contrato_assinado(nome_safe, db) -> bool:
    """True se o último contrato do projeto tem qualquer assinatura (1ª assinatura)
    ou status já assinado. Fonte única da trava total pós-assinatura."""
    c = (db.query(Contrato)
           .filter_by(projeto_nome=nome_safe)
           .order_by(Contrato.id.desc())
           .first())
    if not c:
        return False
    if c.status in ("assinado_loja", "assinado_cliente", "assinado", "vigente"):
        return True
    return len(c.assinaturas) > 0


def _contrato_totalmente_assinado(nome_safe, db) -> bool:
    """True somente quando AMBAS as partes assinaram (loja + cliente) — contrato
    totalmente assinado. Usado para esconder o botão 'Assinar Contrato' (nada mais
    a assinar). Difere de _contrato_assinado (que é True já na 1ª assinatura)."""
    c = (db.query(Contrato)
           .filter_by(projeto_nome=nome_safe)
           .order_by(Contrato.id.desc())
           .first())
    if not c:
        return False
    if c.status in ("assinado", "vigente"):
        return True
    return {"loja", "cliente"}.issubset({a.parte for a in c.assinaturas})


def _pool_ambiente_dict(pa) -> dict:
    return {
        "id":            pa.id,
        "projeto_id":    pa.projeto_id,
        "nome":          pa.nome,
        "versao":        pa.versao,
        "nome_exibicao": pa.nome_exibicao,
        "xml_path":      pa.xml_path,
        "budget_total":  pa.budget_total,
        "order_total":   pa.order_total,
        "created_at":    pa.created_at.strftime("%Y-%m-%d %H:%M") if pa.created_at else "",
    }


def _orcamento_dict(o) -> dict:
    return {
        "id":              o.id,
        "projeto_id":      o.projeto_id,
        "nome":            o.nome,
        "ordem":           o.ordem,
        "desconto_pct":    o.desconto_pct    or 0.0,
        "forma_pagamento": o.forma_pagamento or "",
        "valor_total":     o.valor_total     or 0.0,
        "valor_liquido":   o.valor_liquido   or 0.0,
        "created_at":      o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
        "updated_at":      o.updated_at.strftime("%Y-%m-%d %H:%M") if o.updated_at else "",
        "ambientes":       [],  # preenchido por rotas específicas
        # ── modo sombra: derivados do motor de negociação (Task 7) ──
        "sombra": _sombra_dict(o),
    }


def _sombra_dict(o) -> dict:
    """Sub-objeto com os derivados sombra de um orçamento — cadeia completa do motor
    (modo sombra), para o bloco de validação HOJE × NOVO do modal."""
    return {
        "vbvo":         o.vbvo         or 0.0,
        "cfo":          o.cfo          or 0.0,
        "vbno":         o.vbno         or 0.0,
        "vavo":         o.vavo         or 0.0,
        "com_arq_orc":  o.com_arq_orc  or 0.0,
        "pro_fid_orc":  o.pro_fid_orc  or 0.0,
        "cust_ad":      o.cust_ad      or 0.0,
        "val_liq":      o.val_liq      or 0.0,
        "desc_tot_pct": o.desc_tot_pct or 0.0,
        "markup":       o.markup       or 0.0,
        "val_cont":     o.val_cont     or 0.0,
    }


def _negociacao_breakdown(orc, db, params=None, desc_orc=None, descontos_amb=None, total_cliente=None):
    """Calcula a cadeia do motor para um orçamento, SEM gravar. `params`/`desc_orc`/
    `descontos_amb` opcionais sobrepõem o salvo (estado em edição do modal). `total_cliente`
    (da modalidade via mod_fin) define o Cust_Fin; None ⇒ à vista (Cust_Fin=0)."""
    import mod_negociacao
    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
    if params is None:
        params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
    if desc_orc is None:
        desc_orc = orc.desconto_pct or 0.0
    descontos_amb = descontos_amb or {}
    ambs = []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            d_amb = descontos_amb.get(str(lk.pool_ambiente_id),
                                      descontos_amb.get(lk.pool_ambiente_id,
                                                        lk.desconto_individual_pct or 0.0))
            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                         "desc_amb_pct": float(d_amb or 0.0)})
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc)
    if total_cliente is None:
        cust_fin = 0.0
    else:
        cust_fin = max(0.0, float(total_cliente) - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin)
    return d


def _get_usuario_telefone(usuario_id: int, db) -> str:
    """Retorna telefone do usuário ou string vazia se não encontrado."""
    u = db.get(Usuario, usuario_id)
    return (u.telefone or "").strip() if u else ""


def _montar_dados_projeto_para_contrato(nome_safe: str, orcamento_id: int, db) -> tuple:
    """
    Retorna (projeto_dict, cliente_dict, orcamento_dict) para geração do contrato.
    Lança ValueError se dados essenciais estiverem faltando.
    """
    import json as _json
    proj_path = os.path.join(PROJETOS_DIR, nome_safe, "projeto.json")
    if not os.path.exists(proj_path):
        raise ValueError(f"Projeto não encontrado: {nome_safe}")
    with open(proj_path, encoding="utf-8") as f:
        proj = _json.load(f)

    orcamento = db.get(Orcamento, orcamento_id)
    if not orcamento or orcamento.projeto_id != nome_safe:
        raise ValueError(f"Orçamento {orcamento_id} não pertence ao projeto {nome_safe}")

    ambientes_orc = db.query(OrcamentoAmbiente)\
                      .filter_by(orcamento_id=orcamento_id)\
                      .join(PoolAmbiente)\
                      .all()
    nomes_ambientes = [oa.pool_ambiente.nome_exibicao for oa in ambientes_orc]

    cliente_id = proj.get("cliente_id")
    # Fallback: projetos_meta também guarda cliente_id para projetos novos
    if not cliente_id:
        p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
        if p_meta:
            cliente_id = p_meta.cliente_id
    cliente = db.get(Cliente, cliente_id) if cliente_id else None

    projeto_dict = {
        "nome_projeto": proj.get("nome_projeto", nome_safe),
        "criado_em":    proj.get("criado_em", ""),
        "consultor":    proj.get("consultor_nome", ""),
    }
    if cliente:
        cliente_dict = _cliente_dict(cliente)
        # Preenche campos vazios do banco com o que foi salvo no projeto.json
        cli_proj = proj.get("cliente") or {}
        for campo in ("nome", "cpf", "email", "telefone"):
            if not cliente_dict.get(campo) and cli_proj.get(campo):
                cliente_dict[campo] = cli_proj[campo]
    else:
        # Projeto legado sem registro no banco: usa dados do projeto.json
        cli_proj = proj.get("cliente") or {}
        cliente_dict = {
            "nome":     cli_proj.get("nome")  or proj.get("nome_cliente", ""),
            "cpf":      cli_proj.get("cpf")   or "",
            "email":    cli_proj.get("email") or "",
            "telefone": cli_proj.get("telefone") or "",
            "logradouro": "", "numero": "", "complemento": "",
            "bairro": "", "cidade": "", "estado": "", "cep": "",
            "inst_mesmo_residencial": True,
            "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
            "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
        }
    orcamento_dict = {
        "nome":            orcamento.nome,
        "valor_total":     orcamento.valor_total  or 0.0,
        "valor_liquido":   orcamento.valor_liquido or 0.0,
        "forma_pagamento": orcamento.forma_pagamento or "",
        "ambientes":       nomes_ambientes,
    }
    return projeto_dict, cliente_dict, orcamento_dict


def _parceiro_dict(p, db=None) -> dict:
    d = {
        "id":                  p.id,
        "nome":                p.nome,
        "cpf_cnpj":            p.cpf_cnpj            or "",
        "tipo":                p.tipo                 or "",
        "email":               p.email                or "",
        "telefone":            p.telefone             or "",
        "whatsapp":            p.whatsapp             or "",
        "comissao_padrao_pct": p.comissao_padrao_pct  if p.comissao_padrao_pct is not None else 0.0,
        "observacoes":         p.observacoes          or "",
        "abrangencia":         p.abrangencia          or "loja",
        "rede_id":             p.rede_id,
        "criado_em":           p.criado_em.strftime("%Y-%m-%d") if p.criado_em else "",
        "lojas":               [],
    }
    if db is not None:
        vincs = db.query(ParceiroLoja).filter_by(parceiro_id=p.id).all()
        d["lojas"] = [{"loja_id": v.loja_id,
                       "comissao_padrao_pct": v.comissao_padrao_pct or 0.0}
                      for v in vincs]
    return d


def _aplicar_abrangencia_parceiro(db, p, req, ator):
    """Grava abrangencia/rede_id no parceiro e sincroniza os vínculos parceiro_lojas.
    Retorna lista de erros (vazia se ok). Só vincula lojas visíveis ao ator."""
    erros = mod_tenancy.validar_abrangencia_parceiro(req)
    if erros:
        return erros
    abr = (req.get("abrangencia") or "loja").strip()
    p.abrangencia = abr
    if abr == "rede":
        rede_id = req.get("rede_id")
        p.rede_id = rede_id
        # super_admin/admin_rede via política pura; diretor pode a rede da PRÓPRIA loja
        # (spec: o diretor também cria parceiro de abrangência 'rede').
        permitido = mod_tenancy.pode_ver_rede(ator, rede_id)
        if not permitido and ator.get("loja_id") is not None and rede_id is not None:
            loja_ator = db.get(Loja, ator.get("loja_id"))
            permitido = bool(loja_ator and loja_ator.rede_id == rede_id)
        if not permitido:
            return ["Rede fora do seu escopo."]
        db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
        return []
    p.rede_id = None
    lojas_req = req.get("lojas") or []
    db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
    for item in lojas_req:
        lid = item.get("loja_id")
        loja = db.get(Loja, lid) if lid else None
        if not loja or not mod_tenancy.pode_ver_loja(
                ator, {"id": loja.id, "rede_id": loja.rede_id}):
            return [f"Loja {lid} fora do seu escopo."]
        db.add(ParceiroLoja(parceiro_id=p.id, loja_id=lid,
                            comissao_padrao_pct=float(item.get("comissao_padrao_pct") or 0),
                            ativo=1))
    return []


def _rede_dict(r) -> dict:
    return {
        "id":        r.id,
        "nome":      r.nome,
        "cnpj":      r.cnpj or "",
        "ativo":     bool(r.ativo),
        "criado_em": r.criado_em.strftime("%Y-%m-%d") if r.criado_em else "",
    }


def _loja_dict(l) -> dict:
    return {
        "id":          l.id,
        "rede_id":     l.rede_id,
        "nome":        l.nome,
        "cnpj":        l.cnpj        or "",
        "codigo":      l.codigo      or "",
        "telefone":    l.telefone    or "",
        "email":       l.email       or "",
        "cep":         l.cep         or "",
        "logradouro":  l.logradouro  or "",
        "numero":      l.numero      or "",
        "complemento": l.complemento or "",
        "bairro":      l.bairro      or "",
        "cidade":      l.cidade      or "",
        "estado":      l.estado      or "",
        "testemunha1_nome": l.testemunha1_nome or "",
        "testemunha1_cpf":  l.testemunha1_cpf  or "",
        "testemunha2_nome": l.testemunha2_nome or "",
        "testemunha2_cpf":  l.testemunha2_cpf  or "",
        "ativo":       bool(l.ativo),
        "criado_em":   l.criado_em.strftime("%Y-%m-%d") if l.criado_em else "",
    }


def _ator_dict(db, usuario_sessao):
    """Re-consulta o usuário logado no banco para obter nivel/loja_id/rede_id frescos."""
    u = db.get(Usuario, usuario_sessao.get("id"))
    if not u:
        return {"nivel": usuario_sessao.get("nivel"), "loja_id": None, "rede_id": None}
    return {"nivel": u.nivel, "loja_id": u.loja_id, "rede_id": u.rede_id}


def _obj_da_loja(db, Model, pk, loja_id):
    """Retorna o objeto se existir E pertencer à loja `loja_id`; senão None.
    None cobre 'sem id', 'não existe' e 'é de outra loja'."""
    if not pk or loja_id is None:
        return None
    obj = db.get(Model, pk)
    if obj is None or getattr(obj, "loja_id", None) != loja_id:
        return None
    return obj


def _projeto_da_loja(db, nome_safe, loja_id):
    """Retorna o projetos_meta (PK = nome_safe) se pertencer à loja; senão None.
    Ponto de escopo das entidades 'por projeto' (pool/medição/ciclo/contrato).
    Delega em _obj_da_loja para manter uma única fonte da regra de escopo."""
    return _obj_da_loja(db, Projeto, nome_safe, loja_id)


def _parceiro_visivel_loja(db, parceiro, loja_id):
    """True se o parceiro é visível à loja `loja_id` (abrangência 'loja' com vínculo,
    ou 'rede' com a rede da loja)."""
    if parceiro is None or loja_id is None:
        return False
    abr = (getattr(parceiro, "abrangencia", None) or "loja")
    if abr == "loja":
        vin = db.query(ParceiroLoja).filter(
            ParceiroLoja.parceiro_id == parceiro.id,
            ParceiroLoja.loja_id == loja_id).first()
        return vin is not None
    if abr == "rede":
        loja = db.get(Loja, loja_id)
        return loja is not None and loja.rede_id is not None and parceiro.rede_id == loja.rede_id
    return False


def _filtrar_projetos_por_loja(projetos, db, loja_id):
    """Mantém só os projetos cujo projetos_meta.loja_id == loja_id (a lista vem do storage)."""
    nomes = [p.get("nome_safe") for p in projetos if p.get("nome_safe")]
    if not nomes:
        return []
    permitidos = {r[0] for r in db.query(Projeto.nome_safe)
                  .filter(Projeto.nome_safe.in_(nomes), Projeto.loja_id == loja_id).all()}
    return [p for p in projetos if p.get("nome_safe") in permitidos]


def _loja_dict_para_contrato(db, loja_id):
    """Dict plano dos dados da loja para alimentar/snapshotar o contrato (F3).
    Retorna {} se não houver loja resolvível."""
    if not loja_id:
        return {}
    loja = db.get(Loja, loja_id)
    if not loja:
        return {}
    return {
        "id": loja.id,
        "nome": loja.nome or "", "cnpj": loja.cnpj or "", "codigo": loja.codigo or "",
        "telefone": loja.telefone or "", "email": loja.email or "",
        "cep": loja.cep or "", "logradouro": loja.logradouro or "",
        "numero": loja.numero or "", "complemento": loja.complemento or "",
        "bairro": loja.bairro or "", "cidade": loja.cidade or "", "estado": loja.estado or "",
        "testemunha1_nome": loja.testemunha1_nome or "", "testemunha1_cpf": loja.testemunha1_cpf or "",
        "testemunha2_nome": loja.testemunha2_nome or "", "testemunha2_cpf": loja.testemunha2_cpf or "",
    }


# == MAIN ==
def main():
    # Carrega credenciais do omie_config.json automaticamente
    cfg = config_carregar()
    if cfg.get("app_key") and cfg.get("app_secret"):
        _set_credenciais(cfg["app_key"], cfg["app_secret"])
        print("  Credenciais Omie carregadas automaticamente.")
    else:
        print("  Aviso: omie_config.json sem credenciais. Configure na sidebar.")

    init_db()
    try:
        _db_mig = get_session()
        try:
            from database import migrar_margens_para_orcamentos
            migrar_margens_para_orcamentos(_db_mig, PROJETOS_DIR)
        finally:
            _db_mig.close()
    except Exception as _e:
        print("[MIGRACAO] margens->orcamento:", _e)
    try:
        _db_par = get_session()
        try:
            from database import migrar_parametros_para_projeto
            migrar_parametros_para_projeto(_db_par)
        finally:
            _db_par.close()
    except Exception as _e:
        print("[MIGRACAO] parametros->projeto:", _e)
    port   = 8765
    # Host de bind configurável: padrão 127.0.0.1 (dev local seguro);
    # em produção defina OMIE_HOST=0.0.0.0 para aceitar acesso externo.
    host   = os.environ.get("OMIE_HOST", "127.0.0.1")
    server = HTTPServer((host, port), Handler)
    eh_local = host in ("127.0.0.1", "localhost")
    print("\n  Promob -> Omie  |  Negociacao de Margens  v7.3")
    print("  Bind: %s:%d" % (host, port))
    if eh_local:
        url = "http://127.0.0.1:%d" % port
        print("  Acesse: %s" % url)
        # Conveniencia de dev local: abre o navegador. Em producao (OMIE_HOST=0.0.0.0) nao abre.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    else:
        print("  Acesse pelo IP/dominio do servidor na porta %d (bind em %s)" % (port, host))
    print("  Pressione Ctrl+C para encerrar\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
