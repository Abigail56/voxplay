# VOXPLAY

**Enter the game. Own the moment.** VOXPLAY is a social gaming universe: multiplayer games you play with
friends, each from your own phone. (This project used to be called Voice ID; the database, Docker project
and internal names still say `voiceid`, so existing data and deployments keep working.)

| Page | What's there |
|---|---|
| `/` | The landing page: hero, *Choose your battle*, the featured game, how it works, FAQ |
| `/games` | Every game, with Play now or Coming soon |
| `/brain-clash`, `/brain-clash/CODE` | **Brain Clash**: the team quiz (below). The room link is also the invite |
| `/beat-drop`, `/beat-drop/CODE` | **Beat Drop**: hum a secret song, your team names it |
| `/story-forge`, `/story-forge/CODE` | **Story Forge**: two teams build one story, a line each |
| `/whos-talking` | **Who's Talking?**: the voice game (old `/?join=CODE` links redirect here) |
| `/sign-in` | One player for every game |
| `/admin` | Admins only |

The look is original and anime-styled: a night-sky design system in `frontend/app/globals.css` (violet, hot pink
and neon blue, manga halftone dots, glowing card frames; colour tokens checked for contrast), Kanit Black Italic
for headings and Nunito for text (both SIL OFL, bundled), and two cel-shaded mascots drawn in SVG,
**Nova** and **Pulse**, the Brain Clash captains (`frontend/components/art/Characters.tsx`). They star in the scenes
in `frontend/components/art/Scenes.tsx`: the Nexus portal at dusk, a fighting-game VS screen, Nova singing for
Who's Talking?, and the victory podium.
Every artwork spot is a named slot in `frontend/lib/art.ts` with its file path under
`frontend/public/images/voxplay/`. **To add painted art**, generate it with the prompts in
[docs/ART_PROMPTS.md](docs/ART_PROMPTS.md) (a style guide, a four-character bible: Nova, Pulse, Zuri, DJ Ayo, and
every image's size, crop and path), run `python scripts/prepare_art.py <folder>` to resize and compress it to
WebP, and rebuild. `frontend/scripts/scan-art.mjs` runs before every build and lists the files that exist, so a
slot shows its image only when it's really there (never a broken link) and its drawn scene otherwise.

Every game runs on a **20-second clock** by default (the host can change it). A match opens with a VS splash,
each round with a "ROUND n" flash, and every reveal with a hype burst ("YES!", "STOLEN!", "ON FIRE!"); the losing
team gets its own defeat screen. The landing page shows real live numbers from `GET /stats` (players online,
players, matches played) and the recurring cast.

## Brain Clash: two teams, one battle, one champion

A team quiz for friends, families, classes and group chats. The host opens a room, everyone joins from their own
phone with the code or link, and two teams battle it out. Players need a VOXPLAY account but **no voice setup**.

- **⚔️ Brain Battle:** teams take turns; only the team on turn may answer (3 tries). Miss, and the other team
  gets 10 seconds to steal it for half points.
- **⚡ Quick-Fire:** both teams race, one try each; the first right answer wins the round, plus up to 5 points for speed.
- **📝 Name It Fast:** "Name five African countries": each team builds its own list. 5 points per valid answer;
  repeats score nothing; one answer can name several ("Ghana, Kenya and Togo"). The other team's list stays
  hidden until the round ends.
- **🔗 Word Association:** a word appears; each team scores once for a related word from the accepted list.

Scoring (configurable per room): 10 points for a right answer, 20 for a hard one, 5 per Name It Fast item, up to
+5 for speed. The host picks the mode, categories, rounds, timer, a winning score ("first to 100") and team
names, moves players between teams or shuffles them, starts, skips the answer reveal and can end the match.
A level game gets one tie-breaker question open to both teams; still level, it's a draw.

**Answering.** Type it, or press the mic and say it. Spoken answers are turned into text on the server by
Whisper (the same model as the liveness check) and the recording is thrown away straight after. This is
*speech-to-text*, not *speaker recognition*: Brain Clash never looks at whose voice it is. The checker
([backend/app/brain_clash.py](backend/app/brain_clash.py)) ignores case, accents, punctuation, "um, I think it's",
leading "the", writes numbers as digits ("fifty four" = "54"), allows a small slip in longer words
("kilimanjiro") and accepts each question's alternative answers, but not two answers at once ("Ghana or Nigeria").

**Fair play.** The server holds the questions, the answers, the clock and the score; the browser only sends
what was said. Each answer carries a fresh random id, so the same request can't be replayed; answers for an old
round, after the buzzer or out of turn are refused; points are booked under a Redis lock, so two players can't
both score the same question. Rounds end on the server's clock (any screen may ask "time's up?", the server
checks). Rooms live in Redis like Who's Talking? rooms, changes reach every screen through the same WebSocket
(`/ws?bc=CODE`), and a player who reloads or reconnects lands back in the room with their team and points.
Finished matches are saved in PostgreSQL (`bc_results`).

**The question bank** is [backend/app/data/brain_clash_questions.json](backend/app/data/brain_clash_questions.json):
218 questions, Name It Fast lists and Word Association words across 16 categories (African and Nigerian general
knowledge, African music, Nigerian entertainment, history and culture, current affairs, football, animals and
nature, food, languages, Nigerian Pidgin, African movies, riddles, word challenges, everyday knowledge and funny
challenges). Each has a category, difficulty, answer, accepted alternatives and optional points, explanation,
source and active flag. The file is loaded into the `bc_questions` table at every start, so to add or fix a
question, edit the file and restart. A test checks every question: each answer and alternative must be accepted
by the checker, and every category must be playable.

