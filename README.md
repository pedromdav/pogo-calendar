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
  care about, and writes `public/calendar.ics`. Times are emitted as *floating*
  (no timezone) so events land at the right local time wherever you are — which
  is exactly how Pokémon GO event times work.
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

## Run locally

```sh
python3 generate.py   # writes public/calendar.ics
```
