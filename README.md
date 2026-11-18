# lastfm

A small command-line viewer for Last.fm listening history. It shows
latest scrobbles, and top tracks, albums and artists for a period, as
boxed tables in the terminal. It works for your own account and for any
other public Last.fm user.

It is read-only. It talks to the Last.fm API and never changes an account.

## Features

- Latest scrobbles with relative times ("5 minutes ago")
- Top tracks, albums and artists for 7 days, 30 days, 3 months, 12 months
  or all time
- Top lists for any calendar year (for example 2024)
- View any public Last.fm profile with `-u`, not only your own
- Show only the sections you want
- Tables fit your terminal width and handle accents and wide characters
- No third-party packages

## Requirements

- Python 3.6 or newer
- A free Last.fm API key
- Optional, for keychain storage: macOS `security`, or Linux `secret-tool`

## Install

```bash
chmod +x lastfm.py
cp lastfm.py ~/.local/bin/lastfm
```

Make sure `~/.local/bin` is in your `PATH`. Then run `lastfm -h`.

## Setup

1. Create an API key at https://www.last.fm/api/account/create
2. Store the key with one of the options below.

### Option 1: macOS keychain

```bash
security add-generic-password -a "$USER" -s lastfm-api-key -w
```

### Option 2: Linux keyring

```bash
secret-tool store --label=lastfm service lastfm-api-key
```

### Option 3: config file

Create `~/.config/lastfm/config`:

```
user=your_username
key=your_api_key
```

Then restrict access:

```bash
chmod 600 ~/.config/lastfm/config
```

The script warns you if the file is readable by other users.

### Where each value is read from

| Value    | Order of lookup                                            |
|----------|------------------------------------------------------------|
| Username | `-u`, then `LASTFM_USER`, then `user=` in the config file  |
| API key  | `LASTFM_API_KEY`, then keychain, then `key=` in the config |

## Usage

```
lastfm [-n N] [-w | -m | -q | -y | -a | -c [YEAR]] [-t] [-b] [-r] [-u USER]
```

With no period, it shows the latest scrobbles.

### Periods (use one at a time)

| Flag | Period                                              |
|------|-----------------------------------------------------|
| `-w` | Last 7 days                                         |
| `-m` | Last 30 days                                        |
| `-q` | Last 3 months                                       |
| `-y` | Last 12 months (rolling, counted back from today)   |
| `-a` | All time                                            |
| `-c` | Calendar year, 1 January to 31 December (default: current year, or pass a year such as `-c 2024`) |

Calendar years use your local time. The current year covers 1 January up
to now. Valid years run from 2002 to the current year.

### Sections (use with a period)

| Flag | Section     |
|------|-------------|
| `-t` | Top tracks  |
| `-b` | Top albums  |
| `-r` | Top artists |

Combine them to show several boxes. Without any of them, all three are
shown.

### Viewing other users

Use `-u` to read the data of any Last.fm user, not only your own. It works
with the latest-scrobbles view and with every period and section flag.

```bash
lastfm -u friend                 # latest 10 scrobbles of "friend"
lastfm -u friend -m              # their top tracks, albums and artists, last 30 days
lastfm -u friend -a -r -n 25     # their top 25 artists, all time
lastfm -u friend -c 2024         # their calendar year 2024
```

Notes:

- You still use your own API key. You don't need the other person's key or password.
- `-u` takes priority over `LASTFM_USER` and over `user=` in the config file.
- The data must be public. If a user hides their listening data in their
  Last.fm privacy settings, the API may return an error or an empty list.
- `error 6: User not found` means the username doesn't exist.

### Other options

| Flag         | Meaning                                   |
|--------------|-------------------------------------------|
| `-n N`       | Rows to show (default 10)                 |
| `-u USER`    | View any Last.fm user (default: your own) |
| `-h`         | Help                                      |

## Examples

```bash
lastfm                  # latest 10 scrobbles
lastfm -n 20            # latest 20 scrobbles
lastfm -w               # tracks, albums and artists, last 7 days
lastfm -a -n 25         # all time, 25 rows per table
lastfm -m -b            # top albums, last 30 days
lastfm -y -t -r         # top tracks and artists, last 12 months
lastfm -c               # this calendar year
lastfm -c 2024 -r -n 50 # top 50 artists of 2024
lastfm -u friend -a -r  # another user's top artists, all time
```

## Output

Each period view shows up to three boxes titled "Top tracks",
"Top albums" and "Top artists", followed by the period. Every row has a
rank on the left and the play count on the right. The latest-scrobbles
view has no titles or ranks.

## How calendar years work

The Last.fm "top" methods only support fixed periods. For `-c`, the script
uses the weekly chart methods, which accept any start and end time, and
shows the first N rows.

## Security

- The script is read-only and uses only a username and your API key.
- The key is sent over HTTPS as a query parameter, as the Last.fm API
  expects.
- Prefer the keychain. If you use the config file, keep it at `chmod 600`.
- `LASTFM_API_KEY` can be read by other processes of your user and may
  appear in shell history. Use it for temporary runs.
- Never commit the config file or your key to a public repository.

## Troubleshooting

| Message                                   | Likely cause and fix                                          |
|-------------------------------------------|---------------------------------------------------------------|
| `missing username or API key`             | No username or key found. Check the setup section.           |
| `error 10: Invalid API key`               | The key is wrong or was revoked. Create a new one.            |
| `error 6: User not found`                 | Wrong username.                                               |
| `network error`                           | No connection, or Last.fm is slow. The timeout is 10 seconds. |
| `year must be between 2002 and <year>`    | Use a valid calendar year.                                    |
| `-t, -b and -r need a period`             | Add a period flag such as `-m`.                               |
| Warning: config readable by others        | Run `chmod 600 ~/.config/lastfm/config`.                      |

## License

Add your license here.
