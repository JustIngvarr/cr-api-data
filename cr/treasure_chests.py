"""
Treasure chests generator
"""
import csv
import re

from .base import BaseGen
from .util import camelcase_split


class TreasureChests(BaseGen):

    def __init__(self, config):
        super().__init__(config, id="treasure_chests")

        self.fields = ["Name", "BaseChest", "Arena", "InShop", "InArenaInfo", "TournamentChest", "SurvivalChest",
                       "ShopPriceWithoutSpeedUp", "TimeTakenDays", "TimeTakenHours", "TimeTakenMinutes",
                       "TimeTakenSeconds", "RandomSpells", "DifferentSpells", "ChestCountInChestCycle", "RareChance",
                       "EpicChance", "LegendaryChance", "SkinChance", "GuaranteedSpells", "MinGoldPerCard",
                       "MaxGoldPerCard", "SpellSet", "Exp", "SortValue", "SpecialOffer", "DraftChest", "BoostedChest",
                       "LegendaryOverrideChance"
                       ]
        self.tid_fields = [
            dict(field="TID", output_field="description"),
            dict(field="NotificationTID", output_field="notification")
        ]

        self.base_chests = []
        self.items = []

    def get_base_chest_stats(self, name):
        """Return base chest stats as dict."""
        props = [
            "time_taken_hours", "time_taken_minutes", "time_taken_seconds",
            "random_spells", "different_spells",
            "chest_count_in_chest_cycle",
            "rare_chance", "epic_chance", "legendary_chance", "skin_chance",
            "min_gold_per_card", "max_gold_per_card",
            "sort_value"
        ]
        for item in self.items:
            if name == item["name"]:
                return {k: v for k, v in item.items() if k in props}
        return {}

    def card_count_by_arena(self, name, arena_id, random_spells, chest_reward_multiplier):
        # don’t scale legendary chests
        if name.startswith('Legendary'):
            return int(random_spells)
        # don’t scale epic chests
        if name.startswith('Epic'):
            return int(random_spells)
        # don’t scale draft chest rewards
        if name.startswith("Draft"):
            return int(random_spells)
        # don’t scale season rewards
        if name.startswith("SeasonReward"):
            return int(random_spells)

        if chest_reward_multiplier:
            return int(chest_reward_multiplier / 100 * random_spells)
        return 0

    def card_count_by_type(self, card_count_by_arena, chance):
        if chance == 0:
            return 0
        return 1 / chance * card_count_by_arena

    def include_name(self, name):
        """Return true if chest shoule be included."""
        if name is None:
            return False
        if len(name) == 0:
            return False
        # Exclude old chests
        if re.match('.+_old', name):
            return False
        # Exclude clan chest
        if name.startswith('ClanCrownChest'):
            return False
        # Exclude tournament chests
        if name.startswith('Tournament'):
            return False
        # Exclude challenge chests
        if name.startswith('Survival'):
            return False
        return True

    def run(self):
        """Generate treasure chests."""
        with open(self.csv_path, encoding="utf8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i > 0:
                    if self.include_name(row.get('Name')):
                        item = {'_'.join(camelcase_split(k)).lower(): self.row_value(row, k) for k, v in row.items()
                                if k in self.fields}

                        if item.get("base_chest"):
                            item.update(self.get_base_chest_stats(item["base_chest"]))

                        for tf in self.tid_fields:
                            if row.get(tf["field"]):
                                item[tf["output_field"]] = self.text(row[tf["field"]], "EN")

                        # Card count = random spells
                        item["card_count"] = item["random_spells"]
                        item["card_count_by_arena"] = item["card_count"]

                        # Gold output is affected by card count
                        item["min_gold"] = item["card_count"] * item["min_gold_per_card"]
                        item["max_gold"] = item["card_count"] * item["max_gold_per_card"]

                        arena_dict = self.get_arena(item["arena"])
                        arena_dict_keys = [
                            "name", "arena", "key", "chest_reward_multiplier", "shop_chest_reward_multiplier",
                            "title", "subtitle"
                        ]
                        if arena_dict is not None:
                            arena = {k: v for k, v in arena_dict.items() if k in arena_dict_keys}
                            item.update({
                                "arena": arena
                            })

                            # arena affects these fields
                            card_count_by_arena = self.card_count_by_arena(
                                item["name"],
                                item["arena"]["arena"],
                                item["card_count"],
                                arena.get("chest_reward_multiplier")
                            )
                            item["card_count_by_arena"] = card_count_by_arena

                            # area affects total card chance
                            card_count_rare = self.card_count_by_type(card_count_by_arena, item["rare_chance"])
                            card_count_epic = self.card_count_by_type(card_count_by_arena, item["epic_chance"])
                            card_count_legendary = self.card_count_by_type(card_count_by_arena,
                                                                           item["legendary_chance"])
                            card_count_common = card_count_by_arena - card_count_rare - card_count_epic - card_count_legendary

                            item.update({
                                "card_count_rare": card_count_rare,
                                "card_count_epic": card_count_epic,
                                "card_count_legendary": card_count_legendary,
                                "card_count_common": card_count_common
                            })

                        self.items.append(item)

        self.items = sorted(self.items, key=lambda x: (x["arena"]["arena"], x["sort_value"]))
        self.save_json(self.items, self.json_path)
