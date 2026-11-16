"""A Câmara prepara a sessão somente depois de validar a entrada."""

import pytest
import responses

from raspe.exceptions import ValidationError
from raspe.scrapers.camara import ScraperCamaraDeputados
from tests._helpers import load_sample_bytes


@responses.activate
def test_entrada_invalida_nao_faz_requisicoes(mocker):
    mocker.patch("time.sleep")
    scraper = ScraperCamaraDeputados()
    with pytest.raises(ValidationError, match="ano"):
        scraper.raspar(pesquisa="x", ano=0)
    assert not responses.calls


@responses.activate
def test_primeira_busca_prepara_sessao_com_cookies_e_headers(mocker):
    mocker.patch("time.sleep")
    inicio = "https://www.camara.leg.br/"
    busca = "https://www.camara.leg.br/legislacao/busca"
    responses.add(responses.GET, inicio, body="início", headers={"Set-Cookie": "sessao=abc; Path=/"})
    responses.add(responses.GET, busca, body="busca")
    responses.add(responses.GET, busca, body=load_sample_bytes("camara", "raspar/no_results.html"))

    scraper = ScraperCamaraDeputados()
    assert not responses.calls
    scraper.raspar(pesquisa="inexistente")

    assert [call.request.url.split("?")[0] for call in responses.calls] == [inicio, busca, busca]
    assert responses.calls[1].request.headers["Referer"] == inicio
    assert responses.calls[2].request.headers["Referer"] == busca
    assert responses.calls[2].request.headers["Cookie"] == "sessao=abc"
    assert "Mozilla/5.0" in responses.calls[2].request.headers["User-Agent"]
