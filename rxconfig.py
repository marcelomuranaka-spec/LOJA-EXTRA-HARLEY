import reflex as rx

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
