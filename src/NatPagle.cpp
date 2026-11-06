/*
 * mod-nat-pagle: Nat Pagle pays account wallet coins for his fishing dailies, and tells a player
 * what his higher Anglers ranks add to his shop.
 *
 * The dailies, the reputation and Nat's wares are all world SQL (tools/build_patch.py). This
 * script adds NatPagle.Coins to mod-boss-coins' account wallet when a character hands in one of
 * the dailies, when mod-boss-coins is built into the same server. When his shop opens, it lists
 * in chat the wares the player's next Anglers ranks will add.
 *
 * Released under the MIT License.
 */

#include "Chat.h"
#include "ConditionMgr.h"
#include "Config.h"
#include "Creature.h"
#include "DBCStores.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "QuestDef.h"
#include "ReputationMgr.h"
#include "ScriptMgr.h"
#include "StringFormat.h"
#include "WorldSession.h"

#include <array>
#include <map>
#include <sstream>
#include <vector>
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
        constexpr uint32 NPC_NAT_PAGLE = 12919;
        constexpr uint32 FACTION_ANGLERS = 1170;

        constexpr std::array<char const*, MAX_REPUTATION_RANK> RANK_NAMES =
            { "Hated", "Hostile", "Unfriendly", "Neutral", "Friendly", "Honored", "Revered", "Exalted" };

        uint32 coins = 1;
        bool shopUnlocks = true;

        std::string ItemLink(ItemTemplate const* item)
        {
            std::ostringstream link;
            link << "|c" << std::hex << ItemQualityColors[item->Quality] << std::dec
                 << "|Hitem:" << item->ItemId << ":0:0:0:0:0:0:0:0:0|h[" << item->Name1 << "]|h|r";
            return link.str();
        }

        // The wares the shop holds back from this player only for want of Anglers rank, by the
        // lowest rank that shows each. A ware also held back by something else, such as a
        // progression tier, is left out: reaching the rank alone wouldn't show it. The vendor
        // conditions are read the way the core reads them for the list, and Nat's are all in
        // one condition group.
        std::map<ReputationRank, std::vector<ItemTemplate const*>> RankLockedWares(Player* player, Creature* nat,
            ReputationRank rank)
        {
            std::map<ReputationRank, std::vector<ItemTemplate const*>> locked;
            VendorItemData const* stock = nat->GetVendorItems();
            if (!stock)
                return locked;

            for (uint8 slot = 0; slot < stock->GetItemCount(); ++slot)
            {
                VendorItem const* item = stock->GetItem(slot);
                ItemTemplate const* proto = item ? sObjectMgr->GetItemTemplate(item->item) : nullptr;
                if (!proto)
                    continue;

                // the core never lists another class's bind-on-pickup piece, or the other team's
                if (!(proto->AllowableClass & player->getClassMask()) && proto->Bonding == BIND_WHEN_PICKED_UP)
                    continue;
                if ((proto->HasFlag2(ITEM_FLAG2_FACTION_HORDE) && player->GetTeamId() == TEAM_ALLIANCE) ||
                    (proto->HasFlag2(ITEM_FLAG2_FACTION_ALLIANCE) && player->GetTeamId() == TEAM_HORDE))
                    continue;

                uint32 rankMask = 0;
                ConditionList others;
                for (Condition* condition : sConditionMgr->GetConditionsForNpcVendorEvent(NPC_NAT_PAGLE, item->item))
                {
                    if (condition->ConditionType == CONDITION_REPUTATION_RANK &&
                        condition->ConditionValue1 == FACTION_ANGLERS && !condition->NegativeCondition)
                        rankMask |= condition->ConditionValue2;
                    else
                        others.push_back(condition);
                }

                if (!rankMask || (rankMask & (1 << rank)))
                    continue;

                for (uint8 next = rank + 1; next < MAX_REPUTATION_RANK; ++next)
                {
                    if (!(rankMask & (1 << next)))
                        continue;

                    if (sConditionMgr->IsObjectMeetToConditions(player, nat, others))
                        locked[ReputationRank(next)].push_back(proto);
                    break;
                }
            }

            return locked;
        }

        void SendShopUnlocks(Player* player, Creature* nat)
        {
            FactionEntry const* anglers = sFactionStore.LookupEntry(FACTION_ANGLERS);
            if (!anglers)
                return;

            ReputationMgr const& reputation = player->GetReputationMgr();
            ReputationRank rank = reputation.GetRank(anglers);
            auto locked = RankLockedWares(player, nat, rank);
            if (locked.empty())
                return;

            ChatHandler chat(player->GetSession());
            int32 rankStart = ReputationMgr::ReputationRankToStanding(rank) - ReputationMgr::PointsInRank[rank];
            chat.SendSysMessage(Acore::StringFormat("The Anglers: {}, {}/{}.", RANK_NAMES[rank],
                reputation.GetReputation(anglers) - rankStart, ReputationMgr::PointsInRank[rank]));

            for (auto const& [unlock, wares] : locked)
            {
                std::string links;
                for (ItemTemplate const* ware : wares)
                    links += (links.empty() ? "" : ", ") + ItemLink(ware);
                chat.SendSysMessage(Acore::StringFormat("At {}, Nat Pagle also sells {}.", RANK_NAMES[unlock], links));
            }
        }

        bool IsDaily(Quest const* quest)
        {
            return quest && quest->GetQuestId() >= QUEST_FIRST && quest->GetQuestId() <= QUEST_LAST;
        }

        void PayCoins([[maybe_unused]] Player* player)
        {
#ifdef NAT_PAGLE_BOSS_COINS
            if (!coins || !BossCoins::IsRealPlayer(player))
                return;

            // A Self-Found character can't reach the account wallet, so the coins go in its bags.
            if (BossCoins::IsSelfFound(player->GetGUID().GetCounter()))
            {
                ChatHandler(player->GetSession()).SendSysMessage(Acore::StringFormat(
                    "Nat Pagle slips you {} {}.", coins, BossCoins::CoinName(coins)));
                BossCoins::GiveCoinsToBags(player, coins);
                return;
            }

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

    class NatPagleShopScript : public PlayerScript
    {
    public:
        NatPagleShopScript() : PlayerScript("NatPagleShopScript", { PLAYERHOOK_ON_SEND_LIST_INVENTORY }) { }

        // Fires at the start of WorldSession::SendListInventory, so the lines land in chat as the
        // window opens. A vendor entry means a gossip option asked for another list.
        void OnPlayerSendListInventory(Player* player, ObjectGuid vendorGuid, uint32& vendorEntry) override
        {
            if (!shopUnlocks || vendorEntry || vendorGuid.GetEntry() != NPC_NAT_PAGLE || player->GetSession()->IsHeadless())
                return;

            if (Creature* nat = player->GetNPCIfCanInteractWith(vendorGuid, UNIT_NPC_FLAG_VENDOR))
                SendShopUnlocks(player, nat);
        }
    };

    class NatPagleWorldScript : public WorldScript
    {
    public:
        NatPagleWorldScript() : WorldScript("NatPagleWorldScript") { }

        void OnAfterConfigLoad(bool /*reload*/) override
        {
            coins = sConfigMgr->GetOption<uint32>("NatPagle.Coins", 1);
            shopUnlocks = sConfigMgr->GetOption<bool>("NatPagle.ShopUnlocks", true);
        }
    };
}

void AddNatPagleScripts()
{
    new NatPagle::npc_nat_pagle();
    new NatPagle::NatPagleShopScript();
    new NatPagle::NatPagleWorldScript();
}