*Current affairs* questions are written as dated events ("Who was sworn in as Nigeria's President in May 2023?"),
so they stay true, and carry `as_of` and `source`. Anything that can't be checked when it's added ships with
`"active": false` until someone verifies it (one does today: the 2025 Grammys question).

## Beat Drop and Story Forge

Both run on Brain Clash's rooms (same lobby, teams, invite links, reconnecting and live updates), as the
modes `hum` and `story`. A room keeps to the game it was opened for.

- **🎵 Beat Drop.** Each round a new hummer (the teams take turns) secretly sees a song, from Afrobeats and
  amapiano hits to Naija classics, and records up to 15 seconds of humming. The hum plays on every phone; the
  hummer's teammates have 3 guesses (say it or type it: "Essence by Wizkid" counts), then the other team can
  steal it for half. A right guess scores 10 (20 for hard ones) and the hummer's team +5. A hummer with no
  teammates hums for the other team. Only titles are used: no copyrighted recordings are played. The hum is
  kept in Redis for 10 minutes at most, only so the round can play it.
- **✍️ Story Forge.** The game writes the first line; then the teams take turns adding one line each (typed or
  spoken, at least three words). Every turn has a spark word ("danfo", "tortoise", "WhatsApp"…) worth +10 if the
  line uses it, and a twist for inspiration. The other team then has 12 seconds to fire 🔥 at the line: +3 a
  fire. At the end the whole legend is shown and can be read aloud.
- **🔥 Streaks** (every Brain Clash room): win three rounds in a row and your team is on fire, +5 a round.
- **Emoji reactions** float across every screen in the room.

The songs and sparks are in the same question bank file (kinds `song` and `spark`): 61 songs in 3 playlists,
36 sparks in 3 story worlds. The bank test checks every title (with and without "by <artist>") and every spark.

### The fair-play AI

[backend/app/fairplay.py](backend/app/fairplay.py) flags answers that look like cheating, for the host to judge:

- **What the AI hears.** Every Beat Drop hum goes through Whisper: a hummer who says the title instead of
  humming it is caught. A Story Forge line copied from earlier in the story is caught by comparing the text.
- **How the answer was given.** With each typed answer the browser reports how long the game was hidden
  (switched to another tab or app to look it up), whether the answer was pasted, and how long the typing took;
  the server adds how soon after the question it came, and whether someone on the other team just sent the same
  answer.

Each sign has a weight and they combine like independent probabilities (suspicion = 1 − Π(1 − w)); one sign
alone is never enough, two are. A flagged answer's points are **held**: every player sees the reasons ("Left
the game for 11s before answering · Pasted the answer"), and the host allows or voids it (when the host is the
one flagged, the other team decides). Nobody is punished automatically, so a false alarm costs a tap. Flags are
saved with each finished match (`bc_results.flags`).

## Who's Talking? A voice game

