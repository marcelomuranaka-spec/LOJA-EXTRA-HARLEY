// Itens de cada venda (transacoes): o que foi vendido, em que quantidade e
// por qual preço. Permite venda com vários itens e devolver o estoque ao
// cancelar. produto_id = 0 indica item avulso (sem estoque, ex.: mão de obra).
// descricao guarda o nome do produto no momento da venda, para o comprovante
// continuar correto se o produto for renomeado ou excluído.
//
// ESPELHO DOCUMENTAL criado à mão a partir da tabela real (sem o guid que o
// Xano atribui). Para sincronizar com a extensão do Xano, BAIXE a versão do
// Xano; não envie este arquivo, ou uma tabela duplicada pode ser criada.
table itens_transacao {
  auth = false

  schema {
    int id
    timestamp created_at?=now
  
    // Relacionamento com Transacoes (a venda)
    int transacao_id
  
    // Relacionamento com Produtos (0 = item avulso, sem estoque)
    int produto_id
  
    text descricao
    int quantidade
    decimal valor_unitario
  }

  index = [{type: "primary", field: [{name: "id"}]}]
}
