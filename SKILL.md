---
name: twitter-cli
description: CLI skill for Twitter/X to read timelines, bookmarks, user posts, and profiles from the terminal without API keys
author: jackwener
version: "1.0.0"
tags:
  - twitter
  - x
  - social-media
  - terminal
  - cli
---

# twitter-cli Skill

Use this skill when the user wants to read or interact with Twitter/X content from terminal without API keys.

## Prerequisites

```bash
# Install (requires Python 3.8+)
uv tool install twitter-cli
# Or: pipx install twitter-cli
```

## Authentication

- Auto-extracts browser cookies from Arc/Chrome/Edge/Firefox/Brave.
- Or set environment variables: `TWITTER_AUTH_TOKEN` + `TWITTER_CT0`.

## Command Reference

### Feed

```bash
twitter feed                           # Home timeline (For You)
twitter feed -t following              # Following timeline
twitter feed --max 50                  # Limit count
twitter feed --filter                  # Enable ranking filter
twitter feed --json > tweets.json      # Export as JSON
twitter feed --input tweets.json       # Read from local JSON file
```

### Bookmarks

```bash
twitter bookmarks                      # List bookmarked tweets
twitter bookmarks --max 30 --json
twitter bookmarks --filter             # Apply ranking filter
```

### Search

```bash
twitter search "keyword"
twitter search "AI agent" -t Latest --max 50
twitter search "机器学习" --json
twitter search "topic" -o results.json         # Save to file
twitter search "trending" --filter              # Apply ranking filter
```

### Tweet Detail

```bash
twitter tweet 1234567890                          # View tweet + replies
twitter tweet https://x.com/user/status/12345     # Accepts URL too
```

### List Timeline

```bash
twitter list 1539453138322673664       # Fetch tweets from a Twitter List
```

### User

```bash
twitter user elonmusk                  # User profile
twitter user-posts elonmusk --max 20   # User's tweets
twitter user-posts elonmusk -o tweets.json  # Save to file
twitter likes elonmusk --max 30        # User's likes
twitter likes elonmusk -o likes.json   # Save to file
twitter followers elonmusk --max 50    # User's followers
twitter following elonmusk --max 50    # User's following
```

### Write Operations

```bash
twitter post "Hello from twitter-cli!"              # Post tweet
twitter post "reply text" --reply-to 1234567890      # Reply
twitter delete 1234567890                            # Delete tweet
twitter like 1234567890                              # Like
twitter unlike 1234567890                            # Unlike
twitter retweet 1234567890                           # Retweet
twitter unretweet 1234567890                         # Unretweet
twitter bookmark 1234567890                          # Bookmark
twitter unbookmark 1234567890                        # Unbookmark
```

## JSON / Scripting

```bash
twitter feed --json > tweets.json
twitter feed --input tweets.json
twitter user-posts elonmusk --json | jq '.[0].text'
twitter search "keyword" --json | jq 'length'
twitter search "topic" -o results.json
twitter likes elonmusk -o likes.json
```

## Ranking Filter

Filtering is opt-in (disabled by default). Enable with `--filter`.

```bash
twitter feed --filter
twitter bookmarks --filter
```

The scoring formula:

```text
score = likes_w * likes
      + retweets_w * retweets
      + replies_w * replies
      + bookmarks_w * bookmarks
      + views_log_w * log10(max(views, 1))
```

Configure weights and mode in `config.yaml`.

## Common Patterns for AI Agents

```bash
# Get latest tweets from a user
twitter user-posts elonmusk --max 5 --json

# Search and export for analysis
twitter search "topic" --json > results.json

# Check user profile
twitter user elonmusk --json

# Daily reading workflow
twitter feed -t following --filter
twitter bookmarks --filter
```

## Error Handling

- `No Twitter cookies found` — login to `x.com` in Arc/Chrome/Edge/Firefox/Brave, or set env vars.
- `Cookie expired or invalid (HTTP 401/403)` — re-login to `x.com` and retry.
- `Twitter API error 404` — queryId rotation, retry the command (client has live fallback).

## Safety Notes

- Write operations have built-in random delays (1.5–4s) to avoid rate limits.
- TLS fingerprint and User-Agent are automatically matched to the Chrome version used.
- Do not ask users to share raw cookie values in chat logs.
- Prefer local browser cookie extraction over manual secret copy/paste.
- If auth fails with 401/403, ask the user to re-login to `x.com`.
