-- mod-nat-pagle: undo the module's world database changes. Run it by hand on the world database
-- after removing the module. It isn't applied automatically: AzerothCore only runs the module's
-- db-world and db-characters folders.
--
-- Removes the dailies, their catches and pools, Nat's Tackle Box, The Anglers and what the module
-- added to Nat Pagle's wares; his stock Mudskunk Lure and stock quests stay. Puts the Stranglethorn
-- fishing contest back to stock. It also forgets that the module's updates were applied, so
-- installing the module again applies them again.
-- Idempotent: safe to run again.

UPDATE `creature_template` SET `ScriptName` = 'npc_riggle_bassbait', `npcflag` = `npcflag` & ~128 WHERE `entry` = 15077;
UPDATE `quest_template` SET `Flags` = 0, `RewardItem1` = 0, `RewardAmount1` = 0, `RewardChoiceItemID3` = 0,
    `RewardChoiceItemQuantity3` = 0, `RewardFactionID1` = 0, `RewardFactionOverride1` = 0 WHERE `ID` = 8193;
UPDATE `quest_request_items` SET `CompletionText` = 'Today between 2pm and 4pm we have a contest to determine who the greatest angler of them all is! Just be the FIRST PERSON to bring me 40 Tastyfish fished from the Tastyfish schools found along the coast of Stranglethorn before anyone else does and you will be declared the Master Angler!$b$bIf you are not the first person to bring me 40 fish, my apprentice here will still reward you with money for each 5 Tastyfish you bring her.$b$bOh, and don\'t delay, Tastyfish go bad quickly!' WHERE `ID` = 8193;
UPDATE `quest_request_items` SET `CompletionText` = 'Even though we already have a contest winner, I will still buy your Tastyfish from you at a reasonable price. Whadda ya say!' WHERE `ID` = 8194;
DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 19 AND `SourceEntry` = 8194
    AND `ConditionTypeOrReference` = 11 AND `ConditionValue1` = 198;
INSERT INTO `conditions` (`SourceTypeOrReferenceId`, `SourceGroup`, `SourceEntry`, `SourceId`, `ElseGroup`,
    `ConditionTypeOrReference`, `ConditionTarget`, `ConditionValue1`, `ConditionValue2`, `ConditionValue3`,
    `NegativeCondition`, `ErrorType`, `ErrorTextId`, `ScriptName`, `Comment`)
VALUES (19, 0, 8194, 0, 0, 11, 0, 198, 1, 0, 0, 0, 0, '', 'Fishing Extravaganza - fishing event has a winner');
DELETE FROM `npc_text` WHERE `ID` = 9503720;
DELETE FROM `creature_text` WHERE `CreatureID` = 15077 AND `GroupID` IN (3, 4);
DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 23 AND `SourceGroup` IN (15077, 12919)
    AND `SourceEntry` IN (9503721, 19979, 50287, 33816, 35349);
DELETE FROM `npc_vendor` WHERE `entry` IN (15077, 12919) AND `item` IN (9503721, 19979, 50287, 33816, 35349);
DELETE FROM `itemextendedcost_dbc` WHERE `ID` BETWEEN 90434 AND 90436;
DELETE FROM `spell_dbc` WHERE `ID` = 90470;

DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 19 AND `SourceEntry` BETWEEN 9503700 AND 9503799;
DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 23 AND `SourceGroup` = 12919
    AND `SourceEntry` IN (6533, 6532, 19971, 19972, 19969, 19022, 33820, 45858, 410847, 410652, 19970, 400449);
DELETE FROM `npc_vendor` WHERE `entry` = 12919
    AND `item` IN (6533, 6532, 19971, 19972, 19969, 19022, 33820, 45858, 410847, 410652, 19970, 400449);
DELETE FROM `gossip_menu_option` WHERE `MenuID` = 6445 AND `OptionID` = 1;

DELETE FROM `fishing_loot_template` WHERE `Item` BETWEEN 9503700 AND 9503799;
DELETE FROM `pool_quest` WHERE `pool_entry` IN (9503700, 9503701, 9503702);
DELETE FROM `pool_template` WHERE `entry` IN (9503700, 9503701, 9503702);

DELETE FROM `creature_queststarter` WHERE `quest` BETWEEN 9503700 AND 9503799;
DELETE FROM `creature_questender` WHERE `quest` BETWEEN 9503700 AND 9503799;
DELETE FROM `quest_offer_reward` WHERE `ID` BETWEEN 9503700 AND 9503799;
DELETE FROM `quest_request_items` WHERE `ID` BETWEEN 9503700 AND 9503799;
DELETE FROM `quest_template_addon` WHERE `ID` BETWEEN 9503700 AND 9503799;
DELETE FROM `quest_template` WHERE `ID` BETWEEN 9503700 AND 9503799;

DELETE FROM `item_loot_template` WHERE `Entry` = 9503700;
DELETE FROM `item_template` WHERE `entry` BETWEEN 9503700 AND 9503799;

DELETE FROM `faction_dbc` WHERE `ID` = 1170;

UPDATE `creature_template` SET `ScriptName` = '' WHERE `entry` = 12919 AND `ScriptName` = 'npc_nat_pagle';

DELETE FROM `updates` WHERE `name` LIKE 'mod\_nat\_pagle\_%';
