// Deletes a user account. Used by the admin "Usuários do sistema" page.
query "user/delete" verb=POST {
  api_group = "Admin"

  input {
    int id?
  }

  stack {
    db.del user {
      field_name = "id"
      field_value = $input.id
    }
  }

  response = {message: {"success": "true"}}
  tags = ["harley-store"]
  guid = "hs_admin_user_delete_v1"
}
