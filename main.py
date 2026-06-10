import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class BarbaEnraizadaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='be!', intents=intents)

    async def setup_hook(self):
        # Cargar todos los cogs de la carpeta cogs/
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Cog cargado: {filename}")
                except Exception as e:
                    print(f"❌ Error cargando {filename}: {e}")
        
        # Sincronizar comandos slash
        await self.tree.sync()
        print("🌐 Slash commands sincronizados con Discord.")

bot = BarbaEnraizadaBot()

@bot.event
async def on_ready():
    print(f'🏴‍☠️ {bot.user} ha zarpado. La madera cruje y el bot está en línea.')
    # Opcional: mostrar comandos registrados
    print(f"Comandos disponibles: {[cmd.name for cmd in bot.tree.get_commands()]}")

if __name__ == '__main__':
    if not TOKEN:
        print("❌ ERROR: No se encontró DISCORD_TOKEN en el archivo .env")
    else:
        bot.run(TOKEN)