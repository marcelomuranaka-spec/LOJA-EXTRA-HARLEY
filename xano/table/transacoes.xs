// Registro de Transações (Vendas, Balcão, OS, etc.)
table transacoes {
  auth = false

  schema {
    int id
  
    // Tipo: MOTO, PECAS, BALCAO, COMPRA, ORDEM_SERVICO
    text tipo_transacao
  
    // Relacionamento com Funcionários
    int id_funcionario
  
    // Relacionamento com Clientes (Opcional)
    int id_cliente?
  
    // Relacionamento com Motos de Clientes (Opcional)
    int id_moto_cliente?
  
    timestamp data_transacao?=now
    decimal valor_total?
  
    // Current status of the transaction (e.g., 'completed', 'pending', 'canceled').
    text status? filters=trim
  
    // Date when the transaction was canceled.
    date data_cancelamento?
  
    // Reason for the transaction cancellation.
    text motivo_cancelamento? filters=trim
  }

  index = [{type: "primary", field: [{name: "id"}]}]
  guid = "BP1X9KcmVlziF6gcwo6b7sBVCcY"
}