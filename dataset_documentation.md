# SupeRR Selector Season 2 – Round 1: Dataset Documentation

## 1. Competition context

- **Competition:** SupeRR Selector Season 2 (organised by Rajasthan Royals), Round 1.
- **Task:** Build a data-driven system that measures how **batters and bowlers perform under high-pressure match situations** relative to their usual performance, then rank the **top 10 batters** and **top 10 bowlers** "under pressure".
- **"Pressure" is undefined by the organisers.** Participants must define it themselves (candidate signals: required run rate, wickets in hand, balls remaining, innings stage, closeness of contest, or a combination) and justify it.
- **Submission:** (1) two ranked top-10 lists chosen via Unstop dropdowns, (2) a methodology report covering pressure definition, performance metrics and baselines, fair comparison (sample size, eligibility, IPL vs T20I), evidence, and reliability/limitations.
- **Data scope:** Men's T20 cricket from 2022 onward: **IPL (2022–2026)** plus **T20 Internationals**, plus two minor T20 tournaments (Emerging Teams Asia Cup 2024, Asia Cup Rising Stars 2025).

## 2. File overview

| File | Rows | Cols | Grain (one row = …) | Role |
|---|---|---|---|---|
| `ball_by_ball.csv` | 200,999 | 33 | one delivery | Core fact table: what happened on every ball |
| `matches.csv` | 883 | 22 | one match | Match metadata: date, venue, toss, result, DLS |
| `competitions.csv` | 141 | 4 | one competition/series | Format (T20 vs T20I) and season |
| `teams.csv` | 353 | 3 | one (competition, team) | Which teams took part in each competition |
| `competition_team_player_mapping.csv` | 6,413 | 6 | one (competition, team, player) | Squad/roster of each team per competition |
| `playing_eleven.csv` | 28,381 | 9 | one (match, team, player) | Match-day squad incl. who actually played, batting order, impact sub |

### Relationship diagram (join keys)

```
competitions (comp_id)
   ├── teams (comp_id, team_id)
   ├── competition_team_player_mapping (comp_id, team_id, player_id)
   └── matches (comp_id → match_id)
            ├── ball_by_ball (match_id)
            └── playing_eleven (match_id, team_id, player_id)
```

- `ball_by_ball.match_id` → `matches.match_id` → `matches.comp_id` → `competitions.comp_id` (this is how you get **T20 (IPL) vs T20I** and **season** for each ball).
- `ball_by_ball.striker_id / non_striker_id / bowler_id / dismissed_player_id` → `player_id` in the mapping and playing-eleven files.
- `ball_by_ball.batting_team_id / bowling_team_id` → `team_id` (matches `teams.csv` and mapping).
- Integrity checks run: every `match_id` in ball-by-ball exists in matches; all 959 players in ball-by-ball exist in the mapping file; all team IDs in ball-by-ball exist in `teams.csv`; every match `comp_id` exists in competitions.

---

## 3. `ball_by_ball.csv` — 200,999 rows × 33 columns

**Purpose:** Delivery-level record of every ball. This is the primary source for building pressure situations (score, wickets, balls left, target) and for batter/bowler performance. Covers **867 matches** (of 883 in `matches.csv`; the 16 missing are all "Match Abandoned"), 885 distinct strikers, 646 distinct bowlers. About 94.7k balls are IPL/T20 and 106.3k are T20I.

