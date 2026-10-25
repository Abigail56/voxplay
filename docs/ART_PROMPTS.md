# VOXPLAY artwork: prompts, sizes and where each image goes

This environment can't generate images, so none of these exist yet. The site shows its drawn SVG scenes
in every slot until you add the file. Generate each image below with an AI image tool (Midjourney,
Leonardo, Ideogram, Bing Image Creator / DALL·E, Adobe Firefly…) or give the briefs to an artist.

**Check the tool's licence before you publish.** Some free tiers don't allow commercial use, or don't
give you ownership of the images.

## How to add them

1. Generate an image and save it under its **asset name**, e.g. `voxplay-hero.png` or `nova.png`.
   PNG, JPG or WebP all work.
2. Put all the files in one folder and run:
   `python scripts/prepare_art.py ~/Downloads/voxplay-art`
   It resizes, crops to the right shape, compresses to WebP and saves each file at its path under
   `frontend/public/images/voxplay/`.
3. Rebuild the site (`docker compose up -d --build web`). Before every build, `scripts/scan-art.mjs`
   lists the files that exist, and each slot switches from its drawing to its image. There's no code
   to change and there are never broken image links.

## The style (use it in every prompt)

> **STYLE:** premium cinematic anime key art, semi-realistic anime rendering, detailed painterly shading,
> beautifully detailed faces and expressive eyes, realistic hair strands, carefully designed clothing
> with fabric folds and stitching, dramatic rim lighting, volumetric light, atmospheric depth, dark
> futuristic environment with electric violet (#7c3aed), neon blue (#38bdf8), cyan and magenta (#f472b6)
> accents, rich shadows, subtle highlights, professional colour grading, high detail, sharp focus,
> AAA anime game promotional art

> **AVOID (negative prompt):** text, letters, words, logos, watermark, signature, UI, buttons, frames,
> borders, extra fingers, malformed hands, distorted faces, asymmetrical eyes, extra limbs, blurry,
> low quality, flat colours, chibi, childish cartoon, 3D render, photo, copyrighted characters,
> franchise costumes, excessive glow hiding the faces

Add "no text" to every prompt: the site writes all labels in HTML. In Midjourney, append
`--no text, logo, watermark` and the aspect ratio (e.g. `--ar 16:9`). In other tools, paste the AVOID
list into the negative prompt box.

## The crew: keep these four consistent

Make a **reference sheet** for each character first (front view, three-quarter view and a few
expressions, plain dark background). Then reuse it for every scene they appear in:

- Midjourney: `--cref <sheet URL> --cw 100`
- Leonardo: Character Reference
- Ideogram: Character
- Other tools: image-to-image from the sheet

No tool guarantees a perfect match every time, so expect to regenerate a few and pick the closest.

| | **Nova** | **Pulse** | **Zuri** | **DJ Ayo** |
|---|---|---|---|---|
| Role | Team Nova captain, Brain Clash | Team Pulse captain, Brain Clash | Keeper of tales, Story Forge | Host, Beat Drop |
| Look | Young Nigerian woman, deep brown skin, oval face, high cheekbones, amber-violet eyes, small gold nose stud | Young Ghanaian man, warm brown skin, strong jaw, bright cyan eyes, small plaster on left cheek, silver stud in left ear | Young Kenyan woman, dark skin, soft round face, emerald eyes, freckles of gold shimmer on cheekbones | Young Nigerian man, light-brown skin, wide grin, gap between front teeth, round amber-tinted visor glasses |
| Hair | Long violet box braids gathered in a high bun with a pink band, a few braids falling forward | Spiky swept-up cyan-blue hair with darker roots, short sides, pink sweatband | Long silver-white locs with small gold cuffs | Short twists with magenta tips |
| Clothes | Cropped black-violet tech jacket with cyan piping, hot-pink inner top, fingerless gloves | Oversized black hoodie with a yellow lightning bolt, cyan drawstrings, sleeves pushed up | Flowing midnight-blue long coat with glowing gold geometric embroidery, teal scarf | Oversized varsity jacket with neon pink and orange trims, white tee |
| Accessories | Over-ear headphones with glowing pink and cyan cups, gold hoop earrings | Wristband with a glowing cyan display | A floating holographic book bracelet | Wireless headset mic, small DJ controller |
| Personality | Calm strategist, confident half-smile | Hype, fearless, big grin | Dreamy, wise, gentle smile | Showman, playful, loud |
| Colours | violet + pink | cyan + yellow | teal + gold | magenta + orange |

**Character sheet prompt** (once per character, replace the bracket):
> Character reference sheet of [CHARACTER DESCRIPTION FROM THE TABLE], front view, three-quarter view,
> and three facial expressions (confident, laughing, determined), full upper body, consistent design,
> plain dark violet background, STYLE, no text. *Aspect 3:2, 2048×1365.*

## Every image

Paths are under `frontend/public/images/voxplay/`. "Space" means an area kept clear of characters and
detail, where the website draws its own text.

### 1. Landing page hero: `hero/voxplay-hero.webp` (asset name `voxplay-hero`)

- **Used in:** the landing page hero, loaded first (high priority).
- **Shape:** 16:9, 2400×1350. No transparent background.
- **Cropping:** shown at about 4:3 and cropped around 70% across, 35% down, so keep all four faces in
  the right two thirds. Keep the left third calm and darker.

> Cinematic wide shot of four original anime gamers standing together as a team inside a futuristic
> holographic gaming arena at night: Nova (STYLE NOTES FROM TABLE) in front, Pulse beside her grinning,
> Zuri and DJ Ayo slightly behind, all looking toward the viewer with confident energy, floating
> holographic screens and a glowing circular portal behind them, arena lights, haze, the left third of
> the image darker and calmer with negative space, STYLE, no text.

**Phone version:** `hero/voxplay-hero-mobile.webp` (asset name `voxplay-hero-mobile`), 4:5 at 1080×1350.
Use the same prompt, recomposed as a vertical shot with the four faces in the upper half.

### 2. Brain Clash VS screen: `brain-clash/team-versus.webp` (`team-versus`)

- **Used in:** the Brain Clash banner and game card, the match intro splash, and the Beat Drop and
  Story Forge VS intro.
- **Shape:** 16:9, 1920×1080. Keep the middle fifth empty for the VS mark.
- **Cropping:** shown both wide and narrow (about 1.3:1), so keep both faces inside the middle 70%.

> Dramatic versus-screen illustration: Nova on the left lit in electric violet and magenta, Pulse on the
> right lit in cyan and yellow, both in dynamic three-quarter poses facing each other, a diagonal split
> of energy between them, strong rim lighting, sparks and speed lines, an empty glowing gap in the
> centre, STYLE, no text.

### 3. Lobby arena: `brain-clash/arena.webp` (`arena`)

- **Used in:** the background of the Brain Clash room lobby and match (shown dimmed behind the cards).
- **Shape:** 16:9, 1920×1080. Keep the detail low in the middle, where the panels sit.

> Two rival teams preparing for a match in a huge futuristic arena: a violet team on the left led by
> Nova, a cyan team on the right led by Pulse, stretching and fist-bumping, confident looks across the
> arena floor, a glowing empty stage in the middle, holographic scoreboards without text, haze and spot
> lights, pre-match tension, STYLE, no text.

### 4. Victory: `brain-clash/victory.webp` (`victory`)

- **Used in:** the victory screen for the winners and everyone watching.
- **Shape:** 16:9, 1920×1080.

> Triumphant anime champions celebrating: Nova and Pulse jumping with fists raised beside a glowing
> golden trophy, confetti, beams of golden and violet light, joyful expressions, celebratory energy,
> STYLE, no text.

### 5. Defeat: `brain-clash/defeat.webp` (`defeat`)

- **Used in:** the result screen for the losing team.
- **Shape:** 16:9, 1920×1080.
- **Tone:** determined, not sad.

> Nova and Pulse after a hard-fought match, tasteful dramatic dusk-blue lighting, one wiping her brow
> with a determined smile, the other pulling his sweatband back on, ready for a rematch, soft rain of
> light particles, competitive but warm mood, STYLE, no text.

### 6. Beat Drop: `brain-clash/beat-drop.webp` (`beat-drop`)

- **Used in:** the Beat Drop banner, its game card and its room background.
- **Shape:** 16:9, 1920×1080. Keep the upper right calm for the countdown.

> DJ Ayo at a glowing DJ booth on a futuristic neon stage, Pulse beside him humming into a mic with
> eyes closed, powerful sound waves bursting outward as rings of light, equalizer light beams, crowd
> silhouettes, magenta and cyan stage lighting, cinematic motion blur, STYLE, no text.

### 7. Story Forge: `story-forge/story-forge.webp` (`story-forge`)

- **Used in:** the Story Forge banner, its game card and its room background.
- **Shape:** 16:9, 1920×1080.

> Zuri holding open a floating ancient storybook that glows gold, words of light rising from its pages
> like sparks, a fantasy landscape at night with a huge moon, misty mountains and a distant castle,
> mystery and adventure, teal and gold light, STYLE, no text.

### 8. Who's Talking?: `whos-talking/whos-talking.webp` (`whos-talking`)

- **Used in:** the Who's Talking? banner and game card.
- **Shape:** 16:9, 1920×1080.

> Nova singing into a glowing headset microphone, rings of sound rolling out from her voice, a mysterious
> second silhouette behind a holographic voice-print screen, pink and violet sky, STYLE, no text.

### 9. Game mode tiles: `game-modes/<name>.webp`

- **Used in:** the "how to play" tiles and category tiles on the Brain Clash, Beat Drop and Story
  Forge pages.
- **Shape:** 16:10, 1200×750. The bottom third sits under a dark fade with the title, so keep faces in
  the upper two thirds.

| Asset name | Prompt (then add STYLE, no text) |
|---|---|
| `african-knowledge` | Nova surrounded by floating holographic maps of Africa, glowing landmarks and data panels, studious and confident |
| `music-challenge` | A futuristic concert stage with sound waves as light, Pulse mid-performance, energetic spot lights |
| `culture-challenge` | Zuri and Nova in modern outfits inspired by West and East African textiles, festival lanterns, drums of light |
| `word-association` | Glowing words and symbols floating in the air connected by threads of light, Zuri linking two with a finger |
| `riddles` | A mysterious violet chamber of floating puzzle cubes and runes, Zuri studying a glowing riddle |
| `quick-fire` | Pulse sprinting through streaks of light past a giant glowing countdown ring, intense speed |
| `general-knowledge` | DJ Ayo reaching into a cloud of holographic knowledge cards, curious grin |
| `team-battle` | Two teams charging toward each other across a neon arena, violet versus cyan, dramatic perspective |
| `name-it-fast` | A captain racing to fill a glowing holographic list, ticks lighting up, a countdown ring behind |

### 9b. Category tiles: `categories/<id>.webp`

- **Used in:** the category tiles ("Sixteen ways to win", "Pick your playlist", "Choose your world") on
  the three game pages. Until a category has its image, its tile shows a drawn icon scene.
- **Shape:** 16:10, 1200×750. Keep the subject in the upper two thirds, because the title sits on a fade
  at the bottom.
- **Prompt:** take each line below and add "in the VOXPLAY style: STYLE, no text".

| Asset name | Prompt |
|---|---|
| `african_general` | A glowing holographic map of Africa with landmarks rising from it: pyramids, Kilimanjaro, baobabs |
| `nigerian_general` | Lagos skyline at dusk with Zuma Rock and green-white light trails |
| `african_music` | Talking drums, a kora and a glowing microphone on a neon stage |
| `nigerian_entertainment` | A red carpet with camera flashes, a star-lit stage and a film clapperboard |
| `african_history` | An ancient West African kingdom courtyard with a royal stool, bronze heads and scrolls, warm torchlight |
| `current_affairs` | Holographic news screens and a ballot box glowing in a futuristic newsroom |
| `african_football` | A football bursting into a goal net in a packed floodlit stadium, a trophy gleaming |
| `animals_nature` | A lion and an elephant on the savannah at golden hour under a glowing sky |
| `african_food` | A steaming pot of jollof rice, suya skewers and peppers, warm market light |
| `languages` | Speech bubbles in many scripts floating between two friends talking |
| `pidgin` | Friends laughing on a Lagos street corner, speech bubbles with emoji, warm evening light |
| `african_movies` | A cinema screen glowing in the dark, popcorn, film reels, a Nollywood-style dramatic scene |
| `riddles` | A mysterious violet chamber of floating puzzle cubes and question marks |
| `word_challenges` | Giant glowing letters tumbling through the air, a pencil and an open book |
| `everyday` | A cosy home desk with a lamp, a clock and floating light-bulb ideas |
| `funny` | Friends crying with laughter around a phone, confetti and comedy masks |
| `hum_afrobeats` | A DJ booth and dancing crowd at an Afrobeats party, neon pink and cyan |
| `hum_amapiano` | A log-drum and keyboard on a Johannesburg rooftop party at night, dancers |
| `hum_classics` | A vintage radio and a saxophone, retro highlife band silhouettes, sepia-gold light |
| `story_lagos` | A yellow danfo bus in Lagos traffic at sunset, an owambe party tent in the background |
| `story_legends` | A wise tortoise under a baobab tree beneath a giant moon, a talking drum beside it |
| `story_chaos` | A goat running through a wedding reception, guests shocked, cake flying |

### 10. Waiting and empty states: `states/<name>.webp`

- **Used in:** the loading screen ("Entering the room…" uses `searching`), the lobby waiting card
  (`waiting`) and the room-not-found page (`empty-room`). `creating-room`, `no-games` and
  `reconnecting` are ready for later screens.
- **Shape:** 4:3, 1000×750. Calmer and simpler than the scenes, with plenty of dark space.

| Asset name | Prompt (then add STYLE, simple composition, lots of dark space, no text) |
|---|---|
| `searching` | Nova scanning a holographic radar for players, soft violet glow |
| `waiting` | Pulse and DJ Ayo relaxing on the arena steps, checking their phones, waiting for friends |
| `empty-room` | An empty, softly lit futuristic arena, a single spotlight on the stage |
| `creating-room` | Zuri drawing a glowing doorway portal in the air with her finger |
| `no-games` | A quiet arena with the lights dimmed, holographic screens on standby |
| `reconnecting` | DJ Ayo plugging a glowing signal cable back in, sparks of cyan light |
| `coming-soon` | A mysterious new challenger in silhouette behind a sealed glowing gate (used for coming-soon games) |

### 11. Character portraits: `characters/<name>.webp` (`nova`, `pulse`, `zuri`, `ayo`)

- **Used in:** the "Meet your captains" section on the landing page. Zuri and DJ Ayo appear there once
  their portraits exist.
- **Shape:** 1:1, 1024×1024. Head and shoulders, eyes about 35% from the top.

> Portrait of [CHARACTER FROM TABLE], head and shoulders, three-quarter view, looking at the viewer with
> their signature expression, background a soft gradient in their colours, STYLE, no text.

### 12. Player avatars: `avatars/avatar-01.webp` … `avatar-12.webp`

- **Used in:** every player's avatar (lobby rosters, score lists), picked by name so each player keeps
  the same face. Until they exist, avatars show the player's initial.
- **Shape:** 1:1, 512×512 (saved at 256). The face is centred and fills about 60% of the frame, so it
  works in circles and squares.
- **Range:** twelve original gamers. Vary the skin tones (deep brown to light), hairstyles (braids, locs,
  afro, buzz cut, hijab, twists, bob, mohawk), accessories (visor, headphones, earrings, face paint,
  glasses) and expressions (smirk, laugh, focused, wink).

> Avatar portrait of an original young anime gamer, [VARIATION], centred head and shoulders, plain
> dark violet background, consistent framing, STYLE, no text.

## What the site does with them

- **Fit and loading:** each image fills its frame with `object-fit: cover`, at the focus point set in
  `frontend/lib/art.ts`. The frames have fixed shapes, so nothing jumps while an image loads. The hero
  loads first; everything else loads lazily.
- **Labels:** text over art (mode tiles, banners) sits on a dark fade or a solid glass panel, so it stays
  readable on any picture.
- **Phones:** get `voxplay-hero-mobile.webp` when it exists.
- **Reduced motion:** the animations (character idle, the VS intro slam, the hype bursts) switch off for
  people who choose reduced motion.
