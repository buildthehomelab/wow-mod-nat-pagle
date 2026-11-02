#!/usr/bin/env python3
"""mod-nat-pagle's data: Nat Pagle's fishing dailies, the Anglers reputation, what Nat sells and the
Stranglethorn fishing contest, written out as the module's world SQL and as the rows your client's
spell patch needs.

    python3 build_patch.py --sql ../data/sql/db-world/mod_nat_pagle_world.sql
    python3 build_patch.py --patch patch-z80-spells-and-items.MPQ --client /path/to/client \\
        --out patch-new.MPQ

Everything is defined once, below, so the server and the client can't disagree.

The dailies come in three pools, one per era, and each pool offers one of its dailies a day
(pool_template max_limit 1, the same way Old Man Barlo's and Marcia Chase's dailies rotate).
With mod-individual-progression the Outland pool needs progression state 8 (rewarded quest
66008) and the Northrend pool state 13 (66013), so a character sees one daily a day per era they
have reached. Without that module those quests don't exist, the core skips the conditions that
name them, and all three pools are open. Each daily asks for fish (or junk) that only bites in one zone while the quest is
in your log (fishing_loot_template rows with QuestRequired, on the zone and on each of its areas
that has a fishing table of its own, because the core looks at the area first).

Rewards: Nat's Tackle Box (Azeroth), Old Man Barlo's Bag of Fishing Treasures (Outland) or
Marcia Chase's (Northrend), and reputation with The Anglers, a new faction under Classic. The
module's C++ adds coins to mod-boss-coins' account wallet when that module is built in too.

The Stranglethorn fishing contest keeps its stock quests and NPCs. Master Angler (8193) becomes a
weekly quest open to everyone with 40 Speckled Tastyfish, and pays an Extravagant Extravaganza
Coin on top of a choice of the stock prizes or two more coins. Riggle Bassbait and Nat Pagle sell
what the coins buy (SHOP). src/NatPagleDerby.cpp replaces Riggle's stock script.

--patch is the patch that carries your realm's Item.dbc. A patch MPQ replaces whole files, so the
new rows go into its copies of Item.dbc (the new items, so they have their icons), Faction.dbc
(The Anglers), Spell.dbc (the Surfer Shoes' spell) and ItemExtendedCost.dbc (the coin prices);
every other file is copied unchanged. When the patch doesn't have one of those files yet, the
client's own (--client, newest enUS locale patch) is the base. New rows go in by id and old rows
keep their order. Running it again on its own output changes nothing.
Needs Python 3 and StormLib (`STORMLIB`, default /usr/local/lib/libstorm.dylib).
"""

import argparse
import ctypes
import os
import struct
import sys
import tempfile

NAT_PAGLE = 12919                   # creature_template, stock: his isle off Dustwallow Marsh
TACKLE_BOX = 9503700
POOL_AZEROTH, POOL_OUTLAND, POOL_NORTHREND = 9503700, 9503701, 9503702
FIRST_ID, LAST_ID = 9503700, 9503799

FACTION = 1170
FACTION_REP_INDEX = 107
FACTION_PARENT = 1118               # the "Classic" header
FACTION_FLAGS = 0x10                # peace forced, like the Thorium Brotherhood
FACTION_NAME = "The Anglers"
FACTION_DESCRIPTION = ("Nat Pagle and the anglers who wander from one fishing spot to the next. They "
                       "have no hall and no banner, only a love of quiet water and a good catch.")
ALL_RACES = 1791
REP_PER_DAILY = 500

IP_OUTLAND, IP_NORTHREND = 66008, 66013   # mod-individual-progression's state quests
QUEST_FLAGS_DAILY = 0x1000
QUEST_SORT_FISHING = -101
SKILL_FISHING = 356
BARLO_BAG, MARCIA_BAG = 34863, 46007

RANK_FRIENDLY, RANK_HONORED, RANK_REVERED, RANK_EXALTED = 4, 5, 6, 7

# Each era: pool, lowest level, reward item, the progression quest it needs (None: always).
ERAS = {
    "azeroth": (POOL_AZEROTH, 35, TACKLE_BOX, None),
    "outland": (POOL_OUTLAND, 58, BARLO_BAG, IP_OUTLAND),
    "northrend": (POOL_NORTHREND, 68, MARCIA_BAG, IP_NORTHREND),
}

# The zones' fishing tables: the zone and every area in it with a table of its own (stock AC).
WATERS = {
    "Dustwallow Marsh": [15, 513, 516, 517, 518, 2079, 4047],
    "Stranglethorn Vale": [33, 35, 43, 104, 117, 122, 297, 301, 302, 311, 312, 1577, 1578, 1739, 2339, 3357],
    "Swamp of Sorrows": [8, 300, 1797, 2403],
    "Feralas": [357, 1108, 1112, 2521],
    "Tanaris": [440],
    "Azshara": [16, 1222, 1226, 1227, 1228, 1229, 1230, 1231, 1256, 3140],
    "Zangarmarsh": [3521],
    "Hellfire Peninsula": [3483],
    "Nagrand": [3518, 3614, 3621, 3625],
    "Terokkar Forest": [3519, 3684, 3690, 3691, 3859],
    "Borean Tundra": [3537, 4039, 4043, 4109, 4134],
    "Howling Fjord": [495, 3980, 3982, 3994, 3999, 4001, 4002, 4055, 4058, 4059, 4071, 4263, 4479],
    "Sholazar Basin": [3711, 4290],
    "Grizzly Hills": [394, 4212, 4242, 4244],
    "Dragonblight": [65, 4152, 4157, 4181, 4185, 4224, 4225, 4241, 4478],
}

