/*
 * mod-nat-pagle: Nat Pagle pays account wallet coins for his fishing dailies.
 *
 * The dailies, the reputation and Nat's wares are all world SQL (tools/build_patch.py). This
 * script only adds NatPagle.Coins to mod-boss-coins' account wallet when a character hands in
 * one of the dailies, and only when mod-boss-coins is built into the same server.
 *
 * Released under the MIT License.
 */

#include "Chat.h"
#include "Config.h"
#include "Creature.h"
#include "Player.h"
#include "QuestDef.h"
#include "ScriptMgr.h"
#include "StringFormat.h"
#include "WorldSession.h"
#if __has_include("BossCoins.h")
#include "BossCoins.h"
#define NAT_PAGLE_BOSS_COINS 1
#endif

namespace NatPagle
{
    namespace
    {
        constexpr uint32 QUEST_FIRST = 9503701;
        constexpr uint32 QUEST_LAST = 9503799;

        uint32 coins = 1;

        bool IsDaily(Quest const* quest)
        {
            return quest && quest->GetQuestId() >= QUEST_FIRST && quest->GetQuestId() <= QUEST_LAST;
        }

        void PayCoins([[maybe_unused]] Player* player)
        {
#ifdef NAT_PAGLE_BOSS_COINS
            if (!coins || !BossCoins::IsRealPlayer(player))
                return;

            uint32 balance = 0;
            uint32 added = BossCoins::Wallet::Add(player->GetSession()->GetAccountId(), player->GetGUID().GetCounter(),
                coins, "fishing", 0, nullptr, &balance);
            if (added)
                ChatHandler(player->GetSession()).SendSysMessage(Acore::StringFormat(
                    "Nat Pagle slips you {} {}. Your account wallet now holds {}.", added, BossCoins::CoinName(added), balance));
#endif
        }
    }

    class npc_nat_pagle : public CreatureScript
    {
    public:
        npc_nat_pagle() : CreatureScript("npc_nat_pagle") { }

        // Runs after the core has rewarded the quest. False: the core goes on as usual.
        bool OnQuestReward(Player* player, Creature* /*creature*/, Quest const* quest, uint32 /*opt*/) override
        {
            if (IsDaily(quest))
                PayCoins(player);
            return false;
        }
    };

    class NatPagleWorldScript : public WorldScript
    {
    public:
        NatPagleWorldScript() : WorldScript("NatPagleWorldScript") { }

        void OnAfterConfigLoad(bool /*reload*/) override
        {
            coins = sConfigMgr->GetOption<uint32>("NatPagle.Coins", 1);
        }
    };
}

void AddNatPagleScripts()
{
    new NatPagle::npc_nat_pagle();
    new NatPagle::NatPagleWorldScript();
}