| Column | Type | Description / notes |
|---|---|---|
| `match_id` | int | Match key → `matches.match_id` |
| `innings` | int | 1, 2 are normal innings. **3 and 4 are Super Over innings** (only 38 balls total across 6 matches, so exclude or handle separately) |
| `overid` | int | Over number, **1–20** (1-indexed) |
| `over_ball_num` | int | Ball sequence within the over, **1–13**. Goes above 6 because wides/no-balls are included as rows (so this counts all deliveries, not only legal ones) |
| `innings_ball_num` | int | Running delivery count in the innings (max 135 for innings 1, 136 for innings 2; includes illegal deliveries) |
| `batting_team_id`, `bowling_team_id` | int | Team keys → `teams.team_id` |
| `striker_id`, `striker_name` | int, str | Batter facing the ball |
| `non_striker_id`, `non_striker_name` | int, str | Batter at the other end |
| `bowler_id`, `bowler_name` | int, str | Bowler of the delivery |
| `batting_type` | str | Striker's handedness: `RHB` / `LHB` |
| `bowling_type` | str | 12 categories, e.g. Right-arm Leg-Break, Right-arm medium-fast, Slow left-arm orthodox, Left-arm Chinaman |
| `batting_order` | int | Striker's position in the batting order (1–13) |
| `runs` | int | **Runs off the bat** (0–6; note 5 is rare). See data notes below: this does **not** appear to include extras |
| `is_four`, `is_six` | bool | Boundary flags (consistent with `runs == 4` / `runs == 6` ~99.99% of the time) |
| `is_wicket` | bool | Wicket fell on this delivery (10,881 wickets) |
| `dismissal_type_id`, `dismissal_type` | float, str | Null if no wicket. Types: Caught (7,557), Bowled (1,775), LBW (709), RunOut (600), Stump (214), Hit Wicket (17), Retire Out (6), Obstructing the field (3, spelled two ways: "Obstracting"/"Obstructing") |
| `dismissed_player_id` | float | Who got out. Striker ~97.5% of the time, non-striker ~2.5% (run-outs). Has 11 more non-null values than `is_wicket` has True (12 rows where it is set but `is_wicket` is False, with no dismissal type) |
| `extras_type` | str | Null for normal balls. Values: `wide` (7,714), `legbyes` (2,748), `Overstep` (no-ball, 576), `byes` (529), `other` (264), `Penalty` (1) |
| `extras1_runs` | int | **Behaves as a code for the extras type, not a run count** (none=6, wide=2, legbyes=3, Overstep=1, byes=4, other=5, Penalty=7). Do not sum it as runs |
| `extras_2_runs` | int | Additional runs on extras deliveries (0, 1 or 4). Mostly 0; non-zero mainly on `Overstep`/`other` |
| `pace_or_spin` | str | `Pace` (123,886) / `Spin` (77,113) |
| `bowl_speed` | float | km/h, but **38.7% of rows are 0** (not recorded) and non-zero values include clear outliers (max 1456.1, min 1.32). Treat as unreliable |
| `stroke` | str | Shot played (30 types, e.g. Pull shot, Cover Drive, Worked, Flick). 6,158 nulls, mostly wides/misses |
| `delivery_style` | str | 34 types, e.g. Seamed In, Orthodox, Leg Break, Off Cutter, Inswing. 391 nulls |
| `over_or_around` | str | Bowling over/around the wicket. 407 nulls |
| `on_or_off` | str | Off-side / On-side line |
| `delivery_ist_time` | str | Timestamp of the delivery (UTC string, e.g. `2022-01-23 02:08:52 UTC`). Despite the "ist" name it is labelled UTC. Many early rows have a placeholder `00:00:00` time |

### Data notes and pitfalls for `ball_by_ball.csv`

1. **`runs` is bat runs only.** For wides, byes and leg-byes, `runs` is 0 (leg-byes/byes have `runs` = 0 and the actual number of byes/leg-byes does not appear to be stored anywhere). For `Overstep`/`other`, `runs` holds runs scored off the bat and the extra run(s) are in `extras_2_runs` or implied.
2. **Total team score cannot be reconstructed exactly.** A test using `runs + 1 per wide/no-ball + extras_2_runs` matched the official winning margin exactly for only ~12% of "won by N runs" matches (median error 0, but spread is large, std ≈ 6.7 runs). Byes and leg-bye runs are the likely missing part. For pressure metrics (required run rate, runs needed), expect approximate scores and consider this a stated limitation.
3. **Legal balls ≠ rows.** 192,709 of 200,999 rows are legal deliveries. Exclude `wide` and `Overstep` rows when counting balls faced/bowled and balls remaining. (Wides are not faced by the batter; no-balls are not counted as legal.)
4. **Super Overs (innings 3 and 4)** are tiny (38 balls) and not comparable with normal innings. Exclude from pressure modelling or treat separately.
5. **DLS/shortened matches** exist (see `matches.csv`). Over counts there are not 20.
6. `bowl_speed`, `stroke`, `delivery_style`, `over_or_around` have gaps or noise. Likely not needed for a pressure model.
7. Some matches have as few as 2 rows (abandoned/curtailed). Mean is ~232 rows per match.

