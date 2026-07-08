"""
auth_routes.py — Rotas de autenticação para integrar ao main.py
Orizon Manager | Dalmóbile

Como usar:
  1. No topo do main.py, adicione:
       from auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
  2. No do_GET, ANTES do bloco "if path == '/':", adicione:
       result = handle_auth_get(self, path)
       if result: return
  3. No do_POST, ANTES do bloco "if path == '/config':", adicione:
       result = handle_auth_post(self, path, body)
       if result: return
  4. No do_GET, troque o bloco "if path == '/':" por:
       if path == "/":
           usuario = get_usuario_sessao(self)
           if not usuario:
               self._redirect("/login")
               return
           body = _serve_html().encode()
           ...
"""

import json
import os
from auth import (
    fazer_login, fazer_logout, validar_sessao,
    verificar_desconto, autorizar_desconto,
    get_token_from_cookie, COOKIE_NAME
)
from database import get_session, Usuario, Loja, Rede, membership_loja_ids
import perfis

# ── Caminho do login.html ─────────────────────────────────────────────────────
_LOGIN_HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "login.html")


def get_usuario_sessao(handler) -> dict | None:
    """Retorna o usuário da sessão atual ou None."""
    cookie = handler.headers.get("Cookie", "")
    token  = get_token_from_cookie(cookie)
    return validar_sessao(token)


def handle_auth_get(handler, path: str) -> bool:
    """
    Trata rotas GET de autenticação.
    Retorna True se a rota foi tratada, False caso contrário.
    """
    if path == "/login":
        _serve_login(handler)
        return True

    if path == "/logout":
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        if token:
            fazer_logout(token)
        handler.send_response(302)
        handler.send_header("Location", "/login")
        handler.send_header("Set-Cookie", f"{COOKIE_NAME}=; Max-Age=0; Path=/; HttpOnly")
        handler.end_headers()
        return True

    if path == "/api/auth/me":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
        else:
            db = get_session()
            try:
                ids = membership_loja_ids(db, usuario["id"])
                if usuario.get("loja_id") and usuario["loja_id"] not in ids:
                    ids = ids + [usuario["loja_id"]]
                lojas_obj = db.query(Loja).filter(Loja.id.in_(ids)).all() if ids else []
                rede_ids = {l.rede_id for l in lojas_obj if l.rede_id}
                redes = ({r.id: r.nome for r in db.query(Rede).filter(Rede.id.in_(rede_ids)).all()}
                         if rede_ids else {})
                # rede_id/rede_nome por loja: o front decide se oferece abrangência 'rede'
                lojas = [{"id": l.id, "nome": l.nome, "codigo": l.codigo,
                          "rede_id": l.rede_id, "rede_nome": redes.get(l.rede_id, "")}
                         for l in lojas_obj]
                usuario["lojas"] = lojas
                usuario["loja_ativa_id"] = usuario.get("loja_id")
                # módulos ativos da loja ativa (topologia) — default tudo-ligado se sem loja/config
                import mod_tenancy, modulos as _mod
                _lid = usuario.get("loja_ativa_id") or usuario.get("loja_id")
                _loja_ativa = db.get(Loja, _lid) if _lid else None
                usuario["modulos_ativos"] = sorted(
                    mod_tenancy.modulos_ativos_da_loja(_loja_ativa)
                    if _loja_ativa else _mod.DOMINIOS)
            finally:
                db.close()
            _send_json(handler, {"ok": True, "usuario": usuario})
        return True

    return False


def handle_auth_post(handler, path: str, body: bytes) -> bool:
    """
    Trata rotas POST de autenticação.
    Retorna True se a rota foi tratada, False caso contrário.
    """
    if path == "/api/auth/login":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        resultado = fazer_login(dados.get("login", ""), dados.get("senha", ""))
        if resultado["ok"]:
            token = resultado["token"]
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header(
                "Set-Cookie",
                f"{COOKIE_NAME}={token}; Max-Age=28800; Path=/; HttpOnly"
            )
            resp = json.dumps(resultado).encode()
            handler.send_header("Content-Length", len(resp))
            handler.end_headers()
            handler.wfile.write(resp)
        else:
            _send_json(handler, resultado, 401)
        return True

    if path == "/api/auth/logout":
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        if token:
            fazer_logout(token)
        _send_json(handler, {"ok": True})
        return True

    if path == "/api/auth/verificar_desconto":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        cookie  = handler.headers.get("Cookie", "")
        token   = get_token_from_cookie(cookie)
        desconto = float(dados.get("desconto_pct", 0))
        resultado = verificar_desconto(token, desconto)
        _send_json(handler, resultado)
        return True

    if path == "/api/auth/autorizar_desconto":
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True

        cookie   = handler.headers.get("Cookie", "")
        token    = get_token_from_cookie(cookie)
        resultado = autorizar_desconto(
            token_solicitante  = token,
            login_autorizador  = dados.get("login_autorizador", ""),
            senha_autorizador  = dados.get("senha_autorizador", ""),
            desconto_pct       = float(dados.get("desconto_pct", 0)),
            contexto           = dados.get("contexto", {})
        )
        _send_json(handler, resultado)
        return True

    if path == "/api/auth/liberar_impostos":
        try:
            req = json.loads(body) if body else {}
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True
        login = (req.get("login_autorizador") or "").strip()
        senha = req.get("senha_autorizador") or ""
        db = get_session()
        try:
            u = db.query(Usuario).filter_by(login=login).first()
            if not u or not u.ativo or not u.check_senha(senha):
                _send_json(handler, {"ok": False, "erro": "Usuário ou senha inválidos."}, 401)
                return True
            if not perfis.pode(u.nivel, "aprovar_financeiro"):
                _send_json(handler, {"ok": False, "erro": "Perfil sem permissão para liberar impostos."}, 403)
                return True
            _send_json(handler, {"ok": True, "autorizador": {"nome": u.nome}})
        finally:
            db.close()
        return True

    return False


# ── Helpers internos ──────────────────────────────────────────────────────────
def _serve_login(handler):
    try:
        with open(_LOGIN_HTML, "rb") as f:
            body = f.read()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", len(body))
        handler.end_headers()
        handler.wfile.write(body)
    except FileNotFoundError:
        handler.send_response(404)
        handler.end_headers()
        handler.wfile.write(b"login.html not found")


def _send_json(handler, data: dict, status: int = 200):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)
