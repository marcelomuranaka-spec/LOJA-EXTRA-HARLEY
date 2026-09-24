// Lista o histórico de movimentações de estoque
query movimentacoes_estoque verb=GET {
  api_group = "HARLEY"
  auth = "user"

  input {
  }

  stack {
    db.query movimentacoes_estoque {
      return = {type: "list"}
    } as $model
  }

  response = $model
}
