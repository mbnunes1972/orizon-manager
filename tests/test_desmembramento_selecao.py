"""Fase B — núcleo puro do desmembramento POR SELEÇÃO: numa etapa (9+), os ambientes SELECIONADOS
sofrem a ação da fase; os RESTANTES desmembram para uma nova fase. `particionar_por_selecao` valida e
separa (2 grupos, ordem do pool preservada). O congelamento (congelar_parcelas) e o gate de prazo
(mod_cronograma.prazo_excede_limite) já existem e são orquestrados pelo endpoint (B.2)."""
import mod_parcelas as mp


def test_particionar_separa_selecionados_e_restantes():
    ok, err, sel, rest = mp.particionar_por_selecao([1, 2, 3, 4], [2, 4])
    assert ok and err is None
    assert sel == [2, 4] and rest == [1, 3]        # ordem do pool preservada


def test_particionar_exige_ao_menos_um_selecionado():
    ok, err, sel, rest = mp.particionar_por_selecao([1, 2, 3], [])
    assert not ok and "ao menos um" in err.lower()


def test_particionar_exige_ao_menos_um_restante():
    # tudo selecionado → não há o que desmembrar
    ok, err, sel, rest = mp.particionar_por_selecao([1, 2], [1, 2])
    assert not ok and "desmembrar" in err.lower()


def test_particionar_rejeita_ambiente_fora_do_pool():
    ok, err, sel, rest = mp.particionar_por_selecao([1, 2], [2, 9])
    assert not ok and "9" in err


def test_particionar_dedup_e_ordem():
    ok, err, sel, rest = mp.particionar_por_selecao([10, 20, 30], [30])
    assert ok and sel == [30] and rest == [10, 20]
