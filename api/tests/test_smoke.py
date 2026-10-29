def test_admin_login_page_loads(client):
    assert client.get("/admin/login/").status_code == 200
