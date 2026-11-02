/*
 * mod-nat-pagle: the Stranglethorn fishing contest with more than one winner.
 *
 * Replaces the core's npc_riggle_bassbait (world SQL sets the ScriptName), which closes Master
 * Angler after the first win. Here everyone with 40 Speckled Tastyfish can win, once a week: the
 * quest's weekly flag stops a second win, and its coin and prizes are world SQL too
 * (tools/build_patch.py). This script keeps Riggle's stock timing and lines, opens his shop and
 * pays the first three winners their bonus coins.
 *
 * Winners are counted from character_queststatus_weekly when the turn-ins start, so a restart
 * during the contest keeps the places, and go back to zero when the turn-ins end. A quest's weekly
 * rows are saved and rolled back with the character, and the weekly reset is never on a contest day.
 *
 * Released under the MIT License.
 */

#include "Chat.h"
#include "Config.h"
#include "CreatureScript.h"
#include "DatabaseEnv.h"
#include "GameEventMgr.h"
#include "GameEventScript.h"
#include "Player.h"
#include "QuestDef.h"
#include "ScriptedCreature.h"
#include "ScriptedGossip.h"
#include "StringFormat.h"
#include "WorldScript.h"
#include "WorldSession.h"
#include <atomic>

namespace NatPagle
{
    namespace
    {
        enum RiggleDerby : uint32
        {
            SAY_START               = 0,
            SAY_POOLS_END           = 1,
            SAY_FIRST_PLACE         = 2,    // 3 second place, 4 third place

            QUEST_MASTER_ANGLER     = 8193,

            EVENT_FISHING_POOLS     = 15,
            EVENT_FISHING_TURN_INS  = 90,

            TEXT_NO_WINNER_YET      = 7614,
            TEXT_MORE_WINNERS       = 9503720,

            ITEM_DERBY_COIN         = 9503720
        };

        constexpr uint32 PODIUM = 3;

        std::atomic<uint32> winners{0};
        uint32 firstPlaceCoins = 2;
        uint32 runnerUpCoins = 1;

        void LoadWinners()
        {
            uint32 count = 0;
            if (QueryResult result = CharacterDatabase.Query("SELECT COUNT(*) FROM character_queststatus_weekly WHERE quest = {}",
                uint32(QUEST_MASTER_ANGLER)))
                count = uint32(result->Fetch()[0].Get<uint64>());
            winners = count;
        }

        // Into the bags as far as they fit, the rest by mail.
        void GiveCoins(Player* player, uint32 count)
        {
            ItemPosCountVec dest;
            uint32 noSpace = 0;
            player->CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, ITEM_DERBY_COIN, count, &noSpace);

            if (count > noSpace && !dest.empty())
                if (Item* item = player->StoreNewItem(dest, ITEM_DERBY_COIN, true))
                    player->SendNewItem(item, count - noSpace, true, false);