---

## 4. `matches.csv` — 883 rows × 22 columns

**Purpose:** One row per match. Gives context (date, venue, stage, toss, result, DLS) and the link to competition. Match date range **2022-01-22 → 2026-11-01**. 482 matches are T20I, 401 are T20 (mainly IPL).

| Column | Type | Description / notes |
|---|---|---|
| `match_id` | int | Primary key |
| `comp_id` | int | → `competitions.comp_id` |
| `match_number` | int | Match number within the competition (1–75) |
| `match_date` | str | `YYYY-MM-DD` |
| `stage` | str | League (620), Others (226, used for bilateral T20I series), Final (12), Qualifier (10), Super 4 (6), Eliminator (5), Semi Final (4) |
| `venue_id` | int | 98 venues (names not provided) |
| `venue_country` | str | 17 countries (India 425 matches, UAE 69, New Zealand 52, UK 49, West Indies 44, Zimbabwe 38, …) |
| `home_team_id`, `home_team` | int, str | Home side (36 teams) |
| `away_team_id`, `away_team` | int, str | Away side |
| `home_team_captain_id`, `away_team_captain_id` | float | Player IDs; ~45 nulls each. All non-null IDs exist in the mapping file |
| `toss_win_team_id` | float | 15 nulls |
| `toss_opted` | str | `Fielding` (639) / `Batting` (229); 15 nulls |
| `man_of_the_match` | int | Player ID; **0 = none awarded/unknown (119 matches)** |
| `first_inn_revised_overs`, `second_inn_revised_overs` | float | Only filled for rain-affected (DLS) matches (~25 rows non-null) |
| `revised_target` | float | DLS-revised target; non-null in 23 matches |
| `knock_out` | int | 1 for knockout matches (31), else 0 |
| `win_team_id` | float | Winner; 41 nulls (No Result 21, Abandoned 19, Tied 1) |
| `result` | str | Free text like `India Won by 61 runs` / `Zimbabwe Won by 3 wickets`. Capitalisation of "won" is inconsistent (`won` vs `Won`). Parse with a case-insensitive regex |

**Gotchas:** 16 matches (all "Match Abandoned") have no ball-by-ball rows; 3 matches have no playing-eleven rows. `result` text gives the winning margin, which is handy for checking reconstructed scores. Note `revised_target` shows DLS-adjusted chases where required-rate calculations need the revised target and overs.

---

## 5. `competitions.csv` — 141 rows × 4 columns

**Purpose:** Lookup that tells you the **format** and **season** of each competition. This is what lets you separate IPL (club T20) from T20I (international) for fair comparison across the two contexts.

| Column | Type | Description |
|---|---|---|
| `comp_id` | int | Primary key |
| `comp_name` | str | e.g. `IPL 2024`, `India in Zimbabwe T20I Series 2026` |
| `match_format` | str | `T20I` (134 competitions) or `T20` (7: IPL 2022–2026, Mens T20 Emerging Teams Asia Cup 2024, Asia Cup Rising Stars 2025) |
| `season` | str | Mostly a year (2022, 2023, 2024, 2025, 2026). A few cross-year values: `2022/23` (3), `2023/24` (1), `2024/25` (1) |

**Gotchas:** `season` is a string, not an int. 3 competitions have no matches in `matches.csv` (Afghanistan v Sri Lanka T20I Series 2026, UAE in Nepal T20I Series 2026, India in Bangladesh T20I Series 2025). IPL competitions: comp_ids 1358 (2022), 1715 (2023), 2193 (2024), 2725 (2025), 3298 (2026).

---

## 6. `teams.csv` — 353 rows × 3 columns

**Purpose:** Which teams participated in which competition (a competition ↔ team bridge with names).

| Column | Type | Description |
|---|---|---|
| `comp_id` | int | → `competitions.comp_id` |
| `team_id` | int | Team key |
| `team_name` | str | 38 distinct teams: national sides (England, India, West Indies, Australia …) and the 10 IPL franchises (Chennai Super Kings, Delhi Capitals, Gujarat Titans, Kolkata Knight Riders, Lucknow Super Giants, Mumbai Indians, Punjab Kings, Rajasthan Royals, Royal Challengers Bengaluru, Sunrisers Hyderabad) |

