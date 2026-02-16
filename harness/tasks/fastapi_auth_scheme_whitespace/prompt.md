# get_authorization_scheme_param keeps whitespace inside credentials

`fastapi.security.utils.get_authorization_scheme_param("Bearer   xxx")` returns
`("Bearer", " xxx")` — the leading whitespace from the credentials part isn't
stripped. Per RFC 9110, an HTTP token must not contain whitespace, so the
correct return is `("Bearer", "xxx")`.

The downstream effect: any auth scheme that does `if param == expected_token`
fails because of the leading space. Hard to debug if you don't suspect
whitespace.

Fix `fastapi/security/utils.py`. One-line change: strip the credentials part
before returning. The tests check both HTTP base auth and OAuth2 password
flow paths.
