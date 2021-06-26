import discord
from discord.ext import commands
import random
from discord_bot import PlayGame


intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


bot.add_cog(PlayGame(bot))
cog = bot.get_cog('PlayGame')
commands = cog.get_commands()
print([c.name for c in commands])
bot.run('enter your token hereß')