Typically 2 rows per competition (bilateral series), up to 10 for IPL. Team names are consistent between this file, `matches.csv` and the mapping file.

---

## 7. `competition_team_player_mapping.csv` — 6,413 rows × 6 columns

**Purpose:** The squad list. For each competition, which players belonged to which team. This is the **player master** (ID ↔ name) and lets you attribute a player to a team and tournament, for example to check which IPL team a player was in, or whether a player has both IPL and T20I experience.

| Column | Type | Description |
|---|---|---|
| `comp_id`, `comp_name` | int, str | Competition (140 distinct) |
| `team_id`, `team_name` | int, str | Team (38 distinct) |
| `player_id`, `player_name` | int, str | 1,217 player IDs / 1,210 distinct names |

**Gotchas:** There are **1,217 IDs but 1,210 names**, so a few names are shared by different players. Always join on `player_id`, never on name. Each `player_id` maps to exactly one name. No duplicate rows. All 959 players who appear in `ball_by_ball.csv` are present here. No role (batter/bowler/all-rounder/keeper) column is provided; derive roles from ball-by-ball and playing-eleven data.

---

## 8. `playing_eleven.csv` — 28,381 rows × 9 columns

**Purpose:** Match-day squad per team: who was named, who actually played, batting position, captain, wicket-keeper, and Impact Player substitutions (IPL rule). Useful for role identification (e.g. wicket-keepers), batting-order context, and checking eligibility or appearances.

| Column | Type | Description |
|---|---|---|
| `match_id` | int | → `matches.match_id` (880 matches covered; 3 matches missing) |
| `team_id` | int | Team |
| `player_id` | int | Player (1,082 distinct) |
| `batting_order` | float | 1–13. **Null for every player who did not play** (and 11 who played but never batted/have no order) |
| `is_played` | bool | **True (19,714) = in the playing XI/impact player who took part; False (8,667) = named in squad but did not play** |
| `is_captain` | object (bool) | Null for non-players (8,667 nulls), True/False otherwise |
| `is_wk` | object (bool) | Wicket-keeper flag, same null pattern |
| `is_impact` | int | 1 (558 rows) = came in as Impact Player substitute |
| `is_impact_off` | int | 1 = was replaced by an Impact Player. Impact fields are IPL-specific. Note: in this data `is_impact` and `is_impact_off` rows are distinct sets (they agree on 96% of rows only because most are 0) |

**Gotchas:** Filter on `is_played == True` before counting appearances (~11–12 players per team per match; 12 happens with impact subs). Squad rows with `is_played == False` are bench players. `is_captain` / `is_wk` are stored as object dtype with NaN, so cast carefully.

---

## 9. Suggested analysis hooks (not part of the data, just orientation)

- **Pressure features available from ball-by-ball + matches:** innings, over (`overid`), wickets fallen (cumulative `is_wicket`), balls remaining (via legal-ball count), target (1st-innings total + 1, or `revised_target`), required run rate, current run rate, `knock_out`/`stage` (match importance), batting position, partnership state via `non_striker_id`, bowler `pace_or_spin`/`bowling_type` matchups.
- **Baselines:** each player's overall (non-pressure) strike rate, average, economy, wicket rate, computed from the same file, so pressure vs. normal performance can be compared per player.
- **IPL vs T20I:** use `competitions.match_format` (T20 vs T20I). Scoring environments differ (IPL generally higher scoring, with impact player), so normalise within format or competition.
- **Sample size:** use `playing_eleven.is_played` and ball counts to set minimum-exposure thresholds.

## 10. Quick-reference data-quality checklist

- Join players by `player_id`, never by name (name collisions exist).
- `runs` excludes extras; `extras1_runs` is a type code, not runs.
- Exclude `wide`/`Overstep` rows when counting legal balls; exclude innings 3 and 4 (Super Overs).
- Total scores are only approximately reconstructable (byes/leg-bye runs are missing).
- `bowl_speed` is 0 in ~39% of rows and has absurd outliers. Ignore or clean.
- `man_of_the_match == 0` means no award recorded.
- 16 abandoned matches have no ball-by-ball data; 41 matches have no winner (no result/abandoned/tied).
- DLS-affected matches (23 with `revised_target`) need revised overs/target.
- The data runs through **2026-11-01**, so IPL 2026 is included.