# The dailies. The quest and its item share an id. `chance`: percent of casts in the zone that
# bring one up while the quest needs more.
DAILIES = [
    dict(id=9503701, era="azeroth", zone="Dustwallow Marsh", title="Mudfish Mayhem",
         item="Marsh Mudfish", count=6, display=24701, chance=40,
         text="The mudfish around this isle have gotten bold. Bold and tasty.$b$bCast anywhere in the "
              "waters of Dustwallow Marsh and bring me six Marsh Mudfish. I'd do it myself, but I'm busy. "
              "Resting your eyes is a kind of fishing too, $N.",
         request="Back already? Let's see the haul.",
         reward="Now those are mudfish. Here, take this. Some old tackle I don't use."),
    dict(id=9503702, era="azeroth", zone="Stranglethorn Vale", title="Fin Soup",
         item="Reef Shark Fin", count=4, display=6697, chance=35,
         text="Booty Bay pays good coin for shark fin soup, and I pay good coin for not having to row to "
              "Stranglethorn.$b$bFish the coast of Stranglethorn Vale and bring me four Reef Shark Fins. The "
              "sharks bite through the line more often than not, so the fin is usually all you get. Suits me.",
         request="Smells like Booty Bay. Did you get them?",
         reward="Four fins, and you've still got all your fingers. Good work."),
    dict(id=9503703, era="azeroth", zone="Swamp of Sorrows", title="Sorriest Bait in the World",
         item="Sorrowmoss Eel", count=5, display=24522, chance=35,
         text="The eels in the Swamp of Sorrows are the sorriest-looking things you've ever seen, and the "
              "best bait there is for a Dustwallow snapper.$b$bBring me five Sorrowmoss Eels from the swamp's "
              "waters. Keep them wet. They sulk when they dry out.",
         request="Are they still wriggling?",
         reward="Look at those faces. A snapper won't be able to resist."),
    dict(id=9503704, era="azeroth", zone="Feralas", title="Glimmerfin by Moonlight",
         item="Feathermoon Glimmerfin", count=5, display=24716, chance=35,
         text="There's a fish in Feralas that shines like a lantern under the moon. The night elves at "
              "Feathermoon call it glimmerfin.$b$bFish the rivers and the coast of Feralas and bring me five. "
              "I want to see if they glow in a bucket too.",
         request="Did you find the glowing ones?",
         reward="They do glow! Well, a little. Don't tell anyone I got excited."),
    dict(id=9503705, era="azeroth", zone="Tanaris", title="The Goblin's Bet",
         item="Steamwheedle Swordfish", count=1, display=32261, chance=20,
         text="A goblin in Gadgetzan swears he hooked a swordfish off the Tanaris coast as long as his "
              "boat. I bet him ten gold he's lying.$b$bProve me wrong. Fish the waters of Tanaris and bring "
              "me a Steamwheedle Swordfish. If I'm going to lose the bet, I want to see the fish.",
         request="Well? Is the goblin a liar or not?",
         reward="Huh. Not as long as a boat, but long enough. I owe a goblin ten gold. Take this before I "
                "change my mind."),
    dict(id=9503706, era="azeroth", zone="Azshara", title="Highborne Trinkets",
         item="Tarnished Highborne Trinket", count=3, display=58621, chance=30,
         text="The bays of Azshara are full of what the Highborne dropped when their city went under: "
              "rings, bangles, little silver fish charms. Anglers hook them all the time.$b$bBring me three. "
              "None of them are worth anything, but I like collecting them.",
         request="Got anything shiny for me?",
         reward="Oh, this one has a fish on it. I'm keeping that one."),
    dict(id=9503707, era="outland", zone="Zangarmarsh", title="Sporefish Surprise",
         item="Glowing Sporefish", count=6, display=38901, chance=40,
         text="Over in Outland there's a marsh full of giant mushrooms, and the fish there eat the "
              "spores.$b$bFish the waters of Zangarmarsh and bring me six Glowing Sporefish. The Sporeggar "
              "say they're good eating. The Sporeggar also eat dirt, so I'd like to judge for myself.",
         request="Do they still glow?",
         reward="Smells like a cave. Tastes... also like a cave. Thanks anyway."),
    dict(id=9503708, era="outland", zone="Hellfire Peninsula", title="Fel-Scorched Crawdads",
         item="Fel-Scorched Crawdad", count=5, display=24629, chance=35,
         text="Nothing should live in the water on Hellfire Peninsula. The crawdads didn't get the "
              "message.$b$bBring me five Fel-Scorched Crawdads from Hellfire's pools. Use gloves.",
         request="Did you use gloves?",
         reward="They're warm. Why are they warm? Never mind. Here's your pay."),
    dict(id=9503709, era="outland", zone="Nagrand", title="The Crystalfin",
         item="Oshu'gun Crystalfin", count=1, display=38897, chance=20,
         text="The Kurenai say a fish lives in the lakes of Nagrand whose scales are as clear as the "
              "crystals of Oshu'gun.$b$bOne would do. Fish the lakes of Nagrand and bring me an Oshu'gun "
              "Crystalfin.",
         request="Any luck in Nagrand?",
         reward="You can see right through it. That's the finest fish I've seen in years."),
    dict(id=9503710, era="outland", zone="Terokkar Forest", title="Spirit-Touched Bluefish",
         item="Spirit-Touched Bluefish", count=5, display=24713, chance=35,
         text="My old friend Barlo fishes the lakes of Terokkar and won't stop talking about the "
              "bluefish there. Something about the spirits in the water.$b$bBring me five Spirit-Touched "
              "Bluefish from Terokkar Forest. I'd like to know what he's on about.",
         request="Did Barlo see you? Don't tell him they're for me.",
         reward="They're... ordinary bluefish. Barlo's been out in the sun too long."),
    dict(id=9503711, era="northrend", zone="Borean Tundra", title="Borean Ice Cod",
         item="Borean Ice Cod", count=6, display=53173, chance=40,
         text="Cod from the Borean Tundra keeps for a month without salt. It's frozen before it leaves "
              "the water.$b$bBring me six Borean Ice Cod from the tundra's waters. I'm stocking up for the "
              "winter, whenever that is in Dustwallow.",
         request="Still frozen?",
         reward="Cold as a lich's heart. Perfect."),
    dict(id=9503712, era="northrend", zone="Howling Fjord", title="Hookjaws of the Fjord",
         item="Fjord Hookjaw", count=5, display=53171, chance=35,
         text="The vrykul in the Howling Fjord fish for hookjaws with spears. I fish for them with a "
              "chair and a nap. You'll do it with a pole.$b$bBring me five Fjord Hookjaws from the Howling "
              "Fjord.",
         request="The vrykul didn't give you trouble, I hope.",
         reward="Look at those jaws. No wonder the vrykul use spears."),
    dict(id=9503713, era="northrend", zone="Grizzly Hills", title="Rainbow Trout",
         item="Grizzly Hills Rainbow Trout", count=5, display=1208, chance=35,
         text="The rivers of the Grizzly Hills run so clear you can watch the trout ignore your bait.$b$b"
              "Bring me five Grizzly Hills Rainbow Trout. Watch out for the bears. They fish too, and they "
              "don't like to share.",
         request="Any trouble with the bears?",
         reward="Every colour of the rainbow. Some of them twice."),
    dict(id=9503714, era="northrend", zone="Dragonblight", title="The Wyrmrest Snapper",
         item="Wyrmrest Snapper", count=1, display=51803, chance=20,
         text="The dragons of Wyrmrest Temple have a taste for one fish, and they don't share it.$b$b"
              "Fish the waters of Dragonblight and bring me a Wyrmrest Snapper before they eat them all.",
         request="Did a dragon follow you here?",
         reward="If a dragon comes looking for this, you never saw me."),
    dict(id=9503715, era="northrend", zone="Sholazar Basin", title="Sholazar Glimmerscale",
         item="Sholazar Glimmerscale", count=5, display=53172, chance=35,
         text="The Sholazar Basin is warm in the middle of Northrend, and the fish there have colours "
              "nobody has names for.$b$bBring me five Sholazar Glimmerscales. I want to paint one.",
         request="Did you bring my colours?",
         reward="Beautiful. I'll never be able to paint that. Here, you earned this."),
]

