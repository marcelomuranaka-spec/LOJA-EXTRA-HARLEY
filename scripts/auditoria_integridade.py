"""
Verificação de integridade dos dados no Xano. SOMENTE LEITURA: nada é
alterado. Mostra contagens e ids (nunca nomes, documentos ou contatos).

Usa a mesma conta do app (.env, ver scripts/configurar_xano.ps1).
Uso, na raiz do projeto:  .venv\\Scripts\\python scripts\\auditoria_integridade.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harley_store import integridade  # noqa: E402
from harley_store import xano_client as xano  # noqa: E402

TABELAS = [
    "clientes", "fornecedores", "funcionarios", "produtos", "motos", "motos_clientes",
    "transacoes", "itens_transacao", "ordens_servico", "itens_ordem_servico",
    "entrada_mercadoria", "itens_compra_estoque",
]
# Referências que não estão em integridade.DEPENDENCIAS (cabeçalho -> itens,
# relações criadas depois do modelo original e itens de venda).
OUTRAS_REFERENCIAS = [
    ("itens_transacao", "transacao_id", "transacoes"),
    ("itens_transacao", "produto_id", "produtos"),
    ("itens_ordem_servico", "id_os", "ordens_servico"),
    ("itens_compra_estoque", "id_entrada", "entrada_mercadoria"),
    ("motos", "cliente_id", "clientes"),
]
STATUS_MOTOS = {"Em estoque", "Reservada", "Consignada", "Vendida"}
TIPOS_TRANSACAO = {"BALCAO", "PECAS", "MOTO", "ORDEM_SERVICO", "COMPRA"}
TIPOS_FUNCIONARIO = {"VENDEDOR", "MECANICO", "GERENTE"}
problemas = 0


def relatar(titulo: str, ids: list) -> None:
    global problemas
    if ids:
        problemas += 1
        amostra = ", ".join(str(i) for i in ids[:20]) + (" ..." if len(ids) > 20 else "")
        print(f"  [!] {titulo}: {len(ids)} (ids: {amostra})")
    else:
        print(f"  ok  {titulo}")


def duplicados(registros: list[dict], campo: str, normalizar=lambda v: str(v).strip().upper()) -> list:
    valores = Counter(normalizar(r.get(campo)) for r in registros if r.get(campo))
    return sorted(r["id"] for r in registros if r.get(campo) and valores[normalizar(r.get(campo))] > 1)


def so_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


async def main() -> None:
    dados = {}
    for tabela in TABELAS:
        dados[tabela] = await xano.listar(tabela)
        await asyncio.sleep(2)  # limite de requisições do plano Free do Xano
    ids = {t: {r["id"] for r in dados[t]} for t in TABELAS}
    print("Registros:", ", ".join(f"{t}={len(dados[t])}" for t in TABELAS))

    print("\nRegistros órfãos (apontam para um id que não existe):")
    referencias = [(filha, campo, mae) for mae, lista in integridade.DEPENDENCIAS.items()
                   for filha, campo, _ in lista] + OUTRAS_REFERENCIAS
    for filha, campo, mae in referencias:
        orfaos = sorted(r["id"] for r in dados[filha] if int(r.get(campo) or 0) and int(r[campo]) not in ids[mae])
        relatar(f"{filha}.{campo} -> {mae}", orfaos)

    print("\nDuplicidades:")
    relatar("clientes com o mesmo CPF/CNPJ", duplicados(dados["clientes"], "cpf_cnpj", so_digitos))
    relatar("fornecedores com o mesmo CNPJ", duplicados(dados["fornecedores"], "cnpj", so_digitos))
    for tabela in ("motos", "motos_clientes"):
        relatar(f"{tabela} com a mesma placa", duplicados(dados[tabela], "placa"))
        relatar(f"{tabela} com o mesmo chassi", duplicados(dados[tabela], "chassi"))

    print("\nEstoque e cadastros:")
    produtos = dados["produtos"]
    relatar("produtos com estoque negativo", [p["id"] for p in produtos if (p.get("estoque_qtd") or 0) < 0])
    relatar("produtos sem estoque informado (vazio)", [p["id"] for p in produtos if p.get("estoque_qtd") is None])
    relatar("produtos com preço de venda zero ou vazio", [p["id"] for p in produtos if not p.get("preco_venda")])
    relatar("produtos sem categoria", [p["id"] for p in produtos if not (p.get("categoria") or "").strip()])
    relatar("motos com situação vazia ou desconhecida", [m["id"] for m in dados["motos"] if m.get("status") not in STATUS_MOTOS])
    relatar("motos sem chassi", [m["id"] for m in dados["motos"] if not (m.get("chassi") or "").strip()])
    relatar("funcionários com tipo desconhecido", [f["id"] for f in dados["funcionarios"] if f.get("tipo") not in TIPOS_FUNCIONARIO])

    print("\nVendas (transacoes):")
    vendas = dados["transacoes"]
    itens_por_venda: dict[int, list[dict]] = {}
    for item in dados["itens_transacao"]:
        itens_por_venda.setdefault(int(item.get("transacao_id") or 0), []).append(item)
    # Só vendas novas (com status) têm itens; as antigas foram registradas sem itens.
    novas_ativas = [v for v in vendas if (v.get("status") or "").upper() == "ATIVA"]
    relatar("vendas ativas sem nenhum item", [v["id"] for v in novas_ativas if not itens_por_venda.get(v["id"])])
    relatar("vendas ativas com total diferente da soma dos itens", [
        v["id"] for v in novas_ativas if itens_por_venda.get(v["id"]) and abs(
            sum(int(i.get("quantidade") or 0) * float(i.get("valor_unitario") or 0) for i in itens_por_venda[v["id"]])
            - float(v.get("valor_total") or 0)) > 0.01])
    relatar("itens de venda com quantidade <= 0", [i["id"] for i in dados["itens_transacao"] if int(i.get("quantidade") or 0) <= 0])
    relatar("vendas com tipo desconhecido", [v["id"] for v in vendas if v.get("tipo_transacao") not in TIPOS_TRANSACAO])
    relatar("vendas sem funcionário", [v["id"] for v in vendas if not int(v.get("id_funcionario") or 0)])

    print("\nCompras e ordens de serviço:")
    itens_por_entrada = Counter(int(i.get("id_entrada") or 0) for i in dados["itens_compra_estoque"])
    relatar("compras sem nenhum item", [e["id"] for e in dados["entrada_mercadoria"] if not itens_por_entrada[e["id"]]])
    relatar("itens de compra com quantidade <= 0", [i["id"] for i in dados["itens_compra_estoque"] if int(i.get("quantidade") or 0) <= 0])
    relatar("itens de OS com quantidade <= 0", [i["id"] for i in dados["itens_ordem_servico"] if int(i.get("quantidade") or 0) <= 0])

    print(f"\n{problemas} tipo(s) de problema encontrado(s). Nada foi alterado.")


if __name__ == "__main__":
    asyncio.run(main())
