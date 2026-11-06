# mod-nat-pagle

**Fishing dailies from Nat Pagle** for AzerothCore (3.3.5a), with a reputation to earn along the
way, in the spirit of Mists of Pandaria's Anglers. It also opens the
[Stranglethorn fishing contest](#the-stranglethorn-fishing-contest) to more than one winner.

Nat Pagle, on his isle off Dustwallow Marsh, hands out one fishing daily a day for each part of
the world you can reach. Each one sends you to fish in a particular zone for something that only
bites while you have the quest. Hand it in for a treasure bag and reputation with **The Anglers**,
and spend that reputation on Nat's wares.

## The dailies

Three pools, each offering one of its dailies a day, picked anew at the daily reset (the way Old
Man Barlo's and Marcia Chase's dailies rotate):

| Pool | Level | Zones | Reward |
|---|---|---|---|
| Azeroth | 35 | Dustwallow Marsh, Stranglethorn Vale, Swamp of Sorrows, Feralas, Tanaris, Azshara | Nat's Tackle Box |
| Outland | 58 | Zangarmarsh, Hellfire Peninsula, Nagrand, Terokkar Forest | Bag of Fishing Treasures (Old Man Barlo's) |
| Northrend | 68 | Borean Tundra, Howling Fjord, Grizzly Hills, Dragonblight, Sholazar Basin | Bag of Fishing Treasures (Marcia Chase's) |

Each daily needs Fishing and gives 500 reputation with The Anglers (before your server's
reputation rates). The catch is a quest item that comes up from open water anywhere in its zone,
not from fishing pools.

Nat's Tackle Box holds 2-5 gold, a lure, sometimes a Big-mouth Clam and, rarely, Nat Pagle's
Extreme Angler FC-5000, the Lucky Fishing Hat or Nat Pagle's Extreme Anglin' Boots.

### With mod-individual-progression

The Outland pool shows only from progression state 8 (rewarded quest 66008) and the Northrend
pool from state 13 (66013), so a character sees one daily a day for each era they have reached.
The same gates hold back the Weather-Beaten Fishing Hat and Nat's Lucky Fishing Pole. Without
that module the two quests don't exist, the core skips the conditions that name them (with an
error line in the log at startup), and all three pools and both items are open to everyone.

## The Anglers

A new reputation under Classic in the reputation pane. Nat sells by rank:

| Rank | Wares |
|---|---|
| Friendly | Aquadynamic Fish Attractor, Bright Baubles, High Test Eternium Fishing Line |
| Honored | Lucky Fishing Hat, Nat Pagle's Extreme Anglin' Boots, Nat Pagle's Extreme Angler FC-5000 |
| Revered | Weather-Beaten Fishing Hat (progression 8), Nat's Lucky Fishing Pole (progression 13), Fishy, Tiny Goldfish |
| Exalted | Arcanite Fishing Pole, Azure Water Strider |

Fishy, Tiny Goldfish and the Azure Water Strider are items of
[mod-retail-collection](https://github.com/buildthehomelab/wow-mod-retail-collection) (400449,
410847, 410652); Nat only sells them when the server has them at the moment this module's SQL
is applied, so install mod-retail-collection first. Those three and Nat's Lucky Fishing Pole have
no price: the reputation is what they cost. Items you haven't the rank for don't show, so when
his shop opens Nat lists in chat your Anglers rank and what each higher rank adds, as item links
(`NatPagle.ShopUnlocks`). A ware that also waits on a progression tier is left out until you have
the tier. Nat keeps his stock Mudskunk Lure.

## Account wallet coins

With [mod-boss-coins](https://github.com/buildthehomelab/wow-mod-boss-coins) built into the same
server, each daily also adds `NatPagle.Coins` (1 by default) to the account wallet. Without it the
module builds and works the same, minus the coins.

## The Stranglethorn fishing contest

The stock contest ends with the first turn-in: one character a week becomes Master Angler. Here
every character who brings Riggle Bassbait 40 Speckled Tastyfish during the turn-ins wins, once a
week. Each winner gets:

- 1 Extravagant Extravaganza Coin
- a choice of the Arcanite Fishing Pole, the Hook of the Master Angler or 2 more coins (the pole is
  unique, so a repeat winner picks one of the others)
- the quest's stock money, which scales with level, and 500 reputation with The Anglers before your
  server's rates

The first winner of the week also gets `NatPagle.Derby.FirstPlaceCoins` (2), and the second and
third `NatPagle.Derby.RunnerUpCoins` (1). Riggle announces those three. The win still counts for
Master Angler of Azeroth.

Jang buys 5 Tastyfish at a time during the turn-ins at his stock price, whether or not anyone has
won yet.

The coins buy these from Riggle during the contest and from Nat Pagle all week:

| Coins | Item | With mod-individual-progression |
|---|---|---|
| 8 | Surfer Shoes: use to walk on water for 10 minutes, any damage cancels it | |
| 3 | Hook of the Master Angler: use to turn into a fish, breathe underwater and swim faster | |
| 3 | Toothy's Bucket | from progression state 8 |
| 3 | Snarly's Bucket | from progression state 8 |
| 4 | Boots of the Bay: +15 Fishing, use to teleport to Booty Bay | from progression state 13 |

Without that module the gates' quests don't exist and all five are open to everyone.

## Install

```bash
cd azerothcore/modules
git clone https://github.com/buildthehomelab/wow-mod-nat-pagle.git mod-nat-pagle
```

Clone it as `mod-nat-pagle`: AzerothCore names the loader after the folder. Rebuild, copy
`conf/mod_nat_pagle.conf.dist` to your config folder, and start the server. The SQL in
`data/sql` is applied automatically.

### Client patch

The client needs what the server can't send it: The Anglers in its `Faction.dbc` (or the reputation
pane and the quest rewards show no faction), the new items in its `Item.dbc` (or they show a
question mark icon), the Surfer Shoes' spell in its `Spell.dbc` and the coin prices in its
`ItemExtendedCost.dbc` (or the vendor window shows no price and the client refuses to buy).
`tools/build_patch.py` adds them all to the patch that carries your realm's `Item.dbc`:

```bash
python3 tools/build_patch.py --patch patch-Z.MPQ --client /path/to/client --out patch-Z-new.MPQ
```

A patch MPQ replaces whole files, so the tool adds the rows to the patch's own copies and copies
every other file unchanged. When the patch doesn't have one of those files yet, the client's own is
the base (`--client`, its newest enUS locale patch). Old rows keep their order. Running it again on
its own output changes nothing. It needs Python 3 and [StormLib](https://github.com/ladislav-zezula/StormLib)
(`STORMLIB`, default `/usr/local/lib/libstorm.dylib`).

The world SQL is generated by the same tool, from the same data, so the server and the client
agree: change the dailies, the wares or the faction in `tools/build_patch.py`, then

```bash
python3 tools/build_patch.py --sql data/sql/db-world/mod_nat_pagle_world.sql
```

## Uninstall

Remove the module folder, rebuild, then run `data/sql/uninstall/mod_nat_pagle_uninstall_world.sql`
on the world database and `mod_nat_pagle_uninstall_characters.sql` on the characters database.
The client patch rows do no harm left in place.

## IDs

| What | IDs |
|---|---|
| item_template | 9503700 Nat's Tackle Box, 9503701-9503715 the catches, 9503720 Extravagant Extravaganza Coin, 9503721 Surfer Shoes (9503700-9503799 reserved) |
| quest_template | 9503701-9503715 (each daily shares its catch's id); stock 8193 and 8194 are edited |
| pool_template | 9503700 Azeroth, 9503701 Outland, 9503702 Northrend |
| faction_dbc / Faction.dbc | 1170 The Anglers, reputation index 107, under 1118 Classic |
| creature_template | 12919 Nat Pagle (stock) gets ScriptName `npc_nat_pagle`; 15077 Riggle Bassbait (stock) gets `npc_riggle_derby` and the vendor flag |
| gossip_menu_option | 6445 Nat Pagle (stock) gets option 1, "Let me browse your goods." |
| spell_dbc / Spell.dbc | 90470 Surfing |
| itemextendedcost_dbc / ItemExtendedCost.dbc | 90434-90436 the coin prices |
| npc_text | 9503720 |
| creature_text | 15077 Riggle Bassbait, groups 3 and 4 |

## License

MIT, see [LICENSE](LICENSE).
