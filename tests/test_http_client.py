"""POST de leitura do PoliteSession, sem rede."""

from __future__ import annotations

from scraper.http_client import PoliteSession


class _Resposta:
    def __init__(self, status=200, corpo=None, erro_json=False):
        self.status_code = status
        self._corpo = corpo
        self._erro_json = erro_json
        self.headers = {"content-type": "text/html"}

    def json(self):
        if self._erro_json:
            raise ValueError("nao e json")
        return self._corpo


def _sessao(resposta, chamadas):
    s = PoliteSession(user_agent="teste", delay_seconds=0)

    def post(url, **kwargs):
        chamadas.append((url, kwargs))
        return resposta
    s.session.post = post
    return s


def test_post_json_devolve_o_corpo_e_conta_a_requisicao():
    chamadas = []
    s = _sessao(_Resposta(corpo={"success": True}), chamadas)
    assert s.post_json("https://x.test", data={"action": "ler"}) == {"success": True}
    assert s.request_count == 1
    assert chamadas[0][1]["data"] == {"action": "ler"}
    assert chamadas[0][1]["timeout"] == s.timeout_seconds


def test_post_json_http_de_erro_vira_none():
    assert _sessao(_Resposta(status=403), []).post_json("https://x.test") is None


def test_post_json_resposta_nao_json_vira_none():
    assert _sessao(_Resposta(erro_json=True), []).post_json("https://x.test") is None
