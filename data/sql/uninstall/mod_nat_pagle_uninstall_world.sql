-- mod-nat-pagle: undo the module's world database changes. Run it by hand on the world database
-- after removing the module. It isn't applied automatically: AzerothCore only runs the module's
-- db-world and db-characters folders.
--
-- Removes the dailies, their catches and pools, Nat's Tackle Box, The Anglers and what the module
-- added to Nat Pagle's wares; his stock Mudskunk Lure and stock quests stay. It also forgets that
-- the module's updates were applied, so installing the module again applies them again.
-- Idempotent: safe to run again.

DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 19 AND `SourceEntry` BETWEEN 9503700 AND 9503799;
DELETE FROM `conditions` WHERE `SourceTypeOrReferenceId` = 23 AND `SourceGroup` = 12919
    AND `SourceEntry` IN (6533, 6532, 19971, 19972, 19969, 19022, 33820, 45858, 410847, 410652, 19970, 400449);
DELETE FROM `npc_vendor` WHERE `entry` = 12919
    AND `item` IN (6533, 6532, 19971, 19972, 19969, 19022, 33820, 45858, 410847, 410652, 19970, 400449);

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
