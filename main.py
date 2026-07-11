"""
main.py — Servidor HTTP, rotas e inicialização.
Ponto de entrada da aplicação: python main.py
"""
import os, io, json, time, re, threading, webbrowser, hashlib, uuid
import sys
import logging
import email
from email import policy as _email_policy
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
from database import (init_db, get_session, Cliente, Parceiro, Orcamento,
                       PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status,
                       CicloEtapa, Contrato, ContratoAssinatura, Usuario, Briefing,
                       LogAcaoGerencial, Medicao, Rede, Loja, ParceiroLoja,
                       membership_loja_ids, UsuarioLoja, ProvisaoRegistro,
                       CicloDocumento, CicloRevisao, DocumentoFiscal, Emitente,
                       PerfilEmissao, CicloLogistico, CicloLogisticoTransicao, AssistenciaCaso,
                       Funcionario, Fornecedor, Terceiro, Funcao, FolhaPagamento,
                       AtribuicaoAmbiente)
import mod_expedicao
import mod_assistencias
import mod_cadastro
import mod_folha
import mod_escopo
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
from mod_margens import _normalizar_faixas
from mod_fin import calcular_aymore, calcular_cartao, calcular_venda_programada, calcular_total_flex
from mod_contrato import (calcular_hash_assinatura,
                          gerar_pdf_contrato,
                          construir_contexto, _formatar_valor)
import mod_ciclo
import mod_medicao
import perfis
import mod_usuarios
import mod_tenancy
import mod_arvore
import mod_provisoes
import mod_proposta
from mod_qualidade_xml import avaliar_qualidade_xml

def _enriquecer_projetos_com_status(projetos):
    """Adiciona status, ultimo_orcamento_valor e o consultor (criador) a cada projeto da lista."""
    if not projetos:
        return
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        metas = db.query(Projeto).filter(Projeto.nome_safe.in_(nomes)).all()
        meta_map = {m.nome_safe: m for m in metas}

        # Consultor = usuário que criou o projeto (projetos_meta.criado_por_id).
        cons_ids = {m.criado_por_id for m in metas if getattr(m, "criado_por_id", None)}
        cons_map = ({u.id: u.nome for u in db.query(Usuario).filter(Usuario.id.in_(cons_ids)).all()}
                    if cons_ids else {})

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
            cpid = getattr(meta, "criado_por_id", None) if meta else None
            p['consultor_id']           = cpid
            p['consultor_nome']         = cons_map.get(cpid)
    finally:
        db.close()

def _enriquecer_projetos_com_parceiro(projetos):
    """Resolve o nome do parceiro (arquiteto) de cada projeto a partir do parceiro_id já presente no item."""
    if not projetos:
        return
    ids = {p.get("parceiro_id") for p in projetos if p.get("parceiro_id")}
    if not ids:
        return
    db = get_session()
    try:
        nomes = {pr.id: pr.nome for pr in db.query(Parceiro).filter(Parceiro.id.in_(ids)).all()}
        for p in projetos:
            pid = p.get("parceiro_id")
            p["parceiro_nome"] = nomes.get(pid) if pid else None
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

# Consultor responsável do projeto (criado_por_id) — atribuição por gerente+ ------------------
# Quem pode ser "consultor responsável" (Perfil-4): perfis de loja com acesso operacional.
_NIVEIS_ATRIBUIVEIS = tuple(s for s in perfis.slugs_loja() if perfis.pode(s, "acesso_operacional"))

def _usuario_pertence_a_loja(db, u, loja_id):
    """True se o usuário `u` está ligado à loja (loja_id direto ou vínculo UsuarioLoja)."""
    if u is None or not loja_id:
        return False
    if u.loja_id == loja_id:
        return True
    return db.query(UsuarioLoja).filter_by(usuario_id=u.id, loja_id=loja_id).first() is not None

def _usuarios_atribuiveis_da_loja(db, loja_id):
    """Usuários ATIVOS da loja que podem ser consultor responsável (para o seletor). Ordenados por nome."""
    if not loja_id:
        return []
    from sqlalchemy import or_
    vinc_ids = {r[0] for r in db.query(UsuarioLoja.usuario_id)
                .filter(UsuarioLoja.loja_id == loja_id).all()}
    conds = [Usuario.loja_id == loja_id]
    if vinc_ids:
        conds.append(Usuario.id.in_(vinc_ids))
    us = (db.query(Usuario).filter(Usuario.ativo == 1).filter(or_(*conds)).all())
    us = [u for u in us if u.nivel in _NIVEIS_ATRIBUIVEIS]
    return sorted(us, key=lambda u: (u.nome or "").lower())

# Cadastro (Modulos_Orizon_v9): entidade -> (Model, serialize, aplicar) para dispatch genérico
def _cad_ent(nome):
    return {
        "funcionarios": (Funcionario, mod_cadastro.func_serialize, mod_cadastro.func_aplicar),
        "fornecedores": (Fornecedor,  mod_cadastro.forn_serialize, mod_cadastro.forn_aplicar),
        "terceiros":    (Terceiro,    mod_cadastro.terc_serialize, mod_cadastro.terc_aplicar),
        "funcoes":      (Funcao,      mod_cadastro.funcao_serialize, mod_cadastro.funcao_aplicar),
    }[nome]

# HTML servido como arquivo estático
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