# What Nat sells: (item, lowest Anglers rank, progression quest or None). Stock items; the
# retail ones are only added when the server has them (mod-retail-collection).
VENDOR = [
    (6533, RANK_FRIENDLY, None),           # Aquadynamic Fish Attractor
    (6532, RANK_FRIENDLY, None),           # Bright Baubles
    (19971, RANK_FRIENDLY, None),          # High Test Eternium Fishing Line
    (19972, RANK_HONORED, None),           # Lucky Fishing Hat
    (19969, RANK_HONORED, None),           # Nat Pagle's Extreme Anglin' Boots
    (19022, RANK_HONORED, None),           # Nat Pagle's Extreme Angler FC-5000
    (33820, RANK_REVERED, IP_OUTLAND),     # Weather-Beaten Fishing Hat
    (45858, RANK_REVERED, IP_NORTHREND),   # Nat's Lucky Fishing Pole
    (410847, RANK_REVERED, None),          # Fishy (mod-retail-collection)
    (410652, RANK_REVERED, None),          # Tiny Goldfish (mod-retail-collection)
    (19970, RANK_EXALTED, None),           # Arcanite Fishing Pole
    (400449, RANK_EXALTED, None),          # Azure Water Strider (mod-retail-collection)
]

# Nat's Tackle Box: (item, chance, group, min, max). Group 1 hands out one lure.
TACKLE_BOX_LOOT = [
    (6533, 35, 1, 1, 2),        # Aquadynamic Fish Attractor
    (6532, 35, 1, 1, 2),        # Bright Baubles
    (7307, 15, 1, 2, 3),        # Flesh Eating Worm
    (6811, 15, 1, 1, 1),        # Aquadynamic Fish Lens
    (7973, 20, 0, 1, 2),        # Big-mouth Clam
    (19022, 2, 0, 1, 1),        # Nat Pagle's Extreme Angler FC-5000
    (19972, 1, 0, 1, 1),        # Lucky Fishing Hat
    (19969, 1, 0, 1, 1),        # Nat Pagle's Extreme Anglin' Boots
]

ITEM_CLASS_ARMOR, ITEM_CLASS_QUEST, ITEM_CLASS_MISC = 4, 12, 15
ITEM_SUBCLASS_CLOTH = 1
INVTYPE_FEET = 8
BONDING_PICKUP, BONDING_QUEST = 1, 4
TACKLE_BOX_DISPLAY, TACKLE_BOX_MATERIAL = 9822, 2     # the Waterlogged Crate's
ITEM_FLAG_HAS_LOOT = 0x4

# The Stranglethorn fishing contest. The creature_text, npc_text and quest ids are stock unless
# they fall in this module's range.
RIGGLE = 15077
QUEST_MASTER_ANGLER, QUEST_APPRENTICE_ANGLER = 8193, 8194
QUEST_FLAGS_WEEKLY = 0x8000
NPC_FLAG_VENDOR = 0x80
WORLD_STATE_HAS_WINNER = 198       # the stock script's; only quest 8194 reads it
DERBY_COIN, SURFER_SHOES = 9503720, 9503721
COIN_DISPLAY, COIN_MATERIAL = 55217, 4                # the Dalaran fountain's gold coins
SHOES_DISPLAY, SHOES_MATERIAL = 63888, 7              # Boots of the Bay's
TEXT_MORE_WINNERS = 9503720
SURF_SPELL = 90470
WINNER_REP = 500
TIME_TURN_INS = "before 5pm"

# What the coins buy, from Riggle on contest days and from Nat all week:
# (item, coins, progression quest or None).
SHOP = [
    (SURFER_SHOES, 8, None),
    (19979, 3, None),               # Hook of the Master Angler
    (50287, 4, IP_NORTHREND),       # Boots of the Bay
    (33816, 3, IP_OUTLAND),         # Toothy's Bucket
    (35349, 3, IP_OUTLAND),         # Snarly's Bucket
]
# ItemExtendedCost ids, one per price.
COSTS = {3: 90434, 4: 90435, 8: 90436}
NAT_SHOP_FIRST_SLOT = 21            # after his reputation wares

MASTER_ANGLER_TEXT = (
    "Today between 2pm and 4pm schools of Tastyfish will appear along the coast of Stranglethorn. Bring me 40 "
    "Speckled Tastyfish %s and you are a Master Angler! Everyone who makes it wins a prize, and the first three "
    "get extra Extravagant Extravaganza Coins on top.$b$bOne win a week, friend. If you can't reach 40, my "
    "apprentice here will still pay you for each 5 Tastyfish you bring her.$b$bOh, and don't delay, Tastyfish "
    "go bad quickly!" % TIME_TURN_INS)
APPRENTICE_TEXT = "Forty is a lot of fish. I will buy your Tastyfish from you at a reasonable price, five at a time. Whadda ya say!"
MORE_WINNERS_TEXT = (
    "We have our first Master Angler this week, but this contest has room for more! Bring me 40 Speckled Tastyfish "
    "%s and you win a prize too.$B$BCoins burning a hole in your pocket? Have a look at what I've got." % TIME_TURN_INS)
SAY_SECOND = "$n takes SECOND PLACE! Keep those Tastyfish coming, there is a prize for every Master Angler!"
SAY_THIRD = "$n takes THIRD PLACE! The podium is full, but there is still a prize for every Master Angler!"

SURF_NAME = "Surfing"
SURF_DESCRIPTION = "Allows you to walk across water for $d.  Any damage will cancel the effect."
SURF_AURA = "Walking on water."

# Spell.dbc: the fields the Surfer Shoes' spell sets. Shaman's Water Walking (546), cast on yourself,
# with nothing to pay, in any form and on a mount. Stock Water Walking from an elixir (11319) would
# take the guardian elixir slot.
F_ATTRIBUTES, F_CAST_TIME, F_AURA_INTERRUPT, F_PROC_CHANCE, F_DURATION, F_RANGE = 4, 28, 32, 35, 40, 46
F_EQUIPPED_CLASS, F_EFFECT, F_DIE_SIDES, F_BASE_POINTS, F_TARGET_A, F_AURA = 68, 71, 74, 80, 86, 95
F_VISUAL, F_ICON = 131, 133
F_NAME, F_NAME_MASK, F_RANK_MASK, F_DESCRIPTION, F_DESCRIPTION_MASK, F_AURA_TEXT, F_AURA_TEXT_MASK = 136, 152, 169, 170, 186, 187, 203
F_GCD_CATEGORY, F_GCD, F_DAMAGE_CLASS, F_PREVENTION, F_MULTIPLIER, F_SCHOOL_MASK = 205, 206, 213, 214, 216, 225
SPELL_FIELDS = 234
SPELL_ATTR0_ALLOW_WHILE_MOUNTED = 0x01000000
AURA_INTERRUPT_TAKE_DAMAGE = 0x2
SPELL_EFFECT_APPLY_AURA, TARGET_UNIT_CASTER, SPELL_AURA_WATER_WALK = 6, 1, 104
FLOAT_ONE = 0x3F800000
SPELL_STRING_FIELDS = set(range(136, 152)) | set(range(153, 169)) | set(range(170, 186)) | set(range(187, 203))
SPELL_FLOAT_FIELDS = {47, 77, 78, 79, 101, 102, 103, 119, 120, 121, 216, 217, 218, 229, 230, 231}
# Plain `int` columns of AC's spell_dbc; every other integer column is unsigned.
SPELL_SIGNED_FIELDS = {0, 13, 15, 41, *range(52, 71), 74, 75, 76, 80, 81, 82, *range(110, 116), 224, 228}