An online multiplayer game where an AI has to work out who's talking. Sign up, record your voice once,
then join a game with a code from your own phone. On your turn you read out a silly secret line ("the sleepy
penguin stole my shiny pizzas"), and the AI scores you:

- **🎯 Be yourself:** the AI must recognise you. Points = how sure it is (0–100); 0 if it thinks you're someone else.
- **🎭 Impersonate:** "Bayo, sound like Ada!" Points = how much you sound like Ada, +50 if you fool the AI.
  With **⭐ Humans vs AI** on, the other players hear the impression and rate it 1–5 stars *before* the machine's
  verdict is revealed; the stars score too (10 points a star), and the result shows both side by side.
- **🥸 Disguise:** the opposite of Be yourself. Points = how much you *don't* sound like you, +25 if the AI blames
  another player.
- **🕵️ Guess Who** (3+ players): a secretly chosen player speaks, everyone listens to the clip and votes on who it
  was. +50 for a right guess, +25 to the speaker for each player fooled. The AI guesses too.
- **📞 Broken telephone** (3+ players): the first player puts on any voice; each next player hears the clip
  before theirs and copies it. Points = how close the copy is, and every result shows how far the voice has
  drifted from where the chain started.

Options for any game: **⚡ speed rounds** (20 seconds a turn, up to +20 for being quick, 0 if time runs out),
**🌀 twists** (a style for every turn: whisper it, sing it, like a pirate…; x1.5 in Be yourself), a
**🔥 double final** round, and the **🔁 replay**: each turn's clip is kept for an hour, so the game can end with
**highlights** ("Worst impression", "Best disguise", "Humans vs machine", "Lost in the line"…) you can play back.
Every result shows **who the machine thought you sounded like** ("ada 82%, bayo 31%"), and a live level meter
shows the microphone is hearing you while you record.

**🎧 Solo play** for when nobody's online: guess which built-in voice (9 public LibriSpeech readers) is talking
(the AI guesses from the same clips you heard), or impersonate one, or practise your disguise.

Plus: a **📅 daily challenge** (the same tongue-twister for everyone each day, 3 tries, best counts, 🔥 streaks),
**🏅 13 badges** with progress, **⚔️ country vs country** and the **🏆 Weekly Cup** (this week's Top 8 and last
week's champion; solo play doesn't count there), **emoji reactions** that float across everyone's screen, and a
**📸 shareable result card**.

Everyone in the game sees each result live, the browser reads it out loud, and the winner gets confetti.
At sign-up players give their **country and town or area** (or tap "📍 Use my current location"), and the
**dashboard** shows a world map of where everyone plays from, who's online, open games to join, an all-time
leaderboard with levels, and a live feed of turns. Hosts **invite** friends with a link (share menu, WhatsApp
or copy) that drops them straight into the game. An **admin page** shows everything: every player and
where they play, every game, every turn and every cheat attempt.

**No faking:** the line is new every turn, valid for 2 minutes and good for one try, and Whisper checks
it was really said, so a recording of someone can't be played back. **The server works out every
score**; the browser only sends the recording.

**👯 Voice twins** on the game page puts every player's voice on a map and tells you who sounds most like you
(handy for picking who to impersonate). The older voice-lab API (`/speakers`, `/identify`) has no page in the
game any more; it still works for scripts and the portfolio's demo page.

Tech:

- **Models:** pretrained [SpeechBrain ECAPA-TDNN](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) (voiceprints, trained on VoxCeleb) and
  [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `base.en` (speech-to-text for the liveness check). We don't train anything ourselves.
- **Backend:** Python 3.11, FastAPI (REST + **WebSockets**), **SQLModel** on PostgreSQL + **pgvector**, **Redis**
  (game rooms, live updates via pub/sub, one-time phrases, rate limits), pydantic-settings, PyJWT, FFmpeg
- **Frontend:** Next.js 15, React 19, TypeScript, Zustand, browser `MediaRecorder` for the microphone, Leaflet maps,
  WebSockets, Web Audio sound effects, browser speech for the announcer
- **Everything runs in Docker**, so you don't install PyTorch or Node on your machine.

---

## How the game works

1. **Accounts** ([backend/app/auth.py](backend/app/auth.py), [routers/accounts.py](backend/app/routers/accounts.py)).
   Sign up with a player name and password. Passwords are hashed with scrypt (Python's standard library, a
   salted, deliberately slow hash), never stored. Signing in returns a JWT that the browser sends as
   `Authorization: Bearer …`. Then `POST /me/voice` enrolls your voice as an ordinary speaker named after you.
2. **Rooms** ([backend/app/rooms.py](backend/app/rooms.py), [routers/rooms.py](backend/app/routers/rooms.py)).
   A room is JSON in Redis (deleted 6 hours after its last change): code, host, mode and options, players, the
   turn plan (with each turn's twist), this game's results and, at the end, its highlights. Changes happen under a Redis lock, so two phones can't both take the same turn.
3. **A turn.** The player's phone gets a fresh line (`GET /challenge?kind=line`), records, and sends the clip to
   `POST /rooms/{code}/turn`. The server checks it's really their turn, runs the liveness check and the voice
   model *without* holding the lock (it takes ~2 s), then books the points under the lock, but only if the game
   hasn't moved on in the meantime. Each turn is also saved in PostgreSQL (`game_plays`) for the leaderboard.
   Guess Who and Humans vs AI turns go through one more phase first (`vote` / `rate`), with the clip in Redis for
   the others to hear, and the points are booked at the reveal.
4. **Live updates** (`/ws`, [routers/game.py](backend/app/routers/game.py)). Every change is published on Redis
   pub/sub (`room:<code>` and `dashboard`). Each WebSocket listens to those channels and tells its browser
   *what* changed; the browser then fetches the new state over HTTP. Because the messages go through Redis,
   this works with several API instances. Browsers ping every 15 s, which is how "online" is worked out.
5. **Places** ([backend/app/geocode.py](backend/app/geocode.py)). Sign-up asks for a country and a town or area;
   OpenStreetMap's Nominatim turns "Yaba, Lagos" into a point (answers cached in Redis for 30 days, at most one
   lookup a second, as its usage policy asks). "Use my current location" sends the browser's GPS point once, and
   the pin goes on the *neighbourhood* it's in ("Chalk Farm, London"), not the point itself, which is usually
   someone's home. Players can move their pin or hide it from other players.
6. **Invites.** The waiting room has *Share invite* (the phone's share menu), *WhatsApp*, *Copy link* and *Copy
   code*. The link is `/?join=CODE`: a friend who opens it signs up (or in), records their voice and lands in the
   game.
7. **Dashboard** (`GET /dashboard`): everyone's online status, place (unless hidden), current game, total points,
   open games and the latest turns.
8. **Admin** (`/admin`, [routers/admin.py](backend/app/routers/admin.py)), for the player names in
   `ADMIN_USERNAMES`: headline numbers, a map of the players who share their location, all players with place,
   status, points, turns, cheat attempts, join date and last seen, all games, every turn (filter: cheat attempts
   only), and actions to delete a player or end a stuck game.

Tested end to end with **three separate browsers** ("phones" with robot voices from espeak-ng on fake
microphones, in Lagos, Nairobi and London): sign-up, voice enrollment, location sharing, create, join by code,
6 live turns with every result arriving on every screen, the winner announced on all three, and all three
cities on the map.

## How the voice AI works (step by step)

1. **Preprocess** ([backend/app/audio.py](backend/app/audio.py)).
   FFmpeg decodes any common format (wav, mp3, **webm/opus from the browser**, ogg, m4a, flac),
   mixes it to **mono** and resamples it to **16 kHz** (the rate the model expects).
   An energy-based voice-activity detector then **trims silence**. Clips with less than
   1 second of speech are rejected.
2. **Embed** ([backend/app/embedding.py](backend/app/embedding.py)).
   ECAPA-TDNN turns the clip into a **192-number voiceprint** (an "embedding").
   Clips of the same person point in roughly the same direction.
3. **Enroll** (`POST /speakers`). Each sample's embedding is stored, and their average
   (the **centroid**) is stored on the speaker row in a pgvector `vector(192)` column.
4. **Liveness** (`GET /challenge`, [backend/app/liveness.py](backend/app/liveness.py)). The server hands out
   6 random digits ("four seven two nine one six") for `/identify`, or a random silly line for game turns,
   stored in Redis for 2 minutes and good for **one** try. Whisper transcribes the clip, and at least 5 of the 6
   digits (or 5 of the line's 7 words) must be heard, in order. Otherwise the answer is "unknown", with no
   names or scores.
5. **Identify** (`POST /identify`). PostgreSQL finds the nearest centroids using pgvector's
   cosine-distance operator `<=>` (with an HNSW index). The pure function `decide()` in
   [backend/app/matching.py](backend/app/matching.py) then returns the best speaker
   if its **cosine similarity ≥ threshold (0.40)**, otherwise `"unknown"`.

```
browser mic ──► FFmpeg (16 kHz mono) ──► trim silence ──► ECAPA-TDNN ──► 192-d voiceprint
     │                    │                                                    │
     │                    └──► Whisper ──► "4 7 2 9 1 6"? ──no──► "unknown"    │
     │                                          │ yes                          │
 GET /challenge (Redis, 2 min, one use)         ▼                              │
                          name + score  ◄── decide(threshold) ◄── pgvector top-k
                          or "unknown"
```

**Voice twins** (`GET /voice-twins`, [backend/app/voice_map.py](backend/app/voice_map.py)): PCA squeezes the
192-number voiceprints onto the 2 directions in which the players' voices differ most. The "voice twin"
is computed on all 192 numbers, so it is exact even where the 2D picture is rough. Only map positions
and scores leave the server, never the voiceprints.

---

## Quick start

Requirements: Docker with Docker Compose. Ports used: **3010** (web), **8010** (API) and
**5442** (Postgres). They're chosen so they don't clash with a local Postgres on 5432.

```bash
docker compose up -d --build
```

The first start downloads the model (~80 MB) into a Docker volume, which takes about a minute.
Wait until the API is ready:

```bash
curl http://localhost:8010/health
```

Then open:

- **Game:** http://localhost:3010. Create a player, record your voice, then create a game and share its code.
  To play against yourself on one computer, open a second browser (or a private window) as a second player.
- **API docs (Swagger):** http://localhost:8010/docs

> The microphone only works on `localhost` or HTTPS, because browsers block it on plain-HTTP remote hosts.

### Try it with real voices (no microphone needed)

```bash
# download 9 LibriSpeech speakers x 6 clips into ./data/samples (a few MB)
docker compose run --rm api python scripts/fetch_samples.py

# enroll 3 of them, identify held-out clips as wav/mp3/webm + a stranger -> "unknown".
# These are old recordings that can't say a fresh phrase, so turn the liveness check off for the demo:
REQUIRE_LIVENESS=false docker compose up -d api
docker compose run --rm api python scripts/e2e_demo.py --api http://api:8000
docker compose up -d api      # liveness back on
```

### Run the tests

```bash
docker compose run --rm api pytest -v
```

There are 152 tests:
- `test_matching.py`: cosine similarity, centroids, ranking, threshold/"unknown" decisions, margin rule, EER
- `test_audio.py`: resampling, silence trimming, rejecting garbage and too-short audio
- `test_voice_map.py`: PCA keeps similar voices close, voice twins, consistency
- `test_liveness.py`: random digit phrases, the ways Whisper writes digits, wrong order and old recordings fail,
  phrases expire and work once (in memory and in the real Redis)
- `test_brain_clash.py`: answer checking (accents, fillers, numbers, slips, no hedging), every question in the bank
  is answerable, Brain Battle turns and steals, Quick-Fire speed bonus, Name It Fast items and repeats, Word
  Association, late and replayed answers, the server clock, tie-breaker and draw, win score, rooms, team
  permissions, voice answers, the other team's hidden list, results saved, live WebSocket updates and reconnecting;
  streaks; Beat Drop (the secret song, hums, guesses, the hummer's bonus, a title said aloud flagged); Story Forge
  (sparks, fires, copied lines flagged); the fair-play detector's signs, held points and who may decide
- `test_modes.py`: silly lines and near-miss words, disguise, broken telephone (chains, drift, a player leaving
  mid-chain), humans vs AI ratings, twists and the double final, the replay (and clips deleted straight away when
  it's off), highlights, solo play (guess the voice, impersonate, disguise, kept out of the weekly cup)
- `test_api.py`, `test_demo.py`: full HTTP flows against a real pgvector database (`voiceid_test`): enroll → identify → delete,
  liveness pass / replay fails / phrase reused, voice map,
  demo limits.
- `test_fun.py`: daily phrase, score and streaks, badges, Guess Who (the speaker stays secret, the clip is
  deleted at the reveal, scoring), speed bonus and time-outs, wins, country and weekly leaderboards, reactions.
- `test_game.py`: accounts (passwords never stored, no hint which of name/password was wrong), voice
  enrollment, places at sign-up (unknown places refused, GPS snaps to the area, move and hide your pin),
  admin (players get 403, admins see hidden place names but not hidden pins, cheat attempts, delete a player, end a game), full games in both modes, cheating gets 0,
  only the current player can play, hosts hand over, leaving mid-game, deleting your player, the live WebSocket.
  They use a tiny fake embedder and transcriber, so they run in seconds without PyTorch.

### Stop / clean up

```bash
docker compose down        # stop
docker compose down -v     # stop AND delete the database + model cache volumes
```

---

## API

| Method | Path | What it does |
|---|---|---|
| `POST` | `/speakers` | Enroll: form fields `name`, `consent=true`, one or more `files` |
| `POST` | `/speakers/{id}/samples` | Add more samples to an existing speaker (recomputes the centroid) |
| `GET` | `/speakers` | List enrolled speakers with sample counts |
| `GET` | `/speakers/{id}` | One speaker |
| `DELETE` | `/speakers/{id}` | Permanently delete a speaker and all of their voiceprints |
| | **Voice game** | |
| `POST` | `/auth/signup`, `/auth/login` | JSON `username`, `password` (+ `country`, `place` to sign up) → `token` + your player |
| `GET` / `DELETE` | `/me` | Your player (points, turns, voice, location) / delete everything about you |
| `POST` | `/me/voice` | Form `consent`, `files` → enroll or re-record your voice |
| `PUT` | `/me/location` | JSON `share`, optional `country` + `place` → move your pin, or show / hide it |
| `GET` | `/places/search?q=&country=` | Check a place before signing up ("You'll appear at Yaba, Lagos") |
| `GET` | `/places/here?lat=&lon=` | "Use my current location": the neighbourhood a GPS point is in |
| `POST` | `/rooms` | JSON `mode`, `rounds`, `speed`, `twists`, `crowd`, `double_final`, `replay` → a new game with a code like `TIGER-42` |
| `GET` / `PATCH` | `/rooms/{code}` | A game's state / the host changes the mode and options |
| `POST` | `/rooms/{code}/join`, `/leave`, `/start` | Join, leave (the host role passes on), start or rematch (host) |
| `POST` | `/rooms/{code}/turn` | Form `file`, `challenge_id` → your turn, scored by the server |
| `GET` | `/dashboard` | Players (online, city if shared, game, points), open games, latest turns |
| `GET` | `/voice-twins` | Every player's voice on a 2D map, their voice twin, and which dot is you |
| `POST` | `/rooms/{code}/vote`, `/rate`, `/advance`, `/react` | Guess Who vote; Humans vs AI stars; move on when time's up (the server checks the clock); send an emoji |
| `GET` | `/rooms/{code}/clip` | The clip to hear right now: Guess Who's mystery voice, the impression to rate, or the voice to copy (players in the game only) |
| `GET` | `/rooms/{code}/replay/{turn}` | A finished turn's clip, when the replay is on (kept for an hour) |
| `GET` | `/solo` | The built-in voices and your solo record |
| `GET` | `/solo/voices/{id}/intro` | A built-in voice introducing itself (public LibriSpeech audio) |
| `POST` / `GET` | `/solo/guess`, `/solo/guess/{round}/clip` | A new "guess the voice" round / its mystery clip |
| `POST` | `/solo/guess/{round}` | JSON `speaker_id` → right or wrong, and the AI's pick |
| `POST` | `/solo/turn` | Form `mode` (`impersonate` / `disguise`), `speaker_id`, `file`, `challenge_id` → scored like a game turn |
| `GET` / `POST` | `/daily` | Today's tongue-twister, your tries, streak and leaderboard / send a try |
| `GET` | `/leaderboards` | This week: country vs country, the Weekly Cup's Top 8, last week's champion |
| `WS` | `/ws?token=…&room=…` | Live "something changed" messages for the dashboard and a room |
| `GET` | `/admin/overview`, `/admin/players`, `/admin/rooms`, `/admin/plays?cheats_only=` | Admins only: everything |
| `POST` / `DELETE` | `/admin/rooms/{code}/end`, `/admin/players/{id}` | Admins only: end a game, delete a player |
| | **Brain Clash** | |
| `GET` | `/brain-clash/categories` | The 16 categories and how many active questions each has per mode (no sign-in needed) |
| `POST` | `/brain-clash/rooms` | JSON `settings` (mode, categories, rounds, seconds, win_score, speed_bonus, steals, team_names), `name` → a room like `NOVA-42` |
| `GET` | `/brain-clash/rooms/{code}` | The room as you may see it (answers only after each round) |
| `POST` | `/brain-clash/rooms/{code}/join`, `/leave` | Join (optional `name`, `team`) or come back after a disconnect; leave |
| `PATCH` | `/brain-clash/rooms/{code}/settings` | Host: change the match settings in the lobby |
| `POST` | `/brain-clash/rooms/{code}/team`, `/shuffle` | Switch your team (the host can move anyone); host: deal even teams at random |
| `POST` | `/brain-clash/rooms/{code}/start`, `/end` | Host: start (or rematch); end the match now |
| `POST` | `/brain-clash/rooms/{code}/answer` | Form `round`, `answer_id`, and `text` or `file` (a spoken answer) → checked and scored by the server |
| `POST` | `/brain-clash/rooms/{code}/advance` | Time's up / next question (the server checks its clock; the host may skip the reveal) |
| | **Voice lab** | |
| `GET` | `/challenge?kind=digits\|line` | A fresh phrase to say: 6 digits (default) or a silly line (valid 2 minutes, one use) |
| `POST` | `/identify` | Form fields `file`, `challenge_id` → best match or `"unknown"` |
| `GET` | `/health` | Model loaded? threshold? number of speakers |

Example:

```bash
curl -F name=Ada -F consent=true -F files=@ada1.wav -F files=@ada2.mp3 http://localhost:8010/speakers
curl http://localhost:8010/challenge           # {"challenge_id": "...", "phrase": "four seven two nine one six", ...}
curl -F file=@mystery.webm -F challenge_id=... http://localhost:8010/identify   # mystery.webm says the phrase
```

```json
{
  "label": "Ada",
  "is_match": true,
  "speaker_id": 1,
  "score": 0.7123,
  "threshold": 0.4,
  "reason": "Score is above the threshold.",
  "speech_seconds": 6.1,
  "candidates": [
    {"speaker_id": 1, "name": "Ada", "score": 0.7123},
    {"speaker_id": 2, "name": "Bayo", "score": 0.0912}
  ],
  "liveness": {"passed": true, "phrase": "four seven two nine one six", "heard": "4, 7, 2, 9, 1, 6.", "match": 1.0}
}
```

`score` is the cosine similarity between the clip and the speaker's voiceprint, used as the
confidence. In practice it falls between about −0.1 and 1.0, and higher is more confident.

---

## How the threshold was chosen

`scripts/tune_threshold.py` measures how well the model separates voices **on real data**:

1. For each of **9 LibriSpeech speakers**, 2 clips build the centroid (like enrollment) and the
   other 3–4 clips are test clips.
2. Each test clip is scored against **its own speaker** (34 *genuine* scores) and against
   **every other speaker** (272 *impostor* scores).
3. For each candidate threshold it reports the **false-accept rate** (a stranger is accepted as
   someone), the **false-reject rate** (a real speaker is called unknown) and an **open-set
   accuracy**: each speaker is left out of the database in turn, so their clips *must* come back
   "unknown".

Results (full output in [docs/threshold-tuning.txt](docs/threshold-tuning.txt)):

| | min | mean | max |
|---|---|---|---|
| genuine scores | 0.350 | **0.716** | 0.913 |
| impostor scores | −0.108 | **0.098** | 0.350 |

| threshold | false accepts | false rejects | open-set accuracy |
|---|---|---|---|
| 0.30 | 1.5 % | 0.0 % | 98.7 % |
| 0.35 (EER) | 0.4 % | 2.9 % | 97.1 % |
| **0.40 (chosen)** | **0.0 %** | **2.9 %** | **97.4 %** |
| 0.50 | 0.0 % | 8.8 % | 92.2 % |

**Why 0.40:** it's the lowest threshold with **zero false accepts** on this data. For an identity
system, wrongly naming a stranger as someone is worse than asking a real person to try again.
It also leaves a clear gap above the mean impostor score (0.10).

**Tune it for your setting.** LibriSpeech is clean read speech. Laptop microphones in noisy rooms
give lower genuine scores. If enrolled people often get "unknown", try `0.30–0.35`. To be stricter,
use `0.45–0.50`. You can also set `MIN_MARGIN` (e.g. `0.05`) so the system says "unknown" when two
speakers score almost the same. Best of all, record your own clips into `data/samples/<name>/`
and re-run:

```bash
docker compose run --rm api python scripts/tune_threshold.py --data /data/samples
MATCH_THRESHOLD=0.35 docker compose up -d api      # or put it in .env
```

### End-to-end verification

[docs/e2e-demo-output.txt](docs/e2e-demo-output.txt) shows the result of
`scripts/e2e_demo.py`. Three speakers were enrolled with 2 clips each. Held-out clips sent as
**wav, mp3 and webm/opus** were all identified correctly (scores 0.62–0.83), and a never-enrolled
speaker came back **"unknown"** every time (scores 0.12–0.17). **21/21 correct.** One clip
with only 0.8 s of speech was rejected with a clear 422 error, which is the intended behaviour.

---

## Liveness check: what it stops, and what it doesn't

**It stops replays.** A recording made before the phrase existed can't contain it, and each phrase works
once, for 2 minutes. Tested through the API: an old recording of an enrolled reader came back "unknown"
(Whisper heard what it really says, "It's no better than a badger hole…"), and sending the same phrase
again was refused.

**Why digits, and why 5 of 6.** A robotic text-to-speech voice (espeak-ng, much harder to understand than
a person) read 30 phrases of each kind. Whisper `base.en` heard **27/30 digit phrases** right against only
21/30 phrases mixing words and digits (in a list, "nine" kept turning into "pine"). `small.en` got 30/30
but is about 3 times slower (4 s per clip on a CPU), so it's an option (`ASR_MODEL=small.en`), not the default.
Unrelated sentences never matched more than 40 % of any phrase, far below the 80 % (5 of 6 digits) needed.

**Game turns read silly lines instead** ("the sleepy penguin stole my shiny pizzas"), which are more fun to say
and, at about 2 million combinations handed out once for 2 minutes, just as impossible to have recorded in advance.
Words are harder for Whisper than digits, so the lines were tuned with the same robot-voice test
(`espeak-ng` → Whisper `base.en`). The first version passed only 19/30 lines: most misses were near-hits
("umbrella" for "umbrellas", "rusted" for "rusty") or a mangled number word ("nine" heard as "I'm"). So longer
words now count when they're off by a plural or a letter or two (digits stay exact), the number was dropped,
and short, easily misheard words ("goat" → "got", "brave" → "brain") were swapped for longer ones. Result:
**60/60 lines passed** at the 70 % needed (5 of 7 words), against 26/30 digit phrases in the same run, while
unrelated speech still matched at most 29 % of a line.

**It does not stop a live voice clone.** Someone with an AI clone of Ada's voice could make it say the
phrase within the 2 minutes. Catching that needs an anti-spoofing model trained to tell real from
synthetic speech (for example AASIST, trained on the ASVspoof challenge data). That's the next step
if this is ever used for anything that matters.

---

## Consent and privacy

A voiceprint is **biometric data**. Under laws such as the GDPR (Art. 9), Nigeria's NDPA 2023
and Illinois' BIPA, it needs explicit consent and careful handling. This project builds that in:

- **Consent is required.** `POST /speakers` refuses to enroll anyone unless `consent=true`, and
  the UI has a consent checkbox. The time of consent is stored (`consent_given_at`).
- **Enroll only people who agree**, and tell them what it's for and how long it's kept.
- **Raw audio isn't kept for long.** Only the 192-number embeddings are stored in the database, and uploads
  are processed in memory or in a temp file that is deleted right away. Game turns are the exception, and only in
  Redis: when the other players have to *hear* a clip (Guess Who, Humans vs AI, the voice to copy in Broken
  telephone) it's kept until it has been heard, and with the **replay** on (the host's choice, shown to everyone in
  the waiting room) each turn's clip is kept for an hour. Only players in that game can fetch them, and clips
  are always gone after an hour at most.
- **Right to be forgotten.** `DELETE /speakers/{id}` (the "Delete" button) removes the speaker
  and all of their sample embeddings (`ON DELETE CASCADE`).
- **Treat embeddings as sensitive.** Even without the audio, they identify a person. In production,
  add authentication, HTTPS, encrypted backups and access logging, and don't expose the API publicly as-is.
- **It isn't proof of identity.** The liveness check stops replayed recordings, but not a live AI
  voice clone (see above). Use this for convenience features, not for authorising payments or access on its own.
- **Location is the player's own choice of place.** Sign-up asks for a country and a town or area, and the pin
  goes on that place's centre. "Use my current location" (the browser asks first) is turned into the
  *neighbourhood* the player is in; the GPS point itself isn't stored. Pins are shown to signed-in players only,
  any player can hide theirs (admins still see it), and turns forget where they were played after 30 days
  (`LOCATION_RETENTION_DAYS`). Place names typed at sign-up are sent to OpenStreetMap's Nominatim to find them on
  the map, and viewing the map loads tiles from OpenStreetMap's servers. No IP-address lookups.
- **Admins** (`ADMIN_USERNAMES`) see every player's place name in the players table, including hidden ones, so keep that list short.
  Hidden pins stay off the admin map: their coordinates never leave the server.
- **Accounts.** Passwords are stored only as salted scrypt hashes. "Delete player" removes the account, the
  voiceprint, every turn and the location. Players' voices can't be changed or deleted from the Voice lab.
- **Phrases and rate limits are short-lived.** Redis keeps them for at most a few minutes and never writes them to disk.

---

## Folder structure

```
voice-id/
├── docker-compose.yml          # db (pgvector) :5442, redis :6389, api :8010, web :3010
├── .env.example                # MATCH_THRESHOLD / REQUIRE_LIVENESS overrides
├── README.md
├── docs/
│   ├── threshold-tuning.txt    # output of scripts/tune_threshold.py
│   └── e2e-demo-output.txt     # output of scripts/e2e_demo.py
├── data/                       # sample voices land in data/samples/<speaker>/ (git-ignored)
├── backend/
│   ├── Dockerfile              # python:3.11-slim + ffmpeg + CPU-only PyTorch + both models baked in
│   ├── requirements.txt / requirements-dev.txt
│   ├── db-init/01-test-db.sql  # creates the voiceid_test database
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, lifespan (loads models, Redis), CORS, /health
│   │   ├── config.py           # pydantic-settings from env vars (thresholds, limits, DB + Redis URLs)
│   │   ├── audio.py            # FFmpeg decode → 16 kHz mono, voice activity / silence trimming, validation
│   │   ├── embedding.py        # ECAPA-TDNN wrapper (SpeechBrain), batched embedding
│   │   ├── matching.py         # cosine similarity, centroids, decide() → name / unknown
│   │   ├── voice_map.py        # PCA to 2D, voice twins, consistency
│   │   ├── liveness.py         # digit phrases and silly lines, Whisper wrapper, phrase matching, one-time challenges
│   │   ├── store.py            # Redis (or in-memory): phrases, rate limits, rooms, locks, pub/sub
│   │   ├── auth.py             # scrypt password hashes, JWTs, "who is signed in"
│   │   ├── rooms.py            # game rooms: modes, turn plan, twists, server-side scoring, highlights, Redis persistence
│   │   ├── brain_clash.py      # Brain Clash rules: answer checking, modes, clock, steals, tie-breaker, Redis store
│   │   ├── data/brain_clash_questions.json  # the question bank (source of truth)
│   │   ├── geocode.py          # place names ↔ map points (OpenStreetMap Nominatim, cached)
│   │   ├── services.py         # upload → preprocess → embed / transcribe (in worker threads)
│   │   ├── db.py, models.py    # SQLModel tables (speakers, samples, users, game_plays) + pgvector, async sessions
│   │   ├── schemas.py          # Pydantic response models
│   │   └── routers/
│   │       ├── speakers.py     # enroll, add samples, list, get, delete, voice map
│   │       ├── identify.py     # GET /challenge, liveness check, identify (pgvector + decide())
│   │       ├── accounts.py     # sign up / in, my voice, my location, delete me
│   │       ├── rooms.py        # create / join / start / turn / vote / rate / clips and the replay
│   │       ├── solo.py         # solo play against the built-in voices
│   │       ├── brain_clash.py  # Brain Clash rooms, answers (text or voice), question bank loading
│   │       ├── game.py         # dashboard + the /ws live-updates WebSocket
│   │       └── admin.py        # the admin page's data and actions
│   ├── scripts/
│   │   ├── fetch_samples.py    # download LibriSpeech test voices
│   │   ├── tune_threshold.py   # genuine/impostor scores, EER, threshold sweep
│   │   └── e2e_demo.py         # enroll + identify via the running API
│   └── tests/                  # pytest: matching, audio, voice map, liveness, API
└── frontend/
    ├── Dockerfile              # node:22-alpine multi-stage, Next.js standalone
    ├── app/                    # layout.tsx, page.tsx (landing), games/, brain-clash/, whos-talking/, sign-in/,
    │                           #   admin/, not-found, error, loading, icon.svg, manifest, globals.css
    ├── components/
    │   ├── ClipInput.tsx       # record (MediaRecorder) or upload audio
    │   ├── game/               # Welcome, VoiceSetup, PlayerCard, Lobby, GameOptions, RoomPanel, Solo, World (map,
    │   │                       #   leaderboard, feed), GameHome, Avatar, PlayButton, PlayersMapLeaflet, LocationPicker,
    │   │                       #   Invite, VoiceTwins
    │   ├── admin/AdminDashboard.tsx # the admin page
    │   ├── brain-clash/        # Entry (create / join / how to play) and Room (lobby, match, victory)
    │   ├── portal/, brand/, art/, auth/  # game cards and footer; logo and loader; SVG artwork; sign-in form
    │   └── Phrase.tsx          # the line (or digits) to read out + countdown (lib/useChallenge.ts fetches them)
    ├── lib/api.ts              # typed fetch wrapper for the backend
    ├── lib/game.ts             # levels, avatars, sound effects, spoken announcer
    ├── lib/countries.ts        # country list, names and flags (from the browser's Intl API)
    ├── lib/useLive.ts          # WebSocket live updates with reconnect + ping
    ├── lib/games.ts, art.ts, brainClash.ts  # the game catalogue, artwork slots, Brain Clash mode texts
    ├── lib/useChallenge.ts     # fetches the line to read out and counts down
    └── store/                  # Zustand: signed-in player (useAuthStore)
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `MATCH_THRESHOLD` | `0.40` | Minimum cosine similarity for a match |
| `REDIS_URL` | *(empty)* | Redis for phrases and rate limits; empty = in-process memory (one instance only) |
| `REQUIRE_LIVENESS` | `true` | `/identify` needs a phrase from `/challenge` |
| `CHALLENGE_TTL_SECONDS` | `120` | How long a phrase stays valid |
| `LIVENESS_MIN_MATCH` | `0.8` | Share of the digits that must be heard, in order |
| `LINE_MIN_MATCH` | `0.7` | The same for game turns' silly lines (5 of 7 words) |
| `ASR_MODEL` | `base.en` | faster-whisper model (`small.en` is more accurate, ~3x slower) |
| `JWT_SECRET` | *(random per start)* | Signs sign-in tokens. **Set a long random value in production**, or everyone is signed out on every restart |
| `TOKEN_DAYS` | `7` | How long a sign-in lasts |
| `ROOM_TTL_HOURS` | `6` | Games are deleted this long after their last change |
| `ONLINE_SECONDS` | `90` | A player counts as online if their page pinged this recently |
| `ADMIN_USERNAMES` | *(empty)* | Comma-separated player names who can open `/admin` |
| `GEOCODER_USER_AGENT` | `WhosTalking-VoiceGame/1.0` | Names the app to OpenStreetMap's Nominatim; add a contact URL or email for real use |
| `LOCATION_RETENTION_DAYS` | `30` | Where each turn was played from is forgotten after this long |
| `MIN_MARGIN` | `0.0` | Required lead over the runner-up (0 = off) |
| `MIN_SPEECH_SECONDS` | `1.0` | Reject clips with less speech than this |
| `MAX_CLIP_SECONDS` | `60` | Reject longer clips |
| `MAX_UPLOAD_MB` | `10` | Per-file upload limit |
| `CORS_ORIGINS` | `http://localhost:3010,http://localhost:3001` | Comma-separated allowed origins (the Voice ID UI and the portfolio demo page) |
| `DEMO_RETENTION_HOURS` | `0` | Delete visitors' enrollments after this many hours (0 = keep) |
| `MAX_ACTIVE_ENROLLMENTS` | `0` | Most visitor enrollments kept at once (0 = no limit) |
| `RATE_LIMIT_PER_MINUTE` | `0` | Enroll/identify requests per visitor IP per minute (0 = off) |
| `TRUST_PROXY_HEADERS` | `false` | Read the visitor IP from `X-Forwarded-For` (only behind a proxy) |
| `SEED_SAMPLE_VOICES` | `false` (`true` in docker compose) | Enroll the LibriSpeech readers in `backend/sample_voices/` on startup (solo play needs them) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8010` | Frontend → API URL (build arg) |

## Public demo and deployment

For a public demo, turn on the settings above. They're already on in the Hugging Face Space image. The demo
then works like this:

- **Sample voices.** Nine LibriSpeech readers (`backend/sample_voices/`, CC BY 4.0) are enrolled at startup, so
  there is always someone to match and to play solo against. They can't be deleted or changed (`403`).
- **Visitors' enrollments expire.** Each gets `expires_at`. Expired speakers disappear from every endpoint at once,
  and a background job deletes them for good every 5 minutes (`app/demo.py`).
- **Abuse limits.** Per-IP rate limit (`429`) and a cap on active enrollments (`503 demo is full`).

**Deploying to a free Hugging Face Space:** run `sh deploy/make-hf-space.sh` and upload `dist/hf-space/`. Full steps
are in the portfolio's `docs/DEPLOY.md`. Free Spaces can't reach outside databases, so the Space image
(`deploy/huggingface-space/`) runs its own PostgreSQL + pgvector and Redis next to the API. Add a `JWT_SECRET`
under the Space's *Settings → Secrets*, or players are signed out whenever the Space restarts. Data lasts only while the Space
runs, which suits a demo with 24-hour enrollments.

`DATABASE_URL` also accepts the plain `postgresql://…?sslmode=require` strings that hosts like Neon give you;
`app/config.py` converts them for asyncpg.

## Notes and ideas for next steps

- **Versions.** `huggingface_hub` is pinned to `0.25.2` because SpeechBrain 1.0.3 calls
  `hf_hub_download(use_auth_token=...)`, which newer versions removed.
- **Speed and memory.** The API uses about 610 MB of RAM with both models loaded. On a 4-core laptop
  (CPU only, 2 PyTorch threads) one `/identify` call with the liveness check takes about 2 s. Raise `TORCH_THREADS` if you have more cores.
- **Ideas:** an anti-spoofing model against voice clones, Alembic migrations, auth (JWT),
  a stricter threshold when a match guards something real, live "who's talking now" from the
  microphone, and showcasing it on your portfolio site.
