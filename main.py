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
from database import init_db, get_session, Cliente, Parceiro, Orcamento, PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status, CicloEtapa, Contrato, ContratoAssinatura
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
                          gerar_pdf_contrato, LibreOfficeIndisponivel)

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
            projetos = _listar_projetos()
            _enriquecer_projetos_com_pool(projetos)
            _enriquecer_projetos_com_status(projetos)
            self.send_json({"ok": True, "projetos": projetos})

        elif path == "/projetos/buscar":
            from urllib.parse import parse_qs
            q = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip()
            locais = _buscar_projetos(q)
            for p in locais: p['origem'] = 'local'
            _enriquecer_projetos_com_pool(locais)
            _enriquecer_projetos_com_status(locais)
            omie_res = _buscar_projetos_omie(q)
            nomes_locais = {p['nome_projeto'].lower() for p in locais}
            omie_unicos = [p for p in omie_res if p['nome_projeto'].lower() not in nomes_locais]
            self.send_json({'ok': True, 'projetos': locais + omie_unicos})

        elif path == "/api/clientes":
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                query = db.query(Cliente).order_by(Cliente.nome)
                if q:
                    query = query.filter(
                        (Cliente.nome.ilike(f"%{q}%")) |
                        (Cliente.cpf.ilike(f"%{q}%"))
                    )
                clientes = [_cliente_dict(c) for c in query.all()]
                self.send_json({"ok": True, "clientes": clientes})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "clientes": []})
            finally:
                db.close()

        elif path == "/api/parceiros":
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                query = db.query(Parceiro).order_by(Parceiro.nome)
                if q:
                    query = query.filter(
                        (Parceiro.nome.ilike(f"%{q}%")) |
                        (Parceiro.cpf_cnpj.ilike(f"%{q}%"))
                    )
                parceiros = [_parceiro_dict(p) for p in query.all()]
                self.send_json({"ok": True, "parceiros": parceiros})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "parceiros": []})
            finally:
                db.close()

        elif path == "/api/admin/omie-sync":
            usuario = get_usuario_sessao(self)
            if not usuario or usuario.get("nivel") != "admin":
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
                qs           = parse_qs(urlparse(self.path).query)
                orcamento_id = qs.get("orcamento_id", [None])[0]
                orcamento_id = int(orcamento_id) if orcamento_id else None
                db = get_session()
                try:
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
                db  = get_session()
                try:
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
                            ambientes.append(d)
                    self.send_json({"ok": True, "orcamento_id": oid, "ambientes": ambientes})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m:
                nome_safe = m.group(1)
                print("[ORC] GET orcamentos para projeto_id=%r" % nome_safe)
                db = get_session()
                try:
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
                proj = _carregar_projeto(nome_safe)
                if proj:
                    session_set("projeto_ativo", nome_safe)
                    self.send_json({"ok": True, "projeto": proj})
                else:
                    self.send_json({"ok": False, "erro": "Projeto nao encontrado"}, code=404)
                return

            m = _re.match(r"^/api/clientes/(\d+)$", path)
            if m:
                db = get_session()
                try:
                    c = db.get(Cliente, int(m.group(1)))
                    if c:
                        self.send_json({"ok": True, "cliente": _cliente_dict(c)})
                    else:
                        self.send_json({"ok": False, "erro": "Cliente não encontrado"}, code=404)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/parceiros/(\d+)$", path)
            if m:
                db = get_session()
                try:
                    p = db.get(Parceiro, int(m.group(1)))
                    if p:
                        self.send_json({"ok": True, "parceiro": _parceiro_dict(p)})
                    else:
                        self.send_json({"ok": False, "erro": "Parceiro não encontrado"}, code=404)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/clientes/(\d+)/projetos$", path)
            if m:
                db = get_session()
                try:
                    c = db.get(Cliente, int(m.group(1)))
                    if not c:
                        self.send_json({"ok": False, "erro": "Cliente não encontrado"}, code=404)
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

            m = _re.match(r'^/api/projetos/([^/]+)/ciclo$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
                    etapas = db.query(CicloEtapa)\
                               .filter_by(projeto_nome=nome_safe)\
                               .all()
                    codigos_existentes = {e.etapa_codigo for e in etapas}
                    # Auto-completar etapas 1-5 para projetos que já têm negociação
                    ETAPAS_PRE = ["1","2","3","4","5"]
                    if not any(c in codigos_existentes for c in ETAPAS_PRE):
                        tem_negociacao = db.query(Orcamento).filter(
                            Orcamento.projeto_id == nome_safe,
                            Orcamento.valor_total > 0
                        ).first()
                        if tem_negociacao:
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
                    etapas_sorted = sorted(etapas, key=lambda e: e.etapa_codigo)
                    resultado = [{
                        "etapa_codigo":  e.etapa_codigo,
                        "status":        e.status,
                        "responsavel_id": e.responsavel_id,
                        "iniciado_em":   e.iniciado_em.isoformat() if e.iniciado_em else None,
                        "concluido_em":  e.concluido_em.isoformat() if e.concluido_em else None,
                        "observacoes":   e.observacoes or "",
                    } for e in etapas_sorted]
                    self.send_json({"ok": True, "ciclo": resultado})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                db = get_session()
                try:
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
                db = get_session()
                try:
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
            perfis = perfis_carregar()
            senha_correta = perfis.get("perfis", {}).get("gerente", {}).get("senha_gerente", "1234")
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
            # Carrega dados do cliente do banco para garantir consistência
            db = get_session()
            try:
                c = db.get(Cliente, int(cliente_id))
                if not c:
                    self.send_json({'ok': False, 'erro': 'Cliente não encontrado'})
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
            req  = json.loads(body) if body else {}
            nome = (req.get("nome") or "").strip()
            if not nome:
                self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                return
            cpf = (req.get("cpf") or "").strip() or None
            db  = get_session()
            try:
                if cpf:
                    existente = db.query(Cliente).filter_by(cpf=cpf).first()
                    if existente:
                        self.send_json({"ok": False, "erro": "CPF já cadastrado",
                                        "cliente": _cliente_dict(existente)})
                        return
                c = Cliente(
                    nome       =nome, cpf=cpf,
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

        elif re.match(r"^/api/clientes/(\d+)/editar$", path):
            m_cli = re.match(r"^/api/clientes/(\d+)/editar$", path)
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                c = db.get(Cliente, int(m_cli.group(1)))
                if not c:
                    self.send_json({"ok": False, "erro": "Cliente não encontrado"})
                    return
                campos = ["nome","cpf","email","telefone","whatsapp",
                          "cep","logradouro","numero","complemento",
                          "bairro","cidade","estado","observacoes"]
                for f in campos:
                    if f in req:
                        setattr(c, f, (req[f] or "").strip() or None)
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
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif re.match(r"^/api/parceiros/(\d+)/editar$", path):
            m_par = re.match(r"^/api/parceiros/(\d+)/editar$", path)
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                p = db.get(Parceiro, int(m_par.group(1)))
                if not p:
                    self.send_json({"ok": False, "erro": "Parceiro não encontrado"})
                    return
                for f in ["nome","cpf_cnpj","tipo","email","telefone","whatsapp","observacoes"]:
                    if f in req:
                        setattr(p, f, (req[f] or "").strip() or None)
                if "comissao_padrao_pct" in req:
                    p.comissao_padrao_pct = float(req["comissao_padrao_pct"] or 0)
                if "nome" in req and not p.nome:
                    self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                    return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        else:
            import re as _re

            # ── POST /projetos/<nome_safe>/orcamentos — criar novo orçamento ─────────
            m_novo_orc = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m_novo_orc:
                nome_safe = m_novo_orc.group(1)
                db = get_session()
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
                    _usuario = get_usuario_sessao(self)
                    orc = Orcamento(
                        projeto_id=nome_safe,
                        nome=      nome_orc,
                        ordem=     proxima_ordem,
                        created_by=_usuario['id'] if _usuario else None,
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

                # Hash do conteúdo (ignora campos derivados do nome do arquivo)
                def _content_hash(a):
                    c = {"total": a.get("total"), "grupos": a.get("grupos", [])}
                    return hashlib.sha256(
                        json.dumps(c, sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                hash_novo = _content_hash(amb)

                db = get_session()
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
                            budget_total=  budget_total,
                            order_total=   order_total,
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
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para sobrescrita"})
                    return
                db = get_session()
                try:
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    # Atualiza o registro no pool
                    pa.xml_path      = os.path.join("xmls", temp["arq_nome"])
                    pa.ambientes_json = json.dumps(temp["amb"])
                    pa.budget_total  = temp["budget_total"]
                    pa.order_total   = temp["order_total"]
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
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para nova versão"})
                    return
                db = get_session()
                try:
                    pa_orig = db.get(PoolAmbiente, pid)
                    if not pa_orig or pa_orig.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    nova_versao      = pa_orig.versao + 1
                    # versao=2 → "_v1", versao=3 → "_v2" ...
                    nome_exib_novo   = "%s_v%d" % (pa_orig.nome, nova_versao - 1)
                    arq_nome_novo    = "%s.xml" % nome_exib_novo
                    _usuario = get_usuario_sessao(self)
                    pa_novo = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          pa_orig.nome,
                        versao=        nova_versao,
                        nome_exibicao= nome_exib_novo,
                        xml_path=      os.path.join("xmls", arq_nome_novo),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=  temp["budget_total"],
                        order_total=   temp["order_total"],
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
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
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
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente"})
                    return
                db = get_session()
                try:
                    _usuario = get_usuario_sessao(self)
                    pa = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          temp["nome_base"],
                        versao=        1,
                        nome_exibicao= temp["nome_base"],
                        xml_path=      os.path.join("xmls", temp["arq_nome"]),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=  temp["budget_total"],
                        order_total=   temp["order_total"],
                        created_by=    _usuario['id'] if _usuario else None,
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
                db  = get_session()
                try:
                    orc = db.get(Orcamento, oid)
                    if not orc:
                        self.send_json({"ok": False, "erro": "Orçamento não encontrado"})
                        return
                    pa = db.get(PoolAmbiente, pid)
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

            # ── POST /orcamentos/<oid>/ambientes/<pid> — adicionar ambiente ──────────
            m_add = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)$", path)
            if m_add:
                oid = int(m_add.group(1))
                pid = int(m_add.group(2))
                db  = get_session()
                try:
                    orc = db.get(Orcamento, oid)
                    if not orc:
                        self.send_json({"ok": False, "erro": "Orçamento não encontrado"})
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != orc.projeto_id:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado neste projeto"})
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

            # Rota: POST /projetos/<nome_safe>/margens
            m_mar = _re.match(r"^/projetos/([^/]+)/margens$", path)
            if m_mar:
                nome_safe = m_mar.group(1)
                req  = json.loads(body)
                proj = _carregar_projeto(nome_safe)
                if not proj:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado"})
                    return
                if proj.get("bloqueado"):
                    self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."})
                    return
                # Merge: preserva campos existentes e atualiza os enviados
                m_atual = proj.get("margens") or {}
                m_atual.update({
                    "desconto_pct":          float(req.get("desconto_pct",          m_atual.get("desconto_pct", 0))),
                    "custo_financeiro_pct":  float(req.get("custo_financeiro_pct",  m_atual.get("custo_financeiro_pct", 0))),
                    "fora_da_sede":          bool( req.get("fora_da_sede",           m_atual.get("fora_da_sede", False))),
                    "custo_viagem":       float(req.get("custo_viagem",        m_atual.get("custo_viagem", 0))),
                    "brinde":             float(req.get("brinde",              m_atual.get("brinde", 0))),
                    "brinde_ativo":       bool( req.get("brinde_ativo",        m_atual.get("brinde_ativo", False))),
                    "comissao_arq_pct":   float(req.get("comissao_arq_pct",   m_atual.get("comissao_arq_pct", 0))),
                    "comissao_arq_ativa": bool( req.get("comissao_arq_ativa",  m_atual.get("comissao_arq_ativa", False))),
                    "fidelidade_pct":     float(req.get("fidelidade_pct",     m_atual.get("fidelidade_pct", 0))),
                    "fidelidade_ativa":   bool( req.get("fidelidade_ativa",    m_atual.get("fidelidade_ativa", False))),
                    "incluir_custos":     bool( req.get("incluir_custos",      m_atual.get("incluir_custos", False))),
                    "carga_trib":         float(req.get("carga_trib",          m_atual.get("carga_trib", 8.0))),
                })
                proj["margens"] = m_atual
                _salvar_projeto(proj)
                self.send_json({"ok": True, "margens": proj["margens"]})
                return

            m_sync = _re.match(r"^/api/admin/omie-sync/(\d+)/retry$", path)
            if m_sync:
                usuario = get_usuario_sessao(self)
                if not usuario or usuario.get("nivel") != "admin":
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
                db = get_session()
                try:
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                    if not autorizador or not autorizador.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Credenciais inválidas"})
                        return
                    if autorizador.nivel not in ("gerente", "diretor", "admin"):
                        self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"})
                        return
                    # Verifica se contrato está assinado — nesse caso não pode voltar
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if contrato and contrato.status in ("assinado", "vigente"):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível voltar ao orçamento"})
                        return
                    # Resetar etapa 6 (e 7 se existir sem assinatura)
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
                        contrato.status = "assinado"
                        etapa7 = db.query(CicloEtapa).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="7"
                        ).first()
                        if not etapa7:
                            etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                            db.add(etapa7)
                        etapa7.status       = "assinado"
                        etapa7.concluido_em = datetime.utcnow()
                        etapa7.responsavel_id = usuario["id"]
                    elif parte == "loja":
                        contrato.status = "assinado_loja"
                    else:
                        contrato.status = "assinado_cliente"
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status, "parte": parte})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato — gera PDF do contrato
            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req                  = json.loads(body)
                orcamento_id         = req.get("orcamento_id")
                endereco_instalacao  = (req.get("endereco_instalacao") or "").strip()
                entrada_valor        = float(req.get("entrada_valor") or 0)
                parcelas_descricao   = req.get("parcelas_descricao") or ""
                adendo               = req.get("adendo") or ""
                if not orcamento_id:
                    self.send_json({"ok": False, "erro": "orcamento_id obrigatório"}, code=400)
                    return
                db = get_session()
                try:
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)
                    variaveis = montar_variaveis_contrato(
                        projeto=projeto_dict,
                        cliente=cliente_dict,
                        orcamento=orcamento_dict,
                        endereco_instalacao=endereco_instalacao,
                        entrada_valor=entrada_valor,
                        parcelas_descricao=parcelas_descricao,
                        adendo=adendo,
                    )
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        contrato = Contrato(projeto_nome=nome_safe, orcamento_id=orcamento_id)
                        db.add(contrato)
                        db.flush()
                    contrato.endereco_instalacao = endereco_instalacao
                    contrato.adendo              = adendo
                    contrato.gerado_em           = datetime.utcnow()
                    contrato.gerado_por_id       = usuario["id"]
                    contrato.status              = "rascunho"
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
                orc = db.get(Orcamento, oid)
                if not orc or orc.projeto_id != nome_safe:
                    self.send_json({"ok": False, "erro": "Orçamento não encontrado"})
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
                req = json.loads(body)
                db = get_session()
                try:
                    orc = db.get(Orcamento, oid)
                    if not orc:
                        self.send_json({"ok": False, "erro": "Orçamento não encontrado"}, code=404)
                        return
                    if "valor_total" in req:
                        orc.valor_total = float(req["valor_total"] or 0)
                    if "forma_pagamento" in req:
                        orc.forma_pagamento = req["forma_pagamento"] or None
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
                db = get_session()
                try:
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod
                    ).first()
                    if not etapa:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    if novo_status:
                        if etapa.status == "pendente" and novo_status != "pendente":
                            etapa.iniciado_em = datetime.utcnow()
                        etapa.status = novo_status
                        if novo_status in ("concluido", "aprovado", "assinado", "vigente",
                                           "implantado", "realizado", "entregue", "emitida"):
                            etapa.concluido_em  = datetime.utcnow()
                            etapa.responsavel_id = usuario["id"]
                    if obs is not None:
                        etapa.observacoes = obs
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
                    variaveis = montar_variaveis_contrato(
                        projeto=projeto_dict, cliente=cliente_dict,
                        orcamento=orcamento_dict,
                        endereco_instalacao=contrato.endereco_instalacao or "",
                        entrada_valor=0.0, parcelas_descricao="",
                        adendo=adendo,
                    )
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            self.send_json({"ok": False, "erro": "Rota não encontrada"})
        except Exception as e:
            self.send_json({"ok": False, "erro": str(e)})


