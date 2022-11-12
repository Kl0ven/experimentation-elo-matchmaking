# Elo matchmaking experimentation

This experimentation tries to implement a Skill Based Match Making SBMM.

We have a pool of player with an ELO rating. The SBMM Server tries to create games with N teams of M players

## Match Making

The match making is done by taking the player $\operatorname{P}(1)$ who waited the most in the queue. Then we order the other waiting player by the closest ELO from $\operatorname{P}(1)$ by using $\lvert \operatorname{ELO}(\operatorname{P}(1)) - \operatorname{ELO}(\operatorname{P}(x)) \rvert$. We then create a new list with $\operatorname{P}(1)$ and add $num\_team \times num\_per\_team - 1$ new player from the ordered list. With this new list we put (assuming `num_team = 2`)

- first element in the first team
- second in second team
- third in first team
- fourth in second team
- and so on

We now have 2 Team with a roughly equivalent ELO average.

With this technics a weird edge case happened, where if the `total_number_of_player` is a multiple of $num\_team \times num\_per\_team$ , With $N = total\_number\_of\_player /( num\_team \times num\_per\_team)$  
N group will be formed, and those groupes will stay separated:

![elo-matchmaking-multiple.png](https://raw.githubusercontent.com/Kl0ven/experimentation-elo-matchmaking/main/images/elo-matchmaking-multiple.png)

But if we set $total\_number\_of\_player =  num\_team \times num\_per\_team \times N + 1$
All groupes merges into one.

![elo-matchmaking-not-multiple.png](https://raw.githubusercontent.com/Kl0ven/experimentation-elo-matchmaking/main/images/elo-matchmaking-not-multiple.png)

## Skills

I have added "God" Player as seen in red, Those player have a advantage when it comes to winning a game. With this advantage we can see the going up the rank consistently.

![elo-matchmaking-god-players.png](https://raw.githubusercontent.com/Kl0ven/experimentation-elo-matchmaking/main/images/elo-matchmaking-god-players.png)

## usage

```bash
poetry install
poetry run main.py # compute then save images in images/auto
```

configuration in `main.py`

```python
    server = MatchMakerServer(
        players,
        games_settings={
            "game_duration": 0.01,  # game simulation time
            "team_size": TEAM_SIZE, # number of players per team
            "team_number": TEAM_NUMBER, # number of teams per game
            "k-factor": 20, # elo k-factor
            "nudge": None, # nudge = 0.1 => randomly nudge MMR by 0.1; Very unstable
        },
        smoothing=100, # curve running average
        max_round=100000, # number of game simulated
        show_graph=False, # show live graph; will slow down the simulation
        god_boost=2, # gop player have a 2 times boost on chance to win
    )

```
