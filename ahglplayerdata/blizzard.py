import asyncio
import itertools
from typing import Callable, List

import sc2gamedata

from . import asyncutil

LEAGUE_IDS = list(range(7))


async def get_access_token(client_id: str, client_secret: str) -> str:
    access_token_data = await asyncio.get_event_loop().run_in_executor(
        None, sc2gamedata.get_access_token, client_id, client_secret, "us")
    return access_token_data[0]


async def retrieve_ladder_ids_for_current_season(access_token: str, region: str) -> List[int]:
    current_season_data = await asyncio.get_event_loop().run_in_executor(
        None, sc2gamedata.get_current_season_data, access_token, region)
    current_season_id = current_season_data.get("id", 0)

    async def retrieve_leagues(league_id: int) -> dict:
        return await asyncio.get_event_loop().run_in_executor(
            None, sc2gamedata.get_league_data, access_token, current_season_id, league_id, region)

    league_data_list = await asyncutil.async_map(retrieve_leagues, LEAGUE_IDS)

    def extract_ladder_ids_from_league_data(league_data: dict) -> List[int]:
        tiers = league_data.get("tier", [])
        divisions = itertools.chain.from_iterable(tier.get("division", []) for tier in tiers)
        return [division.get("ladder_id", -1) for division in divisions]

    region_ladder_ids = [
        extract_ladder_ids_from_league_data(league_data) for league_data in league_data_list]

    return list(itertools.chain.from_iterable(region_ladder_ids))


async def retrieve_teams_matching_filter(
        ladder_ids: List[int],
        filter_func: Callable[[dict], bool],
        access_token: str,
        region: str
) -> List[dict]:

    async def fetch_and_filter_teams(ladder_id) -> List[dict]:
        ladder_data = await asyncio.get_event_loop().run_in_executor(
            None, sc2gamedata.get_ladder_data, access_token, ladder_id, region)
        return [team for team in ladder_data.get("team", {}) if filter_func(team)]

    teams = await asyncutil.async_map(fetch_and_filter_teams, ladder_ids)

    return list(itertools.chain.from_iterable(teams))

