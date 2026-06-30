# Dota 2 GSI message format reference

Source sample: `dist/logs/gsi_session_20260626_121409.jsonl`

This document records the GSI payload shape observed in the sample session. The
sample contains 5 JSON Lines frames, written about once per game minute by the
current logger. Treat fields below as observed reference data, not as Valve's
complete public schema. Blocks enabled in `gamestate_integration_gsi_config.cfg`
but not present in this sample, such as `teams` and `allplayers`, should be
handled as optional.

## Top-level shape

Each line is one complete JSON object.

| Field | Type | Observed | Meaning |
| --- | --- | ---: | --- |
| `provider` | object | 5/5 | Game/application metadata. |
| `map` | object | 5/5 | Match clock, score, state and map-level data. |
| `player` | object | 5/5 | Local player's account and economy/stat data. |
| `hero` | object | 5/5 | Local player's selected hero state. |
| `abilities` | object | 5/5 | Local hero abilities keyed as `abilityN`. |
| `items` | object | 5/5 | Inventory, stash, teleport and neutral item slots. |
| `draft` | object | 5/5 | Empty in this sample. |
| `buildings` | object | 5/5 | Visible/reported building health by side and building id. |
| `minimap` | object | 5/5 | Dynamic minimap objects keyed as `oN`. |
| `previously` | object | 5/5 | Delta block containing previous values for changed fields. |
| `added` | object | 4/5 | Delta block marking newly added nested fields/objects. |

## `provider`

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `name` | string | `Dota 2` | Provider name. |
| `appid` | int | `570` | Steam app id. |
| `version` | int | `48` | GSI protocol/provider version observed. |
| `timestamp` | int | `1782447249` | Unix timestamp from Dota 2 payload. |

## `map`

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `name` | string | `start` | Map name/state label observed. |
| `matchid` | string | `0` | Match id. Bot/local games can report `0`. |
| `game_time` | int | `125` | Dota internal game time; includes pre-game offset in this sample. |
| `clock_time` | int | `0` | Display/game clock in seconds. Current code uses this as primary game time. |
| `daytime` | bool | `true` | Day/night state. |
| `nightstalker_night` | bool | `false` | Special night state. |
| `radiant_score` | int | `5` | Radiant kills. Used for enemy death vs miss detection. |
| `dire_score` | int | `1` | Dire kills. Used for enemy death vs miss detection. |
| `game_state` | string | `DOTA_GAMERULES_STATE_GAME_IN_PROGRESS` | Game state enum string. |
| `paused` | bool | `false` | Pause state. |
| `win_team` | string | `none` | Winning team once game ends. |
| `customgamename` | string | empty string | Custom game name, empty here. |
| `ward_purchase_cooldown` | int | `45` | Observer ward purchase cooldown. |

Observed frame clock pairs: `(clock_time, game_time)` =
`(0,125)`, `(60,184)`, `(121,245)`, `(181,305)`, `(241,365)`.

## `player`

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `steamid` | string | `76561198072071107` | Steam ID as string. |
| `accountid` | string | `111805379` | Dota account id as string. |
| `name` | string | player display name | May contain non-ASCII text. |
| `activity` | string | `playing` | Player activity. |
| `team_name` | string | `radiant` | `radiant` or `dire`; current vision tracker uses this first. |
| `player_slot` | int | `0` | Player slot id. |
| `team_slot` | int | `0` | Slot within team. |
| `kills` | int | `0` | Local player kills. |
| `deaths` | int | `0` | Local player deaths. |
| `assists` | int | `0` | Local player assists. |
| `last_hits` | int | `7` | Last hits. |
| `denies` | int | `0` | Denies. |
| `kill_streak` | int | `0` | Current kill streak. |
| `commands_issued` | int | `112` | Issued command count. |
| `kill_list` | object | `{}` | Per-victim kill counts; empty here. |
| `gold` | int | `776` | Total current gold. |
| `gold_reliable` | int | `443` | Reliable gold. |
| `gold_unreliable` | int | `333` | Unreliable gold. |
| `gold_from_hero_kills` | int | `0` | Economy source counter. |
| `gold_from_creep_kills` | int | `283` | Economy source counter. |
| `gold_from_summon_kills` | int | `0` | Economy source counter. |
| `gold_from_income` | int | `363` | Passive income counter. |
| `gold_from_shared` | int | `0` | Shared gold counter. |
| `gpm` | int | `180` | Gold per minute. |
| `xpm` | int | `401` | XP per minute. |

