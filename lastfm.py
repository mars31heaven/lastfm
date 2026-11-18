#!/usr/bin/env python3
"""Minimal Last.fm recent tracks and stats viewer."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://ws.audioscrobbler.com/2.0/"
CONFIG = os.path.expanduser("~/.config/lastfm/config")
KEYCHAIN_COMMANDS = [
    ["security", "find-generic-password", "-s", "lastfm-api-key", "-w"],
    ["secret-tool", "lookup", "service", "lastfm-api-key"],
]
FIRST_YEAR = 2002  # Last.fm launch year
PERIOD_LABELS = {
    "7day": "last 7 days",
    "1month": "last 30 days",
    "3month": "last 3 months",
    "12month": "last 12 months",
    "overall": "all time",
}

# kind: (period method, period result key, chart method, chart result key, item key)
SECTIONS = {
    "tracks": ("user.gettoptracks", "toptracks",
               "user.getweeklytrackchart", "weeklytrackchart", "track"),
    "albums": ("user.gettopalbums", "topalbums",
               "user.getweeklyalbumchart", "weeklyalbumchart", "album"),
    "artists": ("user.gettopartists", "topartists",
                "user.getweeklyartistchart", "weeklyartistchart", "artist"),
}

HELP_EPILOG = """\
setup:
  1. Get an API key at https://www.last.fm/api/account/create
  2. Store it outside your dotfiles, using one of:

     macOS keychain:
       security add-generic-password -a "$USER" -s lastfm-api-key -w

     Linux keyring:
       secret-tool store --label=lastfm service lastfm-api-key

     Config file (then run: chmod 600 ~/.config/lastfm/config):
       user=your_username
       key=your_api_key

  The key can also be passed through LASTFM_API_KEY.
  The username can come from -u, LASTFM_USER or the config file.

other users:
  -u USER   show the data of any Last.fm user instead of your own.
            It works with every period and section flag. Your API key is
            still used, so you only need one key. Profiles whose owners hide
            their listening data may return an error or an empty list.

periods:
  -w   last 7 days
  -m   last 30 days
  -q   last 3 months
  -y   last 12 months (rolling, counted back from today)
  -a   all time
  -c   calendar year, 1 January to 31 December (current year by default,
       or pass a year, e.g. -c 2024). Uses local time. The current year
       covers 1 January up to now.

  Only one period can be used at a time.

  Each period view shows up to three boxes, titled "Top tracks",
  "Top albums" and "Top artists", followed by the period. Every row has
  a rank number on the left and the play count on the right.
  Plain "lastfm" shows the latest scrobbles without titles or ranks.

sections (use together with a period):
  -t   top tracks only
  -b   top albums only
  -r   top artists only

  Combine them to show several boxes, for example -t -r. Without any of
  them, all three boxes are shown.

examples:
  lastfm            latest 10 scrobbles
  lastfm -n 20      latest 20 scrobbles
  lastfm -w         top tracks, albums and artists, last 7 days
  lastfm -m         top tracks, albums and artists, last 30 days
  lastfm -q         top tracks, albums and artists, last 3 months
  lastfm -y         top tracks, albums and artists, last 12 months
  lastfm -a         top tracks, albums and artists, all time
  lastfm -c         top tracks, albums and artists, this calendar year
  lastfm -c 2024    top tracks, albums and artists, calendar year 2024
  lastfm -a -n 25   all time, 25 rows per table
  lastfm -m -b      top albums, last 30 days
  lastfm -y -t -r   top tracks and artists, last 12 months
  lastfm -c 2024 -r -n 50
                    top 50 artists, calendar year 2024
  lastfm -u friend          latest 10 scrobbles of another user
  lastfm -u friend -a -r    top artists of another user, all time
  lastfm -u friend -c 2024  another user's 2024 charts
