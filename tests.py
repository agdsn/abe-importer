from abe_importer.importer.translations import sanitize_username


def test_sanitize_username():
    assert sanitize_username("55_user") == "hss-user-55-user"
    assert sanitize_username("username-") == "username"
    assert sanitize_username("test-user.bar.-") == "test-user.bar"
