"""
Wikipedia lookup for per-track trivia/context.

Wikipedia exposes two fully-public, no-key APIs we use here:
  1. The MediaWiki action API for full-text search:
       https://en.wikipedia.org/w/api.php?action=query&list=search&...
  2. The REST v1 page summary endpoint, which returns a short extract,
     description and a canonical page URL:
       https://en.wikipedia.org/api/rest_v1/page/summary/{title}

Strategy for resolving a Spotify track to a Wikipedia article:
  - Build a fielded query that prefers song articles, e.g.
        "Title" "Artist" song
  - Take the top hit and fetch its REST summary.
  - Skip disambiguation pages ("type": "disambiguation").

Wikipedia asks API consumers to identify themselves with a descriptive
User-Agent (https://meta.wikimedia.org/wiki/User-Agent_policy). We comply.
"""

import asyncio
from typing import Any

import httpx

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1"
USER_AGENT = (
    "Pigify/0.1 (https://github.com/pigify; contact: dev@pigify.local) python-httpx"
)

_semaphore = asyncio.Semaphore(4)


class WikipediaError(Exception):
    pass


async def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with (
        _semaphore,
        httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client,
    ):
        resp = await client.get(url, params=params, headers=headers)
    if resp.status_code == 404:
        return {}
    if resp.status_code >= 400:
        raise WikipediaError(f"Wikipedia {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as e:
        raise WikipediaError(f"Wikipedia returned non-JSON: {e}") from e


async def search_wiki(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Full-text search Wikipedia; returns the raw `search` hit list."""
    data = await _get_json(
        WIKI_API,
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet",
            "format": "json",
            "formatversion": "2",
        },
    )
    return (data.get("query") or {}).get("search") or []


async def search_song(
    artist: str, title: str, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Full-text search Wikipedia for a song article."""
    return await search_wiki(f'"{title}" "{artist}" song', limit=limit)


async def get_summary(title: str) -> dict[str, Any]:
    """Fetch the REST summary for a page title."""
    # The REST endpoint expects the title path-segment URL-encoded; httpx does
    # this for us when we pass it through the URL builder.
    safe_title = title.replace(" ", "_")
    return await _get_json(f"{WIKI_REST}/page/summary/{safe_title}")


def _is_useful_summary(summary: dict[str, Any]) -> bool:
    if not summary:
        return False
    if summary.get("type") == "disambiguation":
        return False
    extract = (summary.get("extract") or "").strip()
    return bool(extract)


async def resolve_song_article(
    *, artist: str, title: str, album: str | None = None
) -> dict[str, Any] | None:
    """
    Try to find a Wikipedia article for the given song. Returns a dict with
    `title`, `extract`, `description`, `url`, `thumbnail` — or None if nothing
    usable was found. Falls back through progressively looser queries (song →
    album + song → artist/band) so a non-obvious title still resolves.
    """
    if not (artist and title):
        return None
    queries = [f'"{title}" "{artist}" song']
    if album:
        queries.append(f'"{title}" "{album}"')
    queries.append(f'"{title}" "{artist}"')
    try:
        for query in queries:
            for hit in await search_wiki(query, limit=5):
                page_title = hit.get("title")
                if not page_title:
                    continue
                try:
                    summary = await get_summary(page_title)
                except WikipediaError:
                    continue
                if not _is_useful_summary(summary):
                    continue
                return {
                    "title": summary.get("title") or page_title,
                    "description": summary.get("description"),
                    "extract": (summary.get("extract") or "").strip(),
                    "url": (
                        (summary.get("content_urls") or {})
                        .get("desktop", {})
                        .get("page")
                    )
                    or f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                    "thumbnail": (summary.get("thumbnail") or {}).get("source"),
                }
    except (TimeoutError, WikipediaError, httpx.HTTPError):
        return None
    return None