# ── Helper ────────────────────────────────────────────────────────────────────
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
        "omie_codigo":       c.omie_codigo or "",
        "omie_sync_status":  c.omie_sync_status or "",
        "omie_sync_erro":    c.omie_sync_erro   or "",
        "omie_sync_at":      c.omie_sync_at.isoformat() if c.omie_sync_at else "",
        "criado_em":   c.criado_em.strftime("%Y-%m-%d") if c.criado_em else "",
    }


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
    }


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
    cliente = db.get(Cliente, cliente_id) if cliente_id else None

    projeto_dict = {
        "nome_projeto": proj.get("nome_projeto", nome_safe),
        "criado_em":    proj.get("criado_em", ""),
        "consultor":    proj.get("consultor_nome", ""),
    }
    cliente_dict = {
        "nome":       cliente.nome       if cliente else proj.get("nome_cliente", ""),
        "cpf":        cliente.cpf        if cliente else "",
        "telefone":   cliente.telefone   if cliente else "",
        "logradouro": cliente.logradouro if cliente else "",
        "numero":     cliente.numero     if cliente else "",
        "bairro":     cliente.bairro     if cliente else "",
        "cidade":     cliente.cidade     if cliente else "",
        "estado":     cliente.estado     if cliente else "",
    }
    orcamento_dict = {
        "nome":            orcamento.nome,
        "valor_total":     orcamento.valor_total  or 0.0,
        "valor_liquido":   orcamento.valor_liquido or 0.0,
        "forma_pagamento": orcamento.forma_pagamento or "",
        "ambientes":       nomes_ambientes,
    }
    return projeto_dict, cliente_dict, orcamento_dict


def _parceiro_dict(p) -> dict:
    return {
        "id":                  p.id,
        "nome":                p.nome,
        "cpf_cnpj":            p.cpf_cnpj            or "",
        "tipo":                p.tipo                 or "",
        "email":               p.email                or "",
        "telefone":            p.telefone             or "",
        "whatsapp":            p.whatsapp             or "",
        "comissao_padrao_pct": p.comissao_padrao_pct  if p.comissao_padrao_pct is not None else 0.0,
        "observacoes":         p.observacoes          or "",
        "criado_em":           p.criado_em.strftime("%Y-%m-%d") if p.criado_em else "",
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
    port   = 8765
    server = HTTPServer(("127.0.0.1", port), Handler)
    url    = "http://127.0.0.1:%d" % port
    print("\n  Promob -> Omie  |  Negociacao de Margens  v7.3")
    print("  Acesse: %s" % url)
    print("  Pressione Ctrl+C para encerrar\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