"""


def read_config():
    values = {}
    if not os.path.isfile(CONFIG):
        return values
    if os.stat(CONFIG).st_mode & 0o077:
        print(f"warning: {CONFIG} is readable by others (run chmod 600)", file=sys.stderr)
    with open(CONFIG) as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def keychain_key():
    for cmd in KEYCHAIN_COMMANDS:
        if shutil.which(cmd[0]):
            try:
                out = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5
                ).stdout.strip()
            except subprocess.SubprocessError:
                continue
            if out:
                return out
    return None


def get_credentials(cli_user):
    cfg = read_config()
    user = cli_user or os.environ.get("LASTFM_USER") or cfg.get("user")
    key = os.environ.get("LASTFM_API_KEY") or keychain_key() or cfg.get("key")
    if not user or not key:
        sys.exit("missing username or API key (see lastfm -h)")
    return user, key


def call(user, key, method, **params):
    params.update(method=method, user=user, api_key=key, format="json")
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "lastfm-cli/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode())
        except Exception:
            sys.exit(f"http error {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"network error: {e}")
    if "error" in data:
        sys.exit(f"error {data['error']}: {data.get('message', '')}")
    return data


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def ago(uts):
    seconds = max(0, int(time.time()) - uts)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = seconds // size
            if unit == "day" and n >= 30:
                return time.strftime("%Y-%m-%d", time.localtime(uts))
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


def cw(text):
    """Display width of a string (handles accents and wide characters)."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def fit(text, width, right=False):
    if cw(text) > width:
        out, used = "", 0
        for ch in text:
            w = cw(ch)
            if used + w > width - 3:
                break
            out += ch
            used += w
        text = out + "..."
    pad = " " * (width - cw(text))
    return pad + text if right else text + pad


def table(rows, title=None, ranked=False):
    """Boxed table, columns sized to content.

    The last column is right-aligned. With ranked=True the first column
    (the rank number) is right-aligned too and is never shortened.
    """
    if title:
        print(f"\n{title}")
    if not rows:
        if title:
            print("  (no data)")
        return
    ncols = len(rows[0])
    right = {ncols - 1} | ({0} if ranked else set())
    shrinkable = [k for k in range(ncols) if k not in right]
    widths = [max(cw(r[i]) for r in rows) for i in range(ncols)]
    total = shutil.get_terminal_size((80, 24)).columns
    # Each column adds 2 padding spaces and 1 border, plus 1 closing border.
    excess = sum(widths) + 3 * ncols + 1 - total

    while excess > 0 and shrinkable:
        i = max(shrinkable, key=lambda k: widths[k])
        if widths[i] <= 8:
            break
        widths[i] -= 1
        excess -= 1

    def rule(left, mid, rgt):
        return left + mid.join("─" * (w + 2) for w in widths) + rgt

    print(rule("┌", "┬", "┐"))
    for r in rows:
        cells = [fit(r[i], widths[i], right=i in right) for i in range(ncols)]
        print("│ " + " │ ".join(cells) + " │")
    print(rule("└", "┴", "┘"))


def recent(user, key, limit):
    data = call(user, key, "user.getrecenttracks", limit=limit + 1)
    tracks = [t for t in as_list(data["recenttracks"].get("track")) if "date" in t]
    rows = [
        (
            t.get("name", ""),
            t.get("artist", {}).get("#text", ""),
            ago(int(t["date"]["uts"])),
        )
        for t in tracks[:limit]
    ]
    table(rows)


def artist_name(item):
    """Artist name from either API layout (period methods or weekly charts)."""
    artist = item.get("artist", {})
    if isinstance(artist, dict):
        return artist.get("name") or artist.get("#text", "")
    return str(artist)


def build_rows(kind, items):
    """Ranked rows: rank, name, [artist], play count."""
    rows = []
    for rank, it in enumerate(items, 1):
        if kind == "artists":
            rows.append((str(rank), it.get("name", ""), it.get("playcount", "")))
        else:
            rows.append((str(rank), it.get("name", ""), artist_name(it),
                         it.get("playcount", "")))
    return rows


