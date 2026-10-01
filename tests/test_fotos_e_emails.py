"""Testes das fotos oficiais, da descrição de compras e dos e-mails (rodam sem internet).

    .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import asyncio
import os
import unittest
from pathlib import Path
from unittest import mock

from harley_store import email_clientes
from harley_store.fotos_oficiais import cilindrada_oficial, foto_oficial
from harley_store.state.compras_state import descricao_dos_itens

ASSETS = Path(__file__).resolve().parent.parent / "assets"


class TestFotosOficiais(unittest.TestCase):
    def test_modelos_da_loja_tem_foto(self):
        for modelo in ["Harley-Davidson Iron 883", "Fat Boy 114", "heritage classic", "Sportster S",
                       "Pan America 1250 Special", "Street Glide Special", "Road Glide Limited",
                       "Low Rider S", "Breakout 117", "Nightster Special"]:
            foto = foto_oficial(modelo)
            self.assertTrue(foto, modelo)
            self.assertTrue((ASSETS / foto.lstrip("/")).exists(), foto)

    def test_modelo_parecido_nao_ganha_foto_errada(self):
        # nada de foto "inventada": modelo não reconhecido fica sem foto
        for modelo in ["Low Rider ST", "Street Glide", "Fat Bob 114", "Sportster", ""]:
            self.assertEqual(foto_oficial(modelo), "", modelo)

    def test_cilindrada(self):
        self.assertEqual(cilindrada_oficial("Iron 883"), 883)
        self.assertEqual(cilindrada_oficial("Breakout 117"), 1923)
        self.assertEqual(cilindrada_oficial("Modelo qualquer"), 0)


class TestDescricaoCompra(unittest.TestCase):
    def test_descricao_dos_itens(self):
        self.assertEqual(descricao_dos_itens([("Pneu Traseiro", 2), ("Óleo 10W30", 10)]),
                         "2x Pneu Traseiro; 10x Óleo 10W30")
        self.assertEqual(descricao_dos_itens([]), "")


class TestEmails(unittest.TestCase):
    def test_sem_configuracao_nao_envia(self):
        with mock.patch.dict(os.environ, {"SENDGRID_API_KEY": "", "SENDGRID_REMETENTE": ""}):
            self.assertFalse(email_clientes.boas_vindas("Ana Souza", "ana@exemplo.com"))

    def test_envia_para_o_sendgrid(self):
        enviado = {}

        class Resposta:
            status_code = 202
            text = ""

        async def post(_self, url, json, headers):
            enviado.update(url=url, json=json, headers=headers)
            return Resposta()

        async def cenario():
            with mock.patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.teste", "SENDGRID_REMETENTE": "loja@exemplo.com"}), \
                    mock.patch("httpx.AsyncClient.post", post):
                self.assertTrue(email_clientes.parabens_compra("<b>Ana</b> Souza", "ana@exemplo.com",
                                                               "Harley-Davidson Fat Boy 114"))
                await asyncio.gather(*email_clientes._tarefas)

        asyncio.run(cenario())
        self.assertEqual(enviado["url"], "https://api.sendgrid.com/v3/mail/send")
        self.assertEqual(enviado["headers"]["Authorization"], "Bearer SG.teste")
        self.assertEqual(enviado["json"]["personalizations"][0]["to"][0]["email"], "ana@exemplo.com")
        self.assertIn("Fat Boy 114", enviado["json"]["subject"])
        corpo_html = enviado["json"]["content"][1]["value"]
        self.assertNotIn("<b>Ana", corpo_html)  # nome do cliente é escapado no HTML


if __name__ == "__main__":
    unittest.main()
