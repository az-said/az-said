"""
stats.py
Pull live GitHub statistics via GraphQL + REST, cache the expensive
lines-of-code scan, and degrade gracefully to placeholder values when
no token is present (so local prototyping always renders).

Env:
  GH_USERNAME  - the GitHub login to report on
  GH_TOKEN     - a PAT with 'repo' + 'read:user' scope (Actions can inject one)
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from urllib import request, error

API = "https://api.github.com/graphql"
REST = "https://api.github.com"
CACHE = Path(__file__).parent / "cache" / "loc_cache.json"


def _post(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = request.Request(API, data=body, method="POST")
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _rest(path: str, token: str):
    req = request.Request(REST + path)
    req.add_header("Authorization", f"bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()), r.status


PROFILE_Q = """
query($login:String!) {
  user(login:$login) {
    name login createdAt
    followers { totalCount }
    following { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false,
                 orderBy:{field:STARGAZERS, direction:DESC}) {
      totalCount
      nodes { name stargazerCount }
    }
    repositoriesContributedTo(first:1,
        contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY, ISSUE]) {
      totalCount
    }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""


def _placeholder() -> dict:
    return {
        "name": "Said Azaizah",
        "login": "saidazaizah",
        "created_at": "2019-01-01T00:00:00Z",
        "repos": 42,
        "contributed": 60,
        "stars": 128,
        "followers": 210,
        "following": 24,
        "commits": 2116,
        "loc_total": 446276,
        "loc_add": 523178,
        "loc_del": 76902,
        "is_placeholder": True,
    }


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(data: dict) -> None:
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=2))


def _lines_of_code(login: str, repos: list[str], token: str) -> tuple[int, int, int]:
    """
    Sum additions/deletions attributed to `login` across owned repos,
    using REST contributor stats. Cached per repo to avoid recomputation.
    """
    cache = _load_cache()
    add = dele = 0
    for full in repos:
        entry = cache.get(full)
        if entry is None:
            try:
                data, status = _rest(f"/repos/{full}/stats/contributors", token)
                if status == 202:  # GitHub is computing; try once more shortly
                    time.sleep(3)
                    data, status = _rest(f"/repos/{full}/stats/contributors", token)
                a = d = 0
                for c in (data or []):
                    if (c.get("author") or {}).get("login") == login:
                        for wk in c.get("weeks", []):
                            a += wk.get("a", 0)
                            d += wk.get("d", 0)
                entry = {"a": a, "d": d}
                cache[full] = entry
            except error.HTTPError:
                entry = {"a": 0, "d": 0}
        add += entry["a"]
        dele += entry["d"]
    _save_cache(cache)
    return add + dele, add, dele


def collect() -> dict:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_USERNAME")
    if not token or not login:
        return _placeholder()

    try:
        res = _post(PROFILE_Q, {"login": login}, token)
        u = res["data"]["user"]
        repos = u["repositories"]["nodes"]
        stars = sum(r["stargazerCount"] for r in repos)
        cc = u["contributionsCollection"]
        commits = cc["totalCommitContributions"] + cc.get("restrictedContributionsCount", 0)
        full_names = [f'{login}/{r["name"]}' for r in repos]
        loc_total, loc_add, loc_del = _lines_of_code(login, full_names, token)
        return {
            "name": u.get("name") or login,
            "login": login,
            "created_at": u["createdAt"],
            "repos": u["repositories"]["totalCount"],
            "contributed": u["repositoriesContributedTo"]["totalCount"],
            "stars": stars,
            "followers": u["followers"]["totalCount"],
            "following": u["following"]["totalCount"],
            "commits": commits,
            "loc_total": loc_total,
            "loc_add": loc_add,
            "loc_del": loc_del,
            "is_placeholder": False,
        }
    except Exception as e:  # never break the render
        p = _placeholder()
        p["error"] = str(e)
        return p


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
