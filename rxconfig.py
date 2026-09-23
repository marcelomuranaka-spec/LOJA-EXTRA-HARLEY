import reflex as rx

# Endereço e portas NÃO ficam aqui: cada ambiente os define por variáveis
# de ambiente REFLEX_* antes de iniciar (o Reflex as aplica por cima desta
# configuração). Não coloque o IP da loja neste arquivo, porque ele é
# versionado e compartilhado pelos dois ambientes.
#   - desenvolvimento: scripts/iniciar_dev.ps1      -> http://localhost:3001
#   - produção:        scripts/iniciar_producao.ps1 -> http://<IP>:3000
#     (o IP fica em producao.local.ps1, fora do git)
config = rx.Config(
    app_name="harley_store",
    # Banco local em arquivo — zero configuração, ótimo para rodar no PDV da loja.
    # Para usar o SQL Server original, troque por algo como:
    #   "mssql+pyodbc://usuario:senha@servidor/HarleyDavidsonStore?driver=ODBC+Driver+17+for+SQL+Server"
    # (nesse caso instale também: pip install pyodbc)
    # Para Postgres:  "postgresql+psycopg2://usuario:senha@host/harley_store"
    db_url="sqlite:///harley_store.db",
    tailwind=None,
)