def _serve_html():
    path = os.path.join(_STATIC_DIR, "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()

# Omie em descontinuação: auto-sincronização de cliente no cadastro DESLIGADA por padrão.
# Reative com a env OMIE_AUTO_SYNC=1 (a sincronização manual "Tentar" na fila segue funcionando).
_OMIE_AUTO_SYNC = os.environ.get("OMIE_AUTO_SYNC", "").strip().lower() in ("1", "true", "on", "sim")


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


_STEPUP_GRANTS = {}   # {(token, recurso): expira_em_epoch}
_STEPUP_TTL = 30 * 60


def _stepup_conceder(token, recurso):
    _STEPUP_GRANTS[(token, recurso)] = time.time() + _STEPUP_TTL


def _stepup_valido(token, recurso):
    exp = _STEPUP_GRANTS.get((token, recurso))
    if exp and exp > time.time():
        return True
    if exp:
        _STEPUP_GRANTS.pop((token, recurso), None)
    return False


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


def _contabil_ctx(handler, exige_edicao):
    """(usuario, db, owner_tipo, owner_id) ou envia erro via handler.send_json e retorna None.
    Gate: módulo financeiro ativo na loja; edição exige aprovar_financeiro OU editar_dados_loja.
    O chamador é responsável por db.close()."""
    import mod_contabil, mod_tenancy
    usuario = get_usuario_sessao(handler)
    if not usuario:
        handler.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return None
    db = get_session()
    # Perfil-4 (rev2 §2): só perfis com acesso ao Financeiro abrem o módulo (Diretoria).
    if _sem_acesso_modulo(usuario, "financeiro", handler=handler):
        db.close(); handler.send_json({"ok": False, "erro": "Sem acesso ao módulo Financeiro.", "precisa_stepup": "financeiro"}, code=403); return None
    loja = db.get(Loja, usuario.get("loja_id")) if usuario.get("loja_id") else None
    if loja is not None and not mod_tenancy.modulo_ativo(loja, "financeiro"):
        db.close(); handler.send_json({"ok": False, "erro": "Módulo financeiro inativo."}, code=403); return None
    if exige_edicao:
        niv = usuario.get("nivel")
        if not (perfis.pode(niv, "aprovar_financeiro") or perfis.pode(niv, "editar_dados_loja")):
            db.close(); handler.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return None
    try:
        ot, oid = mod_contabil.resolver_owner(db, usuario)
    except ValueError as e:
        db.close(); handler.send_json({"ok": False, "erro": str(e)}, code=400); return None
    return usuario, db, ot, oid


def _parse_data(s):
    """String ISO ('2026-07-09' ou datetime completo) -> datetime, ou None."""
    if not s:
        return None
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(s)
    except ValueError:
        try:
            return _dt.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None


def _fin_evento_seguro(loja_id, tipo_evento, valor, projeto_id, ref):
    """Wiring evento→lançamento a partir de um fluxo de negócio (contrato/NF-e).
    **Fail-soft e isolado**: usa sessão própria e NUNCA levanta — contabilidade não pode abortar o
    fluxo. **Idempotente** por `ref`. Só dispara se o módulo financeiro está ativo na loja."""
    try:
        if not loja_id or valor is None or float(valor) <= 0:
            return
        import mod_contabil, mod_tenancy
        db = get_session()
        try:
            loja = db.get(Loja, loja_id)
            if loja is None or not mod_tenancy.modulo_ativo(loja, "financeiro"):
                return
            ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
            mod_contabil.registrar_evento(db, ot, oid, tipo_evento, float(valor),
                                          projeto_id=projeto_id, ref=ref)
        finally:
            db.close()
    except Exception as e:
        logging.getLogger(__name__).warning("wiring financeiro (%s, ref=%s) falhou: %s", tipo_evento, ref, e)


def _fin_provisoes_venda_seguro(orc, projeto_id, ref_base):
    """Auto-constitui as 3 provisões contábeis no fechamento da venda (v6 §6.4), base = **VAVO** do
    orçamento (`orc.vavo` — valor à vista, convenção canônica das provisões % sobre a venda; NÃO
    `valor_total`/Val_Cont, senão diverge da linha da modal/motor quando Cust_Fin>0), a partir do %
    do Financeiro da loja. **Fail-soft/isolado/idempotente** — não aborta o contrato."""
    try:
        loja_id = getattr(orc, "loja_id", None)
        vavo = float(getattr(orc, "vavo", 0) or 0)
        if not loja_id or vavo <= 0:
            return
        import mod_contabil, mod_tenancy
        db = get_session()
        try:
            loja = db.get(Loja, loja_id)
            if loja is None or not mod_tenancy.modulo_ativo(loja, "financeiro"):
                return
            cfg = json.loads(loja.config_financeira_json) if loja.config_financeira_json else {}
            ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
            mod_contabil.constituir_provisoes_venda(db, ot, oid, projeto_id, vavo, cfg, ref_base)
        finally:
            db.close()
    except Exception as e:
        logging.getLogger(__name__).warning("wiring provisões da venda (ref=%s) falhou: %s", ref_base, e)


_REQ_LOJA_ATIVA = None   # header X-Loja-Ativa da requisição atual (HTTPServer single-thread)

def _ler_loja_ativa_header(handler):
    raw = (handler.headers.get("X-Loja-Ativa") or "").strip()
    return int(raw) if raw.isdigit() else None


def mod_perfis_opcoes():
    import modulos, mod_perfis
    doms = [{"id": d["id"], "rotulo": d["rotulo"]} for d in modulos.dominios_com_rotulo()]
    return {"dominios": doms, "paineis": [{"id": "admin", "rotulo": "Painel Administração"},
                                          {"id": "config", "rotulo": "Painel Config"}]}


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
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path = urlparse(self.path).path
        if handle_auth_get(self, path): return
        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            inc = (parse_qs(urlparse(self.path).query).get("incluir_inativas") or ["0"])[0] == "1"
            try:
                contas = mod_contabil.listar_contas(db, ot, oid, incluir_inativas=inc)
                self.send_json({"ok": True, "contas": contas})
            finally:
                db.close()
            return
        if path == "/api/financeiro/lancamentos":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            proj = (qs.get("projeto") or [None])[0]
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                lans = mod_contabil.listar_lancamentos(db, ot, oid, projeto_id=proj, ini=ini, fim=fim)
                self.send_json({"ok": True, "lancamentos": lans})
            finally:
                db.close()
            return
        m_razao = re.match(r"^/api/financeiro/contas/(\d+)/razao$", path)
        if m_razao:
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                r = mod_contabil.razao(db, ot, oid, int(m_razao.group(1)), ini=ini, fim=fim)
                self.send_json({"ok": True, "razao": r})
            except (ValueError, PermissionError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400 if isinstance(e, ValueError) else 403)
            finally:
                db.close()
            return
        if path == "/api/financeiro/dre":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                self.send_json({"ok": True, "dre": mod_contabil.dre(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/projetos-dre":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                self.send_json({"ok": True, "projetos": mod_contabil.margem_todos_projetos(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/periodos":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                self.send_json({"ok": True, "periodos": mod_contabil.listar_periodos(db, ot, oid)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/balanco":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            data = _parse_data((parse_qs(urlparse(self.path).query).get("data") or [None])[0])
            try:
                self.send_json({"ok": True, "balanco": mod_contabil.balanco(db, ot, oid, data_corte=data)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/repasse-fabrica":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0]); fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                self.send_json({"ok": True, "repasse": mod_contabil.total_a_cobrar_fabrica(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/provisoes-venda":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            proj = (parse_qs(urlparse(self.path).query).get("projeto") or [None])[0]
            try:
                if not proj:
                    self.send_json({"ok": False, "erro": "informe ?projeto="}, code=400)
                else:
                    self.send_json({"ok": True, "provisoes_venda": mod_contabil.provisoes_da_venda(db, ot, oid, proj)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/dashboard":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                self.send_json({"ok": True, "dashboard": mod_contabil.dashboard_financeiro(db, ot, oid)})
            finally:
                db.close()
            return
        if path == "/api/expedicao/kanban":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "expedicao"):
                    self.send_json({"ok": False, "erro": "Módulo Expedição inativo."}, code=403); return
                proj_cli = {p.nome_safe: p.cliente_id for p in db.query(Projeto).filter_by(loja_id=lid).all()}
                cli_nome = {c.id: c.nome for c in db.query(Cliente).filter_by(loja_id=lid).all()}
                idx = {s: i for i, s in enumerate(mod_expedicao.STATUS)}
                colunas = [{"status": s, "cards": []} for s in mod_expedicao.STATUS]
                for card in db.query(CicloLogistico).filter_by(loja_id=lid).all():
                    if card.status_atual not in idx:
                        continue
                    cnome = cli_nome.get(proj_cli.get(card.projeto_nome))
                    colunas[idx[card.status_atual]]["cards"].append(mod_expedicao.card_kanban(card, cnome))
                self.send_json({"ok": True, "colunas": colunas,
                                "meta": {"status": mod_expedicao.STATUS,
                                         "captura": mod_expedicao.REALIZADO_AO_ENTRAR,
                                         "campos_prazo": mod_expedicao.CAMPOS_PRAZO,
                                         "campos_realizado": mod_expedicao.CAMPOS_REALIZADO}})
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                p = db.query(Projeto).filter_by(nome_safe=card.projeto_nome).first()
                cli = db.get(Cliente, p.cliente_id) if p and p.cliente_id else None
                self.send_json({"ok": True, "card": mod_expedicao.card_detalhe(db, card, cli.nome if cli else "")})
            finally:
                db.close()
            return

        if path == "/api/assistencias/casos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "assistencias"):
                    self.send_json({"ok": False, "erro": "Módulo Assistências inativo."}, code=403); return
                from urllib.parse import parse_qs
                tipo = (parse_qs(urlparse(self.path).query).get("tipo") or [""])[0].strip()
                self.send_json({"ok": True,
                                "casos": mod_assistencias.listar(db, lid, tipo or None),
                                "a_cobrar_fabrica": mod_assistencias.a_cobrar_fabrica(db, lid),
                                "meta": mod_assistencias.meta()})
            finally:
                db.close()
            return

        # ── Folha de Pagamento (Modulos_Orizon_v10 §2.1) — folha do período ──────────────
        if path == "/api/folha":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if _sem_acesso_modulo(usuario, "folha", handler=self):
                self.send_json({"ok": False, "erro": "Sem acesso ao módulo Folha.", "precisa_stepup": "folha"}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                from urllib.parse import parse_qs
                comp = (parse_qs(urlparse(self.path).query).get("competencia") or [""])[0].strip()
                if not re.match(r'^\d{4}-\d{2}$', comp):
                    self.send_json({"ok": False, "erro": "Informe a competência AAAA-MM."}, code=400); return
                self.send_json({"ok": True, "folha": mod_folha.listar(db, loja_id, comp)})
            finally:
                db.close()
            return

        # ── Cadastro (Modulos_Orizon_v9/v10): listas Funcionários/Fornecedores/Terceiros/Funções ──
        m = re.match(r'^/api/(funcionarios|fornecedores|terceiros|funcoes)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                Model, ser, _ = _cad_ent(m.group(1))
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                q = (qs.get("q") or [""])[0].strip()
                status = (qs.get("status") or [""])[0].strip()
                itens = mod_cadastro.listar(db, Model, ser, loja_id, q or None, status or None)
                # Filtro por função (Modulos_Orizon_v12): dropdown de responsável do Cronograma lista
                # só funcionários da função exigida pela fase.
                funcao_id = (qs.get("funcao_id") or [""])[0].strip()
                if funcao_id:
                    try:
                        fid = int(funcao_id)
                        itens = [x for x in itens if x.get("funcao_id") == fid]
                    except ValueError:
                        pass
                self.send_json({"ok": True, "meta": mod_cadastro.META, "itens": itens})
            finally:
                db.close()
            return
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
                projetos = _filtrar_projetos_por_loja(projetos, db, loja_id, ator=usuario)
                _enriquecer_projetos_com_pool(projetos)
                _enriquecer_projetos_com_status(projetos)
                _enriquecer_projetos_com_parceiro(projetos)
                self.send_json({"ok": True, "projetos": projetos})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path == "/api/projetos/consultores":
            # Seletor de consultor responsável (criação/edição). `pode_atribuir` = gerente+ (não escopo-próprio).
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
                pode = not _ve_apenas_proprios_projetos(usuario.get("nivel"))
                us = _usuarios_atribuiveis_da_loja(db, loja_id)
                self.send_json({"ok": True, "pode_atribuir": pode,
                                "consultores": [{"id": u.id, "nome": u.nome, "nivel": u.nivel} for u in us]})
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
                locais = _filtrar_projetos_por_loja(locais, db, loja_id, ator=usuario)
                for p in locais: p['origem'] = 'local'
                _enriquecer_projetos_com_pool(locais)
                _enriquecer_projetos_com_status(locais)
                _enriquecer_projetos_com_parceiro(locais)
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
                vis_ids = [u.id for u in visiveis]
                memb = {}
                if vis_ids:
                    for uid, lid in db.query(UsuarioLoja.usuario_id, UsuarioLoja.loja_id).filter(
                            UsuarioLoja.usuario_id.in_(vis_ids)).all():
                        memb.setdefault(uid, []).append(lid)
                # Função (cargo) = do Funcionário vinculado (funcionario_id → Funcao); para contas SEM
                # Funcionário, cai em Usuario.funcao_id (Perfil-4: cargo migrado do nível antigo).
                # Perfil = nivel (acesso). Os dois eixos separados.
                func_ids = {u.funcionario_id for u in visiveis if u.funcionario_id}
                funcs = {f.id: f for f in db.query(Funcionario).filter(Funcionario.id.in_(func_ids)).all()} \
                    if func_ids else {}
                funcao_ids = {f.funcao_id for f in funcs.values() if f.funcao_id} \
                    | {u.funcao_id for u in visiveis if u.funcao_id}
                funcoes_map = {fn.id: fn.nome for fn in db.query(Funcao).filter(Funcao.id.in_(funcao_ids)).all()} \
                    if funcao_ids else {}
                def _funcao_nome(u):
                    f = funcs.get(u.funcionario_id) if u.funcionario_id else None
                    if f and f.funcao_id:
                        return funcoes_map.get(f.funcao_id, "")
                    return funcoes_map.get(u.funcao_id, "") if u.funcao_id else ""
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "whatsapp": u.whatsapp or "", "email": u.email or "", "cpf": u.cpf or "",
                     "loja_id": u.loja_id, "rede_id": u.rede_id,
                     "loja_ids": memb.get(u.id, []),
                     "funcao_nome": _funcao_nome(u),
                     "ativo": bool(u.ativo)} for u in visiveis]})
            finally:
                db.close()

        elif path == "/api/admin/perfis-matriz":
            # Admin › Perfis de Usuário: matriz perfil × capacidades da LOJA do ator (Task 7),
            # DB-backed via perfis.matriz_loja. Gate: gerir_usuarios (mesma audiência de Usuários).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            lid = usuario.get("loja_id")
            _m = perfis.matriz_loja(lid)
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "caps_selecionaveis": _m["caps_selecionaveis"],
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})

        elif path == "/api/admin/perfis":
            # CRUD de perfis de acesso configuráveis por loja (Task 7). Leitura: gerir_usuarios;
            # criação/edição (POST/PATCH abaixo): gerir_perfis (só Master).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            _m = perfis.matriz_loja(usuario.get("loja_id"))
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "caps_selecionaveis": _m["caps_selecionaveis"],
                            "modulos_opcoes": mod_perfis_opcoes(),
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})

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

        elif path.startswith("/api/admin/lojas/") and path.endswith("/config-financeira"):
            import re as _re, mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            m = _re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                # Merge com o default preenche chaves novas (ex.: cronograma_padrao, v11) em lojas
                # cujo config foi salvo antes da chave existir — sem apagar valores já configurados.
                _stored = json.loads(loja.config_financeira_json) if loja.config_financeira_json else {}
                cfg = {**mod_provisoes.config_financeira_default(), **_stored}
                self.send_json({"ok": True, "config": cfg})
            finally:
                db.close()

        elif path.startswith("/api/admin/lojas/") and path.endswith("/projetos"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            m = _re.match(r"^/api/admin/lojas/(\d+)/projetos$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                projetos = mod_arvore.projetos_estruturais(db, ator, int(m.group(1)))
                self.send_json({"ok": True, "projetos": projetos})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path.startswith("/api/admin/projetos/") and path.endswith("/etapas"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            m = _re.match(r"^/api/admin/projetos/(.+)/etapas$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                etapas = mod_arvore.etapas_do_projeto(db, ator, unquote(m.group(1)))
                self.send_json({"ok": True, "etapas": etapas})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
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
                    desconto_pct = (orc.desconto_pct or 0.0) if orc else 0.0
                    negociacao = json.loads(orc.negociacao_json) if (orc and orc.negociacao_json) else None
                    parametros = {}
                    if orc:
                        _p = db.get(Projeto, orc.projeto_id)
                        if _p and _p.parametros_json:
                            parametros = json.loads(_p.parametros_json)   # respeita o salvo (edições persistem)
                        else:
                            # projeto sem params salvos: valores iniciais (defaults da loja +
                            # arquiteto/fidelidade do parceiro, se houver)
                            parametros = _params_iniciais_projeto(db, orc.projeto_id, orc.loja_id)
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "desconto_pct": desconto_pct, "negociacao": negociacao,
                                    "parametros": parametros, "ambientes": ambientes})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── GET /api/orcamentos/<id>/provisoes — versões + atual + desatualizado ──
            m = _re.match(r"^/api/orcamentos/(\d+)/provisoes$", path)
            if m:
                # NOTE: bare `mod_provisoes` vira local no do_GET (import local num elif adiante);
                # usar alias evita UnboundLocalError.
                import mod_provisoes as _mprov
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                oid = int(m.group(1))
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

                    def _reg(versao):
                        r = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                        if not r:
                            return None
                        return {"itens": json.loads(r.itens_json), "cfo": r.cfo, "val_liq": r.val_liq,
                                "cust_var": r.cust_var, "marg_cont": r.marg_cont, "decisao": r.decisao,
                                "criado_em": r.criado_em.isoformat() if r.criado_em else None}

                    venda = _reg("venda")
                    d = _negociacao_breakdown(orc, db)
                    atual = {"itens": _mprov.itens_provisao(d),
                             "cfo": float(d.get("CFO") or 0),
                             "val_liq": float(d.get("Val_Liq") or 0),
                             "cust_var": float(d.get("Cust_Var") or 0),
                             "marg_cont": float(d.get("Marg_Cont") or 0)}
                    # Compara só as rubricas que o snapshot conhece: um snapshot pré-fold (10 chaves)
                    # não deve acusar "desatualizado" apenas porque 'atual' ganhou prov_mont/prov_gar
                    # (FASE 2). Snapshot novo (12 chaves) → comparação íntegra, inclui o drift das 2.
                    desatualizado = bool(venda and any(
                        venda["itens"].get(k) != atual["itens"].get(k) for k in venda["itens"]))
                    # custos adicionais (arq/fidelidade/viagem/brinde): já descontados do
                    # Val. Líquido pelo motor — exibidos à parte, não somam no Cust_Var.
                    custos_adicionais = {
                        "com_arq":  float(d.get("Com_Arq")  or 0),
                        "pro_fid":  float(d.get("Pro_Fid")  or 0),
                        "cust_via": float(d.get("Cust_Via") or 0),
                        "brinde":   float(d.get("Bri")      or 0),
                        "total":    float(d.get("Cust_Ad")  or 0),
                        "cust_fin": float(d.get("Cust_Fin") or 0),   # custo financeiro (informativo)
                    }
                    self.send_json({"ok": True, "provisoes": {
                        "venda": venda, "rev1": _reg("rev1"), "rev2": _reg("rev2"),
                        "atual": atual, "desatualizado": desatualizado,
                        "custos_adicionais": custos_adicionais}})
                finally:
                    db.close()
                return

            # ── GET /api/orcamentos/<id>/proposta/pdf — gera proposta sob demanda ──
            m = _re.match(r"^/api/orcamentos/(\d+)/proposta/pdf$", path)
            if m:
                import tempfile, shutil
                import mod_proposta as _mprop
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                oid = int(m.group(1))
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
                    _proj, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(orc.projeto_id, oid, db)
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    usuario_ctx = {"nome": usuario.get("nome", ""),
                                   "telefone": _get_usuario_telefone(usuario["id"], db),
                                   "email": usuario.get("email", "") or ""}
                    # Proposta = PRIMEIRA PÁGINA do contrato (capa) via WeasyPrint, numerada com 'PV...'.
                    from mod_contrato import (construir_contexto as _cc,
                                              gerar_num_proposta as _gnp, gerar_pdf_proposta as _gpp)
                    ctx = _cc(cliente_dict, usuario_ctx, orc.forma_pagamento or "", loja_dict)
                    ctx["_ambientes"] = _ambientes_valor_para_contrato(oid, db)
                    # Número da proposta gerado uma vez e persistido no orçamento (sequencial por 'PV').
                    if not orc.num_proposta:
                        _existing = [o.num_proposta for o in db.query(Orcamento)
                                     .filter(Orcamento.num_proposta.isnot(None)).all()]
                        orc.num_proposta = _gnp(_existing)
                        db.commit()
                    ctx["num_contrato"] = orc.num_proposta   # marcador [NUM_CONTRATO] da capa
                    outdir = tempfile.mkdtemp(prefix="proposta_")
                    try:
                        pdf_path = os.path.join(outdir, "proposta_%d.pdf" % oid)
                        _gpp(ctx, pdf_path)
                        with open(pdf_path, "rb") as fh:
                            data = fh.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Length", len(data))
                        self.send_header("Content-Disposition",
                                         'inline; filename="proposta_%d.pdf"' % oid)
                        self.end_headers()
                        self.wfile.write(data)
                    finally:
                        shutil.rmtree(outdir, ignore_errors=True)
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
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        # escopo por projetista: consultor não abre projeto de outro
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"}, code=404)
                        return
                    _enriquecer_cliente_do_projeto(proj, db)   # contato sempre do cadastro vivo
                    session_set("projeto_ativo", nome_safe)
                    self.send_json({"ok": True, "projeto": proj})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
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
                    par = (json.loads(p.parametros_json) if p.parametros_json
                           else _params_iniciais_projeto(db, nome_safe, loja_id))
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
                    # Auto-completar etapas 1-4 para projetos que já têm negociação
                    ETAPAS_PRE = ["1","2","3","4"]
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
                    # Responsável por função (v12): resolve nomes de função e do funcionário escolhido (batch).
                    _fnc_ids = {e.funcao_responsavel_id for e in etapas_sorted if e.funcao_responsavel_id}
                    _fnc_map = {f.id: f.nome for f in db.query(Funcao).filter(Funcao.id.in_(_fnc_ids)).all()} \
                        if _fnc_ids else {}
                    _fio_ids = {e.responsavel_funcionario_id for e in etapas_sorted if e.responsavel_funcionario_id}
                    _fio_map = {f.id: f.nome for f in db.query(Funcionario).filter(Funcionario.id.in_(_fio_ids)).all()} \
                        if _fio_ids else {}
                    # Mapa de Atribuições (Fase 1) é o DEFAULT do responsável da fase; o
                    # responsavel_funcionario_id (v12) é o override pontual. Efetivo = override OU Mapa.
                    _atrib = _atribuicoes_dicts(db, nome_safe)
                    def _resp_efetivo(e):
                        if e.responsavel_funcionario_id:
                            return e.responsavel_funcionario_id
                        papel = _ETAPA_PAPEL.get(e.etapa_codigo)
                        a = mod_escopo.resolver_responsavel(_atrib, None, papel) if papel else None
                        return a.get("funcionario_id") if a else None
                    _efet_by_cod = {e.etapa_codigo: _resp_efetivo(e) for e in etapas_sorted}
                    _efet_ids = {i for i in _efet_by_cod.values() if i}
                    _efet_map = {f.id: f.nome for f in db.query(Funcionario).filter(Funcionario.id.in_(_efet_ids)).all()} \
                        if _efet_ids else {}
                    resultado = [{
                        "etapa_codigo":  e.etapa_codigo,
                        "status":        e.status,
                        "responsavel_id": e.responsavel_id,
                        "iniciado_em":   e.iniciado_em.isoformat() if e.iniciado_em else None,
                        "concluido_em":  e.concluido_em.isoformat() if e.concluido_em else None,
                        # Cronograma do Ciclo (v11): data prevista (D0+prazo) e data de conclusão
                        # (= concluido_em, exposta com o nome do spec).
                        "data_prevista_conclusao": e.data_prevista_conclusao.isoformat() if e.data_prevista_conclusao else None,
                        "data_conclusao": e.concluido_em.isoformat() if e.concluido_em else None,
                        # Responsável por função (v12): função exigida (herdada) + funcionário escolhido.
                        "funcao_responsavel_id":   e.funcao_responsavel_id,
                        "funcao_responsavel_nome": _fnc_map.get(e.funcao_responsavel_id, ""),
                        "responsavel_funcionario_id":   e.responsavel_funcionario_id,
                        "responsavel_funcionario_nome": _fio_map.get(e.responsavel_funcionario_id, ""),
                        # Responsável EFETIVO (Fase 1): override da etapa OU default do Mapa de Atribuições.
                        "responsavel_efetivo_id":   _efet_by_cod.get(e.etapa_codigo),
                        "responsavel_efetivo_nome": _efet_map.get(_efet_by_cod.get(e.etapa_codigo), ""),
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

            # GET /api/projetos/<nome>/atribuicoes — Mapa de Atribuições (Regras §4). Abrir/editar só
            # Gerência+ e Supervisor de Montagem.
            m = _re.match(r'^/api/projetos/([^/]+)/atribuicoes$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not _pode_editar_mapa(ator.get("nivel")):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json({"ok": True, "papeis": list(mod_escopo.PAPEIS),
                                    "atribuicoes": _serializar_atribuicoes(db, nome_safe),
                                    "ambientes": _ambientes_do_projeto(db, nome_safe)})
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
                    _pdf = _resolver_pdf_contrato(contrato.pdf_path) if contrato else None
                    if not _pdf:
                        self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404)
                        return
                    eh_pdf  = _pdf.endswith(".pdf")
                    ct      = "application/pdf" if eh_pdf else \
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ext     = "pdf" if eh_pdf else "docx"
                    with open(_pdf, 'rb') as f:
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
                    _pdf_ok = _resolver_pdf_contrato(contrato.pdf_path)
                    tem_arquivo = bool(_pdf_ok)
                    arquivo_tipo = ""
                    if tem_arquivo:
                        arquivo_tipo = "pdf" if _pdf_ok.endswith(".pdf") else "docx"
                    import mod_contrato as _mod_contrato
                    _orc_src = db.get(Orcamento, contrato.orcamento_id)
                    _desatualizado = _mod_contrato.contrato_desatualizado(
                        contrato.pagamento_json,
                        _orc_src.forma_pagamento if _orc_src else None)
                    self.send_json({"ok": True, "contrato": {
                        "id":                   contrato.id,
                        "status":               contrato.status,
                        "endereco_instalacao":  contrato.endereco_instalacao or "",
                        "adendo":               contrato.adendo or "",
                        "gerado_em":            contrato.gerado_em.isoformat() if contrato.gerado_em else None,
                        "tem_pdf":              tem_arquivo,
                        "arquivo_tipo":         arquivo_tipo,
                        "assinaturas":          assinaturas,
                        "desatualizado":        _desatualizado,
                        "orcamento_id":         contrato.orcamento_id,
                    }})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/pe — documentos + revisões + status das subfases
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/pe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloDocumento.enviado_em.desc()).all()
                    revs = db.query(CicloRevisao).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloRevisao.aberta_em.desc()).all()
                    etapas = db.query(CicloEtapa).filter(CicloEtapa.projeto_nome == nome_safe,
                                                         CicloEtapa.etapa_codigo.like("11%")).all()
                    subfases = {e.etapa_codigo: {"status": e.status,
                                                 "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None}
                                for e in etapas}
                    self.send_json({"ok": True,
                        "subfases": subfases,
                        "documentos": [{"id": d.id, "etapa_codigo": d.etapa_codigo, "tipo": d.tipo,
                                        "nome_original": d.nome_original,
                                        "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                        "enviado_por_id": d.enviado_por_id} for d in docs],
                        "revisoes": [{"id": r.id, "etapa_codigo": r.etapa_codigo,
                                      "aberta_por_id": r.aberta_por_id,
                                      "aberta_em": r.aberta_em.isoformat() if r.aberta_em else None,
                                      "relatorio_doc_id": r.relatorio_doc_id, "motivo": r.motivo} for r in revs]})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/documento/<id> — baixa um documento (read-only)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/documento/(\d+)$', path)
            if m:
                nome_safe = unquote(m.group(1)); doc_id = int(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe).first()
                    if not doc:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    caminho = os.path.join(_projeto_path(nome_safe), doc.arquivo_path)
                    if not os.path.exists(caminho):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    conteudo = storage_ler_binario(caminho)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'inline; filename="{doc.nome_original}"')
                    self.send_header("Content-Length", str(len(conteudo)))
                    self.end_headers()
                    self.wfile.write(conteudo)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — lista os XMLs da etapa operacional (12)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo = mod_ciclo.tipo_doc_operacional(codigo)
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo)
                              .order_by(CicloDocumento.enviado_em.desc()).all()) if tipo else []
                    out = [{"id": d.id, "nome_original": d.nome_original,
                            "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None} for d in docs]
                    self.send_json({"ok": True, "documentos": out})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/15/nfe — estado da etapa 15 (XMLs da fábrica
            # + emissões associadas), gated por capacidade fiscal (editar_dados_loja).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    _bloq, _msg = _bloqueio_modulo(path, db.get(Loja, loja_id) if loja_id else None)
                    if _bloq:
                        self.send_json({"ok": False, "erro": _msg}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml")
                              .order_by(CicloDocumento.enviado_em.desc()).all())
                    emissoes = {e.fabrica_doc_id: e for e in
                                db.query(DocumentoFiscal).filter_by(projeto_nome=nome_safe).all()
                                if e.fabrica_doc_id is not None}
                    _emit_cache = {}
                    def _emitente(eid):
                        if eid is None:
                            return None
                        if eid not in _emit_cache:
                            _emit_cache[eid] = db.get(Emitente, eid)
                        return _emit_cache[eid]
                    out = []
                    for d in docs:
                        e = emissoes.get(d.id)
                        em = _emitente(e.emitente_id) if e else None
                        emissao = None if not e else {
                            "ref": e.ref, "status": e.status, "chave": e.chave_nfe, "numero": e.numero,
                            "serie": e.serie, "mensagem_sefaz": e.mensagem_sefaz,
                            "erros": json.loads(e.erros_json) if e.erros_json else [],
                            "xml_doc_id": e.xml_doc_id, "danfe_doc_id": e.danfe_doc_id,
                            "emitente_cnpj": em.cnpj if em else None,
                            "emitente_razao": em.razao_social if em else None}
                        out.append({"id": d.id, "nome_original": d.nome_original,
                                    "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                    "emissao": emissao})
                    # Estado da NFS-e (serviço, valor manual) — o DocumentoFiscal tipo="servico"
                    # deste projeto (ref NFSE-<projeto>), serializado como uma emissão de produto.
                    nfse_reg = (db.query(DocumentoFiscal)
                                  .filter_by(projeto_nome=nome_safe, tipo_documento="servico")
                                  .order_by(DocumentoFiscal.id.desc()).first())
                    emn = _emitente(nfse_reg.emitente_id) if nfse_reg else None
                    nfse = None if not nfse_reg else {
                        "ref": nfse_reg.ref, "status": nfse_reg.status, "chave": nfse_reg.chave_nfe,
                        "numero": nfse_reg.numero, "serie": nfse_reg.serie,
                        "mensagem_sefaz": nfse_reg.mensagem_sefaz,
                        "erros": json.loads(nfse_reg.erros_json) if nfse_reg.erros_json else [],
                        "xml_doc_id": nfse_reg.xml_doc_id, "danfe_doc_id": nfse_reg.danfe_doc_id,
                        "emitente_cnpj": emn.cnpj if emn else None,
                        "emitente_razao": emn.razao_social if emn else None}
                    self.send_json({"ok": True, "fabrica_xmls": out, "nfse": nfse})
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/perfil-fiscal — config fiscal (segredos NUNCA retornados)
            m = _re.match(r'^/api/admin/lojas/(\d+)/perfil-fiscal$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if _sem_acesso_modulo(usuario, "fiscal", handler=self):   # Perfil-4: só Diretoria abre Fiscal
                    self.send_json({"ok": False, "erro": "Sem acesso ao módulo Fiscal.", "precisa_stepup": "fiscal"}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    em, _attr = _emitente_do_dono(db, "loja", loja)
                    self.send_json(_fiscal_get(em))
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/modulos — domínios ativos (topologia)
            m = _re.match(r'^/api/admin/lojas/(\d+)/modulos$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    import modulos as _mod
                    ativos = mod_tenancy.modulos_ativos_da_loja(loja)
                    dominios = [{"id": x["id"], "rotulo": x["rotulo"], "depende_de": x["depende_de"],
                                 "ativo": x["id"] in ativos} for x in _mod.dominios_com_rotulo()]
                    self.send_json({"ok": True, "ativos": sorted(ativos), "dominios": dominios})
                finally:
                    db.close()
                return

            # GET /api/admin/redes/<id>/perfil-fiscal — config do Emitente central da rede
            m = _re.match(r'^/api/admin/redes/(\d+)/perfil-fiscal$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    rid = int(m.group(1))
                    rede = db.get(Rede, rid)
                    if not rede:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_ver_rede(ator, rid):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    em, _attr = _emitente_do_dono(db, "rede", rede)
                    self.send_json(_fiscal_get(em))
                finally:
                    db.close()
                return

            # GET /api/admin/redes/<id>/perfil-emissao — default de emissão da rede
            m = _re.match(r'^/api/admin/redes/(\d+)/perfil-emissao$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    rid = int(m.group(1))
                    rede = db.get(Rede, rid)
                    if not rede:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_ver_rede(ator, rid):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json(_perfil_emissao_get(db, "rede", rid, rede))
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/perfil-emissao — override de emissão da loja
            m = _re.match(r'^/api/admin/lojas/(\d+)/perfil-emissao$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json(_perfil_emissao_get(db, "loja", loja.id, loja))
                finally:
                    db.close()
                return

            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b'{}'

        if handle_auth_post(self, path, body): return

        # ── Expedição (Modulos_Orizon_v5, módulo 7): CicloLogistico — criar/mover/editar ──
        if path == "/api/expedicao/cards":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "expedicao"):
                    self.send_json({"ok": False, "erro": "Módulo Expedição inativo."}, code=403); return
                req = json.loads(body or b'{}')
                projeto = (req.get("projeto_nome") or "").strip()
                if not projeto:
                    self.send_json({"ok": False, "erro": "Selecione o projeto."}, code=400); return
                if db.query(Projeto).filter_by(nome_safe=projeto, loja_id=lid).first() is None:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado nesta loja."}, code=404); return
                card = mod_expedicao.criar_ciclo(db, lid, projeto, req.get("numero_pedido"),
                                                 req.get("prazos") or {}, usuario.get("id"))
                db.commit()
                self.send_json({"ok": True, "id": card.id}, code=201)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)/mover$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                req = json.loads(body or b'{}')
                ok, err = mod_expedicao.mover(db, card, req.get("novo_status"),
                                              req.get("realizados") or {}, usuario.get("id"))
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                mod_expedicao.atualizar_detalhe(db, card, json.loads(body or b'{}'))
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Assistências (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6) ─────────────────
        if path == "/api/assistencias/casos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "assistencias"):
                    self.send_json({"ok": False, "erro": "Módulo Assistências inativo."}, code=403); return
                req = json.loads(body or b'{}')
                projeto = (req.get("projeto_nome") or "").strip() or None
                if projeto and db.query(Projeto).filter_by(nome_safe=projeto, loja_id=lid).first() is None:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado nesta loja."}, code=404); return
                caso = mod_assistencias.criar_caso(db, lid, projeto, req.get("sub_tipo"), req.get("motivo"),
                                                   req.get("descricao"), req.get("valor"), usuario.get("id"))
                db.commit()
                self.send_json({"ok": True, "id": caso.id, "tipo_custo": caso.tipo_custo}, code=201)
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/assistencias/casos/(\d+)/realizar$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            import mod_contabil
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                caso = db.get(AssistenciaCaso, int(m.group(1)))
                if caso is None or (lid and caso.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                ot, oid = mod_contabil.resolver_owner(db, usuario)
                ok, err = mod_assistencias.realizar_caso(db, ot, oid, caso, (json.loads(body or b'{}')).get("valor"))
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Folha de Pagamento: gerar folha do período / pagar um registro ───────────────
        if path == "/api/folha/gerar":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                comp = ((json.loads(body or b'{}')).get("competencia") or "").strip()
                if not re.match(r'^\d{4}-\d{2}$', comp):
                    self.send_json({"ok": False, "erro": "Informe a competência AAAA-MM."}, code=400); return
                cfg = _cfg_financeira_loja(db, loja_id)
                mod_folha.gerar_folha(db, loja_id, comp, cfg)
                db.commit()
                self.send_json({"ok": True, "folha": mod_folha.listar(db, loja_id, comp)})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/folha/(\d+)/pagar$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_contabil
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                reg = db.get(FolhaPagamento, int(m.group(1)))
                if reg is None or (lid and reg.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ot, oid = mod_contabil.resolver_owner(db, usuario)
                ok, err = mod_folha.pagar(db, ot, oid, reg)
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Cadastro (Modulos_Orizon_v9/v10): criar/editar Funcionário/Fornecedor/Terceiro/Função ──
        m = re.match(r'^/api/(funcionarios|fornecedores|terceiros|funcoes)(?:/(\d+))?$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                ent = m.group(1); rid = m.group(2)
                Model, ser, apl = _cad_ent(ent)
                req = json.loads(body or b'{}')
                if rid:
                    obj = db.query(Model).filter_by(id=int(rid), loja_id=loja_id).first()
                    if obj is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                else:
                    obj = Model(loja_id=loja_id); db.add(obj)
                if not ((req.get("nome") or "").strip() or (rid and obj.nome)):
                    self.send_json({"ok": False, "erro": "Nome é obrigatório."}, code=400); return
                apl(db, obj, req, loja_id)
                db.flush()
                if ent == "funcionarios":   # fronteira: sincroniza a conta de login vinculada
                    okc, errc = mod_cadastro.func_sync_acesso(db, obj, req)
                    if not okc:
                        db.rollback(); self.send_json({"ok": False, "erro": errc}, code=400); return
                db.commit()
                self.send_json({"ok": True, "id": obj.id, "item": ser(obj, db)}, code=(200 if rid else 201))
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                nova = mod_contabil.criar_conta(db, ot, oid, dd.get("pai_id"), dd.get("nome", ""))
                self.send_json({"ok": True, "conta": nova}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/sugerir-conta":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                self.send_json({"ok": True, "sugestao": mod_contabil.sugerir_conta(db, ot, oid, dd.get("texto", ""))})
            finally:
                db.close()
            return
        if path == "/api/financeiro/lancamentos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                _ia = json.dumps(dd["ia_sugestao"]) if dd.get("ia_sugestao") else None
                lan = mod_contabil.lancar(
                    db, ot, oid,
                    conta_debito_id=dd.get("conta_debito_id"),
                    conta_credito_id=dd.get("conta_credito_id"),
                    valor=dd.get("valor"),
                    data=_parse_data(dd.get("data")),
                    projeto_id=dd.get("projeto_id"),
                    historico=dd.get("historico", ""),
                    ia_sugestao=_ia)
                self.send_json({"ok": True, "lancamento": lan}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/reconciliar":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                rec = mod_contabil.reconciliar(db, ot, oid, ini=_parse_data(dd.get("ini")),
                                               fim=_parse_data(dd.get("fim")),
                                               metodologia=dd.get("metodologia", "proporcional_receita"))
                self.send_json({"ok": True, "reconciliacao": rec})
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/periodos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                r = mod_contabil.fechar_periodo(db, ot, oid, ini=_parse_data(dd.get("ini")),
                                                fim=_parse_data(dd.get("fim")),
                                                metodologia=dd.get("metodologia", "proporcional_receita"))
                self.send_json({"ok": True, "periodo": r}, code=201)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/eventos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                lan = mod_contabil.registrar_evento(
                    db, ot, oid, dd.get("tipo"), dd.get("valor"),
                    projeto_id=dd.get("projeto_id"), data=_parse_data(dd.get("data")),
                    historico=dd.get("historico", ""), motivo=dd.get("motivo"))
                self.send_json({"ok": True, "lancamento": lan}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        m_conta_rm = re.match(r"^/api/financeiro/contas/(\d+)/remover$", path)
        if m_conta_rm:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                r = mod_contabil.remover_conta(db, ot, oid, int(m_conta_rm.group(1)))
                self.send_json({"ok": True, **r})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
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
                        # Consultor responsável (criado_por_id, gravado só na criação): por padrão o
                        # usuário logado; gerente+ pode indicar outro consultor da loja.
                        criador = usuario.get("id") if usuario else None
                        cons_id = req.get("consultor_id")
                        if cons_id and not _ve_apenas_proprios_projetos(usuario.get("nivel")):
                            alvo = _db_ciclo.query(Usuario).filter_by(id=int(cons_id)).first()
                            if _usuario_pertence_a_loja(_db_ciclo, alvo, loja_id):
                                criador = int(cons_id)
                        p_meta.criado_por_id = criador
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
            import validacao_doc
            for _val, _rot, _tipo in ((req.get("cpf"), "CPF", "cpf"),
                                      (req.get("cnpj"), "CNPJ", "cnpj")):
                _e = validacao_doc.erro_doc(_val, _rot, _tipo)
                if _e:
                    self.send_json({"ok": False, "erro": _e}, code=400)
                    return
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
                tipo_dest = (req.get("tipo_dest") or "").strip() or "nao_contribuinte"
                c = Cliente(
                    nome       =nome, cpf=cpf,
                    loja_id    =loja_id,
                    tipo_dest         =tipo_dest,
                    cnpj              =(req.get("cnpj")               or "").strip() or None,
                    inscricao_estadual=(req.get("inscricao_estadual") or "").strip() or None,
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
                    municipio_ibge=(req.get("municipio_ibge") or "").strip() or None,
                    observacoes=(req.get("observacoes") or "").strip() or None,
                )
                db.add(c)
                db.commit()
                db.refresh(c)
                cliente_id = c.id
                if not _OMIE_AUTO_SYNC:
                    # Omie desligado: não sincroniza no cadastro; marca 'dispensado' para não cair na
                    # fila (que inclui omie_sync_status NULL).
                    c.omie_sync_status = "dispensado"
                    db.commit(); db.refresh(c)
                self.send_json({"ok": True, "cliente": _cliente_dict(c)})

                if _OMIE_AUTO_SYNC:
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
                import validacao_doc
                for _val, _rot, _tipo in ((req.get("cpf"), "CPF", "cpf"),
                                          (req.get("cnpj"), "CNPJ", "cnpj")):
                    _e = validacao_doc.erro_doc(_val, _rot, _tipo)
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                campos = ["nome","cpf","cnpj","inscricao_estadual",
                          "email","telefone","whatsapp",
                          "cep","logradouro","numero","complemento",
                          "bairro","cidade","estado","municipio_ibge","observacoes",
                          "inst_logradouro","inst_numero","inst_complemento",
                          "inst_bairro","inst_cidade","inst_cep","inst_uf"]
                for f in campos:
                    if f in req:
                        setattr(c, f, (req[f] or "").strip() or None)
                if "tipo_dest" in req:
                    c.tipo_dest = (req["tipo_dest"] or "").strip() or "nao_contribuinte"
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
            import validacao_doc
            _e = validacao_doc.erro_doc(req.get("cpf_cnpj"), "CPF/CNPJ")
            if _e:
                self.send_json({"ok": False, "erro": _e}, code=400)
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
                    pix                 =(req.get("pix")                   or "").strip() or None,
                )
                db.add(p)
                db.flush()        # atribui p.id sem efetivar — transação única e atômica
                # Sempre aplica abrangência (default 'loja' → loja ativa do ator): garante
                # que o parceiro nunca nasça órfão/invisível para quem o cadastrou.
                ator = (_ator_dict(db, usuario) if usuario
                        else {"nivel": "", "loja_id": None, "rede_id": None, "active_loja_id": None})
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
                if "cpf_cnpj" in req:
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cpf_cnpj"), "CPF/CNPJ")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                for f in ["nome","cpf_cnpj","tipo","email","telefone","whatsapp","observacoes","pix"]:
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
                proj_orcs = db.query(Orcamento).filter_by(projeto_id=nome_safe).all()
                for o in proj_orcs:
                    try: _recalcular_orcamento(o, db)
                    except Exception as _e: print("[FAXINA] recalc parametros:", _e)
                db.commit()
                brk = _negociacao_breakdown(proj_orcs[0], db) if proj_orcs else None
                self.send_json({"ok": True, "parametros": novos, "sombra": brk})
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
                _bc = _bloqueio_comercial(ator)      # visão do papel (§3): operacional não vê comercial
                if _bc:
                    self.send_json({"ok": False, "erro": _bc}, code=403); return
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
                if "desconto_pct" in req:
                    orc.desconto_pct = float(req["desconto_pct"])
                db.commit()
                try:
                    _recalcular_orcamento(orc, db)
                    db.commit()
                    self.send_json({"ok": True, "desconto_pct": orc.desconto_pct or 0.0,
                                    "sombra": _negociacao_breakdown(orc, db)})
                except Exception as _e:
                    db.rollback()
                    print("[CUTOVER] falha ao recalcular orçamento:", _e)
                    self.send_json({"ok": True, "desconto_pct": orc.desconto_pct or 0.0,
                                    "sombra": None, "erro_sombra": str(_e)})
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
                _bc = _bloqueio_comercial(ator)      # visão do papel (§3): operacional não vê comercial
                if _bc:
                    self.send_json({"ok": False, "erro": _bc}, code=403); return
                orc = _obj_da_loja(db, Orcamento, int(m_prev.group(1)), loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                d = _negociacao_breakdown(orc, db)
                self.send_json({"ok": True, "sombra": d, "ambientes": d.get("ambientes", [])})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/provisoes/(rev1|rev2)$", path):
            # ── POST /api/orcamentos/<id>/provisoes/<rev1|rev2> — Concorda/Revisa ──
            import mod_provisoes as _mprov
            m_prov = re.match(r"^/api/orcamentos/(\d+)/provisoes/(rev1|rev2)$", path)
            oid = int(m_prov.group(1)); versao = m_prov.group(2)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"))
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                anterior_versao = "venda" if versao == "rev1" else "rev1"
                anterior = db.query(ProvisaoRegistro).filter_by(
                    orcamento_id=oid, versao=anterior_versao).first()
                if not anterior:
                    self.send_json({"ok": False,
                        "erro": "Registre a versão anterior primeiro (%s)." % anterior_versao},
                        code=409); return
                decisao = (req.get("decisao") or "").strip()
                if decisao == "concorda":
                    itens = json.loads(anterior.itens_json)
                    cfo, vl = anterior.cfo, anterior.val_liq
                elif decisao == "revisa":
                    try:
                        itens = {k: max(0.0, float(v or 0)) for k, v in (req.get("itens") or {}).items()}
                    except (TypeError, ValueError):
                        self.send_json({"ok": False, "erro": "Valores de itens inválidos"}, code=400); return
                    cfo, vl = anterior.cfo, anterior.val_liq   # base congelada (versão anterior: venda p/ rev1, rev1 p/ rev2)
                else:
                    self.send_json({"ok": False, "erro": "decisao deve ser concorda|revisa"}, code=400); return
                cust_var, marg = _mprov.cust_var_marg_cont(cfo, vl, itens)
                existente = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                if existente:
                    db.delete(existente); db.flush()
                db.add(ProvisaoRegistro(orcamento_id=oid, versao=versao,
                    itens_json=json.dumps(itens, ensure_ascii=False),
                    cfo=cfo, val_liq=vl, cust_var=cust_var, marg_cont=marg,
                    decisao=decisao, por_id=aprovador.id))
                db.commit()
                self.send_json({"ok": True})
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
                    _desconto_novo = 0.0
                    if _origem_id:
                        _origem = _obj_da_loja(db, Orcamento, int(_origem_id), loja_id)
                        if _origem:
                            _desconto_novo = _origem.desconto_pct or 0.0
                    orc = Orcamento(
                        projeto_id=nome_safe,
                        nome=      nome_orc,
                        ordem=     proxima_ordem,
                        desconto_pct= _desconto_novo,
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
                    # compat: se só loja_ids vier (sem loja_id), usa o primeiro como primário
                    req_tenant = dict(req)
                    if "loja_ids" in req_tenant and not req_tenant.get("loja_id"):
                        ids_raw = req_tenant["loja_ids"]
                        if ids_raw:
                            req_tenant["loja_id"] = int(ids_raw[0])
                    loja_id, rede_id, erros_tenant = mod_tenancy.atribuir_tenant_usuario(ator, req_tenant)
                    loja_ids, erros_lojas = mod_tenancy.lojas_do_novo_usuario(ator, req)
                    erros = erros + erros_tenant + erros_lojas
                    # valida cada loja no escopo do ator (admin_rede/diretor)
                    if not erros and loja_ids and not mod_tenancy._eh_super_admin(ator):
                        for lid in loja_ids:
                            loja = db.get(Loja, lid)
                            if not loja or not mod_tenancy.pode_ver_loja(
                                    ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                erros = erros + ["Loja fora do seu escopo."]; break
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cpf"), "CPF", "cpf")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                    primary_loja_id = loja_ids[0] if loja_ids else None
                    u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                                nivel=req["nivel"].strip(),
                                telefone=(req.get("telefone") or "").strip(),
                                whatsapp=(req.get("whatsapp") or "").strip(),
                                email=(req.get("email") or "").strip(),
                                cpf=(req.get("cpf") or "").strip(),
                                loja_id=primary_loja_id, rede_id=rede_id)
                    u.set_senha(req["senha"])
                    db.add(u); db.flush()
                    for lid in loja_ids:
                        db.add(UsuarioLoja(usuario_id=u.id, loja_id=lid))
                    db.commit()
                    self.send_json({"ok": True, "id": u.id})
                finally:
                    db.close()
                return

            if path == "/api/admin/perfis":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    import perfil_store
                    p, err = perfil_store.criar_perfil(db, usuario.get("loja_id"),
                                req.get("nome", ""), req.get("base", ""), req.get("modulos", []),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}}, code=201)
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
                import validacao_doc
                _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                if _e:
                    self.send_json({"ok": False, "erro": _e}, code=400)
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
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
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
                    # Resetar etapa 7 (a geração do contrato iniciou a 7); a etapa 4
                    # (Orçamento) permanece concluída — voltar ao orçamento reabre o contrato.
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

            # POST /api/projetos/<nome>/ciclo/<codigo>/data-prevista — edita a data prevista de
            # conclusão de uma etapa (Cronograma do Ciclo, Modulos_Orizon_v11). Protegida por
            # reautenticação Gerente+ (mesmo princípio dos gates financeiros) e auditada (quem/quando/
            # valor antigo → novo) em LogAcaoGerencial.
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/data-prevista$', path)
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
                    nova_str = (req.get("data_prevista") or "").strip()   # "AAAA-MM-DD"
                    autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                    if not autorizador or not autorizador.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Credenciais inválidas"}, code=403)
                        return
                    if not perfis.pode(autorizador.nivel, "autorizar"):
                        self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"}, code=403)
                        return
                    try:
                        nova_dt = datetime.strptime(nova_str, "%Y-%m-%d") if nova_str else None
                    except ValueError:
                        self.send_json({"ok": False, "erro": "Data inválida (use AAAA-MM-DD)"}, code=400)
                        return
                    if nova_dt is None:
                        self.send_json({"ok": False, "erro": "Informe a nova data prevista"}, code=400)
                        return
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod).first()
                    if etapa is None:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    antigo = etapa.data_prevista_conclusao
                    etapa.data_prevista_conclusao = nova_dt
                    db.add(LogAcaoGerencial(
                        solicitante_id=solicitante["id"],
                        autorizador_id=autorizador.id,
                        acao="editar_data_prevista",
                        projeto_nome=nome_safe,
                        etapa_alvo=etapa_cod,
                        contexto=json.dumps({
                            "valor_antigo": antigo.isoformat() if antigo else None,
                            "valor_novo":   nova_dt.isoformat(),
                        }),
                    ))
                    db.commit()
                    self.send_json({"ok": True, "data_prevista_conclusao": nova_dt.isoformat()})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/responsavel — escolhe o FUNCIONÁRIO responsável
            # pela etapa (Cronograma do Projeto, Modulos_Orizon_v12). O funcionário precisa ter a FUNÇÃO
            # exigida pela fase (funcao_responsavel_id, herdada do padrão no D0). funcionario_id vazio limpa.
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/responsavel$', path)
            if m:
                nome_safe = unquote(m.group(1))
                etapa_cod = unquote(m.group(2))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    req = json.loads(body or b'{}')
                    fio_id = req.get("funcionario_id")
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod).first()
                    if etapa is None:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    if fio_id in (None, "", 0, "0"):
                        etapa.responsavel_funcionario_id = None
                    else:
                        func = db.get(Funcionario, int(fio_id))
                        if func is None or func.loja_id != loja_id:
                            self.send_json({"ok": False, "erro": "Funcionário não encontrado"}, code=404); return
                        # Restrição por função: se a fase exige uma função, o funcionário tem de tê-la.
                        if etapa.funcao_responsavel_id and func.funcao_id != etapa.funcao_responsavel_id:
                            self.send_json({"ok": False,
                                            "erro": "Funcionário não tem a função exigida por esta fase"}, code=400)
                            return
                        etapa.responsavel_funcionario_id = func.id
                    db.commit()
                    self.send_json({"ok": True, "responsavel_funcionario_id": etapa.responsavel_funcionario_id})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/atribuicoes — upsert de uma atribuição do Mapa (Regras §4/§5).
            # Body: {papel, pool_ambiente_id|null, funcionario_id|null, terceiro_id|null}. Alvo vazio
            # limpa a linha. Alvo tem de pertencer à loja E ter Função compatível com o papel (§7).
            # 1:1 por (papel, ambiente) — substitui. Auditado em LogAcaoGerencial. Só Gerência+/Supervisor.
            m = _re.match(r'^/api/projetos/([^/]+)/atribuicoes$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not _pode_editar_mapa(ator.get("nivel")):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    req = json.loads(body or b'{}')
                    papel = (req.get("papel") or "").strip()
                    if papel not in mod_escopo.PAPEIS:
                        self.send_json({"ok": False, "erro": "Papel inválido"}, code=400); return
                    amb_id = req.get("pool_ambiente_id")
                    amb_id = int(amb_id) if amb_id not in (None, "", 0, "0") else None
                    # ambiente, se informado, tem de ser do projeto
                    if amb_id is not None:
                        pa = db.get(PoolAmbiente, amb_id)
                        if pa is None or pa.projeto_id != nome_safe:
                            self.send_json({"ok": False, "erro": "Ambiente não encontrado"}, code=404); return
                    fio_id = req.get("funcionario_id") or None
                    ter_id = req.get("terceiro_id") or None
                    # localiza a linha vigente (projeto, ambiente, papel)
                    reg = (db.query(AtribuicaoAmbiente)
                           .filter_by(projeto_nome=nome_safe, papel=papel)
                           .filter(AtribuicaoAmbiente.pool_ambiente_id.is_(None) if amb_id is None
                                   else AtribuicaoAmbiente.pool_ambiente_id == amb_id).first())
                    antigo = None
                    if reg is not None:
                        antigo = reg.funcionario_id or (("t%d" % reg.terceiro_id) if reg.terceiro_id else None)
                    # alvo vazio → limpar
                    if not fio_id and not ter_id:
                        if reg is not None:
                            db.delete(reg)
                        novo = None
                    else:
                        # resolve alvo, valida loja + função compatível com o papel (§7)
                        if fio_id:
                            alvo = db.get(Funcionario, int(fio_id)); ter_id = None
                        else:
                            alvo = db.get(Terceiro, int(ter_id)); fio_id = None
                        if alvo is None or alvo.loja_id != loja_id:
                            self.send_json({"ok": False, "erro": "Profissional não encontrado"}, code=404); return
                        fnome = ""
                        if getattr(alvo, "funcao_id", None):
                            _fn = db.get(Funcao, alvo.funcao_id); fnome = _fn.nome if _fn else ""
                        if not mod_escopo.funcao_compativel(papel, fnome):
                            self.send_json({"ok": False,
                                            "erro": "Profissional não tem função compatível com este papel"}, code=400)
                            return
                        if reg is None:
                            reg = AtribuicaoAmbiente(loja_id=loja_id, projeto_nome=nome_safe,
                                                     pool_ambiente_id=amb_id, papel=papel)
                            db.add(reg)
                        reg.funcionario_id = int(fio_id) if fio_id else None
                        reg.terceiro_id    = int(ter_id) if ter_id else None
                        reg.atribuido_por_id = usuario["id"]
                        novo = reg.funcionario_id or (("t%d" % reg.terceiro_id) if reg.terceiro_id else None)
                    db.add(LogAcaoGerencial(
                        solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                        acao="atribuir_mapa", projeto_nome=nome_safe, etapa_alvo=papel,
                        contexto=json.dumps({"papel": papel, "pool_ambiente_id": amb_id,
                                             "alvo_antigo": antigo, "alvo_novo": novo})))
                    db.commit()
                    self.send_json({"ok": True, "atribuicoes": _serializar_atribuicoes(db, nome_safe)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/parceiro — associa/remove o parceiro (arquiteto) do
            # projeto (etapa "Criação do Projeto"). Editável só ATÉ a assinatura do contrato.
            m = _re.match(r'^/api/projetos/([^/]+)/parceiro$', path)
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
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_totalmente_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado por ambas as partes — o parceiro não pode mais ser alterado"},
                                       code=400)
                        return
                    req = json.loads(body or b'{}')
                    pid = req.get("parceiro_id")
                    parceiro_dict = None
                    if pid:
                        parc = db.get(Parceiro, int(pid))
                        if parc is None or not _parceiro_visivel_loja(db, parc, loja_id):
                            self.send_json({"ok": False, "erro": "Parceiro fora do seu escopo"}, code=400)
                            return
                        parceiro_dict = _parceiro_dict(parc, db)
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto não encontrado"}, code=404)
                        return
                    proj["parceiro_id"] = int(pid) if pid else None
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "parceiro": parceiro_dict})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/editar — altera os campos de criação (nome, cliente,
            # parceiro, consultor). Cliente/parceiro travam após contrato assinado; nome e
            # consultor seguem editáveis. Reatribuir consultor exige gerente+ (escopo não-próprio).
            m = _re.match(r'^/api/projetos/([^/]+)/editar$', path)
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
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto não encontrado"}, code=404)
                        return
                    req = json.loads(body or b'{}')
                    assinado = _contrato_totalmente_assinado(nome_safe, db)
                    pode_atribuir = not _ve_apenas_proprios_projetos(usuario.get("nivel"))

                    # Nome exibido (a chave nome_safe é preservada) — sempre editável
                    if "nome_projeto" in req:
                        nv = (req.get("nome_projeto") or "").strip()
                        if nv:
                            proj["nome_projeto"] = nv

                    # Consultor responsável — só gerente+; editável mesmo após o contrato
                    if "consultor_id" in req:
                        if not pode_atribuir:
                            self.send_json({"ok": False, "erro": "Sem permissão para reatribuir o consultor"}, code=403)
                            return
                        cid = req.get("consultor_id")
                        if cid:
                            alvo = db.query(Usuario).filter_by(id=int(cid)).first()
                            if not _usuario_pertence_a_loja(db, alvo, loja_id):
                                self.send_json({"ok": False, "erro": "Consultor fora da loja"}, code=400)
                                return
                            _meta.criado_por_id = int(cid)

                    # Cliente — travado após contrato assinado
                    if "cliente_id" in req:
                        if assinado:
                            self.send_json({"ok": False, "erro": "Contrato assinado — cliente não pode ser alterado"}, code=400)
                            return
                        cid = req.get("cliente_id")
                        if cid:
                            c = _obj_da_loja(db, Cliente, int(cid), loja_id)
                            if not c:
                                self.send_json({"ok": False, "erro": "Cliente fora da loja"}, code=400)
                                return
                            proj["cliente_id"] = int(cid)
                            proj["cliente"] = {"nome": c.nome, "cpf": c.cpf or "",
                                               "email": c.email or "", "telefone": c.telefone or ""}
                            _meta.cliente_id = int(cid)

                    # Parceiro — travado após contrato assinado ("" / null remove)
                    if "parceiro_id" in req:
                        if assinado:
                            self.send_json({"ok": False, "erro": "Contrato assinado — parceiro não pode ser alterado"}, code=400)
                            return
                        pid = req.get("parceiro_id")
                        if pid:
                            parc = db.get(Parceiro, int(pid))
                            if parc is None or not _parceiro_visivel_loja(db, parc, loja_id):
                                self.send_json({"ok": False, "erro": "Parceiro fora do seu escopo"}, code=400)
                                return
                        proj["parceiro_id"] = int(pid) if pid else None

                    _salvar_projeto(proj)
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
                        # Cronograma do Ciclo (Modulos_Orizon_v11): D0 = assinatura total do contrato
                        # (mesmo gatilho das Provisões). Constitui data_prevista_conclusao por etapa a
                        # partir do Cronograma de Projeto Padrão (Config). Fail-soft: não bloqueia a
                        # assinatura se algo falhar.
                        try:
                            import mod_cronograma
                            _cfg_crono = _cfg_financeira_loja(db, loja_id)
                            mod_cronograma.gerar_cronograma_projeto(
                                db, nome_safe, _cfg_crono, datetime.utcnow())
                            db.commit()
                        except Exception as _ec:
                            db.rollback()
                            print("[CRONOGRAMA] gerar_cronograma_projeto falhou:", _ec)
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
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
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
                        "_ambientes":      _ambientes_valor_para_contrato(orcamento_id, db),
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
                        contrato.loja_id = loja_id
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    # Número do contrato (gerado uma vez; mantido em regerações).
                    if not contrato.num_contrato:
                        from mod_contrato import gerar_num_contrato
                        _existing = [c.num_contrato for c in db.query(Contrato)
                                     .filter(Contrato.num_contrato.isnot(None)).all()]
                        contrato.num_contrato = gerar_num_contrato(_existing, loja_dict.get("codigo", ""))
                    variaveis["num_contrato"] = contrato.num_contrato
                    db.commit()
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    contrato.status = "para_assinatura"
                    # A geração do contrato conclui a etapa Orçamento (4) — aprovar o
                    # orçamento e gerar o contrato são a mesma transição (Orçamento → Contrato).
                    _set_etapa_status(db, nome_safe, "4", "concluido", usuario["id"])
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
                    _orc_venda = db.get(Orcamento, contrato.orcamento_id)
                    _registrar_provisao_venda(db, _orc_venda,
                                              por_id=(usuario.get("id") if usuario else None))
                    db.commit()
                    # v6 §6.4: auto-constitui as 3 provisões contábeis (% × valor da venda), fail-soft
                    _fin_provisoes_venda_seguro(_orc_venda, nome_safe, "prov:" + str(contrato.id))
                    resp = {"ok": True, "contrato_id": contrato.id, "status": "para_assinatura"}
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

            # POST /api/projetos/<nome>/ciclo/<codigo>/documento — upload append-only (PE)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/documento$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo_esperado = mod_ciclo.tipo_doc_de(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "executar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_documento_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    # rollback é no-op se o commit já ocorreu (linha do doc persiste; o
                    # download degrada com 404 se o arquivo não foi para o disco).
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — upload XML da etapa
            # operacional (12), append-only, CYCLE-GATED (sem capability de PE).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo_esperado = mod_ciclo.tipo_doc_operacional(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Esta etapa não aceita upload de pedidos."}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo XML."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", usuario["id"])
                    db.add(LogAcaoGerencial(solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                            acao="ciclo_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe-fabrica — upload da NF-e da fábrica
            # (etapa 15), append-only, gated por capacidade fiscal (editar_dados_loja).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe-fabrica$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da NF-e da fábrica."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", "15", unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="15").first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, "15", "em_andamento", usuario["id"])
                    db.add(LogAcaoGerencial(solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                            acao="ciclo_nfe_fabrica_xml", projeto_nome=nome_safe, etapa_alvo="15"))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/revisao — revisão + reabertura em cascata
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/revisao$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    sf = mod_ciclo.SUBFASES_PE.get(codigo)
                    if not sf or not sf["revisavel"]:
                        self.send_json({"ok": False, "erro": "Esta subfase não permite revisão."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "revisar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Revisão exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o relatório complementar (obrigatório)."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo="pe_relatorio_complementar",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc); db.flush()   # doc.id para a revisão
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos = [e.etapa_codigo for e in todas]
                    resetar = mod_ciclo.codigos_a_resetar(codigo, codigos)
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe).order_by(Contrato.id.desc()).first()
                    cstatus = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False, "erro": "Contrato já assinado — não é possível revisar esta etapa"}, code=400); return
                    resetar_set = set(resetar)
                    status_anterior = {e.etapa_codigo: e.status for e in todas
                                       if e.etapa_codigo in resetar_set}
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status = "pendente"; e.iniciado_em = None; e.concluido_em = None; e.responsavel_id = None
                    # a etapa-mãe 11 volta a "em andamento" (PE deixou de estar concluído).
                    # _set_etapa_status cria/atualiza a linha, mas não zera concluido_em/responsavel_id
                    # ao sair de "concluido" — limpamos aqui para não deixar carimbo obsoleto.
                    e11 = _set_etapa_status(db, nome_safe, "11", "em_andamento", u.id)
                    e11.concluido_em = None; e11.responsavel_id = None
                    rev = CicloRevisao(projeto_nome=nome_safe, etapa_codigo=codigo, aberta_por_id=u.id,
                                       relatorio_doc_id=doc.id, motivo=(campos.get("motivo") or None))
                    db.add(rev)
                    db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                            acao="pe_revisao", projeto_nome=nome_safe, etapa_alvo=codigo,
                            contexto=json.dumps({"resetadas": sorted(resetar_set),
                                                 "status_anterior": status_anterior})))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/concluir — fecha a subfase de PE
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/concluir$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if codigo not in mod_ciclo.SUBFASES_PE:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    req = json.loads(body or b'{}')
                    u = _usuario_com_capacidade(db, req.get("login", ""), req.get("senha", ""), "executar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).all()
                    tipos_presentes = {d.tipo for d in docs}
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    status_por = {e.etapa_codigo: e.status for e in todas}
                    ok, erro = mod_ciclo.guarda_conclusao(codigo, tipos_presentes, status_por)
                    if not ok:
                        self.send_json({"ok": False, "erro": erro}, code=400); return
                    _set_etapa_status(db, nome_safe, codigo, "concluido", u.id)
                    if codigo == mod_ciclo.PE_SUBFASE_FINAL:
                        _set_etapa_status(db, nome_safe, "11", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_concluir_" + codigo, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/admin/lojas/<id>/nfe/emitir-teste — emissão de teste (homologação)
            m = _re.match(r'^/api/admin/lojas/(\d+)/nfe/emitir-teste$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_nfe, mapa_fiscal, nfe_emissao, mod_fiscal
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "produto")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "produto")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da fábrica."}, code=400); return
                    projeto_nome = campos.get("projeto_nome")
                    projeto = db.get(Projeto, projeto_nome) if projeto_nome else None
                    if not projeto:
                        self.send_json({"ok": False, "erro": "Informe um projeto válido da loja."}, code=400); return
                    if projeto.loja_id != loja.id:
                        self.send_json({"ok": False, "erro": "O projeto não pertence a esta loja."}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    try:
                        markup = float(campos.get("markup_pct") or 0)
                    except ValueError:
                        markup = 0.0
                    _fname, data = arquivos["arquivo"]
                    preview = mod_nfe.preview(data, markup)
                    ref = "TESTE-" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(emitente, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja.id, projeto_nome, nota, tipo_documento="produto",
                                             emitente_id=emitente.id)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value if hasattr(res.status, "value") else res.status,
                                    "chave": res.chave, "numero": res.numero, "serie": res.serie,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/admin/lojas/<id>/modulos — grava topologia (domínios ativos).
            # ativos=None religa tudo; senão valida cada item ∈ modulos.DOMINIOS. Gated como o GET.
            m = _re.match(r'^/api/admin/lojas/(\d+)/modulos$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                import modulos as _mod
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    ativos = req.get("ativos")
                    if ativos is None:
                        loja.modulos_ativos = None
                    else:
                        if not isinstance(ativos, list):
                            self.send_json({"ok": False, "erro": "ativos deve ser lista ou null"}, code=400); return
                        invalidos = [x for x in ativos if x not in _mod.DOMINIOS]
                        if invalidos:
                            self.send_json({"ok": False, "erro": "Módulo(s) inválido(s): %s" % ", ".join(map(str, invalidos))}, code=400); return
                        _ok, _msg = _mod.topologia_valida(ativos)
                        if not _ok:
                            self.send_json({"ok": False, "erro": _msg}, code=400); return
                        loja.modulos_ativos = json.dumps(list(ativos))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/emitir-nfe — emite a NF-e da loja
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/emitir-nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import mod_nfe, mapa_fiscal, nfe_emissao, mod_fiscal
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    projeto = _projeto_da_loja(db, nome_safe, loja_id)
                    if projeto is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    loja = db.get(Loja, loja_id)
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "produto")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "produto")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    # Contribuinte exige Inscrição Estadual na NF-e. Se ainda não estiver cadastrada,
                    # coleta a IE do body no ato da emissão e persiste no Cliente.
                    if (cliente.tipo_dest == "contribuinte") and not (cliente.inscricao_estadual or "").strip():
                        ie = (req.get("ie") or "").strip()
                        if not ie:
                            self.send_json({"ok": False, "erro": "Informe a Inscrição Estadual do cliente para emitir a NF-e (contribuinte)."}, code=400); return
                        cliente.inscricao_estadual = ie
                        db.add(cliente); db.commit()
                    doc_id = req.get("fabrica_doc_id")
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe,
                                                             etapa_codigo="15", tipo="nfe_fabrica_xml").first() if doc_id else None
                    if not doc:
                        self.send_json({"ok": False, "erro": "XML da fábrica inválido."}, code=400); return
                    try:
                        markup = float(req.get("markup_pct") or 0)
                    except (TypeError, ValueError):
                        markup = 0.0   # markup inválido → custo (aceitável: emissão só em homologação por padrão)
                    xml_bytes = storage_ler_binario(os.path.join(_projeto_path(nome_safe), doc.arquivo_path))
                    preview = mod_nfe.preview(xml_bytes, markup)
                    ref = "NFE-" + nome_safe + "-" + str(doc.id)
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(emitente, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="produto",
                                             emitente_id=emitente.id, fabrica_doc_id=doc.id)
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        # wiring: NF-e produto autorizada = faturamento (D Contas a Receber / C Receita)
                        _fin_evento_seguro(loja_id, "faturamento", preview.get("totais", {}).get("venda_total"),
                                           nome_safe, "fat:" + ref)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value, "chave": res.chave, "numero": res.numero,
                                    "serie": res.serie, "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/emitir-nfse — emite a NFS-e (serviço, valor manual)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/emitir-nfse$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import mapa_fiscal, nfe_emissao, mod_fiscal
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    projeto = _projeto_da_loja(db, nome_safe, loja_id)
                    if projeto is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    loja = db.get(Loja, loja_id)
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "servico")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "servico")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    # IBGE do tomador é obrigatório para a NFS-e (L999 "Tomador Não Identificado").
                    # Clientes novos já capturam via ViaCEP no cadastro; para os antigos, backfill best-effort.
                    # Consistência (auditoria A11): alinha cidade/UF à MESMA fonte (ViaCEP) que define o IBGE,
                    # senão o tomador iria com município textual divergente do código IBGE.
                    if not (cliente.municipio_ibge or "").strip() and (cliente.cep or "").strip():
                        end = _endereco_por_cep(cliente.cep)
                        if end:
                            cliente.municipio_ibge = end["ibge"]
                            if end.get("cidade"): cliente.cidade = end["cidade"]
                            if end.get("uf"):     cliente.estado = end["uf"]
                            db.commit()
                    try:
                        valor = float(req.get("valor_servico") or 0)
                    except (TypeError, ValueError):
                        valor = 0.0
                    if valor <= 0:
                        self.send_json({"ok": False, "erro": "Informe o valor do serviço."}, code=400); return
                    # NFS-e por TENTATIVA: um RPS rejeitado é "morto" (a Focus deduplica por ref), então
                    # re-emitir usa um ref novo (NFSE-<projeto>-<n>). Se a última tentativa já está
                    # autorizada, é idempotente (não emite de novo). Corrige o beco-sem-saída da auditoria (A4).
                    nfse_regs = (db.query(DocumentoFiscal)
                                   .filter_by(projeto_nome=nome_safe, tipo_documento="servico")
                                   .order_by(DocumentoFiscal.id.asc()).all())
                    # Idempotente enquanto a última está autorizada OU ainda processando (evita 2ª nota
                    # antes de a 1ª resolver). Só rejeitada/cancelada libera uma nova tentativa.
                    if nfse_regs and nfse_regs[-1].status in ("autorizado", "processando"):
                        reg = nfse_regs[-1]
                        if reg.status == "autorizado":   # NFS-e autorizada conclui a etapa 15 (A14)
                            _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        self.send_json({"ok": True, "ref": reg.ref, "status": reg.status,
                                        "chave": reg.chave_nfe, "numero": reg.numero, "serie": reg.serie,
                                        "mensagem_sefaz": reg.mensagem_sefaz,
                                        "erros": json.loads(reg.erros_json) if reg.erros_json else [],
                                        "xml_doc_id": reg.xml_doc_id, "danfe_doc_id": reg.danfe_doc_id}); return
                    ref = "NFSE-%s-%d" % (nome_safe, len(nfse_regs) + 1)
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    discriminacao = req.get("discriminacao") or "Serviço de montagem/instalação de móveis planejados"
                    nota = mapa_fiscal.montar_nota_nfse(emitente, cliente, round(valor, 2), ref, data_emissao, discriminacao)
                    res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="servico",
                                             emitente_id=emitente.id)
                    # NFS-e autorizada conclui a etapa 15, como a NF-e de produto (auditoria A14).
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        # wiring: NFS-e (serviço) autorizada = faturamento de serviço
                        _fin_evento_seguro(loja_id, "faturamento", round(valor, 2), nome_safe, "fat:" + ref)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value, "chave": res.chave, "numero": res.numero,
                                    "serie": res.serie, "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/consultar
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/consultar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    ref = req.get("ref")
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    if not reg or reg.projeto_nome != nome_safe:   # a NF-e tem de pertencer a este projeto (evita cross-tenant via ref do body)
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.consultar(db, ref)
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                    self.send_json({"ok": True, "status": res.status.value, "chave": res.chave,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/cancelar
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/cancelar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    ref = req.get("ref")
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    if not reg or reg.projeto_nome != nome_safe:   # a NF-e tem de pertencer a este projeto (evita cross-tenant via ref do body)
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.cancelar(db, ref, req.get("justificativa") or "")
                    if res.status.value == "cancelado":
                        # nota cancelada → etapa 15 volta a não-conclusiva (não deixar "emitida" com NF-e cancelada)
                        _set_etapa_status(db, nome_safe, "15", "em_andamento", usuario["id"]); db.commit()
                    self.send_json({"ok": True, "status": res.status.value, "mensagem_sefaz": res.mensagem_sefaz})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            else:
                self.send_response(404)
                self.end_headers()

    def do_PUT(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        # ── PUT /api/financeiro/contas/<id> (renomear/reordenar) ──────────────
        m_conta = re.match(r"^/api/financeiro/contas/(\d+)$", path)
        if m_conta:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body) if body else {}
                r = mod_contabil.editar_conta(db, ot, oid, int(m_conta.group(1)),
                                              nome=dd.get("nome"), ordem=dd.get("ordem"))
                self.send_json({"ok": True, "conta": r})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/config-financeira ───────────────────────
        m_cfg = re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
        if m_cfg:
            import mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            erros = mod_provisoes.validar_config_financeira(req)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_cfg.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                loja.config_financeira_json = json.dumps(req, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal — config não-secreta ──────
        m_pf = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal$", path)
        if m_pf:
            import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            ok, erro = mod_fiscal.validar_config(req)
            if not ok:
                self.send_json({"ok": False, "erro": erro}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_pf.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                _fiscal_put_config(em, req)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal — config do Emitente central ──
        m_rpf = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal$", path)
        if m_rpf:
            import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            ok, erro = mod_fiscal.validar_config(req)
            if not ok:
                self.send_json({"ok": False, "erro": erro}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_rpf.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                _fiscal_put_config(em, req)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/segredos — write-only, cifrado ──
        m_seg = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/segredos$", path)
        if m_seg:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_seg.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                _fiscal_put_segredos(em, req)
                db.commit()
                self.send_json({"ok": True})
            except Exception:
                db.rollback()
                self.send_json({"ok": False, "erro": "Falha ao salvar segredos"}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal/segredos — write-only, cifrado ──
        m_rseg = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal/segredos$", path)
        if m_rseg:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_rseg.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                _fiscal_put_segredos(em, req)
                db.commit()
                self.send_json({"ok": True})
            except Exception:
                db.rollback()
                self.send_json({"ok": False, "erro": "Falha ao salvar segredos"}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/ambiente — troca explícita ──
        m_amb = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/ambiente$", path)
        if m_amb:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            amb = req.get("ambiente")
            if amb not in ("homologacao", "producao"):
                self.send_json({"ok": False, "erro": "ambiente inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_amb.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                ok, erro = _fiscal_put_ambiente(em, amb)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                db.commit()
                self.send_json({"ok": True, "ambiente_ativo": amb})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal/ambiente — troca explícita ──
        m_ramb = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal/ambiente$", path)
        if m_ramb:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            amb = req.get("ambiente")
            if amb not in ("homologacao", "producao"):
                self.send_json({"ok": False, "erro": "ambiente inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_ramb.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                ok, erro = _fiscal_put_ambiente(em, amb)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                db.commit()
                self.send_json({"ok": True, "ambiente_ativo": amb})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-emissao — default de emissão da rede ──
        m_pemr = re.match(r"^/api/admin/redes/(\d+)/perfil-emissao$", path)
        if m_pemr:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_pemr.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                payload, code = _perfil_emissao_put(db, "rede", rid, rede, req)
                self.send_json(payload, code=code)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-emissao — override de emissão da loja ──
        m_peml = re.match(r"^/api/admin/lojas/(\d+)/perfil-emissao$", path)
        if m_peml:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_peml.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                payload, code = _perfil_emissao_put(db, "loja", loja.id, loja, req)
                self.send_json(payload, code=code)
            finally:
                db.close()
            return

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
                try:
                    _recalcular_orcamento(orc, db); db.commit()
                    self.send_json({"ok": True, "sombra": _negociacao_breakdown(orc, db)})
                except Exception as _e:
                    db.rollback()
                    self.send_json({"ok": True, "sombra": None, "erro_sombra": str(_e)})
                return
            except ValueError as ve:
                db.rollback()
                self.send_json({"ok": False, "erro": str(ve)}, code=400)
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/orcamentos/<id>/out-forn — editar outros fornecedores ──
        m_out = re.match(r"^/api/orcamentos/(\d+)/out-forn$", path)
        if m_out:
            oid = int(m_out.group(1))
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
                try:
                    orc.out_forn = max(0.0, float(req.get("out_forn") or 0))
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "Valor inválido"}, code=400)
                    return
                db.commit()
                self.send_json({"ok": True, "sombra": _negociacao_breakdown(orc, db)})
                return
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
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
                    # backend autoritativo: NÃO aceita valor_total/valor_liquido do frontend
                    if "forma_pagamento" in req:
                        orc.forma_pagamento = req["forma_pagamento"] or None
                    if "negociacao_json" in req:
                        orc.negociacao_json = req["negociacao_json"] or None
                    orc.updated_at = datetime.utcnow()
                    db.flush()                      # forma_pagamento disponível para o recálculo
                    try:
                        _recalcular_orcamento(orc, db)
                    except Exception as _e:
                        print("[CUTOVER] recalculo no PATCH falhou:", _e)
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
                    # Guarda das etapas operacionais (12/13/14): exige XML / números /
                    # relatório antes de concluir. Usa o obs recebido no request (se veio
                    # junto do status) ou o persistido na etapa.
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in mod_ciclo.ETAPAS_OPERACIONAIS:
                        tem_xml = db.query(CicloDocumento).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="12",
                            tipo=mod_ciclo.tipo_doc_operacional("12")).first() is not None
                        obs_efetivo   = obs if obs is not None else etapa.observacoes
                        numeros_txt   = obs_efetivo if etapa_cod == "13" else None
                        relatorio_txt = obs_efetivo if etapa_cod == "14" else None
                        ok_op, erro_op = mod_ciclo.guarda_conclusao_operacional(
                            etapa_cod, tem_xml, numeros_txt, relatorio_txt)
                        if not ok_op:
                            self.send_json({"ok": False, "erro": erro_op}, code=400)
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
                    loja_dict = _loja_dict_para_contrato(db, contrato.loja_id or loja_id)
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
                        "_ambientes":      _ambientes_valor_para_contrato(contrato.orcamento_id, db),
                    })
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    if not contrato.loja_id:
                        contrato.loja_id = loja_id
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m_perfil = re.match(r"^/api/admin/perfis/([a-z0-9_]+)$", path)
            if m_perfil:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    import perfil_store
                    p, err = perfil_store.editar_perfil(db, usuario.get("loja_id"), m_perfil.group(1),
                                nome=req.get("nome"), modulos=req.get("modulos"),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}, code=403); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}})
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
                    if "cpf" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cpf"), "CPF", "cpf")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
                    if "nome" in req:     u.nome     = req["nome"].strip()
                    if "nivel" in req:    u.nivel    = req["nivel"].strip()
                    if "telefone" in req: u.telefone = (req.get("telefone") or "").strip()
                    if "whatsapp" in req: u.whatsapp = (req.get("whatsapp") or "").strip()
                    if "email" in req:    u.email    = (req.get("email") or "").strip()
                    if "cpf" in req:      u.cpf      = (req.get("cpf") or "").strip()
                    if "ativo" in req:    u.ativo    = 1 if req["ativo"] else 0
                    if req.get("senha"):  u.set_senha(req["senha"])
                    # Apenas super_admin e admin_rede gerenciam memberships de lojas.
                    # Atores de loja (diretor/gerente_adm_fin) não reescrevem usuario_lojas —
                    # o modal deles só exibe a própria loja e re-escreveria a lista incorretamente,
                    # revogando memberships atribuídas por um admin_rede silenciosamente.
                    if "loja_ids" in req and (
                            mod_tenancy._eh_super_admin(ator)
                            or mod_tenancy._eh_admin_rede(ator)):
                        novas, erros_l = mod_tenancy.lojas_do_novo_usuario(ator, req)
                        if erros_l:
                            self.send_json({"ok": False, "erro": " ".join(erros_l)}); return
                        if not mod_tenancy._eh_super_admin(ator):
                            for lid in novas:
                                loja = db.get(Loja, lid)
                                if not loja or not mod_tenancy.pode_ver_loja(
                                        ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                    self.send_json({"ok": False, "erro": "Loja fora do seu escopo."}); return
                        db.query(UsuarioLoja).filter(UsuarioLoja.usuario_id == u.id).delete()
                        for lid in novas:
                            db.add(UsuarioLoja(usuario_id=u.id, loja_id=lid))
                        u.loja_id = novas[0] if novas else u.loja_id
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
                    if "cnpj" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
                        r.cnpj = (req["cnpj"] or "").strip() or None
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
                    if "cnpj" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
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


def _endereco_por_cep(cep):
    """Consulta o ViaCEP e devolve {'ibge', 'cidade', 'uf'} (best-effort, offline-safe) ou None.
    Nunca lança — qualquer falha (rede, CEP inválido, JSON, sem IBGE) degrada para None."""
    try:
        dig = re.sub(r"\D", "", cep or "")   # `re` (global do módulo); `_re` só existe local nos handlers
        if len(dig) != 8:
            return None
        import requests
        r = requests.get("https://viacep.com.br/ws/%s/json/" % dig, timeout=5)
        d = (r.json() or {}) if r.status_code == 200 else {}
        ibge = d.get("ibge")
        if not ibge:
            return None
        return {"ibge": ibge, "cidade": d.get("localidade") or None, "uf": d.get("uf") or None}
    except Exception:
        return None


def _ibge_por_cep(cep):
    """Compat: só o código IBGE do município (via `_endereco_por_cep`). Usado no backfill de
    clientes antigos sem `municipio_ibge`."""
    end = _endereco_por_cep(cep)
    return end["ibge"] if end else None


def _bloqueio_modulo(path, loja):
    """(True, msg) se o path pertence a um módulo de domínio DESLIGADO para a loja; senão (False, None).
    Default tudo-ligado → nunca bloqueia sem config explícita. Topologia (ARQUITETURA-MODULOS.md)."""
    import modulos as _mod
    mod = _mod.modulo_do_path(path)
    if mod is None or loja is None:
        return (False, None)
    if mod_tenancy.modulo_ativo(loja, mod):
        return (False, None)
    return (True, "Módulo '%s' não está habilitado para esta loja." % mod)


def _cliente_dict(c) -> dict:
    return {
        "id":          c.id,
        "nome":        c.nome,
        "cpf":         c.cpf         or "",
        "tipo_dest":         c.tipo_dest         or "nao_contribuinte",
        "cnpj":              c.cnpj              or "",
        "inscricao_estadual":c.inscricao_estadual or "",
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
        "municipio_ibge": c.municipio_ibge or "",
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


def _cfg_financeira_loja(db, loja_id):
    """config_financeira (dict) da loja, ou o default. Base dos defaults de negociação
    (comissão do arquiteto, fidelidade, carga tributária) herdados por projetos novos."""
    import mod_provisoes
    loja = db.get(Loja, loja_id) if loja_id else None
    if loja and loja.config_financeira_json:
        try:
            # Merge com o default preenche chaves novas (ex.: cronograma_padrao, v11) em configs
            # salvos antes da chave existir — o gatilho da assinatura usa esta função.
            return {**mod_provisoes.config_financeira_default(), **json.loads(loja.config_financeira_json)}
        except Exception:
            pass
    return mod_provisoes.config_financeira_default()


def _params_iniciais_projeto(db, projeto_nome, loja_id):
    """parametros de um projeto SEM parametros_json salvos: defaults da loja e — se houver
    parceiro no projeto — comissão do arquiteto e fidelidade já ATIVAS (valores de cadastro).
    % do arquiteto = o do próprio parceiro; se ausente, o default da loja. Fidelidade entra
    sempre que houver parceiro. São apenas os valores INICIAIS: uma vez salvos em
    parametros_json, passam a ser respeitados como estão (as edições persistem)."""
    import mod_omie
    from mod_orcamento_params import parametros_default_loja
    par = parametros_default_loja(_cfg_financeira_loja(db, loja_id))
    proj_json = mod_omie._carregar_projeto(projeto_nome) or {}
    parceiro_id = proj_json.get("parceiro_id")
    if parceiro_id:
        parc = db.get(Parceiro, int(parceiro_id))
        pct_parc = float(getattr(parc, "comissao_padrao_pct", 0) or 0) if parc else 0.0
        par["comissao_arq_ativa"] = True
        if pct_parc > 0:
            par["comissao_arq_pct"] = pct_parc
        par["fidelidade_ativa"] = True
    return par


def _negociacao_breakdown(orc, db):
    """Calcula a cadeia do motor lendo SÓ os insumos salvos (parametros_json, desconto do
    orçamento, descontos por ambiente, forma_pagamento). Sem overrides do frontend. NÃO grava."""
    import mod_negociacao, mod_provisoes, mod_orcamento_params
    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
    # Carrega cfg da loja uma única vez — usado para defaults de params E para provisões
    _loja = db.get(Loja, orc.loja_id) if getattr(orc, "loja_id", None) else None
    cfg = {}
    if _loja and _loja.config_financeira_json:
        try:
            cfg = json.loads(_loja.config_financeira_json)
        except Exception:
            cfg = {}
    if not cfg:
        cfg = mod_provisoes.config_financeira_default()
    # Projetos sem parametros_json herdam os defaults de negociação da loja (incl. carga_trib)
    params = (json.loads(proj.parametros_json) if (proj and proj.parametros_json)
              else mod_orcamento_params.parametros_default_loja(cfg))
    desc_orc = orc.desconto_pct or 0.0
    ambs, ids = [], []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                         "desc_amb_pct": float(lk.desconto_individual_pct or 0.0)})
            ids.append(lk.pool_ambiente_id)
    total_cliente = None
    try:
        fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else None
        if isinstance(fp, dict) and fp.get("total_cliente"):
            total_cliente = float(fp["total_cliente"])
    except Exception:
        total_cliente = None
    pool_proj = db.query(PoolAmbiente).filter_by(projeto_id=orc.projeto_id).all()
    n_total_proj = len(pool_proj) or None
    vbvo_proj = sum((pa.budget_total or 0.0) for pa in pool_proj) or None
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc,
                                           n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    cust_fin = 0.0 if total_cliente is None else max(0.0, total_cliente - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin,
                                          n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    for i, amb in enumerate(d.get("ambientes", [])):
        amb["id"] = ids[i] if i < len(ids) else None
    # v1: usa o Val_Liq do próprio orçamento como proxy do acumulado mensal do consultor.
    # Fase 2 troca por um acumulador mensal por (consultor, loja, mês). Ver spec/PROVISOES_E_VARIAVEIS.md.
    com_venda_pct = mod_provisoes.resolver_comissao_venda(cfg, d.get("Val_Liq", 0.0), desc_orc)
    prov = mod_provisoes.provisoes_orcamento(d, cfg, out_forn=(orc.out_forn or 0.0),
                                             com_venda_pct=com_venda_pct)
    d.update(prov)
    return d


def _registrar_provisao_venda(db, orc, por_id):
    """Grava (ou re-snapshota) a versão 'venda' das provisões a partir do breakdown atual."""
    d = _negociacao_breakdown(orc, db)
    itens = mod_provisoes.itens_provisao(d)
    existente = db.query(ProvisaoRegistro).filter_by(
        orcamento_id=orc.id, versao="venda").first()
    if existente:
        db.delete(existente); db.flush()
    db.add(ProvisaoRegistro(
        orcamento_id=orc.id, versao="venda",
        itens_json=json.dumps(itens, ensure_ascii=False),
        cfo=float(d.get("CFO") or 0), val_liq=float(d.get("Val_Liq") or 0),
        cust_var=float(d.get("Cust_Var") or 0), marg_cont=float(d.get("Marg_Cont") or 0),
        decisao=None, por_id=por_id))


def _recalcular_orcamento(orc, db):
    """Recalcula a negociação pelo motor e GRAVA: colunas sombra + valor_total/valor_liquido.
    `valor_total` vem da modalidade (forma_pagamento.total_cliente, já calculada com o VAVO);
    à vista ⇒ valor_total = VAVO. NÃO grava se contrato assinado (chamador já checa)."""
    d = _negociacao_breakdown(orc, db)
    orc.vbvo, orc.cfo, orc.vbno, orc.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
    orc.cust_ad, orc.val_liq = d["Cust_Ad"], d["Val_Liq"]
    orc.com_arq_orc, orc.pro_fid_orc = d["Com_Arq"], d["Pro_Fid"]
    orc.desc_tot_pct, orc.markup, orc.prov_imp = d["Desc_Tot"], d["Markup"], d["Prov_Imp"]
    orc.cust_fin, orc.val_cont = d["Cust_Fin"], d["Val_Cont"]
    # persistência autoritativa (cutover):
    orc.valor_total = d["Val_Cont"]
    orc.valor_liquido = d["Val_Liq"]


def _get_usuario_telefone(usuario_id: int, db) -> str:
    """Retorna telefone do usuário ou string vazia se não encontrado."""
    u = db.get(Usuario, usuario_id)
    return (u.telefone or "").strip() if u else ""


def _ambientes_valor_para_contrato(orcamento_id, db):
    """Lista [(nome_exibicao, valor_com_financeiro), ...] para a seção de ambientes
    do contrato. Reusa o breakdown do motor e o rateio de mod_contrato."""
    from mod_contrato import ambientes_valor_contrato
    orc = db.get(Orcamento, orcamento_id)
    if not orc:
        return []
    d = _negociacao_breakdown(orc, db)
    nome_por_id = {
        oa.pool_ambiente_id: oa.pool_ambiente.nome_exibicao
        for oa in db.query(OrcamentoAmbiente)
                    .filter_by(orcamento_id=orcamento_id)
                    .join(PoolAmbiente).all()
    }
    itens = [(nome_por_id.get(a.get("id"), ""), float(a.get("VAVA") or 0.0))
             for a in d.get("ambientes", [])]
    return ambientes_valor_contrato(itens, d.get("VAVO", 0.0), d.get("Val_Cont", 0.0))


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
        "pix":                 p.pix                  or "",
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
    abr = (req.get("abrangencia") or "loja").strip()
    # Usuário de loja: sem seleção explícita de lojas, o parceiro entra na loja ATIVA do
    # ator. O seletor de lojas é conveniência administrativa; consultor/gerente não precisa
    # dele — "no mínimo", o parceiro entra na loja de quem o cadastrou.
    if abr == "loja" and not (req.get("lojas") or []):
        loja_ativa = ator.get("active_loja_id") or ator.get("loja_id")
        if loja_ativa is not None:
            req = {**req, "lojas": [{"loja_id": loja_ativa,
                                     "comissao_padrao_pct": req.get("comissao_padrao_pct") or 0}]}
    erros = mod_tenancy.validar_abrangencia_parceiro(req)
    if erros:
        return erros
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


def _ator_dict(db, usuario_sessao, header_loja_id=None):
    """Re-consulta o usuário logado e resolve a loja ativa (multi-loja)."""
    if header_loja_id is None:
        header_loja_id = _REQ_LOJA_ATIVA
    u = db.get(Usuario, usuario_sessao.get("id"))
    if not u:
        return {"nivel": usuario_sessao.get("nivel"), "loja_id": None,
                "rede_id": None, "active_loja_id": None, "lojas_ids": []}
    membership = membership_loja_ids(db, u.id)
    active = mod_tenancy.resolver_loja_ativa(membership, header_loja_id, u.loja_id)
    return {"nivel": u.nivel, "loja_id": u.loja_id, "rede_id": u.rede_id,
            "active_loja_id": active, "lojas_ids": membership}


def _resolver_pdf_contrato(pdf_path):
    """Resolve o caminho do arquivo do contrato de forma robusta. O `pdf_path` salvo pode ser
    um caminho ABSOLUTO (ex.: Windows 'E:/...') que não resolve neste ambiente (WSL/Linux,
    case-sensitive); nesse caso cai para CONTRATOS_DIR/<basename>. Retorna o caminho válido
    (existente) ou None."""
    if not pdf_path:
        return None
    if os.path.exists(pdf_path):
        return pdf_path
    from mod_contrato import CONTRATOS_DIR
    base = os.path.basename(str(pdf_path).replace('\\', '/'))
    alt = os.path.join(CONTRATOS_DIR, base)
    return alt if os.path.exists(alt) else None


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


# ── Mapa de Atribuições (Regras_Funcoes_Perfis_Atribuicoes §4/§5) — helpers de I/O; a REGRA pura
#    mora em mod_escopo. ────────────────────────────────────────────────────────────────────────
def _pode_editar_mapa(nivel):
    """Abrir/editar o Mapa: Gerência+ (autorizar/aprovar_financeiro) ou Supervisor de Montagem."""
    return bool(nivel) and (perfis.pode(nivel, "autorizar") or perfis.pode(nivel, "aprovar_financeiro")
                            or nivel == "supervisor_montagem")


def _bloqueio_comercial(ator):
    """Visão do papel (Regras §3): operacional (PE/Medidor/Montagem) NUNCA vê o comercial
    (negociação, valores, margem, comissão). Retorna a msg de erro (403) ou None."""
    if mod_escopo.visao_do_papel(ator) == "operacional":
        return "Sem acesso ao comercial (visão operacional)."
    return None


def _sem_acesso_modulo(usuario, modulo_id, handler=None):
    """True se o PERFIL do usuário não acessa o módulo (Perfil-4 rev2 §2, matriz de acesso).
    Se `handler` for dado, honra um grant de step-up (senha de quem tem o perfil) na sessão."""
    if perfis.acessa_modulo((usuario or {}).get("nivel"), modulo_id):
        return False
    if handler is not None:
        from auth_routes import get_token_from_cookie
        token = get_token_from_cookie(handler.headers.get("Cookie", ""))
        if _stepup_valido(token, modulo_id):
            return False
    return True


# Etapa do ciclo → papel operacional do Mapa (Regras §7). O Mapa é o default do responsável da fase.
_ETAPA_PAPEL = {
    "9": "medicao", "10": "medicao",
    "11": "projeto_executivo", "11a": "projeto_executivo", "11b": "projeto_executivo",
    "11c": "projeto_executivo", "11e": "projeto_executivo",
    "17": "montagem", "18": "assistencia",
}


def _ambientes_do_projeto(db, nome_safe):
    """[{id, nome}] dos PoolAmbiente do projeto (para a grade do Mapa)."""
    return [{"id": pa.id, "nome": pa.nome_exibicao or pa.nome}
            for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe)
                        .order_by(PoolAmbiente.id.asc()).all()]


def _atribuicoes_dicts(db, nome_safe):
    """Atribuições vigentes do projeto como dicts puros (para mod_escopo)."""
    return [{"id": a.id, "papel": a.papel, "pool_ambiente_id": a.pool_ambiente_id,
             "funcionario_id": a.funcionario_id, "terceiro_id": a.terceiro_id}
            for a in db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()]


def _serializar_atribuicoes(db, nome_safe):
    """Atribuições do projeto com nomes resolvidos (funcionário/terceiro, função, ambiente)."""
    regs = db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()
    fio = {f.id: f for f in db.query(Funcionario).filter(Funcionario.id.in_(
        [r.funcionario_id for r in regs if r.funcionario_id])).all()} if regs else {}
    ter = {t.id: t for t in db.query(Terceiro).filter(Terceiro.id.in_(
        [r.terceiro_id for r in regs if r.terceiro_id])).all()} if regs else {}
    fnc = {}
    fids = {o.funcao_id for o in list(fio.values()) + list(ter.values()) if getattr(o, "funcao_id", None)}
    if fids:
        fnc = {f.id: f.nome for f in db.query(Funcao).filter(Funcao.id.in_(fids)).all()}
    amb = {pa.id: (pa.nome_exibicao or pa.nome)
           for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe).all()}
    out = []
    for r in regs:
        alvo = fio.get(r.funcionario_id) if r.funcionario_id else ter.get(r.terceiro_id)
        out.append({
            "id": r.id, "papel": r.papel, "pool_ambiente_id": r.pool_ambiente_id,
            "ambiente_nome": amb.get(r.pool_ambiente_id, "(projeto inteiro)") if r.pool_ambiente_id else "(projeto inteiro)",
            "funcionario_id": r.funcionario_id, "terceiro_id": r.terceiro_id,
            "responsavel_nome": (alvo.nome if alvo else ""),
            "funcao_nome": fnc.get(getattr(alvo, "funcao_id", None), "") if alvo else "",
        })
    return out


# ── Perfil fiscal: lógica comum entre o dono LOJA (loja.emitente_id) e o dono
#    REDE (rede.emitente_central_id). Os handlers só resolvem o Emitente do dono
#    (via _emitente_do_dono) e delegam a estas funções puras. ────────────────────
def _opcoes_emitente(db, kind, obj):
    """Opções de Emitente que um dono (loja|rede) pode escolher no Perfil de Emissão.
    Loja: o próprio CNPJ (self) + a central da rede (se houver). Rede: só a central."""
    ops = []
    if kind == "loja":
        if getattr(obj, "emitente_id", None):
            e = db.get(Emitente, obj.emitente_id)
            if e:
                ops.append({"id": e.id,
                            "label": "Este CNPJ — " + (e.razao_social or e.cnpj or str(e.id)),
                            "papel": "self"})
        if getattr(obj, "rede_id", None):
            r = db.get(Rede, obj.rede_id)
            if r and r.emitente_central_id:
                c = db.get(Emitente, r.emitente_central_id)
                if c:
                    ops.append({"id": c.id,
                                "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)),
                                "papel": "central"})
    else:
        if getattr(obj, "emitente_central_id", None):
            c = db.get(Emitente, obj.emitente_central_id)
            if c:
                ops.append({"id": c.id,
                            "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)),
                            "papel": "central"})
    return ops


def _perfil_emissao_get(db, kind, owner_id, obj):
    """Estado do Perfil de Emissão do dono: emitente_id de cada tipo_doc + opções."""
    out = {"ok": True, "opcoes": _opcoes_emitente(db, kind, obj)}
    for tipo in ("produto", "servico"):
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=kind, owner_id=owner_id, tipo_doc=tipo).first())
        out[tipo] = pe.emitente_id if pe else None
    return out


def _perfil_emissao_put(db, kind, owner_id, obj, req):
    """Upsert/delete das linhas de PerfilEmissao conforme {produto, servico}.
    Só toca um tipo se a chave estiver presente no corpo. Valida contra as opções.
    Retorna (payload_ou_erro, code)."""
    opcoes_ids = [o["id"] for o in _opcoes_emitente(db, kind, obj)]
    for tipo in ("produto", "servico"):
        if tipo not in req:
            continue
        val = req.get(tipo)
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=kind, owner_id=owner_id, tipo_doc=tipo).first())
        if val is None:
            if pe:
                db.delete(pe)
            continue
        try:
            val = int(val)
        except (TypeError, ValueError):
            return {"ok": False, "erro": "emitente_id inválido"}, 400
        if val not in opcoes_ids:
            return {"ok": False,
                    "erro": "emitente %s não é opção válida para este dono" % val}, 400
        if pe:
            pe.emitente_id = val
        else:
            db.add(PerfilEmissao(owner_tipo=kind, owner_id=owner_id,
                                 tipo_doc=tipo, emitente_id=val))
    db.commit()
    return _perfil_emissao_get(db, kind, owner_id, obj), 200


def _emitente_do_dono(db, kind, obj):
    """Devolve (Emitente|None, nome_do_atributo_FK) do dono (loja/rede)."""
    attr = "emitente_id" if kind == "loja" else "emitente_central_id"
    eid = getattr(obj, attr, None)
    return (db.get(Emitente, eid) if eid else None), attr


def _fiscal_criar_emitente(db, obj, attr, rede_id):
    """Cria um Emitente novo (homologação) e o linka ao dono. Retorna o Emitente."""
    em = Emitente(ambiente_ativo="homologacao", rede_id=rede_id)
    db.add(em); db.flush()
    setattr(obj, attr, em.id)
    return em


def _fiscal_get(em):
    """Payload do GET do perfil fiscal. NUNCA vaza token (só *_definido)."""
    import mod_fiscal, fiscal_cripto
    if not em:
        padrao = mod_fiscal.emitente_padrao_teste()
        placeholders = padrao.pop("placeholders")
        return {"ok": True, "existe": False, "perfil": padrao,
                "placeholders": placeholders, "ambiente_ativo": "homologacao",
                "token_homolog_definido": False, "token_prod_definido": False,
                "cert_validade": None, "cert_cnpj": None}
    perfil = {c: getattr(em, c) for c in (
        "razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
        "csosn_padrao", "csosn_contribuinte", "cfop_dentro_uf", "cfop_fora_uf",
        "serie_nfe", "discrimina_impostos", "cnae_servico", "cod_servico_municipio",
        "aliquota_iss", "retencao_json", "municipio_ibge", "papel_cnpj",
        "logradouro", "numero", "bairro", "cidade", "uf", "cep")}
    return {"ok": True, "existe": True, "perfil": perfil,
            "placeholders": json.loads(em.placeholders_json or "[]"),
            "ambiente_ativo": em.ambiente_ativo,
            "token_homolog_definido": fiscal_cripto.token_definido(em.focus_token_homolog_enc),
            "token_prod_definido": fiscal_cripto.token_definido(em.focus_token_prod_enc),
            "cert_validade": em.cert_validade.isoformat() if em.cert_validade else None,
            "cert_cnpj": em.cert_cnpj}


def _fiscal_put_config(em, req):
    """Aplica a allowlist de config não-secreta no Emitente (já resolvido/criado)."""
    for c in ("razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
              "csosn_padrao", "csosn_contribuinte", "cfop_dentro_uf", "cfop_fora_uf",
              "serie_nfe", "discrimina_impostos", "cnae_servico", "cod_servico_municipio",
              "aliquota_iss", "retencao_json", "municipio_ibge", "papel_cnpj",
              "logradouro", "numero", "bairro", "cidade", "uf", "cep",
              "cert_validade", "cert_cnpj"):
        if c in req:
            setattr(em, c, req[c])
    if "placeholders" in req:
        em.placeholders_json = json.dumps(req["placeholders"], ensure_ascii=False)


def _fiscal_put_segredos(em, req):
    """Grava tokens cifrados (write-only). None limpa; "" mantém."""
    import fiscal_cripto
    for campo, col in (("focus_token_homolog", "focus_token_homolog_enc"),
                       ("focus_token_prod", "focus_token_prod_enc")):
        if campo in req:
            v = req[campo]
            if v is None:
                setattr(em, col, None)
            elif v != "":
                setattr(em, col, fiscal_cripto.encrypt(v))


def _fiscal_put_ambiente(em, amb):
    """Troca o ambiente ativo. Retorna (ok, erro). Guarda produção via placeholders."""
    import mod_fiscal
    if amb == "producao":
        placeholders = json.loads(em.placeholders_json or "[]")
        if not mod_fiscal.pode_ativar_producao(placeholders):
            return False, ("Não é possível ativar produção com valores de teste pendentes: "
                           + ", ".join(placeholders))
    em.ambiente_ativo = amb
    return True, None


def _enriquecer_cliente_do_projeto(proj, db):
    """Atualiza o bloco 'cliente' do projeto.json (snapshot) com os dados VIVOS do cadastro
    (tabela clientes), para a tela de etapas nunca exibir contato defasado após uma edição."""
    if not isinstance(proj, dict):
        return
    cid = proj.get("cliente_id") or (proj.get("cliente") or {}).get("id")
    if not cid:
        return
    try:
        c = db.get(Cliente, int(cid))
    except (TypeError, ValueError):
        return
    if c is not None:
        proj["cliente"] = {**(proj.get("cliente") or {}), **_cliente_dict(c)}


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


def _ve_apenas_proprios_projetos(nivel):
    """True se o perfil vê só os projetos que criou (base operador). Gerência+ — e os
    operacionais de pós-venda — veem todos da loja. Dirigido pela BASE (perfis.py) para
    sobreviver à migração de nivel e escopar corretamente perfis customizados."""
    return perfis.base(nivel) == "operador"


def _usuario_ids_atribuidos_projeto(db, nome_safe):
    """Conjunto de usuario_id com QUALQUER atribuição no projeto (Mapa) — resolve
    Funcionario.usuario_id / Terceiro.usuario_id. Alimenta mod_escopo (Regras §5)."""
    regs = db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()
    if not regs:
        return set()
    fids = {r.funcionario_id for r in regs if r.funcionario_id}
    tids = {r.terceiro_id for r in regs if r.terceiro_id}
    uids = set()
    if fids:
        uids |= {u for (u,) in db.query(Funcionario.usuario_id).filter(Funcionario.id.in_(fids)).all() if u}
    if tids:
        uids |= {u for (u,) in db.query(Terceiro.usuario_id).filter(Terceiro.id.in_(tids)).all() if u}
    return uids


def _projetos_atribuidos_ao_usuario(db, usuario_id, loja_id):
    """Nomes dos projetos (na loja) onde o login `usuario_id` está atribuído no Mapa (via
    Funcionário/Terceiro vinculado). Vazio se o login não tem vínculo/atribuição."""
    if not usuario_id:
        return set()
    from sqlalchemy import or_
    fids = [r[0] for r in db.query(Funcionario.id).filter(Funcionario.usuario_id == usuario_id).all()]
    tids = [r[0] for r in db.query(Terceiro.id).filter(Terceiro.usuario_id == usuario_id).all()]
    conds = []
    if fids:
        conds.append(AtribuicaoAmbiente.funcionario_id.in_(fids))
    if tids:
        conds.append(AtribuicaoAmbiente.terceiro_id.in_(tids))
    if not conds:
        return set()
    return {r[0] for r in db.query(AtribuicaoAmbiente.projeto_nome).filter(
        AtribuicaoAmbiente.loja_id == loja_id, or_(*conds)).all()}


def _projeto_visivel_ao_ator(meta, ator, db=None):
    """Visibilidade DENTRO da loja (Regras §3/§6), via mod_escopo. Gerência+ tudo; Consultor por
    posse; operacional (PE/Medidor/Montagem) só o atribuído no Mapa; admin nada. `db` é necessário
    só para os operacionais (resolver o Mapa)."""
    if meta is None:
        return False
    if not mod_escopo.escopo_por_atribuicao(ator):
        return mod_escopo.pode_ver_projeto(ator, meta, set())     # fast path — sem consulta ao Mapa
    if db is None:
        return False                                              # conservador: operacional sem Mapa não vê
    atribuidos = _usuario_ids_atribuidos_projeto(db, getattr(meta, "nome_safe", None))
    return mod_escopo.pode_ver_projeto(ator, meta, atribuidos)


def _filtrar_projetos_por_loja(projetos, db, loja_id, ator=None):
    """Mantém só os projetos da loja (F4) e, dentro dela, o que o ator pode ver (Regras §3):
    Consultor → os que criou/legados; operacional (PE/Medidor/Montagem) → só os atribuídos no Mapa;
    demais → tudo na loja."""
    from sqlalchemy import or_
    nomes = [p.get("nome_safe") for p in projetos if p.get("nome_safe")]
    if not nomes:
        return []
    q = db.query(Projeto.nome_safe).filter(
        Projeto.nome_safe.in_(nomes), Projeto.loja_id == loja_id)
    if ator and _ve_apenas_proprios_projetos(ator.get("nivel")):
        q = q.filter(or_(Projeto.criado_por_id == ator.get("id"),
                         Projeto.criado_por_id.is_(None)))
    permitidos = {r[0] for r in q.all()}
    if ator and mod_escopo.escopo_por_atribuicao(ator):
        atrib = _projetos_atribuidos_ao_usuario(db, ator.get("id"), loja_id)
        permitidos &= atrib
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
    # (migrações margens->orcamento e margens->parametros removidas na faxina: a coluna
    #  Orcamento.margens foi removida; parâmetros vêm de Projeto.parametros_json e o desconto
    #  de Orcamento.desconto_pct.)
    port   = 8765
    # Host de bind configurável: padrão 127.0.0.1 (dev local seguro);
    # em produção defina ORIZON_HOST=0.0.0.0 para aceitar acesso externo.
    host   = os.environ.get("ORIZON_HOST", "127.0.0.1")
    server = HTTPServer((host, port), Handler)
    eh_local = host in ("127.0.0.1", "localhost")
    print("\n  Promob -> Omie  |  Negociacao de Margens  v7.3")
    print("  Bind: %s:%d" % (host, port))
    if eh_local:
        url = "http://127.0.0.1:%d" % port
        print("  Acesse: %s" % url)
        # Conveniencia de dev local: abre o navegador. Em producao (ORIZON_HOST=0.0.0.0) nao abre.
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
