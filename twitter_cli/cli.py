"""CLI entry point for twitter-cli.

Usage:
    twitter feed                      # fetch home timeline (For You)
    twitter feed -t following         # fetch following feed
    twitter feed --max 50             # custom fetch count
    twitter feed --filter             # enable score-based filtering
    twitter feed --json               # JSON output
    twitter favorite                  # fetch bookmarks
    twitter likes                     # fetch your liked tweets
    twitter feed --input tweets.json  # load existing data
    twitter feed --output out.json    # save filtered tweets
    twitter user elonmusk             # view user profile
    twitter user-posts elonmusk       # list user tweets
    twitter cookie                    # print current cookie
    twitter cookie-verify             # verify a cookie from CLI/env
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import click
from rich.console import Console

from . import __version__
from .auth import (
    format_cookie_string,
    get_cookies,
    resolve_input_cookies,
    verify_cookies_with_profile,
)
from .client import TwitterClient
from .config import load_config
from .filter import filter_tweets
from .formatter import print_filter_stats, print_tweet_table, print_user_profile
from .serialization import tweets_from_json, tweets_to_json


console = Console()
FEED_TYPES = ["for-you", "following"]


def _setup_logging(verbose):
    # type: (bool) -> None
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@contextmanager
def _suppress_logging(silent):
    # type: (bool) -> None
    """Temporarily suppress logger output for clean JSON mode."""
    if not silent:
        yield
        return

    previous_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous_disable)


def _load_tweets_from_json(path):
    # type: (str) -> List[Tweet]
    """Load tweets from a JSON file (previously exported)."""
    file_path = Path(path)
    if not file_path.exists():
        raise RuntimeError("Input file not found: %s" % path)

    try:
        raw = file_path.read_text(encoding="utf-8")
        return tweets_from_json(raw)
    except (ValueError, OSError) as exc:
        raise RuntimeError("Invalid tweet JSON file %s: %s" % (path, exc))


def _get_client(silent=False):
    # type: (bool) -> TwitterClient
    """Create an authenticated API client."""
    if not silent:
        console.print("\n🔐 Getting Twitter cookies...")
    cookies = get_cookies()
    return TwitterClient(cookies["auth_token"], cookies["ct0"])


def _resolve_fetch_count(max_count, configured):
    # type: (Optional[int], int) -> int
    """Resolve fetch count with bounds checks."""
    if max_count is not None:
        if max_count <= 0:
            raise RuntimeError("--max must be greater than 0")
        return max_count
    return max(configured, 1)


def _apply_filter(tweets, do_filter, config, silent=False):
    # type: (List[Tweet], bool, dict, bool) -> List[Tweet]
    """Optionally apply tweet filtering."""
    if not do_filter:
        return tweets
    filter_config = config.get("filter", {})
    original_count = len(tweets)
    filtered = filter_tweets(tweets, filter_config)
    if not silent:
        print_filter_stats(original_count, filtered, console)
        console.print()
    return filtered


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.version_option(version=__version__)
def cli(verbose):
    # type: (bool) -> None
    """twitter — Twitter/X CLI tool, forked and maintained by qsoyq. 🐦"""
    _setup_logging(verbose)


def _fetch_and_display(fetch_fn, label, emoji, max_count, as_json, output_file, do_filter):
    # type: (Callable[..., Any], str, str, Optional[int], bool, Optional[str], bool) -> None
    """Common fetch-filter-display logic for timeline-like commands."""
    with _suppress_logging(as_json):
        config = load_config()
        try:
            fetch_count = _resolve_fetch_count(max_count, config.get("fetch", {}).get("count", 50))
            if not as_json:
                console.print("%s Fetching %s (%d tweets)...\n" % (emoji, label, fetch_count))
            start = time.time()
            tweets = fetch_fn(fetch_count)
            elapsed = time.time() - start
            if not as_json:
                console.print("✅ Fetched %d %s in %.1fs\n" % (len(tweets), label, elapsed))
        except RuntimeError as exc:
            console.print("[red]❌ %s[/red]" % exc)
            sys.exit(1)

        filtered = _apply_filter(tweets, do_filter, config, silent=as_json)

    if output_file:
        Path(output_file).write_text(tweets_to_json(filtered), encoding="utf-8")
        if not as_json:
            console.print("💾 Saved to %s\n" % output_file)

    if as_json:
        click.echo(tweets_to_json(filtered))
        return

    print_tweet_table(filtered, console, title="%s %s — %d tweets" % (emoji, label, len(filtered)))
    console.print()


@cli.command()
@click.option(
    "--type",
    "-t",
    "feed_type",
    type=click.Choice(FEED_TYPES),
    default="for-you",
    help="Feed type: for-you (algorithmic) or following (chronological).",
)
@click.option(
    "--max", "-n", "max_count", type=int, default=None, help="Max number of tweets to fetch."
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option(
    "--input", "-i", "input_file", type=str, default=None, help="Load tweets from JSON file."
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=str,
    default=None,
    help="Save filtered tweets to JSON file.",
)
@click.option("--filter", "do_filter", is_flag=True, help="Enable score-based filtering.")
def feed(feed_type, max_count, as_json, input_file, output_file, do_filter):
    # type: (str, Optional[int], bool, Optional[str], Optional[str], bool) -> None
    """Fetch home timeline with optional filtering."""
    with _suppress_logging(as_json):
        config = load_config()
        try:
            if input_file:
                if not as_json:
                    console.print("📂 Loading tweets from %s..." % input_file)
                tweets = _load_tweets_from_json(input_file)
                if not as_json:
                    console.print("   Loaded %d tweets" % len(tweets))
            else:
                fetch_count = _resolve_fetch_count(
                    max_count, config.get("fetch", {}).get("count", 50)
                )
                client = _get_client(silent=as_json)
                label = "following feed" if feed_type == "following" else "home timeline"
                if not as_json:
                    console.print("📡 Fetching %s (%d tweets)...\n" % (label, fetch_count))
                start = time.time()
                if feed_type == "following":
                    tweets = client.fetch_following_feed(fetch_count)
                else:
                    tweets = client.fetch_home_timeline(fetch_count)
                elapsed = time.time() - start
                if not as_json:
                    console.print("✅ Fetched %d tweets in %.1fs\n" % (len(tweets), elapsed))
        except RuntimeError as exc:
            console.print("[red]❌ %s[/red]" % exc)
            sys.exit(1)

        filtered = _apply_filter(tweets, do_filter, config, silent=as_json)

    if output_file:
        Path(output_file).write_text(tweets_to_json(filtered), encoding="utf-8")
        if not as_json:
            console.print("💾 Saved filtered tweets to %s\n" % output_file)

    if as_json:
        click.echo(tweets_to_json(filtered))
        return

    title = "👥 Following" if feed_type == "following" else "📱 Twitter"
    title += " — %d tweets" % len(filtered)
    print_tweet_table(filtered, console, title=title)
    console.print()


@cli.command()
@click.option(
    "--max", "-n", "max_count", type=int, default=None, help="Max number of tweets to fetch."
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option(
    "--output", "-o", "output_file", type=str, default=None, help="Save tweets to JSON file."
)
@click.option("--filter", "do_filter", is_flag=True, help="Enable score-based filtering.")
def favorite(max_count, as_json, output_file, do_filter):
    # type: (Optional[int], bool, Optional[str], bool) -> None
    """Fetch bookmarked (favorite) tweets."""
    client = _get_client(silent=as_json)
    _fetch_and_display(
        lambda count: client.fetch_bookmarks(count),
        "favorites",
        "🔖",
        max_count,
        as_json,
        output_file,
        do_filter,
    )


@cli.command()
@click.option(
    "--max", "-n", "max_count", type=int, default=None, help="Max number of tweets to fetch."
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.option(
    "--output", "-o", "output_file", type=str, default=None, help="Save tweets to JSON file."
)
@click.option("--filter", "do_filter", is_flag=True, help="Enable score-based filtering.")
def likes(max_count, as_json, output_file, do_filter):
    # type: (Optional[int], bool, Optional[str], bool) -> None
    """Fetch your liked tweets (only available for the authenticated user)."""
    client = _get_client(silent=as_json)
    if not as_json:
        console.print("👤 Resolving your user ID...")
    user_id = client.fetch_current_user_id()
    _fetch_and_display(
        lambda count: client.fetch_likes(user_id, count),
        "likes",
        "❤️",
        max_count,
        as_json,
        output_file,
        do_filter,
    )


@cli.command()
@click.argument("screen_name")
def user(screen_name):
    # type: (str,) -> None
    """View a user's profile. SCREEN_NAME is the @handle (without @)."""
    screen_name = screen_name.lstrip("@")
    try:
        client = _get_client()
        console.print("👤 Fetching user @%s..." % screen_name)
        profile = client.fetch_user(screen_name)
    except RuntimeError as exc:
        console.print("[red]❌ %s[/red]" % exc)
        sys.exit(1)

    console.print()
    print_user_profile(profile, console)


