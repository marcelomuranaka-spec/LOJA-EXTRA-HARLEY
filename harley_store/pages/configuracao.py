import reflex as rx

from ..components.confirm_dialog import confirm_delete_button
from ..components.layout import page
from ..components.ui import secao, tabela, vazio
from ..state.configuracao_state import ConfiguracaoState as C

NOVIDADES = [
    ("shield-check", "Perfis de acesso",
     "Sua conta é Administradora. Em Usuários do sistema você cria contas, define senhas e escolhe quem mais "
     "é administrador (botão “Tornar administrador”). Funcionários usam as telas da loja, mas não veem a "
     "Administração. O sistema sempre mantém pelo menos um administrador."),
    ("log-in", "Login mais seguro",
     "“Criar conta” e “Esqueci minha senha” saíram da tela de login (o Xano já os bloqueava). Quem precisar de "
     "acesso ou esquecer a senha fala com um administrador. A sessão agora é conferida no Xano: cookie inventado "
     "não abre mais o sistema."),
    ("server", "Conta de serviço",
     "O servidor do sistema não usa mais a sua conta pessoal: usa a conta “Sistema Harley Store” (perfil "
     "Funcionário). Ela aparece em Usuários do sistema e está protegida contra exclusão."),
    ("users", "Clientes",
     "Pesquisa por nome, CPF, telefone, e-mail ou cidade; filtros; ordenação; paginação; e a ficha do cliente "
     "(visão 360º) com motos, compras, ordens de serviço, orçamentos, interações, e-mails e linha do tempo."),
    ("bike", "Motos",
     "Motos dos clientes com foto, cadastradas na própria ficha do cliente. Motos da loja com situações "
     "Disponível, Reservada, Consignada, Em manutenção, Fora de estoque e Vendida, filtros por marca, ano e "
     "preço, e fotos adicionais."),
    ("package", "Produtos, categorias e estoque",
     "Estoque protegido (editar um produto não apaga uma venda feita ao mesmo tempo), ajuste de estoque, "
     "alerta de estoque baixo e cadastro de categorias. Ordem de serviço recusa peça sem estoque."),
    ("shopping-cart", "Vendas / Balcão",
     "Busca de cliente e produto digitando, venda de moto da loja (a moto vira Vendida sozinha), desconto em R$ "
     "ou %, forma de pagamento e comprovante logo após finalizar."),
    ("user-search", "Leads e e-mails",
     "Funil de leads com conversão em cliente (sem duplicar cadastro) e envio de e-mails pelo SendGrid, sempre "
     "por um clique, com histórico."),
]


def _novidade(item: tuple) -> rx.Component:
    icone, titulo, texto = item
    return rx.hstack(
        rx.icon(icone, size=18, color=rx.color("orange", 9), flex_shrink="0", margin_top="0.15rem"),
        rx.vstack(rx.text(titulo, weight="bold", size="2"), rx.text(texto, size="2", color=rx.color("gray", 11)),
                  spacing="0", align="start"),
        spacing="3",
        align="start",
        width="100%",
    )


def _campo_linha(c: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(rx.code(c["nome"])),
        rx.table.cell(c["tipo"]),
        rx.table.cell(rx.text(c["para_que"], size="2")),
        rx.table.cell(rx.cond(c["falta"], rx.badge("criar", color_scheme="orange", variant="soft"),
                              rx.badge(rx.icon("check", size=12), "ok", color_scheme="green", variant="soft"))),
    )


def _passos_tabela(item: dict) -> rx.Component:
    return rx.cond(
        item["nova"],
        rx.text(
            "No Xano: Database → Add Table → nome ", rx.code(item["tabela"]),
            " → crie os campos abaixo (todos opcionais, exceto o nome) → depois, em API → grupo das tabelas da "
            "loja (o mesmo de clientes/produtos), Add API Endpoint → CRUD Database Operations → tabela ",
            rx.code(item["tabela"]), " → exigir autenticação como as demais.",
            size="2",
        ),
        rx.text(
            "No Xano: Database → tabela ", rx.code(item["tabela"]),
            " → Add Field para cada campo marcado “criar” (opcional). Depois abra os endpoints POST e PATCH dessa "
            "tabela e inclua os mesmos campos nos inputs (e no “Add Record”/“Edit Record”), senão o Xano ignora "
            "o valor.",
            size="2",
        ),
    )


