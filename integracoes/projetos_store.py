# -*- coding: utf-8 -*-
"""projetos_store.py — armazenamento em disco dos projetos (pasta + projeto.json + XMLs Promob).

Herdeiro LOCAL do antigo mod_omie.py (faxina 2026-07-23): a integração Omie foi removida
do produto; ficaram aqui só as funções de arquivo de projeto (criar/carregar/salvar/listar,
carga de XMLs do Promob, bloqueio com hash e verificação de integridade).
"""
import os, re, json, unicodedata, uuid
import xml.etree.ElementTree as ET
from datetime import datetime

from storage import (
    PROJETOS_DIR,
    storage_ler_json, storage_salvar_json, storage_existe,
    storage_listar, storage_salvar_texto, storage_salvar_binario,
    storage_ler_binario, storage_deletar,
    so_digitos, _sha256_str,
)
from .promob_grupos import GRUPOS, ler_xml_str


def _nome_safe(nome):
    """Remove acentos, substitui espacos por _, remove chars invalidos, max 60."""
    s = ''.join(c for c in unicodedata.normalize('NFD', nome or '') if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\\/*?:"<>|]', '', s).strip()
    s = re.sub(r'\s+', '_', s)
    return (s or 'projeto')[:60]

def _projeto_path(nome_safe):
    return os.path.join(PROJETOS_DIR, nome_safe)

def _carregar_projeto(nome_safe):
    """Le e retorna projeto.json. Retorna None se nao existir."""
    path = os.path.join(_projeto_path(nome_safe), 'projeto.json')
    if not storage_existe(path):
        return None
    return storage_ler_json(path)

def _salvar_projeto(dados_projeto):
    """Persiste projeto.json atualizando atualizado_em."""
    nome_safe = dados_projeto.get('nome_safe', '')
    pasta = _projeto_path(nome_safe)
    xmls_dir = os.path.join(pasta, 'xmls')
    if not storage_existe(xmls_dir):
        os.makedirs(xmls_dir, exist_ok=True)
    dados_projeto['atualizado_em'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    storage_salvar_json(os.path.join(pasta, 'projeto.json'), dados_projeto)

def _criar_projeto(nome_projeto, cliente_nome, cliente_cpf='', cliente_email='', cliente_telefone='', cliente_id=None, parceiro_id=None):
    """Cria pasta + projeto.json inicial. Retorna o projeto criado."""
    nome_safe = _nome_safe(nome_projeto)
    proj = {
        'nome_safe': nome_safe,
        'nome_projeto': nome_projeto,
        'cliente_id': cliente_id,
        'parceiro_id': parceiro_id,
        'cliente': {'nome': cliente_nome, 'cpf': cliente_cpf,
                    'email': cliente_email, 'telefone': cliente_telefone},
        'criado_em': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'atualizado_em': '',
        'margens': {
            'desconto_pct': 0.0,
            'custo_viagem': 0.0, 'fora_da_sede': False,
            'brinde': 0.0, 'brinde_ativo': False,
            'comissao_arq_pct': 0.0, 'comissao_arq_ativa': False,
            'fidelidade_pct': 0.0, 'fidelidade_ativa': False
        },
        'forma_pagamento': None,
        'ambientes': [],
        'orcamentos': []
    }
    # Garante unicidade do nome_safe
    base = nome_safe; i = 2
    while storage_existe(_projeto_path(nome_safe)):
        nome_safe = '%s_%d' % (base, i); i += 1
    proj['nome_safe'] = nome_safe
    _salvar_projeto(proj)
    return proj

def _listar_projetos():
    """Lista todos os projetos em PROJETOS/."""
    resultado = []
    for nome_safe in storage_listar(PROJETOS_DIR):
        proj = _carregar_projeto(nome_safe)
        if not proj:
            continue
        # Compatibilidade: app_12 salvava cliente como string
        cli = proj.get('cliente', {})
        if isinstance(cli, str):
            cliente_nome = cli
        else:
            cliente_nome = cli.get('nome', '') if isinstance(cli, dict) else ''
        resultado.append({
            'nome_safe':      nome_safe,
            'nome_projeto':   proj.get('nome_projeto', proj.get('cliente', '')),
            'cliente_nome':   cliente_nome,
            'cliente_id':     proj.get('cliente_id'),
            'cliente_cpf':    cli.get('cpf', '') if isinstance(cli, dict) else '',
            'parceiro_id':    proj.get('parceiro_id'),
            'atualizado_em':  proj.get('atualizado_em', ''),
            'n_ambientes':    len(proj.get('ambientes', [])),
            'n_selecionados': sum(1 for a in proj.get('ambientes', []) if a.get('selecionado')),
        })
    return resultado

def _buscar_projetos(q):
    """Filtra projetos por nome_projeto, cliente.nome ou cliente.cpf."""
    q = q.strip().lower()
    resultado = []
    for p in _listar_projetos():
        if (q in p['nome_projeto'].lower() or
            q in p['cliente_nome'].lower() or
            q in so_digitos(p.get('cliente_cpf', ''))):
            resultado.append(p)
    return resultado


def _extrair_cliente_e_ambiente(xml_str):
    root = ET.fromstring(xml_str)
    cd = {}
    for d in root.findall(".//CUSTOMERSDATA/DATA"):
        vid, val = d.get("ID", ""), d.get("VALUE", "")
        if vid == "nomecliente":
            cd["nome"] = val
        elif vid == "cpfcnpj":
            cd["cpf"] = val
    amb_el = root.find(".//AMBIENT")
    if amb_el is not None:
        cd["_ambiente_desc"] = amb_el.get("DESCRIPTION", "")
    return cd

def carregar_xmls(arquivos_xml):
    ambientes     = []
    cliente_dados = {}
    for arq_nome, arq_conteudo in arquivos_xml:
        try:
            amb   = ler_xml_str(arq_nome, arq_conteudo)
            extra = _extrair_cliente_e_ambiente(arq_conteudo)
            if not cliente_dados.get("nome") and extra.get("nome"):
                cliente_dados = {"nome": extra["nome"], "cpf": extra.get("cpf", "")}
            amb["ambiente"] = extra.get("_ambiente_desc") or amb["projeto"]
            ambientes.append(amb)
        except Exception as e:
            ambientes.append({
                "arquivo": arq_nome, "projeto": arq_nome, "ambiente": arq_nome,
                "data": datetime.today().strftime("%d/%m/%Y"),
                "total": 0.0, "grupos": [], "erro": str(e),
            })
    total_projeto = sum(a["total"] for a in ambientes)
    return {
        "ok":            True,
        "versao":        "3.0",
        "gerado_em":     datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "total_projeto": round(total_projeto, 2),
        "cliente":       cliente_dados,
        "ambientes":     ambientes,
        "grupos_ref":    GRUPOS,
    }

def _adicionar_ambientes(nome_safe, arquivos_xml):
    """
    Processa XMLs, copia para xmls/, adiciona/substitui em projeto.json.
    Retorna projeto atualizado.
    """
    projeto = _carregar_projeto(nome_safe)
    if not projeto:
        raise FileNotFoundError('Projeto nao encontrado: %s' % nome_safe)
    pasta_xmls = os.path.join(_projeto_path(nome_safe), 'xmls')
    os.makedirs(pasta_xmls, exist_ok=True)
    for nome_arq, conteudo in arquivos_xml:
        storage_salvar_texto(os.path.join(pasta_xmls, nome_arq), conteudo)
    dados = carregar_xmls(arquivos_xml)
    for amb in dados.get('ambientes', []):
        arq = amb['arquivo']
        projeto['ambientes'] = [a for a in projeto['ambientes'] if a['arquivo'] != arq]
        amb['selecionado'] = True
        amb['arquivo_path'] = os.path.join(pasta_xmls, arq)
        projeto['ambientes'].append(amb)
    _salvar_projeto(projeto)
    return projeto

def bloquear_projeto(nome_safe: str) -> dict:
    """
    Marca o projeto como aprovado/bloqueado.
    Calcula SHA-256 de cada XML em xmls/ e salva em hashes_xml.
    Após isso, nenhuma alteração de ambiente é permitida pelo backend.
    """
    import hashlib
    proj = _carregar_projeto(nome_safe)
    if not proj:
        raise FileNotFoundError("Projeto nao encontrado: %s" % nome_safe)
    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
    hashes = {}
    if os.path.isdir(pasta_xmls):
        for fname in sorted(os.listdir(pasta_xmls)):
            fpath = os.path.join(pasta_xmls, fname)
            if os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    hashes[fname] = hashlib.sha256(f.read()).hexdigest()
    proj["bloqueado"]    = True
    proj["bloqueado_em"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    proj["hashes_xml"]   = hashes
    _salvar_projeto(proj)
    return proj


def verificar_integridade_xmls(nome_safe: str) -> dict:
    """Verifica se os XMLs ainda correspondem aos hashes gravados na aprovação."""
    import hashlib
    proj = _carregar_projeto(nome_safe)
    if not proj or not proj.get("bloqueado"):
        return {"ok": True, "bloqueado": False}
    hashes_ok  = proj.get("hashes_xml", {})
    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
    erros = []
    for fname, h_esperado in hashes_ok.items():
        fpath = os.path.join(pasta_xmls, fname)
        if not os.path.isfile(fpath):
            erros.append("Arquivo ausente: %s" % fname)
            continue
        with open(fpath, "rb") as f:
            h_atual = hashlib.sha256(f.read()).hexdigest()
        if h_atual != h_esperado:
            erros.append("Hash diferente (possivel adulteracao): %s" % fname)
    return {"ok": len(erros) == 0, "bloqueado": True, "erros": erros}


# == LÓGICA DE GRUPOS OMIE ==

def _arquivar_xmls(nome_safe, arquivos_xml):
    """Copia XMLs para pasta de historico com timestamp."""
    pasta = os.path.join(PROJETOS_DIR, nome_safe)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_hist = os.path.join(pasta, "xmls_aprovados", ts)
    os.makedirs(pasta_hist, exist_ok=True)
    for nome_arq, conteudo in arquivos_xml:
        storage_salvar_texto(os.path.join(pasta_hist, nome_arq), conteudo)
    return pasta_hist
