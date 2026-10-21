-- mod-nat-pagle: undo the module's traces in the characters database. Run it by hand after
-- removing the module (and after mod_nat_pagle_uninstall_world.sql).
--
-- Forgets The Anglers reputation, the dailies' quest log entries and history, and the pools'
-- picks, and removes the module's items (Nat's Tackle Box, the catches) from bags and banks.
-- Idempotent: safe to run again.

DELETE FROM `character_reputation` WHERE `faction` = 1170;

DELETE FROM `character_queststatus` WHERE `quest` BETWEEN 9503700 AND 9503799;
DELETE FROM `character_queststatus_daily` WHERE `quest` BETWEEN 9503700 AND 9503799;
DELETE FROM `character_queststatus_rewarded` WHERE `quest` BETWEEN 9503700 AND 9503799;
DELETE FROM `pool_quest_save` WHERE `pool_id` IN (9503700, 9503701, 9503702);

DELETE ci FROM `character_inventory` ci
    JOIN `item_instance` ii ON ii.`guid` = ci.`item`
    WHERE ii.`itemEntry` BETWEEN 9503700 AND 9503799;
DELETE FROM `item_instance` WHERE `itemEntry` BETWEEN 9503700 AND 9503799
    AND `guid` NOT IN (SELECT `item_guid` FROM `mail_items`);