## `hero`

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `id` | int | `128` | Hero numeric id. |
| `name` | string | `npc_dota_hero_snapfire` | Internal hero name. |
| `facet` | int | `0` | Selected facet id observed. |
| `xpos`, `ypos` | int | `-977`, `-1090` | World/map coordinates. |
| `level` | int | `4` | Hero level. |
| `xp` | int | `1617` | Current XP. |
| `alive` | bool | `true` | Current code suppresses timer speech while dead. |
| `respawn_seconds` | int | `0` | Remaining respawn time. |
| `buyback_cost` | int | `302` | Current buyback cost. |
| `buyback_cooldown` | int | `0` | Buyback cooldown seconds. |
| `health`, `max_health` | int | `868`, `868` | Health values. |
| `health_percent` | int | `100` | Health percentage. |
| `mana`, `max_mana` | int | `435`, `435` | Mana values. |
| `mana_percent` | int | `100` | Mana percentage. |
| `silenced` | bool | `false` | Status flag. |
| `stunned` | bool | `false` | Status flag. |
| `disarmed` | bool | `false` | Status flag. |
| `magicimmune` | bool | `false` | Status flag. |
| `hexed` | bool | `false` | Status flag. |
| `muted` | bool | `false` | Status flag. |
| `break` | bool | `false` | Break status flag. |
| `aghanims_scepter` | bool | `false` | Scepter owned/active flag. |
| `aghanims_shard` | bool | `false` | Shard owned flag. |
| `smoked` | bool | `false` | Smoke state. |
| `permanent_buffs` | object | `{}` | Empty in this sample. |
| `has_debuff` | bool | `false` | Any debuff flag. |
| `talent_1` ... `talent_8` | bool | `false` | Talent selection flags. |
| `attributes_level` | int | `0` | Attribute bonus level. |

## `abilities`

Dynamic keys are `ability0` through `ability4` in this sample. Each ability
object has the same shape:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `name` | string | `snapfire_scatterblast` | Ability internal name. |
| `level` | int | `2` | Ability level. |
| `can_cast` | bool | `true` | Whether it can currently be cast. |
| `passive` | bool | `false` | Passive ability flag. |
| `ability_active` | bool | `true` | Active/enabled flag. |
| `cooldown` | int | `0` | Remaining cooldown. |
| `max_cooldown` | int | `15` | Max/current cooldown duration. |
| `ultimate` | bool | `false` | Ultimate flag. |

## `items`

Observed item keys:

- Inventory: `slot0` through `slot8`
- Stash: `stash0` through `stash5`
- Teleport: `teleport0`
- Neutral items: `neutral0`, `neutral1`
- Preserved neutral choices: `preserved_neutral6` through `preserved_neutral10`

Occupied item slots contain:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `name` | string | `item_tango` | `empty` means no item in the slot. |
| `purchaser` | int | `0` | Purchaser slot/player id. Missing for empty slots. |
| `item_level` | int | `1` | Neutral/item tier-like value observed. Missing for empty slots. |
| `can_cast` | bool | `true` | Usability flag. Missing for empty slots. |
| `cooldown` | int | `0` | Remaining cooldown. Missing for empty slots. |
| `max_cooldown` | int | `0` | Max/current cooldown duration. Missing for empty slots. |
| `passive` | bool | `false` | Passive flag. Missing for empty slots. |
| `item_charges` | int | `3` | Charge count as reported by item block. Missing for empty slots. |
| `charges` | int | `3` | Charge count duplicate/alternate field. Missing for empty slots. |

Empty slots only had:

| Field | Type | Example |
| --- | --- | --- |
| `name` | string | `empty` |

## `buildings`

Observed top-level side key: `radiant`. Other sessions may include `dire` or
both sides, so code should not hard-code this sample's side set.

Building keys are Dota building ids, for example:

- `dota_goodguys_tower1_top`
- `dota_goodguys_tower2_mid`
- `dota_goodguys_tower4_bot`
- `good_rax_melee_top`
- `good_rax_range_bot`
- `dota_goodguys_fort`

Each building object contains:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `health` | int | `1800` | Current health. |
| `max_health` | int | `1800` | Max health. |

## `minimap`

`minimap` is an object keyed by transient object ids such as `o0`, `o98`,
`o141`. These keys are not stable semantic identifiers; use object fields such
as `image`, `team`, `unitname` and `name` to classify entries.

