from __future__ import annotations

from twitter_cli.auth import parse_cookie_string, resolve_input_cookies


def test_parse_cookie_string_extracts_auth_token_and_ct0() -> None:
    cookies = parse_cookie_string("foo=bar; auth_token=a1; ct0=b2; lang=en")
    assert cookies == {"auth_token": "a1", "ct0": "b2"}


def test_resolve_input_cookies_reads_twitter_cookie_env(monkeypatch) -> None:
    monkeypatch.setenv("TWITTER_COOKIE", "auth_token=env-a; ct0=env-b; lang=en")
    cookies = resolve_input_cookies()
    assert cookies == {"auth_token": "env-a", "ct0": "env-b"}
