// Updates a user's email address. Used by the admin "Usuários do sistema" page.
query "user/update-email" verb=POST {
  api_group = "Admin"

  input {
    int id?
    email email? filters=trim|lower
  }

  stack {
    db.edit user {
      field_name = "id"
      field_value = $input.id
      data = {email: $input.email}
    } as $usuario
  }

  response = {
    id: $usuario.id
    created_at: $usuario.created_at
    name: $usuario.name
    email: $usuario.email
    role: $usuario.role
  }
  tags = ["harley-store"]
  guid = "hs_admin_user_update_email_v1"
}
