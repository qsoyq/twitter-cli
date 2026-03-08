from __future__ import annotations

from click.testing import CliRunner

from twitter_cli.cli import cli
from twitter_cli.models import UserProfile
from twitter_cli.serialization import tweets_to_json


def test_cli_user_command_works_with_client_factory(monkeypatch) -> None:
    class FakeClient:
        def fetch_user(self, screen_name: str) -> UserProfile:
            return UserProfile(id="1", name="Alice", screen_name=screen_name)

    monkeypatch.setattr("twitter_cli.cli._get_client", lambda silent=False: FakeClient())
    runner = CliRunner()
    result = runner.invoke(cli, ["user", "alice"])
    assert result.exit_code == 0


def test_cli_feed_json_input_path(tmp_path, tweet_factory) -> None:
    json_path = tmp_path / "tweets.json"
    json_path.write_text(tweets_to_json([tweet_factory("1")]), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["feed", "--input", str(json_path), "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.output


def test_cli_likes_command(monkeypatch, tweet_factory) -> None:
    fake_tweets = [tweet_factory("10"), tweet_factory("11")]

    class FakeClient:
        def fetch_current_user_id(self) -> str:
            return "999"

        def fetch_likes(self, user_id: str, count: int = 20):
            return fake_tweets

    monkeypatch.setattr("twitter_cli.cli._get_client", lambda silent=False: FakeClient())
    runner = CliRunner()
    result = runner.invoke(cli, ["likes", "--max", "5", "--json"])
    assert result.exit_code == 0
    assert '"id": "10"' in result.output
    assert '"id": "11"' in result.output


def test_cli_cookie_command_outputs_current_cookie(monkeypatch) -> None:
    monkeypatch.setattr(
        "twitter_cli.cli.get_cookies",
        lambda: {"auth_token": "auth-123", "ct0": "ct0-456"},
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["cookie"])
    assert result.exit_code == 0
    assert result.output.strip() == "auth_token=auth-123; ct0=ct0-456"


def test_cli_cookie_verify_command_accepts_cookies_option(monkeypatch) -> None:
    captured = {}

    def fake_verify(auth_token: str, ct0: str) -> UserProfile:
        captured["auth_token"] = auth_token
        captured["ct0"] = ct0
        return UserProfile(id="1", name="Alice", screen_name="alice")

    monkeypatch.setattr("twitter_cli.cli.verify_cookies_with_profile", fake_verify)
    runner = CliRunner()
    result = runner.invoke(cli, ["cookie-verify", "--cookies", "auth_token=a1; ct0=b2"])
    assert result.exit_code == 0
    assert captured == {"auth_token": "a1", "ct0": "b2"}
    assert "Cookie is valid" in result.output
    assert "alice" in result.output


def test_cli_cookie_verify_command_reads_cookies_env_var(monkeypatch) -> None:
    captured = {}

    def fake_verify(auth_token: str, ct0: str) -> UserProfile:
        captured["auth_token"] = auth_token
        captured["ct0"] = ct0
        return UserProfile(id="2", name="Bob", screen_name="bob")

    monkeypatch.setattr("twitter_cli.cli.verify_cookies_with_profile", fake_verify)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["cookie-verify"],
        env={"TWITTER_CLI_COOKIES": "auth_token=env-auth; ct0=env-ct0"},
    )
    assert result.exit_code == 0
    assert captured == {"auth_token": "env-auth", "ct0": "env-ct0"}
    assert "Cookie is valid" in result.output