            if (noSpace)
                player->SendItemRetrievalMail(ITEM_DERBY_COIN, noSpace);
        }
    }

    class npc_riggle_derby : public CreatureScript
    {
    public:
        npc_riggle_derby() : CreatureScript("npc_riggle_derby") { }

        struct npc_riggle_derbyAI : public ScriptedAI
        {
            // Spawned during the turn-ins means a restart or a reloaded grid: he has already said it.
            explicit npc_riggle_derbyAI(Creature* creature) : ScriptedAI(creature),
                _announcedStart(sGameEventMgr->IsActiveEvent(EVENT_FISHING_TURN_INS)) { }

            void UpdateAI(uint32 diff) override
            {
                if (_timer > diff)
                {
                    _timer -= diff;
                    return;
                }
                _timer = 1000;

                bool turnIns = sGameEventMgr->IsActiveEvent(EVENT_FISHING_TURN_INS);
                if (turnIns && !me->IsQuestGiver())
                    me->SetNpcFlag(UNIT_NPC_FLAG_QUESTGIVER);
                else if (!turnIns && me->IsQuestGiver())
                    me->RemoveNpcFlag(UNIT_NPC_FLAG_QUESTGIVER);

                if (turnIns && !_announcedStart)
                {
                    Talk(SAY_START);
                    _announcedStart = true;
                }

                bool pools = sGameEventMgr->IsActiveEvent(EVENT_FISHING_POOLS);
                if (_poolsUp && !pools)
                    Talk(SAY_POOLS_END);
                _poolsUp = pools;
            }

        private:
            uint32 _timer = 0;
            bool _announcedStart;
            bool _poolsUp = false;
        };

        bool OnGossipHello(Player* player, Creature* creature) override
        {
            if (creature->IsQuestGiver())
                player->PrepareQuestMenu(creature->GetGUID());

            // A chat icon: the client opens a lone vendor option by itself, without the greeting.
            AddGossipItemFor(player, GOSSIP_ICON_CHAT, "What can I get for my Extravaganza Coins?", GOSSIP_SENDER_MAIN, GOSSIP_ACTION_TRADE);
            SendGossipMenuFor(player, winners ? uint32(TEXT_MORE_WINNERS) : uint32(TEXT_NO_WINNER_YET), creature->GetGUID());
            return true;
        }

        bool OnGossipSelect(Player* player, Creature* creature, uint32 /*sender*/, uint32 action) override
        {
            CloseGossipMenuFor(player);
            if (action == GOSSIP_ACTION_TRADE)
                player->GetSession()->SendListInventory(creature->GetGUID());
            return true;
        }

        bool OnQuestReward(Player* player, Creature* creature, Quest const* quest, uint32 /*opt*/) override
        {
            if (quest->GetQuestId() != QUEST_MASTER_ANGLER)
                return false;

            uint32 place = ++winners;
            if (place > PODIUM)
                return true;

            creature->AI()->Talk(SAY_FIRST_PLACE + place - 1, player);

            uint32 bonus = place == 1 ? firstPlaceCoins : runnerUpCoins;
            if (bonus)
            {
                GiveCoins(player, bonus);
                ChatHandler(player->GetSession()).SendSysMessage(Acore::StringFormat(
                    "Riggle Bassbait hands you {} bonus {} for your place on the podium.", bonus, bonus == 1 ? "coin" : "coins"));
            }
            return true;
        }

        CreatureAI* GetAI(Creature* creature) const override
        {
            return new npc_riggle_derbyAI(creature);
        }
    };

    class NatPagleDerbyEventScript : public GameEventScript
    {
    public:
        NatPagleDerbyEventScript() : GameEventScript("NatPagleDerbyEventScript", { GAMEEVENTHOOK_ON_START, GAMEEVENTHOOK_ON_STOP }) { }

        void OnStart(uint16 eventId) override
        {
            if (eventId == EVENT_FISHING_TURN_INS)
                LoadWinners();
        }

        // Riggle arrives an hour before the next turn-ins start: he shouldn't greet with last week's winners.
        void OnStop(uint16 eventId) override
        {
            if (eventId == EVENT_FISHING_TURN_INS)
                winners = 0;
        }
    };

    class NatPagleDerbyWorldScript : public WorldScript
    {
    public:
        NatPagleDerbyWorldScript() : WorldScript("NatPagleDerbyWorldScript") { }

        void OnAfterConfigLoad(bool /*reload*/) override
        {
            firstPlaceCoins = sConfigMgr->GetOption<uint32>("NatPagle.Derby.FirstPlaceCoins", 2);
            runnerUpCoins = sConfigMgr->GetOption<uint32>("NatPagle.Derby.RunnerUpCoins", 1);
        }
    };
}

void AddNatPagleDerbyScripts()
{
    new NatPagle::npc_riggle_derby();
    new NatPagle::NatPagleDerbyEventScript();
    new NatPagle::NatPagleDerbyWorldScript();
}