Every observed minimap object had:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `xpos` | int | `-6589` | World/map x coordinate. |
| `ypos` | int | `-4206` | World/map y coordinate. |
| `image` | string | `minimap_enemyicon` | Minimap icon type. Useful for classification. |
| `team` | int | `2` | Team id. Observed: `2`, `3`, `4`, `5`. |
| `yaw` | int | `270` | Facing angle. Can be negative in sample deltas/current data. |
| `unitname` | string | `npc_dota_hero_viper` | Unit internal name; can be empty. |
| `visionrange` | int | `1800` | Vision radius. |

Hero minimap objects additionally had:

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `name` | string | `npc_dota_hero_viper` | Present on observed hero icons. Current code falls back to `unitname`. |

Observed team ids:

| Team id | Meaning in current code/sample |
| ---: | --- |
| `2` | Radiant |
| `3` | Dire |
| `4` | Neutral/special map objects in sample |
| `5` | Neutral/shop/watcher-like map objects in sample |

Observed `image` values include:

| Image | Count in sample | Typical object |
| --- | ---: | --- |
| `minimap_herocircle_self` | 5 | Local hero. |
| `minimap_herocircle` | 20 | Allied hero. |
| `minimap_enemyicon` | 22 | Visible enemy hero. |
| `minimap_creep` | 188 | Lane creeps. |
| `minimap_courier`, `minimap_courier_flying` | 5 | Courier. |
| `minimap_tower90`, `minimap_tower45` | 110 | Towers. |
| `minimap_racks90`, `minimap_racks45` | 60 | Barracks. |
| `minimap_ancient` | 10 | Ancient. |
| `minimap_ward_obs` | 15 | Fountain/observer ward icons in sample. |
| `minimap_watcher` | 50 | Watchers. |
| `minimap_lotuspool` | 10 | Lotus pools. |
| `minimap_underlord_portal` | 10 | Twin gates. |
| `minimap_shop`, `minimap_secretshop` | 20 | Shops. |
| `minimap_miscbuilding` | 80 | Misc buildings/watch towers/fillers. |
| `minimap_plaincircle` | 85 | Generic special objects, pets, thinkers, empty unit names, etc. |

Hero detection rule used by `src/vision_tracker.py`:

- Hero icons are entries whose `image` contains `herocircle` or equals
  `minimap_enemyicon`.
- Hero name is `name` first, then `unitname`.
- Valid hero names start with `npc_dota_hero_`.
- Enemy team is the opposite of `player.team_name` (`2` radiant, `3` dire).

## `previously` and `added`

Dota GSI includes delta helper blocks alongside the full current state:

| Block | Observed | Meaning |
| --- | ---: | --- |
| `previously` | 5/5 | Contains previous values for fields that changed since the prior GSI payload. |
| `added` | 4/5 | Marks newly added nested fields or objects. Values can be `true` or nested objects. |

Observed `previously` child blocks:

- `map`
- `player`
- `hero`
- `items`
- `buildings`
- `minimap`

Observed `added` child block:

- `minimap`

Development guidance:

- Prefer the main blocks (`map`, `hero`, `minimap`, etc.) for current state.
- Use `previously` only when you need exact before/after transitions from the
  raw GSI payload.
- Do not assume `previously` mirrors the complete schema. It only contains
  changed fields.
- Do not assume `added` exists on every frame.

## Fields used by this project

Current modules depend on these fields most directly:

| Code area | Fields |
| --- | --- |
| Session detection | `map.game_state`, `map.clock_time` |
| Session logging cadence | `map.clock_time` |
| Vision tracking | `minimap`, `player.team_name`, `map.radiant_score`, `map.dire_score` |
| Hero classification | `minimap.oN.image`, `minimap.oN.team`, `minimap.oN.name`, `minimap.oN.unitname`, `minimap.oN.xpos`, `minimap.oN.ypos` |
| Resource timer alerts | `map.clock_time`, `hero.alive` |
| Night alert | `map.daytime` |
| AI advisor input | Full frame payload |

## Robust parsing recommendations

- Treat every top-level block as optional except when the calling feature
  explicitly requires it.
- Treat `minimap.oN` keys as frame-local and unstable; never persist behavior by
  `oN` alone.
- For item slots, check `name == "empty"` before reading cooldown, charge or
  purchaser fields.
- For `buildings`, iterate side keys and building ids dynamically.
- For score-based logic, compare `radiant_score`/`dire_score` with the prior
  frame and tolerate missing values by defaulting to `0`.
- Prefer `map.clock_time` for user-facing game clock logic in this project;
  `map.game_time` may include pre-game offset.
- Preserve UTF-8 when reading/writing frames; player names can contain Chinese
  or other non-ASCII characters.
