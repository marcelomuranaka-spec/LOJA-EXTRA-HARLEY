// Registro de Entrada de Mercadorias (Fornecimento)
table entrada_mercadoria {
  auth = false

  schema {
    int id
  
    // Relacionamento com a tabela de Fornecedores
    int id_fornecedor
  
    timestamp data_entrada?=now
    decimal valor_total?
  }

  index = [{type: "primary", field: [{name: "id"}]}]
  guid = "TROYX6aw69oEPepfYciv6KlYY2g"
}