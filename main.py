import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class BarbaEnraizadaBot(commands.Bot):
    def __init__(self):
        # Configuramos los intents básicos
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='be!', intents=intents)

    async def setup_hook(self):
        # El barco despierta y carga sus compartimientos (Cogs)
        await self.load_extension('cogs.economia')
        await self.load_extension('cogs.tiendas') # Lo activaremos cuando hagamos las tiendas
        
        # Sincronizamos los comandos / con Discord
        await self.tree.sync()
        print("🌐 Slash commands del Barba Enraizada sincronizados.")

bot = BarbaEnraizadaBot()

@bot.event
async def on_ready():
    print(f'🏴‍☠️ {bot.user} ha zarpado. La madera cruje y el bot está en línea.')

if __name__ == '__main__':
    bot.run(TOKEN)