// Itens de cada Ordem de Serviço (Peças utilizadas)
table itens_ordem_servico {
  auth = false

  schema {
    int id
  
    // Relacionamento com Ordem de Serviço
    int id_os
  
    // Relacionamento com Produto/Peça
    int id_produto
  
    int quantidade
    decimal valor_total_item
  }

  index = [{type: "primary", field: [{name: "id"}]}]
  guid = "_Eb2No0irv6FucCS7QlRREna0ek"
}