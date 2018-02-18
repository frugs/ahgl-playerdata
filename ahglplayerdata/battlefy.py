from typing import List, Set

import aiohttp
import itertools

URL_TEMPLATE = "https://dtmwra1jsgyb0.cloudfront.net/tournaments/{tournament_id}/teams?page={page}&limit={limit}"
LIMIT = 500


async def retrieve_battlefy_teams(tournament_id: str) -> List[dict]:
    with aiohttp.ClientSession() as session:

        async def retrieve_page(page_no: int) -> List[dict]:
            resp = await session.request(
                    "GET",
                    URL_TEMPLATE.format(tournament_id=tournament_id, page=page_no, limit=LIMIT))
            return await resp.json() if resp.status == 200 else []

        teams = []
        current_page = 1
        while True:
            page_data = await retrieve_page(current_page)

            if not page_data:
                break

            teams.extend(page_data)
            current_page += 1

        return teams


def extract_players(battlefy_teams: List[dict]) -> Set[str]:
    return set(itertools.chain.from_iterable(
        [player.get("inGameName", "") for player in team.get("players", [])]
        for team
        in battlefy_teams))