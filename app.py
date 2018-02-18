import asyncio
import json
import os
import re
from typing import Tuple

import itertools

from ahglplayerdata import battlefy, blizzard, asyncutil

CLIENT_ID = os.getenv("BATTLE_NET_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("BATTLE_NET_CLIENT_SECRET", "")
TOURNAMENT_ID = os.getenv("TOURNAMENT_ID", "5a0a5ab14bd47c09ac5e966b")

REGIONS = ["us", "eu", "kr"]
SEASONS = 2


def generate_player_summary(battlefy_player: str, ladder_team: dict) -> Tuple[str, str, int, str]:
    played_race_count = next(iter(ladder_team["member"][0].get("played_race_count", [])), {})
    battle_tag = ladder_team["member"][0].get("character_link", {}).get("battle_tag", "Unknown")
    race = played_race_count.get("race", {}).get("en_US", "Unknown")
    mmr = ladder_team.get("rating", 0)
    return battlefy_player, battle_tag, race, mmr


def canonicalise_battlefy_player(battlefy_player: str) -> str:
    special_characters_removed = re.sub(r'[^\w#]', " ", battlefy_player)
    valid_battle_tags = [
        battle_tag
        for battle_tag
        in special_characters_removed.split()
        if re.match(r'^\w+#\d+$', battle_tag)
    ]

    return next(iter(valid_battle_tags), "").casefold()


async def async_main():
    battlefy_teams = await battlefy.retrieve_battlefy_teams(TOURNAMENT_ID)
    battlefy_players = battlefy.extract_players(battlefy_teams)
    canonical_battlefy_players = [
        canonicalise_battlefy_player(battlefy_player) for battlefy_player in battlefy_players]

    async def retrieve_ladder_teams_for_region(region: str):
        access_token = await blizzard.get_access_token(CLIENT_ID, CLIENT_SECRET)
        ladder_ids = await blizzard.retrieve_ladder_ids_for_recent_seasons(access_token, SEASONS, region)

        def is_ladder_team_battlefy_player(ladder_team: dict) -> bool:
            return any(
                member.get("character_link", {}).get("battle_tag", "").casefold() in canonical_battlefy_players or
                member.get("legacy_link", {}).get("name", "").casefold() in canonical_battlefy_players
                for member
                in ladder_team.get("member", []))

        return await blizzard.retrieve_teams_matching_filter(
            ladder_ids,
            is_ladder_team_battlefy_player,
            access_token, region)

    ladder_teams = itertools.chain.from_iterable(
        await asyncutil.async_map(retrieve_ladder_teams_for_region, REGIONS))

    highest_ranked_ladder_teams_per_battle_tag = {}
    for ladder_team in ladder_teams:
        battle_tag = ladder_team["member"][0].get("character_link", {}).get("battle_tag", "").casefold()
        mmr = ladder_team.get("rating", 0)

        if mmr > highest_ranked_ladder_teams_per_battle_tag.get(battle_tag, {}).get("rating", 0):
            highest_ranked_ladder_teams_per_battle_tag[battle_tag] = ladder_team

    def generate_battlefy_team_summary(battlefy_team: dict) -> dict:

        team_players = [
            canonicalise_battlefy_player(player.get("inGameName", "")) or player.get("inGameName", "Unknown")
            for player
            in battlefy_team.get("players", [])]

        team_player_summaries = []
        for battlefy_player in team_players:
            if battlefy_player in highest_ranked_ladder_teams_per_battle_tag:
                team_player_summaries.append(
                    generate_player_summary(
                        battlefy_player, highest_ranked_ladder_teams_per_battle_tag[battlefy_player]))
            else:
                for ladder_team in highest_ranked_ladder_teams_per_battle_tag.values():
                    if battlefy_player == ladder_team["member"][0].get("legacy_link", {}).get("name", "").casefold():
                        team_player_summaries.append(
                            generate_player_summary(battlefy_player, ladder_team))
                        break
                else:
                    team_player_summaries.append((battlefy_player, "Unknown", "Unknown", 0))

        players = [
            {
                "battlefy_player": battlefy_player,
                "battle_tag": battle_tag,
                "race": race,
                "mmr": mmr
            }
            for battlefy_player, battle_tag, race, mmr
            in team_player_summaries]
        players.sort(key=lambda x: x["mmr"], reverse=True)

        ranked_mmrs = [mmr for _, _, _, mmr in team_player_summaries if mmr > 0]
        ranked_player_count = len(ranked_mmrs)
        average_ranked_mmr = sum(ranked_mmrs) // ranked_player_count if ranked_player_count else 0

        return {
            "name": battlefy_team.get("name", "Unknown"),
            "players": players,
            "average_ranked_mmr": average_ranked_mmr
        }

    battlefy_team_summaries = [
        generate_battlefy_team_summary(battlefy_team)
        for battlefy_team
        in battlefy_teams
    ]
    battlefy_team_summaries.sort(key=lambda x: x["average_ranked_mmr"], reverse=True)

    print(json.dumps(battlefy_team_summaries, indent=2))


def main():
    asyncio.get_event_loop().run_until_complete(async_main())


if __name__ == "__main__":
    main()
