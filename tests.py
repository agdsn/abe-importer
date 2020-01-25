from abe_importer.importer.translations import sanitize_username, maybe_fix_mail


def test_sanitize_username():
    assert sanitize_username("55_user") == "hss-user-55-user"
    assert sanitize_username("username-") == "username"
    assert sanitize_username("test-user.bar.-") == "test-user.bar"


def test_mail_fix():
    assert maybe_fix_mail("user.@foo.bar") == "user_@foo.bar"
    assert maybe_fix_mail("user._@foo.bar") == "user._@foo.bar"
    assert maybe_fix_mail("nor_mal.user@foo.bar") == "nor_mal.user@foo.bar"