@cli.command("user-posts")
@click.argument("screen_name")
@click.option(
    "--max", "-n", "max_count", type=int, default=20, help="Max number of tweets to fetch."
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
def user_posts(screen_name, max_count, as_json):
    # type: (str, int, bool) -> None
    """List a user's tweets. SCREEN_NAME is the @handle (without @)."""
    screen_name = screen_name.lstrip("@")
    with _suppress_logging(as_json):
        try:
            fetch_count = _resolve_fetch_count(max_count, 20)
            client = _get_client(silent=as_json)
            if not as_json:
                console.print("👤 Fetching @%s's profile..." % screen_name)
            profile = client.fetch_user(screen_name)
            if not as_json:
                console.print("📝 Fetching tweets (%d)...\n" % fetch_count)
            start = time.time()
            tweets = client.fetch_user_tweets(profile.id, fetch_count)
            elapsed = time.time() - start
            if not as_json:
                console.print("✅ Fetched %d tweets in %.1fs\n" % (len(tweets), elapsed))
        except RuntimeError as exc:
            console.print("[red]❌ %s[/red]" % exc)
            sys.exit(1)

    if as_json:
        click.echo(tweets_to_json(tweets))
        return

    print_tweet_table(tweets, console, title="📝 @%s — %d tweets" % (screen_name, len(tweets)))
    console.print()


@cli.command()
def cookie():
    # type: () -> None
    """Print the currently resolved cookie as auth_token=...; ct0=..."""
    try:
        cookies = get_cookies()
    except RuntimeError as exc:
        console.print("[red]❌ %s[/red]" % exc)
        sys.exit(1)

    click.echo(format_cookie_string(cookies["auth_token"], cookies["ct0"]))


@cli.command("cookie-verify")
@click.option(
    "--cookies",
    "cookies_value",
    type=str,
    default=None,
    envvar="TWITTER_CLI_COOKIES",
    help="Raw cookie string like 'auth_token=...; ct0=...'. Also reads TWITTER_CLI_COOKIES.",
)
def cookie_verify(cookies_value):
    # type: (Optional[str],) -> None
    """Verify a cookie from CLI options or environment variables."""
    try:
        cookies = resolve_input_cookies(cookies_value)
        console.print("🔍 Verifying cookie via current user profile...\n")
        profile = verify_cookies_with_profile(cookies["auth_token"], cookies["ct0"])
    except RuntimeError as exc:
        console.print("[red]❌ %s[/red]" % exc)
        sys.exit(1)

    console.print("[green]✅ Cookie is valid[/green]")
    console.print()
    if profile:
        print_user_profile(profile, console)
        return

    console.print(
        "ℹ️ Cookie passed lightweight verification, but current user profile was not available."
    )


if __name__ == "__main__":
    cli()
