import asyncio
import json
import os
from typing import Tuple

import itertools

from ahglplayerdata import battlefy, blizzard, asyncutil

CLIENT_ID = os.getenv("BATTLE_NET_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("BATTLE_NET_CLIENT_SECRET", "")
API_KEY = os.getenv("BATTLE_NET_API_KEY", "")
TOURNAMENT_ID = os.getenv("TOURNAMENT_ID", "")

REGIONS = ["us", "eu", "kr"]


def generate_player_summary(ladder_team: dict) -> Tuple[int, str]:
    played_race_count = next(iter(ladder_team["member"][0].get("played_race_count", [])), {})
    race = played_race_count.get("race", {}).get("en_US", "Unknown")
    mmr = ladder_team.get("rating", 0)
    return race, mmr


async def async_main():
    battlefy_teams = await battlefy.retrieve_battlefy_teams(TOURNAMENT_ID)
    battlefy_players = battlefy.extract_players(battlefy_teams)

    async def retrieve_ladder_teams_for_region(region: str):
        access_token = await blizzard.get_access_token(CLIENT_ID, CLIENT_SECRET)
        ladder_ids = await blizzard.retrieve_ladder_ids_for_current_season(access_token, region)

        def is_ladder_team_battlefy_player(ladder_team: dict) -> bool:
            return any(
                member.get("character_link", {}).get("battle_tag", "") in battlefy_players
                for member
                in ladder_team.get("member", []))

        return await blizzard.retrieve_teams_matching_filter(
            ladder_ids,
            is_ladder_team_battlefy_player,
            access_token, region)

    ladder_teams = itertools.chain.from_iterable(
        await asyncutil.async_map_ignore_failed(retrieve_ladder_teams_for_region, REGIONS))

    highest_ranked_ladder_teams_per_player = {}
    for ladder_team in ladder_teams:
        battle_tag = ladder_team["member"][0]["character_link"]["battle_tag"]
        mmr = ladder_team.get("rating", 0)

        if mmr > highest_ranked_ladder_teams_per_player.get(battle_tag, {}).get("rating", 0):
            highest_ranked_ladder_teams_per_player[battle_tag] = ladder_team

    player_summaries = dict(
        (battle_tag, generate_player_summary(ladder_team))
        for battle_tag, ladder_team
        in highest_ranked_ladder_teams_per_player.items())

    def generate_battlefy_team_summary(battlefy_team: dict) -> dict:

        team_battle_tags = [
            player.get("inGameName", "Unknown")
            for player
            in battlefy_team.get("players", [])]

        team_player_summaries = [
            player_summaries.get(battle_tag, ("Unknown", 0))
            for battle_tag
            in team_battle_tags]

        players = [
            {
                "name": name,
                "race": race,
                "mmr": mmr
            }
            for name, race, mmr
            in (zip(team_battle_tags, *zip(*team_player_summaries)))]
        players.sort(key=lambda x: x["mmr"], reverse=True)

        ranked_mmrs = [mmr for _, mmr in team_player_summaries if mmr > 0]
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
