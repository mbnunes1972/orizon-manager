# -*- coding: utf-8 -*-
"""OVERSIGHT-MODO, Queixa 2 (forma) — docs/db/TAREFA_OVERSIGHT_MODO.md, 28/09.

"O botão do oversight não está claro pra mim como funciona exatamente (...) deve ser diferente e
talvez posicionado em outro lugar para não confundir" — Marcelo, 28/09. O Oversight deixou de ser
um `.oc-chip` igual aos filtros (Todas/Grupos/Projetos/Arquivadas/Urgentes/Pendentes) e virou um
switch (`.sw`/`.sw-slider`, o MESMO componente já usado em Fiscal → Configuração Fiscal), com
rótulo "Ver toda a loja" e um aviso discreto na lista quando ligado. Fecha só com aceite visual
do Marcelo (item 7 do conserto) — este arquivo trava a FORMA (não há teste JS neste projeto:
verificação por inspeção do texto/estrutura fonte, mesmo padrão de outros achados de UI da
suíte), não substitui o aceite."""
import os
import re

REPO = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO, "static", "index.html")


def _html():
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


def test_chip_antigo_do_oversight_nao_existe_mais():
    """A CLASSE `.oc-chip-oversight` (a regra CSS e o atributo `class=`) some -- o comentário que
    cita o nome antigo pra explicar a mudança (histórico) é esperado e fica de fora da checagem."""
    html = _html()
    assert "class=\"oc-chip oc-chip-oversight" not in html, \
        "o Oversight voltou a ser um .oc-chip -- é exatamente a forma que o Marcelo pediu pra tirar"
    assert ".oc-chip-oversight{" not in html, "a regra CSS antiga do chip ainda existe"


def test_switch_do_oversight_usa_o_mesmo_componente_de_fiscal():
    """Reusa `.sw`/`.sw-slider` (Fiscal → Configuração Fiscal, "Discrimina impostos") -- não um
    estilo de switch novo."""
    html = _html()
    for prefixo in ("atd", "int"):
        assert 'id="%s-modo-wrap"' % prefixo in html
        assert 'id="%s-modo-check"' % prefixo in html
        assert 'class="sw"' in html
    # o switch fica DENTRO do wrap, não é mais um span.oc-chip
    m = re.search(r'<label class="oc-modo-wrap"[^>]*id="atd-modo-wrap".*?</label>', html, re.S)
    assert m, "wrap do switch (atd) não encontrado"
    assert '<span class="sw">' in m.group(0)
    assert 'onchange="atendOversightToggle()"' in m.group(0)


def test_rotulo_diz_o_que_o_switch_faz():
    """"Ver toda a loja" comunica mais que "Oversight" (pedido explícito do conserto, item 4)."""
    html = _html()
    assert "Ver toda a loja" in html
    assert html.count("Ver toda a loja") >= 2   # atd + int


def test_aviso_discreto_na_lista_quando_ligado():
    """Item 5 do conserto: a lista precisa dizer que está em outro modo, não só o switch aceso."""
    html = _html()
    assert 'id="atd-modo-aviso"' in html and 'id="int-modo-aviso"' in html
    assert "Todas as conversas da loja" in html


def test_modo_setar_reusado_pelos_dois_renderers_nao_duplicado():
    """1 função decide como o switch/aviso aparecem -- atendRender() e intRender() chamam a
    MESMA `_ocModoSetar`, não duas cópias do toggle (mesmo espírito da lição das quatro cópias
    do predicado de partição, agora extendida pro pedaço de UI)."""
    html = _html()
    assert html.count("function _ocModoSetar(") == 1
    assert "_ocModoSetar('atd'" in html
    assert "_ocModoSetar('int'" in html


def test_comportamento_de_empilhar_com_o_chip_continua_intacto():
    """Prova (item 6 do conserto / item 5 da Prova): "o comportamento NÃO muda -- continua
    empilhando com o filtro". Trava que a linha que filtra pelo chip escolhido por cima da fonte
    (Oversight ligado ou não) não foi tocada."""
    html = _html()
    assert "base.filter(c=>_ocDaChip(c,_atdChip))" in html
    assert "base.filter(c=>_ocDaChip(c,_intChip))" in html
    # a FONTE ainda alterna por _atdOversight/_intOversight -- é isso que faz o toggle
    # independente do chip, e o filtro por cima é o que faz ele empilhar
    assert "_atdOversight ? _ocTodasDoCanal('atd') : _atdInbox" in html
    assert "_intOversight ? _ocTodasDoCanal('int') : _intInbox" in html


def test_oversight_continua_abrindo_em_leitura_botao_entrar_intacto():
    """Item 6 do conserto: "continua abrindo em leitura, o botão Entrar na conversa continua
    como está" -- trava que OVERSIGHT-ENTRAR não foi mexido por esta tarefa."""
    html = _html()
    assert "await ocAbrirConversaPorId(c.id, _titAtd, false, c.tipo, c.projeto_nome);   // oversight" in html
    assert 'id="oc-entrar-btn"' in html
