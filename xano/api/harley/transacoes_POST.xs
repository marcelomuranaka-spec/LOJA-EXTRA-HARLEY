// Add transacoes record
query transacoes verb=POST {
  api_group = "HARLEY"
  auth = "user"

  input {
    dblink {
      table = "transacoes"
    }
  }

  stack {
    db.add transacoes {
      enforce_hidden_fields = false
      data = {
        tipo_transacao : $input.tipo_transacao
        id_funcionario : $input.id_funcionario
        id_cliente     : $input.id_cliente
        id_moto_cliente: $input.id_moto_cliente
        data_transacao : $input.data_transacao
        valor_total    : $input.valor_total
      }
    } as $model
  }

  response = $model
  guid = "wWFICjS1LhUd4uEW5uTnJqtZe6o"
}