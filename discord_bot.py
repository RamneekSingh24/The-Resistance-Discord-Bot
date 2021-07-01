import random

import discord
from discord.ext import tasks, commands
import game


class PlayGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.game_is_running = False
        self.game_is_started = False
        self.num_players = 0
        self.curr_game = None
        self.game_channel = None
        self.index = 0
        self.timer_message = None
        self.can_skip_timer = False
        # self.randomPrint.start()
        self.game_advancer.start()
        # self.printer.start()

        # Variables for saving player inputs:

        self.player_proposals = []  # List[player.id]
        self.player_votes = {}  # Dict[player.id, player.vote(0=for, 1=against)
        self.attack_choices = []  # List[int(0/1)] 0 = pass, 1 = fail
        self.proposed_attackers = []  # List[player.id]
        self.sent_attack_choice = []  # List[player.id]

    game_players = {}
    MAX_PLAYERS = 10
    MIN_PLAYERS = 1

    @commands.command()
    async def start_game(self, ctx):
        if self.game_is_running:
            await ctx.send(
                """A game is already running. A new game can only be started if the running game is over, or is ended by the bot owner.""")
        elif not self.bot.is_owner(ctx.author):
            await ctx.send('Game can be only started by the owner.')
        else:
            self.game_channel = ctx.channel
            self.game_is_started = True
            msg = 'Started Registration' + \
                  '\nPlayers can now register by using !register' + \
                  '\nGame will start once there are atleast 5 players and the bot owner enters !play_game'
            await ctx.send(msg)

    @commands.command()
    async def register(self, ctx):
        if self.game_is_running:
            return
        if not self.game_is_started:
            await ctx.send('Please contact the owner to start the game first using !start_game')
            return
        user_id = ctx.author.id
        if user_id in self.game_players:
            await ctx.send('Player {0.author.name} is already registered'.format(ctx))
        elif self.num_players == self.MAX_PLAYERS:
            await ctx.send('Reached max limit for players(10). Please join in the next game!')
        else:
            self.game_players[user_id] = ctx.author
            self.num_players = self.num_players + 1
            await ctx.send('Added {0.author.name} to the game! Number of players: '.format(ctx) + str(self.num_players))

    @commands.command()
    async def play_game(self, ctx):
        if self.game_is_running:
            await ctx.send("A game is already running!")
        elif not self.game_is_started:
            await ctx.send('Please contact the owner to start the game first using !start_game')
        elif self.num_players < self.MIN_PLAYERS:
            await ctx.send('Game can only be played with at-least 5 players.')
        # elif not self.bot.is_owner(ctx.author):
        #     await ctx.send('Game can be only started by the owner.')
        else:
            # players = List[(player_id, player_name)]
            self.game_is_running = True
            players = [(p.id, p.name) for p in self.game_players.values()]
            self.curr_game = game.Game(players)
            player_names = [self.game_players[player].name for player in self.game_players]
            await ctx.send('Starting Game with %d players: ' % self.num_players + str(player_names))

    @commands.command()
    async def propose_players(self, ctx, *args):
        if not self.game_is_running:
            return
        if not ctx.author.id == self.curr_game.get_leader_id():
            await ctx.send(f'{ctx.author.name}, you are not the leader for this round.')
        else:
            proposed_ids = set(args)
            if not len(proposed_ids) == self.curr_game.curr_round.num_players_to_propose:
                await ctx.send(f'{ctx.author.name}, Please propose the correct amount of players.')
            if not proposed_ids.issubset(set(self.game_players.keys())):
                await ctx.send(f'{ctx.author.name}, Please propose the correct amount of players.')
            else:
                self.player_proposals = list(proposed_ids)
                self.can_skip_timer = True
                await ctx.send('Noted proposal!')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        elif not isinstance(message.channel, discord.DMChannel):
            # await self.bot.process_commands(message)
            return
        else:
            await self.handle_dm(message)
            # await message.channel.send(f"hello {message.author.name}")

    @tasks.loop(seconds=2.0)
    async def printer(self):
        print(self.index)
        self.index += 1
        await self.send_time_left_message()

    # @tasks.loop(seconds=2.0)
    # async def randomPrint(self):
    #     myint = random.randint(0, 10)
    #     while True:
    #         print(myint)
    #         for server in self.bot.guilds:
    #             print('hi')
    #             print(server)
    #         time.sleep(3)
    #         break

    @tasks.loop(seconds=2.5)
    async def game_advancer(self):
        if not self.game_is_running:
            return
        else:
            try:
                if not (self.curr_game.curr_round.is_over() or self.can_skip_timer):
                    await self.send_time_left_message()
                else:
                    await self.adv_game()
                    self.can_skip_timer = False
            except:
                # TODO: complete error
                error = "error"
                await self.end_game(error)
                pass

    async def send_time_left_message(self):
        if self.game_channel is None:
            return
        # time_left = time.time()
        time_left = self.curr_game.curr_round.time_left()
        if self.timer_message is None:
            self.timer_message = await self.game_channel.send(time_left)
        else:
            await self.timer_message.edit(content=f'Time left for current round: {time_left}')

    async def adv_game(self):
        curr_round = self.curr_game.curr_round
        if isinstance(curr_round, game.RoundDiscussion):
            self.add_random_proposals()
            self.proposed_attackers = self.player_proposals
            msg = self.curr_game.advance_game(proposed_players=self.player_proposals)
            await self.game_channel.send(msg)
        elif isinstance(curr_round, game.RoundVoting):
            self.add_random_votes()
            msg = self.curr_game.advance_game(votes=self.player_votes)
            await self.game_channel.send(msg)
            if "Spies Won" in msg:
                await self.end_game()
            elif "Voting failed" in msg:
                self.player_proposals = []
                self.player_proposals = {}
                self.proposed_attackers = []

        elif isinstance(curr_round, game.RoundAttack):
            self.add_random_attack_choices()
            msg = self.curr_game.advance_game(attack_choices=self.attack_choices)
            await self.game_channel.send(msg)
            if "Resistance Won" in msg or "Spies Won" in msg:
                await self.end_game()
            else:
                self.player_proposals = []
                self.player_votes = {}
                self.attack_choices = []
                self.proposed_attackers = []
                self.sent_attack_choice = []

    async def end_game(self, error=None):
        if error is not None:
            await self.game_channel.send(f"Game ended due to an error.{error}")
        else:
            await self.game_channel.send("Game has ended")

        self.game_is_running = False
        self.game_is_started = False
        self.num_players = 0
        self.curr_game = None
        self.game_channel = None
        self.index = 0
        self.timer_message = None
        self.can_skip_timer = False
        # Variables for saving player inputs:
        self.player_proposals = []  # List[player.id]
        self.player_votes = {}  # Dict[player.id, player.vote(0=for, 1=against)
        self.attack_choices = []  # List[int(0/1)] 0 = pass, 1 = fail
        self.proposed_attackers = []  # List[player.id]
        self.sent_attack_choice = []  # List[player.id]

    def add_random_proposals(self):
        remaining = self.curr_game.curr_round.num_players_to_propose - len(self.player_proposals)
        for i in range(remaining):
            left_player_ids = [i for i in self.game_players.keys() if i not in self.player_proposals]
            rand_prop = random.choice(left_player_ids)
            self.player_proposals.append(rand_prop)

    def add_random_votes(self):
        remaining_players = [i for i in self.game_players.keys() if i not in self.player_votes]
        for pid in remaining_players:
            self.player_votes[pid] = random.randint(0, 1)

    def add_random_attack_choices(self):
        remaining = self.curr_game.curr_round.num_attackers - len(self.attack_choices)
        for i in range(remaining):
            self.attack_choices.append(0)  # Favor the resistance

    async def handle_dm_msg_discussion_round(self, message):
        await message.channel.send(f"Hi {message.author}, currently running discussion round. "
                                   f"If you are the leader please send a message for player proposals "
                                   f"in the games server's text channel.")

    async def handle_dm_msg_voting_round(self, message):
        msg = message.content.strip().lower()
        if "agree" in msg:
            self.player_votes[message.author.id] = 1
            await message.channel.send("Voted Recorded!")
        elif "disagree" in msg:
            self.player_votes[message.author.id] = 0
            await message.channel.send("Vote Recorded!")
        else:
            await message.channel.send("Currently running voting round. "
                                       "Please send a dm \'agree\' or \'disagree\' without quotes.")

    async def handle_dm_msg_attack_round(self, message):
        author_id = message.author.id
        if author_id not in self.proposed_attackers:
            await message.channel.send("Currently running attack round. You are not an attacker.")
        elif author_id in self.sent_attack_choice:
            await message.channel.send("You have already made your decision!")
        else:
            if "fail" in message.content:
                self.attack_choices.append(1)
                self.sent_attack_choice.append(author_id)
                await message.channel.send("Noted your choice.")
            elif "pass" in message.content:
                self.attack_choices.append(0)
                self.sent_attack_choice.append(author_id)
                await message.channel.send("Noted your choice.")
            else:
                await message.channel.send("Currently running attacking round. Please send \'pass\' "
                                           "or \'fail\', without quotes to register your choice. If you don't "
                                           "If you don't send your choice within the time left for this round. "
                                           "Your choice will be automatically taken as \'pass\'.")

    async def handle_dm(self, message):
        if not self.game_is_running:
            await message.channel.send(f"Hi, {message.author}, please wait for the game to start.")
            return
        if isinstance(self.curr_game.curr_round, game.RoundDiscussion):
            await self.handle_dm_msg_discussion_round(message)
        elif isinstance(self.curr_game.curr_round, game.RoundVoting):
            await self.handle_dm_msg_voting_round(message)
            if len(self.player_votes) == len(self.game_players):
                self.can_skip_timer = True
        elif isinstance(self.curr_game.curr_round, game.RoundAttack):
            await self.handle_dm_msg_attack_round(message)
            if len(self.attack_choices) == self.curr_game.curr_round.num_attackers:
                self.can_skip_timer = True


