# pogo-calendar

A subscribable **`.ics` calendar feed of Pokémon GO events** — Community Days,
big events, and raids (incl. raid hours). It auto-refreshes twice a day via
GitHub Actions and is served for free from GitHub Pages, so once it's set up you
never have to touch it: the events just show up in your calendar.

Data comes from [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck), a
community-maintained JSON mirror of [Leek Duck](https://leekduck.com/events/).

## How it works

```
ScrapedDuck events.json  ──>  generate.py  ──>  public/calendar.ics  ──>  GitHub Pages
                              (filter + build .ics)        (subscribe in Google Calendar)
```

- `generate.py` — stdlib-only Python. Fetches events, filters to the types you
  care about, and writes `public/calendar.ics`, pinned to a timezone (default
  `Europe/Zurich`) with that zone's daylight-saving rules embedded.
- `.github/workflows/build.yml` — runs on push + a twice-daily cron, regenerates
  the feed, and deploys `public/` to GitHub Pages.

## One-time setup

1. **Create a GitHub repo** and push this folder to it:
   ```sh
   git init && git add -A && git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/pogo-calendar.git
   git push -u origin main
   ```
2. **Enable Pages:** repo → **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.
3. The workflow runs automatically on push. When it finishes, your feed lives at:
   ```
   https://<your-username>.github.io/pogo-calendar/calendar.ics
   ```
   (Visit `https://<your-username>.github.io/pogo-calendar/` for a subscribe page.)

## Subscribe

**Google Calendar:** Other calendars (＋) → **From URL** → paste the feed URL.
Google polls subscribed URLs periodically (often every several hours to a day).

**iPhone:** Settings → Calendar → Accounts → Add Account → Other →
Add Subscribed Calendar → paste the URL.

## Customise what's tracked

Edit the `INCLUDE` dict at the top of `generate.py`. Each key is a Leek Duck
`eventType`; the value is the emoji shown in the event title. Currently included:

| eventType        | shown as |
|------------------|----------|
| `community-day`  | 🌟 |
| `raid-battles`   | ⚔️ |
| `raid-hour`      | ⚔️ |
| `raid-day`       | ⚔️ |
| `max-mondays`    | ⚔️ |
| `pokemon-go-fest`| 🎉 |
| `event`          | 📅 |

Other available types include `pokemon-spotlight-hour`, `go-battle-league`,
`season`, `go-pass`, `choose-your-path`. Add any of them to `INCLUDE` to track them.

## Timezone & travelling

Pokémon GO events like Community Days and Raid Hours happen at the same
wall-clock time in **every** local timezone (a 14:00 Community Day is 14:00
wherever you are). The truly "follows you as you travel" representation is a
*floating* time — which **Apple/iPhone Calendar honours**, but **Google Calendar
does not** (it misreads floating times as UTC and shifts them). So this feed pins
to one concrete timezone instead.

The default is `Europe/Zurich`. To use another zone:

```sh
python3 generate.py --tz America/New_York   # or: POGO_TZ=America/New_York python3 generate.py
```

**When you travel**, repoint the hosted feed to your current zone without editing
code: set a repo variable `POGO_TZ` (Settings → Secrets and variables → Actions →
Variables) to e.g. `Asia/Tokyo`, then re-run the workflow (Actions tab → Run
workflow). The feed rebuilds in the new zone; your subscription picks it up on its
next refresh. Set it back when you return home.

> Tip: if you use **Apple Calendar** as your main app, ping me and I can switch
> the generator to floating times instead — then events follow your travel
> automatically with no timezone juggling.

## Run locally

```sh
python3 generate.py                  # default timezone
python3 generate.py --tz Asia/Tokyo  # any IANA timezone
```
