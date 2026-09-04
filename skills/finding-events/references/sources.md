# sources.md — where events actually live

**Load before:** running searches.

## Contents

- §1 How to use this file
- §2 The three layers, and why the good result is usually in layer 2
- §3 General listings
- §4 Community and niche
- §5 Film and film-making
- §6 Neurodivergent, accessible, sober and quiet
- §7 Dating and social
- §8 Query patterns that work
- §9 What does not work

---

## 1. How to use this file

This is a **map for building queries**, not a directory to read out. Platforms change, listings
move, and a name here is a starting point to search — never a citation. If you name a source to
the user, you have checked it exists and has current listings.

Nothing in this file is time-stamped, so treat every platform name as "was worth trying" rather
than "is currently the best". If a search returns a strong source not listed here, use it and say
where it came from.

## 2. The three layers, and why the good result is usually in layer 2

| Layer | What it is | Good for | Weak at |
|---|---|---|---|
| **Listings** | Ticketing and what's-on aggregators | Volume, dates, prices, breadth | Niche interests; anything free or informal |
| **Community** | Groups that meet regularly and announce to members | Niche interests, small events, recurring things, people who will still be there next month | Discovery — often invisible to general search |
| **Niche** | The place a specific scene organises: a cinema, a union, a subreddit, a Discord | Precisely the thing asked for | Coverage; you have to know it exists |

For a broad ask ("what's on this weekend"), layer 1 carries it. For anything specific —
film-making, a particular board game, a support-shaped social — **layer 1 will return near-nothing
useful and layer 2 will carry it**. Search all three regardless; the failure mode is stopping at
layer 1 and reporting that there is nothing on.

## 3. General listings

Ticketing and aggregation, broadly national with strong city coverage:

- **Eventbrite** — the widest net for workshops, classes and small events. `site:eventbrite.co.uk`
- **Meetup** — recurring groups more than one-off events. Strong for hobbies and skills
- **Luma (lu.ma)** — increasingly where tech, creative and community events are hosted
- **Dice**, **Skiddle**, **Fatsoma**, **Resident Advisor** — music and nightlife leaning
- **Facebook Events** — still where a lot of informal and community events live, poorly indexed
- **Time Out** and equivalent city magazines — editorial what's-on, good for breadth
- **Design My Night** — venue-led listings

City-specific editorial (London examples; find the local equivalent elsewhere): *Secret London*,
*London on the Inside*, and borough or council what's-on pages, which carry free and community
events the commercial platforms miss entirely.

## 4. Community and niche

Where layer 2 lives, and how to reach it by search:

- **Meetup groups** rather than Meetup events — a group page shows the next several dates
- **Discord and Slack communities** — usually found via a subreddit or a group's website, not directly
- **Subreddits** for the city and for the interest; `site:reddit.com {city} {interest}` finds the
  recurring "what's on" and "anyone going to" threads
- **Library, museum, community centre and council** programmes — free, well-run, badly listed
- **Universities and adult education** — public lectures and short courses, often open to all
- **Independent venues' own mailing lists and websites** — the event exists before it reaches a
  ticketing platform, and sometimes never reaches one

## 5. Film and film-making

Separate the two, because they need different sources.

**Watching** — independent and repertory cinemas run the interesting programmes: seasons, Q&As,
double bills, restorations. In London that means the BFI, the Prince Charles Cinema, the Rio, the
Genesis, Close-Up, and the Picturehouse and Curzon chains. Elsewhere, search
`independent cinema {city}` and `repertory OR arthouse cinema {city} what's on`. Festivals run
year-round and are worth a separate query: `{city} film festival {month year}`.

**Making** — a different world, and the one people usually mean by "film-making":

- Screenings with filmmaker Q&As, which are where people actually meet
- Short film nights and open-submission screenings — search `short film night {city}`,
  `filmmaker meetup {city}`, `screenwriters group {city}`
- Crew and collaboration boards — search `find crew {city} short film`, and the UK-facing
  production-community sites
- Film bodies and regional screen agencies run workshops and networking; search
  `film {city OR region} workshop networking`
- Equipment hire houses and post-production facilities run free talks to get people through the door

The distinction matters: someone asking about film-making usually wants **people**, not a screen.

## 6. Neurodivergent, accessible, sober and quiet

The single most important thing here: **these events are rarely tagged as such on general
platforms.** Searching Eventbrite for "neurodivergent" finds events *about* neurodivergence, not
events that happen to be suitable. Both are worth returning, and they are different answers.

**Explicitly neurodivergent-led or -friendly:**
- Search `autistic led {city}`, `ADHD social {city}`, `neurodivergent friendly {interest} {city}`
- Charities and peer-led organisations run regular socials that never reach ticketing platforms
- Relaxed and sensory-friendly performances: most large venues and cinema chains run these, listed
  under "relaxed", "autism-friendly" or "sensory adapted" rather than under accessibility

**Suitable without being labelled** — often the better answer. Look for the structural features
rather than the label: capped numbers, a stated agenda and end time, seated, daytime, an activity
to focus on rather than open mingling, and somewhere quiet to withdraw to. A 15-person board games
afternoon is frequently a better result than an event with "neurodivergent" in the title.

**Physical access:** user-contributed access reviews (Euan's Guide is the established UK one) beat
venue self-description, which is routinely optimistic. For music and live events, Attitude is
Everything publishes venue access information. Always prefer a specific claim — "step-free entrance,
accessible toilet on the ground floor" — over the word "accessible".

**Sober:** search `alcohol free {interest} {city}`, `sober social {city}`, `daytime {interest}
{city}`. Activity-led and daytime events are structurally sober whether or not they say so.

## 7. Dating and social

- Structured singles events (speed dating, curated dinners, activity-based) are on Eventbrite,
  Fatsoma and Design My Night, plus their own sites
- Dinner-with-strangers formats — search `dinner with strangers {city}`, `supper club singles {city}`
- Activity-first socials — running, climbing, board games, life drawing — where meeting people is
  the side effect. Often a better answer than an explicit dating event, and worth offering
- Interest-community socials for a named identity or community; search the community's own
  organisations rather than the platforms

Check the age bracket, the format, and whether the numbers are balanced or capped — all three are
usually stated, and all three change whether it is worth going.

## 8. Query patterns that work

```
{interest} events {city} {month year}
"{interest}" {city} tickets
{city} what's on {daterange}
{interest} meetup {city}
{interest} group {city} monthly
{interest} {city} site:eventbrite.co.uk
{interest} {city} site:meetup.com
{interest} {city} site:lu.ma
site:reddit.com {city} {interest} events
neurodivergent friendly {interest} {city}
relaxed OR quiet OR "sensory friendly" {interest} {city}
step free access {venue name}
free {interest} events {city} {daterange}
```

`scripts/plan_queries.py` builds most of these with the dates already resolved. Run it rather than
assembling queries by hand.

## 9. What does not work

- **Asking a search engine "what's on this weekend"** without a place — returns aggregator SEO pages
- **Trusting a snippet's date.** Search snippets cache old dates constantly. §vetting covers this
- **Aggregator round-up articles** ("50 things to do in London") — mostly stale, mostly ranking bait.
  Occasionally a lead worth chasing to the organiser's page; never a result in themselves
- **Stopping at layer 1** for a niche interest and concluding nothing is on
- **Searching only the city name** for somewhere large. London events are found by area — search the
  neighbourhood as well as the city