def surf_spell_row():
    """The spell's row with its text fields still zero: the callers add the strings."""
    row = [0] * SPELL_FIELDS
    row[0] = SURF_SPELL
    row[F_ATTRIBUTES] = SPELL_ATTR0_ALLOW_WHILE_MOUNTED
    row[F_CAST_TIME] = 1
    row[F_AURA_INTERRUPT] = AURA_INTERRUPT_TAKE_DAMAGE
    row[F_PROC_CHANCE] = 101
    row[F_DURATION] = 6                 # ten minutes, like 546
    row[F_RANGE] = 1                    # self
    row[F_EQUIPPED_CLASS] = 0xFFFFFFFF
    row[F_EFFECT] = SPELL_EFFECT_APPLY_AURA
    row[F_DIE_SIDES] = 1
    row[F_BASE_POINTS] = 0xFFFFFFFF
    row[F_TARGET_A] = TARGET_UNIT_CASTER
    row[F_AURA] = SPELL_AURA_WATER_WALK
    row[F_VISUAL], row[F_ICON] = 4483, 101
    row[F_NAME_MASK] = NAME_MASK
    row[F_RANK_MASK] = 16712172
    row[F_DESCRIPTION_MASK] = row[F_AURA_TEXT_MASK] = 16712188
    row[F_GCD_CATEGORY], row[F_GCD] = 133, 1500
    row[F_DAMAGE_CLASS], row[F_PREVENTION] = 1, 1
    row[F_MULTIPLIER:F_MULTIPLIER + 3] = [FLOAT_ONE] * 3
    row[F_SCHOOL_MASK] = 8              # nature
    return row


# Item.dbc rows: (id, class, subclass, material, display, inventory type, sheath).
def item_rows():
    rows = [(TACKLE_BOX, ITEM_CLASS_MISC, 0, TACKLE_BOX_MATERIAL, TACKLE_BOX_DISPLAY, 0, 0)]
    rows += [(d["id"], ITEM_CLASS_QUEST, 0, -1, d["display"], 0, 0) for d in DAILIES]
    rows.append((DERBY_COIN, ITEM_CLASS_MISC, 0, COIN_MATERIAL, COIN_DISPLAY, 0, 0))
    rows.append((SURFER_SHOES, ITEM_CLASS_ARMOR, ITEM_SUBCLASS_CLOTH, SHOES_MATERIAL, SHOES_DISPLAY, INVTYPE_FEET, 0))
    return rows


# --- DBC ---------------------------------------------------------------------------------------

def read_dbc(path):
    data = open(path, "rb").read()
    magic, count, fields, size, strsize = struct.unpack_from("<4s4I", data, 0)
    if magic != b"WDBC" or size != fields * 4:
        sys.exit("%s isn't a plain WDBC file" % path)
    rows = [list(struct.unpack_from("<%dI" % fields, data, 20 + i * size)) for i in range(count)]
    strings = bytearray(data[20 + count * size:20 + count * size + strsize])
    return rows, strings, fields


def write_dbc(path, rows, strings, fields):
    with open(path, "wb") as f:
        f.write(struct.pack("<4s4I", b"WDBC", len(rows), fields, fields * 4, len(strings)))
        for r in rows:
            f.write(struct.pack("<%dI" % fields, *r))
        f.write(strings)


def put_rows(rows, new):
    """The rows with `new` in place of rows of the same id, the rest in id order among them. The
    old rows keep their order: the client reads some DBCs in file order, so re-sorting one can
    break it."""
    by_id = {r[0]: r for r in new}
    rows = [by_id.pop(r[0], r) for r in rows]
    for row in sorted(by_id.values(), key=lambda r: r[0]):
        at = len(rows)
        while at > 0 and rows[at - 1][0] > row[0]:
            at -= 1
        rows.insert(at, row)
    return rows


def string_at(strings, at):
    return strings[at:strings.index(b"\0", at)].decode("utf-8")


def add_string(strings, text):
    """Offset of text in the string block, appended unless it is already there as a whole string."""
    raw = text.encode("utf-8") + b"\0"
    at = strings.find(b"\0" + raw)
    if at >= 0:
        return at + 1
    at = len(strings)
    strings.extend(raw)
    return at


# --- MPQ ---------------------------------------------------------------------------------------

