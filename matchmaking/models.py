from typing import List, Iterator, Tuple
from enum import Enum
from logging import getLogger
from collections import defaultdict
import asyncio
import random
from string import ascii_lowercase
from datetime import datetime
from time import perf_counter

logger = getLogger(__file__)


class GameOutcome(Enum):
    P1_WIN = "P1_WIN"
    P2_WIN = "P2_WIN"
    DRAW = "DRAW"


class Player:
    def __init__(self, name, true_rating=100, elo=100, god=False) -> None:
        self._elo = elo
        self.name = name
        self.last_played = datetime.now()
        self.last_played_ns = perf_counter()
        self.god = god
        self.true_rating = true_rating
        self.win, self.lose = 0, 0

    @property
    def elo(self):
        return self._elo

    @elo.setter
    def elo(self, new_elo):
        logger.info("Update ELO of %s from %s to %s", self, self._elo, new_elo)
        self._elo = new_elo

    @property
    def rating(self):
        return 10 ** (self.elo / 400)

    def __str__(self) -> str:
        god = "god" if self.god else ""
        return f"Player {self.name} {self.ratio:.2} {god}".strip()

    @property
    def ratio(self):
        total = self.win + self.lose
        return self.win / total if total > 0 else 0.0

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return hash(self.name)

    def get_elo_delta(self, other: "Player", result: GameOutcome, k_factor=32):
        rating_1 = self.rating
        rating_2 = other.rating
        expected_1 = rating_1 / (rating_1 + rating_2)

        if result == GameOutcome.DRAW:
            score_1 = 0.5
        else:
            score_1 = 1 if result == GameOutcome.P1_WIN else 0

        return k_factor * (score_1 - expected_1)

    def nudge(self, nudge):
        direction = 0 if self.god else random.randint(0, 1)
        if direction:
            self.true_rating -= nudge
        else:
            self.true_rating += nudge

        self.true_rating = max(0, self.true_rating)

    def add_win(self):
        self.win += 1

    def add_lose(self):
        self.lose += 1


class Team:
    def __init__(self, players: List[Player]) -> None:
        self.players = set(players)
        self._score = None

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, score):
        self._score = score

    def compare(self, other: "Team"):
        if self.score > other.score:
            return GameOutcome.P1_WIN
        if self.score < other.score:
            return GameOutcome.P2_WIN
        return GameOutcome.DRAW


class Game:
    def __init__(self, teams: List[Team], nudge=0, god_boost=0.5) -> None:
        self.teams = teams
        self.tag = "".join(random.choice(ascii_lowercase) for _ in range(5))
        self.nudge = nudge
        self.god_boost = god_boost

    def players(self, ignore_team=None) -> Iterator[Tuple[Team, Player]]:
        for team in self.teams:
            if team == ignore_team:
                continue
            for player in team.players:
                yield team, player

    def update_elo(self, k_factor=32):
        delta = defaultdict(list)
        for team, player in self.players():
            for other_team, other_player in self.players(ignore_team=team):
                outcome = team.compare(other_team)
                if outcome == GameOutcome.P1_WIN:
                    player.add_win()
                elif outcome == GameOutcome.P2_WIN:
                    player.add_lose()
                delta[player].append(
                    player.get_elo_delta(other_player, outcome, k_factor=k_factor)
                )

        for player, player_deltas in delta.items():
            player.elo = player.elo + sum(player_deltas) / len(player_deltas)
            if self.nudge:
                player.nudge(self.nudge)

    def compute_score(self):
        teams_elo = {}
        for team in self.teams:
            if self.nudge:
                true_rating = [p.true_rating for p in team.players]
            else:
                true_rating = [p.elo for p in team.players]

            nb_god = len([p for p in team.players if p.god])
            avg = sum(true_rating) / len(true_rating)
            teams_elo[team] = avg + (avg * self.god_boost * nb_god)

        results = []
        for _ in self.teams:
            (team,) = random.choices(
                list(teams_elo.keys()), list(teams_elo.values()), k=1
            )
            teams_elo.pop(team)
            results.append(team)

        for score, team in enumerate(results[::-1]):
            team.score = score

    async def run(self, duration: int):
        logger.info("Game %s started", self.tag)
        await asyncio.sleep(duration)
        self.compute_score()
        logger.info("Game %s finished", self.tag)
