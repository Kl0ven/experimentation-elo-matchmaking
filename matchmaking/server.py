import asyncio
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional
from numpy import histogram, arange
import matplotlib.pyplot as plt
from tqdm import tqdm
from matchmaking.models import Game, Player, Team
from time import perf_counter

SAVE_FOLDER = "images/auto"


class PlayerStatus(Enum):
    IN_GAME = 1
    WAITING = 2


class PlayerStore:
    def __init__(self, players: List[Player]) -> None:
        self.players: Dict[Player, PlayerStatus] = {
            p: PlayerStatus.WAITING for p in players
        }

    def get(self, wanted_status: PlayerStatus):
        return [p for p, status in self.players.items() if status == wanted_status]

    def get_all(self):
        return [p for p, _ in self.players.items()]

    def set(self, players: List[Player], status: PlayerStatus):
        for player in players:
            self.players[player] = status
            player.last_played = datetime.now()
            player.last_played_ns = perf_counter()


class LivePlot:
    def __init__(
        self, player_store: PlayerStore, show_graph=False, smoothing=10
    ) -> None:
        self.players = player_store
        self.elo_plot_data = {p: [] for p in self.players.get_all()}
        self.latency_plot_data = {"avg": [], "max": [], "raw": []}
        self.show_live = show_graph
        self.cycle = 0
        self.running_average = smoothing
        self.latency_buffer = []
        shape = (4, 8)

        self.elo_plot = plt.subplot2grid(shape, (0, 0), colspan=6, rowspan=3)
        self.latency_plot = plt.subplot2grid(shape, (3, 0), colspan=6)
        self.latency_hist_plot = plt.subplot2grid(shape, (0, 6), rowspan=4, colspan=2)
        mng = plt.get_current_fig_manager()
        mng.full_screen_toggle()
        plt.tight_layout()
        plt.subplots_adjust(right=0.95)

    def show(self):
        if not self.show_live or self.cycle % 10 != 0:
            return
        self.__draw(self.elo_plot_data, self.latency_plot_data)
        plt.pause(0.1)

    def update_data(self):
        self.cycle += 1
        for player in self.players.get_all():
            self.elo_plot_data[player].append(player.elo)

        self.latency_plot_data["avg"].append(
            sum(self.latency_buffer) / len(self.latency_buffer)
        )

        self.latency_plot_data["max"].append(max(self.latency_buffer))

        self.latency_plot_data["raw"].extend(self.latency_buffer)

        self.latency_buffer = []

    def update_latency(self, players: List[Player]):
        now = perf_counter()
        self.latency_buffer.extend(
            (now - player.last_played_ns) * 1000 for player in players
        )

    def __preprocessing(self):
        processed_data = {}
        for player, data in self.elo_plot_data.items():
            processed_data[player] = []
            for i in range(len(data) - self.running_average):
                window = data[i : i + self.running_average]
                processed_data[player].append(sum(window) / self.running_average)

        for i in range(2):
            for name in self.latency_plot_data.keys():
                self.latency_plot_data[name][i] = 0

        return processed_data, self.latency_plot_data

    def __draw(self, elo_data, latency_data):
        self.elo_plot.clear()
        for player, elo in elo_data.items():
            self.elo_plot.plot(
                elo, label=str(player), color="red" if player.god else "grey"
            )
        self.elo_plot.legend(loc="upper right", ncol=2)

        self.latency_plot.clear()
        self.latency_plot.plot(latency_data["avg"], label="Average Latency")
        self.latency_plot.plot(latency_data["max"], label="Maximum Latency")
        self.latency_plot.legend(loc="upper right")

        self.latency_hist_plot.clear()
        counts, bins = histogram(
            latency_data["raw"], density=True, bins=arange(0.1, 1, 0.005)
        )
        self.latency_hist_plot.hist(bins[:-1], bins, weights=counts)

    def save(self):
        data = self.__preprocessing()
        self.__draw(*data)
        os.makedirs(SAVE_FOLDER, exist_ok=True)
        plt.gcf().set_size_inches(25, 10)
        plt.savefig(
            os.path.join(
                SAVE_FOLDER,
                datetime.now().strftime("%m-%d-%Y %H-%M-%S"),
            ),
            bbox_inches="tight",
            dpi=200,
        )
        plt.show()


class MatchMakerServer:
    def __init__(
        self,
        players,
        games_settings,
        max_round=None,
        show_graph=False,
        smoothing=10,
        god_boost=0.5,
    ) -> None:
        self.players = PlayerStore(players=players)
        self.games_settings = games_settings
        self.team_size = games_settings.get("team_size")
        self.team_number = games_settings.get("team_number")
        self.k_factor = games_settings.get("k-factor")
        self.nudge = games_settings.get("nudge")
        self.game_duration = games_settings.get("game_duration")
        self.active_games: Dict[Game, asyncio.Task] = {}
        self.max_round = max_round
        self.plot = LivePlot(self.players, show_graph, smoothing=smoothing)
        self.god_boost = god_boost

    def find_players(self, num_per_teams, num_teams) -> Optional[List[List[Player]]]:
        waiting_players = self.players.get(PlayerStatus.WAITING)
        waiting_players.sort(key=lambda x: x.last_played)
        if len(waiting_players) < num_per_teams * num_teams:
            return None

        # retrieve the player who waited the most
        first_player = waiting_players.pop(0)

        # add it to the buffer
        pending_players = [first_player]

        # sort remaining players by closest MMR
        waiting_players.sort(key=lambda x: abs(x.elo - first_player.elo))

        # complete the buffer with players
        pending_players = (
            pending_players + waiting_players[: num_per_teams * num_teams - 1]
        )

        # sort them by MMR
        # This way by putting p1 in t1, p2 in t2, p3 in t1
        # The t1 and t2 average will be close
        pending_players.sort(key=lambda x: x.elo)

        teams = []
        for i in range(num_teams):
            # take every `num_teams - i` players
            teams.append(team := pending_players[:: num_teams - i])
            # remove the player from the working buffer
            for player in team:
                pending_players.remove(player)

        return teams

    def try_create_game(self):
        players_teams = self.find_players(
            num_per_teams=self.team_size, num_teams=self.team_number
        )
        if players_teams is None:
            return
        teams = [Team(players=players) for players in players_teams]
        game = Game(teams=teams, nudge=self.nudge, god_boost=self.god_boost)
        self.plot.update_latency(player for _, player in game.players())

        self.players.set((player for _, player in game.players()), PlayerStatus.IN_GAME)
        self.active_games[game] = asyncio.create_task(game.run(self.game_duration))

    async def handle_games(self):
        finished_game = []
        for game, task in self.active_games.items():
            if not task.done():
                continue
            finished_game.append(game)
            task.result()
            game.update_elo(k_factor=self.k_factor)
            self.players.set(
                (player for _, player in game.players()), PlayerStatus.WAITING
            )
        for game in finished_game:
            self.active_games.pop(game, None)
        if finished_game:
            self.plot.update_data()

        return len(finished_game)

    async def run(self):
        if self.max_round:
            pbar = tqdm(total=self.max_round)
        round_finished = 0
        while True:
            self.try_create_game()
            finished_game = await self.handle_games()
            await asyncio.sleep(0.01)
            self.plot.show()
            if self.max_round:
                pbar.update(finished_game)
                round_finished += finished_game
                if round_finished > self.max_round:
                    self.plot.save()
                    break