def stormlib():
    lib = ctypes.CDLL(os.environ.get("STORMLIB", "/usr/local/lib/libstorm.dylib"))
    H = ctypes.c_void_p
    lib.SFileOpenArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(H)]
    lib.SFileExtractFile.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    lib.SFileFindFirstFile.argtypes = [H, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]
    lib.SFileFindFirstFile.restype = H
    lib.SFileFindNextFile.argtypes = [H, ctypes.c_void_p]
    lib.SFileFindClose.argtypes = [H]
    lib.SFileCreateArchive.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(H)]
    lib.SFileAddFileEx.argtypes = [H, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    lib.SFileCloseArchive.argtypes = [H]
    for fn in (lib.SFileOpenArchive, lib.SFileExtractFile, lib.SFileFindNextFile, lib.SFileFindClose,
               lib.SFileCreateArchive, lib.SFileAddFileEx, lib.SFileCloseArchive):
        fn.restype = ctypes.c_bool
    return lib, H


def unpack(mpq, folder):
    """Extracts every file; returns {archive name: local path}."""
    lib, H = stormlib()
    h = H()
    if not lib.SFileOpenArchive(mpq.encode(), 0, 0x100, ctypes.byref(h)):
        sys.exit("can't open " + mpq)
    names = []
    found = ctypes.create_string_buffer(2048)  # SFILE_FIND_DATA starts with the name (1024 bytes)
    find = lib.SFileFindFirstFile(h, b"*", found, None)
    while find:
        name = found.value.decode("latin-1")
        if name not in ("(listfile)", "(attributes)", "(signature)"):
            names.append(name)
        if not lib.SFileFindNextFile(find, found):
            lib.SFileFindClose(find)
            break
    files = {}
    for i, name in enumerate(names):
        local = os.path.join(folder, "%05d" % i)
        if not lib.SFileExtractFile(h, name.encode("latin-1"), local.encode(), 0):
            sys.exit("can't extract %s from %s" % (name, mpq))
        files[name] = local
    lib.SFileCloseArchive(h)
    if not files:
        sys.exit("%s has no files (or no listfile)" % mpq)
    return files


def pack(out, files):
    """files: [(local path, archive name)]. zlib-compressed, with listfile and attributes."""
    lib, H = stormlib()
    if os.path.exists(out):
        os.remove(out)
    h = H()
    if not lib.SFileCreateArchive(out.encode(), 0x00300000, max(64, len(files) * 2), ctypes.byref(h)):
        sys.exit("can't create " + out)
    for src, name in files:
        if not lib.SFileAddFileEx(h, src.encode(), name.encode("latin-1"), 0x80000200, 0x02, 0x02):
            lib.SFileCloseArchive(h)
            os.remove(out)
            sys.exit("can't add " + name)
    if not lib.SFileCloseArchive(h):
        os.remove(out)
        sys.exit("can't finish " + out)


LOCALE_MPQS = ["patch-enUS-3.MPQ", "patch-enUS-2.MPQ", "patch-enUS.MPQ", "locale-enUS.MPQ"]


def client_dbc(client, name, out):
    """The client's own copy of a DBC: from its newest enUS locale patch."""
    lib, H = stormlib()
    for mpq in LOCALE_MPQS:
        archive = os.path.join(client, "Data", "enUS", mpq)
        if not os.path.exists(archive):
            continue
        h = H()
        if not lib.SFileOpenArchive(archive.encode(), 0, 0x100, ctypes.byref(h)):
            continue
        ok = lib.SFileExtractFile(h, ("DBFilesClient\\%s" % name).encode(), out.encode(), 0)
        lib.SFileCloseArchive(h)
        if ok:
            return out
    sys.exit("no %s in %s/Data/enUS" % (name, client))


# --- the client rows ---------------------------------------------------------------------------

def patch_items(path):
    rows, strings, fields = read_dbc(path)
    if fields != 8:
        sys.exit("Item.dbc has %d fields, not 8" % fields)
    new = [[i, cls, sub, 0xFFFFFFFF, material & 0xFFFFFFFF, display, inv, sheath]
           for i, cls, sub, material, display, inv, sheath in item_rows()]
    write_dbc(path, put_rows(rows, new), strings, fields)
    print("Item.dbc: %d rows (%d-%d)" % (len(new), new[0][0], new[-1][0]))


FACTION_FIELDS = 57
NAME_MASK = 0xFF01FE


def patch_faction(path):
    rows, strings, fields = read_dbc(path)
    if fields != FACTION_FIELDS:
        sys.exit("Faction.dbc has %d fields, not %d" % (fields, FACTION_FIELDS))
    old = next((r for r in rows if r[0] == FACTION), None)
    if old and string_at(strings, old[23]) != FACTION_NAME:
        sys.exit("Faction.dbc row %d is taken by %r" % (FACTION, string_at(strings, old[23])))
    taken = [r[0] for r in rows if r[1] == FACTION_REP_INDEX and r[0] != FACTION]
    if taken:
        sys.exit("Faction.dbc reputation index %d is taken by faction %d" % (FACTION_REP_INDEX, taken[0]))
    if not any(r[0] == FACTION_PARENT for r in rows):
        sys.exit("Faction.dbc has no parent %d" % FACTION_PARENT)
    row = [0] * FACTION_FIELDS
    row[0], row[1] = FACTION, FACTION_REP_INDEX
    row[2] = ALL_RACES
    row[14] = FACTION_FLAGS
    row[18] = FACTION_PARENT
    row[21], row[22] = 5, 5     # like the stock factions
    row[23] = add_string(strings, FACTION_NAME)
    row[39] = NAME_MASK
    row[40] = add_string(strings, FACTION_DESCRIPTION)
    row[56] = NAME_MASK
    write_dbc(path, put_rows(rows, [row]), strings, fields)
    print("Faction.dbc %d %s" % (FACTION, FACTION_NAME))


def patch_spell(path):
    rows, strings, fields = read_dbc(path)
    if fields != SPELL_FIELDS:
        sys.exit("Spell.dbc has %d fields, not %d" % (fields, SPELL_FIELDS))
    old = next((r for r in rows if r[0] == SURF_SPELL), None)
    if old and string_at(strings, old[F_NAME]) != SURF_NAME:
        sys.exit("Spell.dbc row %d is taken by %r" % (SURF_SPELL, string_at(strings, old[F_NAME])))
    row = surf_spell_row()
    row[F_NAME] = add_string(strings, SURF_NAME)
    row[F_DESCRIPTION] = add_string(strings, SURF_DESCRIPTION)
    row[F_AURA_TEXT] = add_string(strings, SURF_AURA)
    write_dbc(path, put_rows(rows, [row]), strings, fields)
    print("Spell.dbc %d %s" % (SURF_SPELL, SURF_NAME))


COST_FIELDS, COST_ITEM, COST_COUNT = 16, 4, 9


def patch_costs(path):
    rows, strings, fields = read_dbc(path)
    if fields != COST_FIELDS:
        sys.exit("ItemExtendedCost.dbc has %d fields, not %d" % (fields, COST_FIELDS))
    new = []
    for coins, cost in sorted(COSTS.items()):
        old = next((r for r in rows if r[0] == cost), None)
        if old and old[COST_ITEM] != DERBY_COIN:
            sys.exit("ItemExtendedCost.dbc row %d is taken: it costs item %d" % (cost, old[COST_ITEM]))
        row = [0] * COST_FIELDS
        row[0], row[COST_ITEM], row[COST_COUNT] = cost, DERBY_COIN, coins
        new.append(row)
    write_dbc(path, put_rows(rows, new), strings, fields)
    print("ItemExtendedCost.dbc: %d rows (%d-%d)" % (len(new), new[0][0], new[-1][0]))


# --- SQL ---------------------------------------------------------------------------------------

def q(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def rank_mask(lowest):
    return sum(1 << rank for rank in range(lowest, RANK_EXALTED + 1))


RANK_NAMES = {RANK_FRIENDLY: "Friendly", RANK_HONORED: "Honored", RANK_REVERED: "Revered", RANK_EXALTED: "Exalted"}


def build_sql():
    quest_ids = [d["id"] for d in DAILIES]
    vendor_items = [item for item, _, _ in VENDOR]
    out = []
    w = out.append
    w("-- mod-nat-pagle: Nat Pagle's fishing dailies, The Anglers reputation and his rewards.")
    w("-- Generated by tools/build_patch.py: run the tool again, don't edit this file.")
    w("")

    w("-- The Anglers (the client gets the same row in its Faction.dbc).")
    w("DELETE FROM `faction_dbc` WHERE `ID` = %d;" % FACTION)
    w("INSERT INTO `faction_dbc` (`ID`, `ReputationIndex`, `ReputationRaceMask_1`, `ReputationFlags_1`, "
      "`ParentFactionID`, `ParentFactionCap_1`, `ParentFactionCap_2`, `Name_Lang_enUS`, `Name_Lang_Mask`, "
      "`Description_Lang_enUS`, `Description_Lang_Mask`) VALUES")
    w("(%d, %d, %d, %d, %d, 5, 5, %s, %d, %s, %d);" % (FACTION, FACTION_REP_INDEX, ALL_RACES, FACTION_FLAGS,
                                                     FACTION_PARENT, q(FACTION_NAME), NAME_MASK,
                                                     q(FACTION_DESCRIPTION), NAME_MASK))
    w("")

    w("-- Items: Nat's Tackle Box and the dailies' catches.")
    w("DELETE FROM `item_template` WHERE `entry` BETWEEN %d AND %d;" % (FIRST_ID, LAST_ID))
    w("DELETE FROM `item_loot_template` WHERE `Entry` = %d;" % TACKLE_BOX)
    cols = ("`entry`, `class`, `subclass`, `SoundOverrideSubclass`, `name`, `displayid`, `Quality`, `Flags`, "
            "`BuyCount`, `SellPrice`, `AllowableClass`, `AllowableRace`, `ItemLevel`, `maxcount`, `stackable`, "
            "`bonding`, `description`, `Material`, `RequiredDisenchantSkill`, `minMoneyLoot`, `maxMoneyLoot`, "
            "`spellcooldown_1`, `spellcategorycooldown_1`, `spellcooldown_2`, `spellcategorycooldown_2`, "
            "`spellcooldown_3`, `spellcategorycooldown_3`, `spellcooldown_4`, `spellcategorycooldown_4`, "
            "`spellcooldown_5`, `spellcategorycooldown_5`")
    cooldowns = ", ".join(["-1"] * 10)
    w("INSERT INTO `item_template` (%s) VALUES" % cols)
    rows = ["(%d, %d, 0, -1, %s, %d, 1, %d, 1, 1250, -1, -1, 45, 0, 20, %d, %s, %d, -1, 20000, 50000, %s)" % (
        TACKLE_BOX, ITEM_CLASS_MISC, q("Nat's Tackle Box"), TACKLE_BOX_DISPLAY, ITEM_FLAG_HAS_LOOT, BONDING_PICKUP,
        q("Smells of bait. Nat swears it's lucky."), TACKLE_BOX_MATERIAL, cooldowns)]
    levels = {era: level for era, (_, level, _, _) in ERAS.items()}
    for d in DAILIES:
        rows.append("(%d, %d, 0, -1, %s, %d, 1, 0, 1, 0, -1, -1, %d, %d, %d, %d, '', -1, -1, 0, 0, %s)" % (
            d["id"], ITEM_CLASS_QUEST, q(d["item"]), d["display"], levels[d["era"]] + 10, d["count"], d["count"],
            BONDING_QUEST, cooldowns))
    w(",\n".join(rows) + ";")
    w("INSERT INTO `item_loot_template` (`Entry`, `Item`, `Reference`, `Chance`, `QuestRequired`, `LootMode`, "
      "`GroupId`, `MinCount`, `MaxCount`, `Comment`) VALUES")
    w(",\n".join("(%d, %d, 0, %d, 0, 1, %d, %d, %d, %s)" % (TACKLE_BOX, item, chance, group, lo, hi,
                                                         q("Nat's Tackle Box"))
                 for item, chance, group, lo, hi in TACKLE_BOX_LOOT) + ";")
    w("")

    w("-- The dailies.")
    for table in ("quest_template", "quest_template_addon", "quest_request_items", "quest_offer_reward"):
        w("DELETE FROM `%s` WHERE `ID` BETWEEN %d AND %d;" % (table, FIRST_ID, LAST_ID))
    w("DELETE FROM `creature_queststarter` WHERE `quest` BETWEEN %d AND %d;" % (FIRST_ID, LAST_ID))
    w("DELETE FROM `creature_questender` WHERE `quest` BETWEEN %d AND %d;" % (FIRST_ID, LAST_ID))
    w("INSERT INTO `quest_template` (`ID`, `QuestType`, `QuestLevel`, `MinLevel`, `QuestSortID`, `Flags`, "
      "`RewardItem1`, `RewardAmount1`, `RewardFactionID1`, `RewardFactionOverride1`, `LogTitle`, `LogDescription`, "
      "`QuestDescription`, `QuestCompletionLog`, `RequiredItemId1`, `RequiredItemCount1`) VALUES")
    rows = []
    for d in DAILIES:
        _, level, reward, _ = ERAS[d["era"]]
        what = d["item"] if d["count"] == 1 else "%d %s" % (d["count"], plural(d["item"]))
        log = "Bring %s to Nat Pagle. Fish for %s in the waters of %s." % (
            what, "it" if d["count"] == 1 else "them", d["zone"])
        rows.append("(%d, 2, -1, %d, %d, %d, %d, 1, %d, %d, %s, %s, %s, %s, %d, %d)" % (
            d["id"], level, QUEST_SORT_FISHING, QUEST_FLAGS_DAILY, reward, FACTION, REP_PER_DAILY * 100,
            q(d["title"]), q(log), q(d["text"]), q("Return to Nat Pagle in Dustwallow Marsh."), d["id"], d["count"]))
    w(",\n".join(rows) + ";")
    w("INSERT INTO `quest_template_addon` (`ID`, `RequiredSkillID`, `RequiredSkillPoints`, `SpecialFlags`) VALUES")
    w(",\n".join("(%d, %d, 1, 1)" % (i, SKILL_FISHING) for i in quest_ids) + ";")
    w("INSERT INTO `quest_request_items` (`ID`, `CompletionText`) VALUES")
    w(",\n".join("(%d, %s)" % (d["id"], q(d["request"])) for d in DAILIES) + ";")
    w("INSERT INTO `quest_offer_reward` (`ID`, `RewardText`) VALUES")
    w(",\n".join("(%d, %s)" % (d["id"], q(d["reward"])) for d in DAILIES) + ";")
    w("INSERT INTO `creature_queststarter` (`id`, `quest`) VALUES")
    w(",\n".join("(%d, %d)" % (NAT_PAGLE, i) for i in quest_ids) + ";")
    w("INSERT INTO `creature_questender` (`id`, `quest`) VALUES")
    w(",\n".join("(%d, %d)" % (NAT_PAGLE, i) for i in quest_ids) + ";")
    w("")

    w("-- One daily a day from each era's pool.")
    w("DELETE FROM `pool_quest` WHERE `pool_entry` IN (%d, %d, %d);" % (POOL_AZEROTH, POOL_OUTLAND, POOL_NORTHREND))
    w("DELETE FROM `pool_template` WHERE `entry` IN (%d, %d, %d);" % (POOL_AZEROTH, POOL_OUTLAND, POOL_NORTHREND))
    w("INSERT INTO `pool_template` (`entry`, `max_limit`, `description`) VALUES")
    w(",\n".join("(%d, 1, %s)" % (pool, q("Nat Pagle - %s fishing dailies" % era.capitalize()))
                 for era, (pool, _, _, _) in ERAS.items()) + ";")
    w("INSERT INTO `pool_quest` (`entry`, `pool_entry`, `description`) VALUES")
    w(",\n".join("(%d, %d, %s)" % (d["id"], ERAS[d["era"]][0], q(d["title"])) for d in DAILIES) + ";")
    w("")

    w("-- The catches: only while the daily needs them.")
    w("DELETE FROM `fishing_loot_template` WHERE `Item` BETWEEN %d AND %d;" % (FIRST_ID, LAST_ID))
    w("INSERT INTO `fishing_loot_template` (`Entry`, `Item`, `Reference`, `Chance`, `QuestRequired`, `LootMode`, "
      "`GroupId`, `MinCount`, `MaxCount`, `Comment`) VALUES")
    rows = []
    for d in DAILIES:
        for entry in WATERS[d["zone"]]:
            rows.append("(%d, %d, 0, %d, 1, 1, 0, 1, 1, %s)" % (entry, d["id"], d["chance"], q(d["item"])))
    w(",\n".join(rows) + ";")
    w("")

    w("-- Outland and Northrend dailies wait for mod-individual-progression's state quests.")
    w("DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 19 AND `SourceEntry` BETWEEN %d AND %d;"
      % (FIRST_ID, LAST_ID))
    rows = []
    for d in DAILIES:
        gate = ERAS[d["era"]][3]
        if gate:
            rows.append("(19, 0, %d, 0, 0, 8, 0, %d, 0, 0, 0, 0, 0, '', %s)" % (
                d["id"], gate, q("Nat Pagle daily %s: progression quest %d" % (d["title"], gate))))
    w("INSERT INTO `conditions` (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`, `ElseGroup`, "
      "`ConditionTypeOrReference`, `ConditionTarget`, `ConditionValue1`, `ConditionValue2`, `ConditionValue3`, "
      "`NegativeCondition`, `ErrorType`, `ErrorTextId`, `ScriptName`, `Comment`) VALUES")
    w(",\n".join(rows) + ";")
    w("")

    vendor_ids = ", ".join(map(str, vendor_items))
    w("-- Nat's wares by Anglers rank (and progression state). The retail items only when the server has")
    w("-- them (mod-retail-collection). His stock Mudskunk Lure stays.")
    w("DELETE FROM `npc_vendor` WHERE `entry` = %d AND `item` IN (%s);" % (NAT_PAGLE, vendor_ids))
    w("DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 23 AND `SourceGroup` = %d AND `SourceEntry` IN (%s);"
      % (NAT_PAGLE, vendor_ids))
    w("INSERT INTO `npc_vendor` (`entry`, `slot`, `item`, `maxcount`, `incrtime`, `ExtendedCost`, `VerifiedBuild`)")
    w("SELECT %d, v.`slot`, v.`item`, 0, 0, 0, 0 FROM (" % NAT_PAGLE)
    w("\n  UNION ALL ".join("SELECT %d AS `slot`, %d AS `item`" % (slot, item)
                           for slot, item in enumerate(vendor_items, start=1)))
    w(") v JOIN `item_template` i ON i.`entry` = v.`item`;")
    columns = ["SourceTypeOrReferenceId", "SourceGroup", "SourceEntry", "SourceId", "ElseGroup",
               "ConditionTypeOrReference", "ConditionTarget", "ConditionValue1", "ConditionValue2", "ConditionValue3",
               "NegativeCondition", "ErrorType", "ErrorTextId", "ScriptName", "Comment"]
    rows = []
    for item, rank, gate in VENDOR:
        rows.append([23, NAT_PAGLE, item, 0, 0, 5, 0, FACTION, rank_mask(rank), 0, 0, 0, 0, "''",
                     q("Nat Pagle sells %d at %s with The Anglers" % (item, RANK_NAMES[rank]))])
        if gate:
            rows.append([23, NAT_PAGLE, item, 0, 0, 8, 0, gate, 0, 0, 0, 0, 0, "''",
                         q("Nat Pagle sells %d from progression quest %d" % (item, gate))])
    # The first SELECT names the derived table's columns.
    selects = ["SELECT " + ", ".join("%s AS `%s`" % (v, c) for v, c in zip(rows[0], columns))]
    selects += ["SELECT " + ", ".join(map(str, r)) for r in rows[1:]]
    w("INSERT INTO `conditions` (%s)" % ", ".join("`%s`" % c for c in columns))
    w("SELECT c.* FROM (\n  " + "\n  UNION ALL ".join(selects) + "\n) c")
    w("JOIN `npc_vendor` v ON v.`entry` = %d AND v.`item` = c.`SourceEntry`;" % NAT_PAGLE)
    w("")

    w("-- Nat pays the wallet coins (src/NatPagle.cpp).")
    w("UPDATE `creature_template` SET `ScriptName` = 'npc_nat_pagle' WHERE `entry` = %d;" % NAT_PAGLE)
    w("")

    build_derby_sql(w)
    return "\n".join(out) + "\n"


def spell_sql_values():
    def value(i, v):
        if i in SPELL_STRING_FIELDS:
            return "''"
        if i in SPELL_FLOAT_FIELDS:
            return "%g" % struct.unpack("<f", struct.pack("<I", v))[0]
        return str(struct.unpack("<i", struct.pack("<I", v))[0] if i in SPELL_SIGNED_FIELDS else v)

    values = [value(i, v) for i, v in enumerate(surf_spell_row())]
    values[F_NAME] = q(SURF_NAME)
    values[F_DESCRIPTION] = q(SURF_DESCRIPTION)
    values[F_AURA_TEXT] = q(SURF_AURA)
    return ", ".join(values)


def build_derby_sql(w):
    w("-- The Stranglethorn fishing contest: every character with 40 Tastyfish wins, once a week.")
    w("UPDATE `creature_template` SET `ScriptName` = 'npc_riggle_derby', `npcflag` = `npcflag` | %d WHERE `entry` = %d;"
      % (NPC_FLAG_VENDOR, RIGGLE))
    w("UPDATE `quest_template` SET `Flags` = %d, `RewardItem1` = %d, `RewardAmount1` = 1, `RewardChoiceItemID3` = %d, "
      "`RewardChoiceItemQuantity3` = 2, `RewardFactionID1` = %d, `RewardFactionOverride1` = %d WHERE `ID` = %d;"
      % (QUEST_FLAGS_WEEKLY, DERBY_COIN, DERBY_COIN, FACTION, WINNER_REP * 100, QUEST_MASTER_ANGLER))
    w("UPDATE `quest_request_items` SET `CompletionText` = %s WHERE `ID` = %d;" % (q(MASTER_ANGLER_TEXT), QUEST_MASTER_ANGLER))
    w("")
    w("-- Jang buys Tastyfish whether or not anyone has won, at his stock price.")
    w("DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 19 AND `SourceEntry` = %d "
      "AND `ConditionTypeOrReference` = 11 AND `ConditionValue1` = %d;" % (QUEST_APPRENTICE_ANGLER, WORLD_STATE_HAS_WINNER))
    w("UPDATE `quest_request_items` SET `CompletionText` = %s WHERE `ID` = %d;" % (q(APPRENTICE_TEXT), QUEST_APPRENTICE_ANGLER))
    w("")
    w("-- What Riggle says beyond the stock lines.")
    w("DELETE FROM `npc_text` WHERE `ID` = %d;" % TEXT_MORE_WINNERS)
    w("INSERT INTO `npc_text` (`ID`, `text0_0`, `text0_1`, `BroadcastTextID0`, `lang0`, `Probability0`) VALUES "
      "(%d, %s, %s, 0, 0, 1);" % (TEXT_MORE_WINNERS, q(MORE_WINNERS_TEXT), q(MORE_WINNERS_TEXT)))
    w("DELETE FROM `creature_text` WHERE `CreatureID` = %d AND `GroupID` IN (3, 4);" % RIGGLE)
    w("INSERT INTO `creature_text` (`CreatureID`, `GroupID`, `ID`, `Text`, `Type`, `Language`, `Probability`, `Emote`, "
      "`Duration`, `Sound`, `BroadcastTextId`, `TextRange`, `comment`) VALUES")
    w(",\n".join("(%d, %d, 0, %s, 14, 0, 100, 0, 0, 0, 0, 2, 'Fishing Extravaganza')" % (RIGGLE, group, q(text))
                 for group, text in ((3, SAY_SECOND), (4, SAY_THIRD))) + ";")
    w("")
    w("-- The coin and the Surfer Shoes (the client gets the same rows in its Item.dbc).")
    w("INSERT INTO `item_template` (`entry`, `class`, `subclass`, `SoundOverrideSubclass`, `name`, `displayid`, `Quality`, "
      "`BuyCount`, `AllowableClass`, `AllowableRace`, `InventoryType`, `ItemLevel`, `maxcount`, `stackable`, `bonding`, "
      "`description`, `Material`, `RequiredDisenchantSkill`, `spellid_1`, `spelltrigger_1`, `spellcooldown_1`, "
      "`spellcategorycooldown_1`, `spellcooldown_2`, `spellcategorycooldown_2`, `spellcooldown_3`, "
      "`spellcategorycooldown_3`, `spellcooldown_4`, `spellcategorycooldown_4`, `spellcooldown_5`, "
      "`spellcategorycooldown_5`) VALUES")
    cooldowns = ", ".join(["-1"] * 10)
    w("(%d, %d, 0, -1, %s, %d, 2, 1, -1, -1, 0, 45, 0, 250, %d, %s, %d, -1, 0, 0, %s),"
      % (DERBY_COIN, ITEM_CLASS_MISC, q("Extravagant Extravaganza Coin"), COIN_DISPLAY, BONDING_PICKUP,
         q("Riggle Bassbait and Nat Pagle take these for fishing prizes."), COIN_MATERIAL, cooldowns))
    w("(%d, %d, %d, -1, %s, %d, 3, 1, -1, -1, %d, 45, 1, 1, %d, %s, %d, -1, %d, 0, %s);"
      % (SURFER_SHOES, ITEM_CLASS_ARMOR, ITEM_SUBCLASS_CLOTH, q("Surfer Shoes"), SHOES_DISPLAY, INVTYPE_FEET,
         BONDING_PICKUP, q("Whatever you do, don't look down."), SHOES_MATERIAL, SURF_SPELL, cooldowns))
    w("")
    w("-- The Surfer Shoes' spell (the client gets the same row in its Spell.dbc).")
    w("DELETE FROM `spell_dbc` WHERE `ID` = %d;" % SURF_SPELL)
    w("INSERT INTO `spell_dbc` VALUES\n(%s);" % spell_sql_values())
    w("")
    w("-- The coin prices (the client gets the same rows in its ItemExtendedCost.dbc).")
    cost_ids = sorted(COSTS.values())
    w("DELETE FROM `itemextendedcost_dbc` WHERE `ID` BETWEEN %d AND %d;" % (cost_ids[0], cost_ids[-1]))
    w("INSERT INTO `itemextendedcost_dbc` (`ID`, `HonorPoints`, `ArenaPoints`, `ArenaBracket`, `ItemID_1`, `ItemID_2`, "
      "`ItemID_3`, `ItemID_4`, `ItemID_5`, `ItemCount_1`, `ItemCount_2`, `ItemCount_3`, `ItemCount_4`, `ItemCount_5`, "
      "`RequiredArenaRating`, `ItemPurchaseGroup`) VALUES")
    w(",\n".join("(%d, 0, 0, 0, %d, 0, 0, 0, 0, %d, 0, 0, 0, 0, 0, 0)" % (cost, DERBY_COIN, coins)
                 for coins, cost in sorted(COSTS.items())) + ";")
    w("")
    shop_ids = ", ".join(str(item) for item, _, _ in SHOP)
    w("-- The coin shop: Riggle on contest days, Nat all week. Outland and Northrend goods wait for")
    w("-- mod-individual-progression's state quests.")
    w("DELETE FROM `npc_vendor` WHERE `entry` IN (%d, %d) AND `item` IN (%s);" % (RIGGLE, NAT_PAGLE, shop_ids))
    w("DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 23 AND `SourceGroup` IN (%d, %d) AND `SourceEntry` IN (%s);"
      % (RIGGLE, NAT_PAGLE, shop_ids))
    w("INSERT INTO `npc_vendor` (`entry`, `slot`, `item`, `maxcount`, `incrtime`, `ExtendedCost`, `VerifiedBuild`) VALUES")
    rows = []
    for vendor, first_slot in ((RIGGLE, 1), (NAT_PAGLE, NAT_SHOP_FIRST_SLOT)):
        for slot, (item, coins, _) in enumerate(SHOP, start=first_slot):
            rows.append("(%d, %d, %d, 0, 0, %d, 0)" % (vendor, slot, item, COSTS[coins]))
    w(",\n".join(rows) + ";")
    w("INSERT INTO `conditions` (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`, `ElseGroup`, "
      "`ConditionTypeOrReference`, `ConditionTarget`, `ConditionValue1`, `ConditionValue2`, `ConditionValue3`, "
      "`NegativeCondition`, `ErrorType`, `ErrorTextId`, `ScriptName`, `Comment`) VALUES")
    rows = []
    for vendor in (RIGGLE, NAT_PAGLE):
        for item, _, gate in SHOP:
            if gate:
                rows.append("(23, %d, %d, 0, 0, 8, 0, %d, 0, 0, 0, 0, 0, '', %s)" % (
                    vendor, item, gate, q("Fishing coin shop sells %d from progression quest %d" % (item, gate))))
    w(",\n".join(rows) + ";")




def plural(name):
    if name.endswith(("fish", "Cod", "Trout")):
        return name
    return name + "s"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sql", help="write the module's world SQL here")
    ap.add_argument("--patch", help="your realm's live spell patch (has Item.dbc)")
    ap.add_argument("--client", help="a 3.3.5a client folder: its Faction.dbc, when --patch has none")
    ap.add_argument("--out", help="the new spell patch")
    args = ap.parse_args()
    if not args.sql and not args.patch:
        ap.error("nothing to do: give --sql and/or --patch with --out")

    if args.sql:
        with open(args.sql, "w", encoding="utf-8") as f:
            f.write(build_sql())
        print("wrote", args.sql)

    if args.patch:
        if not args.out:
            ap.error("--patch needs --out")
        with tempfile.TemporaryDirectory() as tmp:
            files = unpack(args.patch, tmp)
            if "DBFilesClient\\Item.dbc" not in files:
                sys.exit("%s has no Item.dbc" % args.patch)
            patch_items(files["DBFilesClient\\Item.dbc"])
            for dbc, patch_one in (("Faction.dbc", patch_faction), ("Spell.dbc", patch_spell),
                                   ("ItemExtendedCost.dbc", patch_costs)):
                name = "DBFilesClient\\" + dbc
                if name not in files:
                    if not args.client:
                        sys.exit("%s has no %s: pass --client to start from the client's" % (args.patch, dbc))
                    files[name] = client_dbc(args.client, dbc, os.path.join(tmp, dbc))
                patch_one(files[name])
            pack(args.out, [(local, name) for name, local in sorted(files.items())])
            print("%s: %d files, %.1f MB" % (args.out, len(files), os.path.getsize(args.out) / 1e6))


if __name__ == "__main__":
    main()
