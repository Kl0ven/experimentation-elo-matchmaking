from matchmaking.server import MatchMakerServer
from matchmaking.models import Player
from matchmaking.utils import setup_logger
import asyncio
import random


TEAM_SIZE = 5
TEAM_NUMBER = 2
NUM_PLAYER = TEAM_SIZE * TEAM_NUMBER * 5 + 1

if __name__ == "__main__":
    setup_logger()
    players = [
        Player(i, true_rating=random.randint(200, 200), elo=random.randint(1000, 2000))
        for i in range(NUM_PLAYER)
    ]
    for player in players[:5]:
        player.god = True
        player.elo = 1000
    server = MatchMakerServer(
        players,
        games_settings={
            "game_duration": 0.01,
            "team_size": TEAM_SIZE,
            "team_number": TEAM_NUMBER,
            "k-factor": 20,
            "nudge": None,
        },
        smoothing=100,
        max_round=100000,
        show_graph=False,
        god_boost=2,
    )

    asyncio.run(server.run())