def top(user, key, period, limit, kinds):
    label = PERIOD_LABELS[period]
    for kind in kinds:
        method, outer, _, _, inner = SECTIONS[kind]
        data = call(user, key, method, period=period, limit=limit)
        items = as_list(data[outer].get(inner))
        table(build_rows(kind, items), f"Top {kind} · {label}", ranked=True)


def year_range(year):
    """Unix timestamps for 1 Jan of `year` (local time) up to the year end or now."""
    this_year = time.localtime().tm_year
    if not FIRST_YEAR <= year <= this_year:
        sys.exit(f"year must be between {FIRST_YEAR} and {this_year}")
    start = int(time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1)))
    end = int(time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1)))
    return start, min(end, int(time.time()))


def top_year(user, key, year, limit, kinds):
    """Top tracks, albums and artists for a calendar year.

    The user.gettop* methods only support fixed periods, so this uses the
    weekly chart methods, which accept an arbitrary from/to range.
    """
    start, end = year_range(year)
    label = f"calendar year {year}"
    for kind in kinds:
        _, _, method, outer, inner = SECTIONS[kind]
        data = call(user, key, method, **{"from": start, "to": end})
        items = as_list(data[outer].get(inner))[:limit]
        table(build_rows(kind, items), f"Top {kind} · {label}", ranked=True)


def main():
    p = argparse.ArgumentParser(
        prog="lastfm",
        usage="lastfm [-n N] [-w | -m | -q | -y | -a | -c [YEAR]] "
              "[-t] [-b] [-r] [-u USER]",
        description="Show your latest Last.fm scrobbles in the terminal.",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-n", "--limit", type=int, default=10, metavar="N",
                   help="rows to show (default 10)")
    p.add_argument("-u", "--user", metavar="USER",
                   help="Last.fm username to view (default: your own, from "
                        "LASTFM_USER or the config file)")
    group = p.add_mutually_exclusive_group()
    group.add_argument("-w", "--week", action="store_const", dest="period",
                       const="7day",
                       help="top tracks, albums and artists, last 7 days")
    group.add_argument("-m", "--month", action="store_const", dest="period",
                       const="1month",
                       help="top tracks, albums and artists, last 30 days")
    group.add_argument("-q", "--quarter", action="store_const", dest="period",
                       const="3month",
                       help="top tracks, albums and artists, last 3 months")
    group.add_argument("-y", "--year", action="store_const", dest="period",
                       const="12month",
                       help="top tracks, albums and artists, last 12 months (rolling)")
    group.add_argument("-a", "--all", action="store_const", dest="period",
                       const="overall",
                       help="top tracks, albums and artists, all time")
    group.add_argument("-c", "--calendar", nargs="?", type=int, const=0,
                       default=None, metavar="YEAR",
                       help="top tracks, albums and artists for a calendar year "
                            "(default: current year)")
    p.add_argument("-t", "--tracks", action="append_const", dest="sections",
                   const="tracks", help="show only top tracks (with a period)")
    p.add_argument("-b", "--albums", action="append_const", dest="sections",
                   const="albums", help="show only top albums (with a period)")
    p.add_argument("-r", "--artists", action="append_const", dest="sections",
                   const="artists", help="show only top artists (with a period)")
    args = p.parse_args()

    has_period = args.calendar is not None or args.period
    if args.sections and not has_period:
        p.error("-t, -b and -r need a period (-w, -m, -q, -y, -a or -c)")
    kinds = [k for k in SECTIONS if not args.sections or k in args.sections]

    user, key = get_credentials(args.user)

    if args.calendar is not None:
        year = args.calendar or time.localtime().tm_year
        top_year(user, key, year, args.limit, kinds)
    elif args.period:
        top(user, key, args.period, args.limit, kinds)
    else:
        recent(user, key, args.limit)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        sys.exit(130)
