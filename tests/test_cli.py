from __future__ import annotations

from click.testing import CliRunner
import pytest

from twitter_cli.cli import cli
from twitter_cli.models import UserProfile
from twitter_cli.serialization import tweets_to_json


def test_cli_user_command_works_with_client_factory(monkeypatch) -> None:
    class FakeClient:
        def fetch_user(self, screen_name: str) -> UserProfile:
            return UserProfile(id="1", name="Alice", screen_name=screen_name)

    monkeypatch.setattr("twitter_cli.cli._get_client", lambda config=None: FakeClient())
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


@pytest.mark.parametrize(
    "args",
    [
        ["favorites"],
        ["bookmarks"],
        ["search", "x"],
        ["user-posts", "alice"],
        ["likes", "alice"],
        ["list", "123"],
    ],
)
def test_cli_commands_wrap_client_creation_errors(monkeypatch, args) -> None:
    monkeypatch.setattr(
        "twitter_cli.cli._get_client",
        lambda config=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    runner = CliRunner()

    result = runner.invoke(cli, args)

    assert result.exit_code == 1
    assert "boom" in result.output
    assert type(result.exception).__name__ == "SystemExit"


def test_cli_tweet_accepts_shared_url_with_query(monkeypatch) -> None:
    class FakeClient:
        def fetch_tweet_detail(self, tweet_id: str, max_count: int):
            assert tweet_id == "12345"
            assert max_count == 50
            return []

    monkeypatch.setattr("twitter_cli.cli._get_client", lambda config=None: FakeClient())
    monkeypatch.setattr(
        "twitter_cli.cli.load_config",
        lambda: {"fetch": {"count": 50}, "filter": {}, "rateLimit": {}},
    )
    runner = CliRunner()

    result = runner.invoke(cli, ["tweet", "https://x.com/user/status/12345?s=20"])

    assert result.exit_code == 0


def test_cli_bookmark_alias_works(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def bookmark_tweet(self, tweet_id: str) -> bool:
            calls.append(tweet_id)
            return True

    monkeypatch.setattr("twitter_cli.cli._get_client", lambda config=None: FakeClient())
    runner = CliRunner()

    result = runner.invoke(cli, ["bookmark", "123"])

    assert result.exit_code == 0
    assert calls == ["123"]
