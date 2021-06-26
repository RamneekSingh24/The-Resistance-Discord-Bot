import enum
import random
import time
import discord

class GameType:
    def __init__(self, num_spies, rounds):
        self.num_spies = num_spies
        self.rounds = rounds


num_players_to_game_type = {
    1: GameType(1, [1, 1, 1, 1, 1]),
    5: GameType(2, [2, 3, 2, 3, 3]),
    6: GameType(3, [2, 3, 4, 3, 4]),
    7: GameType(3, [2, 3, 3, 4, 4]),
    8: GameType(3, [3, 4, 4, 5, 5]),
    9: GameType(3, [3, 4, 4, 5, 5]),
    10: GameType(4, [3, 4, 4, 5, 5])
}


class PlayerType(enum.Enum):
    resistance = 0
    spy = 1


class Round:
    def is_over(self) -> bool:
        pass

    def time_left(self) -> int:
        pass


class RoundDiscussion(Round):
    def __init__(self, num_players_to_propose):
        self.num_players_to_propose = num_players_to_propose
        self.start_time = time.time()

    def is_over(self):
        return time.time() - self.start_time > 20.0

    def time_left(self):
        return int(20.0 - time.time())


class RoundVoting(Round):
    def __init__(self, proposed_player_ids):
        self.start_time = time.time()
        self.proposed_players = proposed_player_ids

    def is_over(self):
        return time.time() - self.start_time > 45.0

    def time_left(self):
        return int(45.0 - time.time())

    def passed(self, votes):
        votes = list(votes.values())
        agree_count = votes.count(1)
        disagree_count = votes.count(0)
        return agree_count > disagree_count


class RoundAttack(Round):
    def __init__(self, num_attackers):
        self.start_time = time.time()
        self.num_attackers = num_attackers

    def is_over(self):
        return time.time() - self.start_time > 25.0

    def time_left(self):
        return int(25.0 - time.time())

    def spies_won_round(self, game_type, round_no, choices):
        required_fails = 2 if round_no == 4 and game_type.rounds[round_no] > 3 else 1
        return choices.count(1) >= required_fails


class Player:
    def __init__(self, player_id, player_name, player_type):
        self.player_id = player_id
        self.player_type = player_type
        self.player_name = player_name


class gameState(enum.Enum):
    discuss = 0
    voting = 1
    attack = 2


class Game:
    def __init__(self, players):
        # players = List[(player_id, player_name)]
        random.shuffle(players)
        self.game_type = num_players_to_game_type[len(players)]
        self.spies = random.sample(players, self.game_type.num_spies)
        self.leader_pos = 0
        self.players = [
            Player(player[0], player[1], PlayerType.spy if player[0] in self.spies else PlayerType.resistance)
            for player in players]
        self.players_dict = {player.player_id: player for player in self.players}
        self.rounds_won = {PlayerType.resistance: 0, PlayerType.spy: 0}

        self.curr_round_num = 0
        self.curr_state = None
        self.curr_round = None
        self.curr_num_voting_rounds = 0

    def start_game(self):
        # leader_id = self.players[self.leader_pos].player_id
        players_name_to_id = {p.player_name: p.player_id for p in self.players}
        leader_name = self.players[self.leader_pos].player_name
        msg = "Game has been started!\n Current Running  Round 1: Discussion Phase. Leader is %s." % leader_name
        msg += "\nThe registered players and their ids are: \n"
        msg += str(players_name_to_id)
        self.curr_round_num = 1
        self.curr_state = gameState.discuss
        self.curr_state = RoundDiscussion(self.game_type.rounds[self.curr_round])
        return msg

    def advance_game(self, proposed_players=None, votes=None, attack_choices=None):
        if isinstance(self.curr_round, RoundDiscussion):
            leader_name = self.players[self.leader_pos].player_name
            proposed_players_names = [self.players_dict[pid].player_name for pid in proposed_players]
            msg = f"Finished Discussion Round. Leader : {leader_name} has proposed % {proposed_players_names} to attack.\
            \n Please Vote on the proposal. Voting round has begun and will last 45.0 seconds." \
                  f" Please dm me agree or disagree to register your vote."
            self.curr_state = gameState.voting
            self.curr_round = RoundVoting(proposed_players)
            self.curr_num_voting_rounds += 1
            return msg

        elif isinstance(self.curr_round, RoundVoting):
            if not self.curr_round.passed(votes):
                if not self.curr_num_voting_rounds < 5:
                    return "Spies Won!"
                self.leader_pos = self.leader_pos + 1 % len(self.players)
                leader_name = self.players[self.leader_pos].player_name
                msg = f"Voting failed!. New Leader, {leader_name} please propose the players to attack."
                self.curr_state = gameState.discuss
                self.curr_round = RoundDiscussion(self.game_type.rounds[self.curr_round])
                return msg
            else:
                proposed_players_names = [self.players_dict[p].player_name for p in self.curr_round.proposed_players]
                msg = f"Voting passed. Players : {proposed_players_names} move on to the attacking round which has " \
                      f"begun! "
                self.curr_num_voting_rounds = 0
                self.curr_state = gameState.attack
                num_attackers = self.game_type.rounds[self.curr_round]
                self.curr_round = RoundAttack(num_attackers)
                return msg

        elif isinstance(self.curr_round, RoundAttack):
            who_won_round = "Resistance"
            if self.curr_round.spies_won_round(self.game_type, self.curr_round_num, attack_choices):
                self.rounds_won[PlayerType.spy] += 1
                who_won_round = "Spies"
            else:
                self.rounds_won[PlayerType.resistance] += 1

            if self.rounds_won[PlayerType.resistance] >= 3:
                msg = "Resistance Won!"
                return msg
            elif self.rounds_won[PlayerType.spy] >= 3:
                msg = "Spies Won!"
                return msg
            else:
                self.curr_round_num += 1
                msg = f"Round was won by {who_won_round}!. Current Score is:\n" \
                      f"Resistance: {self.rounds_won[PlayerType.resistance]}\n" \
                      f"Spies: {self.rounds_won[PlayerType.spy]}\n" \
                      f"Moving on to Round no: {self.curr_round_num} discussion phase"
                self.curr_state = gameState.discuss
                self.curr_round = RoundDiscussion()
                return msg

        else:
            return "Game has not been Started"

    def get_leader_id(self):
        return self.players[self.leader_pos].player_id