def _requisito(item: dict) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.cond(item["ativo"],
                        rx.badge(rx.icon("circle-check", size=12), "Ativo", color_scheme="green", variant="solid"),
                        rx.badge(rx.icon("plug-zap", size=12), "Aguardando", color_scheme="orange", variant="solid")),
                rx.text(item["titulo"], weight="bold"),
                spacing="2",
                align="center",
                flex_wrap="wrap",
            ),
            rx.text("Libera: ", item["libera"], size="2", color=rx.color("gray", 11)),
            rx.cond(
                ~item["ativo"].to(bool),
                rx.vstack(
                    rx.match(
                        item["tipo"],
                        ("endpoint", rx.text(
                            "No Xano: API → grupo das tabelas da loja (URL termina em api:LtU_pM2N) → Add API "
                            "Endpoint → POST, caminho upload/image → Inputs: File Resource chamado content → "
                            "Function Stack: Create Image from File (value = content, acesso public) → Response: "
                            "a imagem criada → Publish. Exija autenticação como os demais.", size="2")),
                        ("env", rx.vstack(
                            rx.text("1) Crie a conta no SendGrid e verifique o e-mail remetente (Sender "
                                    "Authentication). 2) Gere uma API Key com permissão Mail Send. 3) No arquivo "
                                    ".env do servidor (pasta do sistema; na produção, C:\\HARLEY_PROD\\.env) "
                                    "acrescente as linhas abaixo e reinicie o sistema:", size="2"),
                            rx.code_block("SENDGRID_API_KEY=SG.xxxxxxxx\nSENDGRID_REMETENTE=contato@sualoja.com.br\n"
                                          "SENDGRID_NOME_REMETENTE=Harley Store", language="bash", width="100%"),
                            rx.text("A chave nunca vai para o navegador nem para o git.", size="1",
                                    color=rx.color("gray", 10)),
                            spacing="2", width="100%", align="start")),
                        _passos_tabela(item),
                    ),
                    rx.cond(item["campos"].to(list).length() > 0,
                            tabela(["Campo", "Tipo no Xano", "Para quê", ""],
                                   rx.foreach(item["campos"].to(list[dict]), _campo_linha))),
                    spacing="2",
                    width="100%",
                    align="start",
                ),
            ),
            spacing="2",
            align="start",
            width="100%",
        ),
        width="100%",
    )


def _forma(f: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(f["nome"]),
        rx.table.cell(rx.cond(f["ativo"], rx.badge("Ativa", color_scheme="green", variant="soft"),
                              rx.badge("Desativada", color_scheme="gray", variant="soft"))),
        rx.table.cell(rx.flex(
            rx.button(rx.cond(f["ativo"], "Desativar", "Ativar"), size="1", variant="soft", color_scheme="gray",
                      on_click=C.alternar_forma(f["id"])),
            confirm_delete_button(C.excluir_forma(f["id"]), item_label=f"a forma “{f['nome']}”"),
            gap="0.5rem")),
    )


def _formas() -> rx.Component:
    return secao(
        "Formas de pagamento do balcão",
        rx.cond(
            C.formas_existe,
            rx.vstack(
                rx.hstack(
                    rx.input(value=C.nova_forma, on_change=C.set_nova_forma, placeholder="Ex.: PIX",
                             width="100%", max_width="280px"),
                    rx.button(rx.icon("plus", size=14), "Adicionar", on_click=C.adicionar_forma),
                    rx.cond(C.formas.length() == 0,
                            rx.button("Criar as formas mais comuns", variant="soft", on_click=C.criar_formas_padrao)),
                    spacing="2", flex_wrap="wrap",
                ),
                rx.cond(C.formas.length() > 0,
                        tabela(["Forma", "Situação", "Ações"], rx.foreach(C.formas, _forma)),
                        vazio("Nenhuma forma cadastrada: o balcão usa Dinheiro, PIX, débito e crédito.")),
                spacing="3", width="100%",
            ),
            rx.text("Enquanto a tabela formas_pagamento não existe, o balcão oferece Dinheiro, PIX, Cartão de débito "
                    "e Cartão de crédito.", size="2", color=rx.color("gray", 11)),
        ),
        icone="credit-card",
    )


def configuracao_page() -> rx.Component:
    return page(
        secao("O que mudou no sistema", *[_novidade(n) for n in NOVIDADES], icone="sparkles"),
        secao(
            "Recursos que dependem do Xano",
            rx.text("Tudo abaixo já está pronto no sistema. Cada item liga sozinho quando o que ele precisa for criado "
                    "no painel do Xano (só acréscimos: nenhum dado existente é apagado ou alterado). Depois de criar, "
                    "clique em “Verificar agora”.", size="2", color=rx.color("gray", 11)),
            rx.hstack(
                rx.text(rx.text.strong(C.ativos), " de ", rx.text.strong(C.total), " recursos ativos", size="3"),
                rx.progress(value=rx.cond(C.total > 0, C.ativos * 100 / C.total, 0), width="180px"),
                rx.spacer(),
                rx.button(rx.icon("refresh-cw", size=14), "Verificar agora", on_click=C.verificar_agora),
                spacing="3", align="center", width="100%", flex_wrap="wrap",
            ),
            rx.vstack(rx.foreach(C.itens, _requisito), spacing="3", width="100%"),
            icone="plug-zap",
        ),
        _formas(),
        secao(
            "E-mail (SendGrid)",
            rx.cond(
                C.sendgrid_ok,
                rx.vstack(rx.text("Configurado. Remetente: ", rx.text.strong(C.remetente), size="2"),
                          rx.button(rx.icon("send", size=14), "Enviar e-mail de teste para mim", variant="soft",
                                    on_click=C.testar_email),
                          spacing="2", align="start"),
                rx.text("Não configurado — veja o item “Chave do SendGrid” acima.", size="2"),
            ),
            rx.text("Regra: o sistema nunca envia e-mail sozinho; todo envio parte de um clique.", size="1",
                    color=rx.color("gray", 10)),
            icone="mail",
        ),
        secao(
            "Servidor",
            rx.text("Conta de serviço usada pelo servidor para acessar o Xano: ", rx.code(C.conta_servico), size="2"),
            rx.text("Para trocar a conta ou a senha dela, rode scripts\\configurar_xano.ps1 no computador do sistema.",
                    size="1", color=rx.color("gray", 10)),
            icone="server",
        ),
        title="Configuração do sistema",
        subtitle="Novidades, recursos a ativar no Xano, formas de pagamento e e-mail. Só administradores.",
    )
