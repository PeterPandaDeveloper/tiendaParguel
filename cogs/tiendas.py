import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from utils.ui_barco import VistaTienda

COMPARTIMIENTOS_PATH = "data/compartimientos/"
ROL_OFICIAL = "Tesorero" # Candado de seguridad para oficiales

def check_oficial():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if any(rol.name.lower() == ROL_OFICIAL.lower() for rol in interaction.user.roles):
            return True
        return False
    return app_commands.check(predicate)

class Tiendas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pt-elegir-tienda", description="Abre la bodega de carga de El Brote Hundido")
    async def abrir_tienda(self, interaction: discord.Interaction):
        # Escanear archivos JSON en la carpeta de compartimientos
        archivos = [f for f in os.listdir(COMPARTIMIENTOS_PATH) if f.endswith('.json')]
        
        if not archivos:
            return await interaction.response.send_message("🪵 Las compuertas de El Brote Hundido están selladas. No hay bodegas disponibles.", ephemeral=True)

        opciones = []
        # Leemos rápidamente los JSON para extraer los nombres, descripciones y emojis
        for archivo in archivos:
            with open(os.path.join(COMPARTIMIENTOS_PATH, archivo), 'r', encoding='utf-8') as f:
                data = json.load(f)
                opciones.append(discord.SelectOption(
                    label=data['nombre_tienda'], 
                    description=data['descripcion'][:50], 
                    emoji=data['emoji'], 
                    value=archivo
                ))

        class SelectorCompartimientos(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="⚓ Inspeccionar bodegas del barco...", min_values=1, max_values=1, options=opciones)

            async def callback(self, inter: discord.Interaction):
                archivo_seleccionado = self.values[0]
                with open(os.path.join(COMPARTIMIENTOS_PATH, archivo_seleccionado), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                embed = discord.Embed(
                    title=f"{data['emoji']} {data['nombre_tienda']}",
                    description=f"*{data['descripcion']}*\n\nRevisa los suministros disponibles abajo.",
                    color=discord.Color.dark_green()
                )
                
                await inter.response.send_message(embed=embed, view=VistaTienda(archivo_seleccionado), ephemeral=True)

        vista = discord.ui.View()
        vista.add_item(SelectorCompartimientos())
        
        await interaction.response.send_message("🌊 **Has abordado 'El Brote Hundido'.**\nLa madera cruje bajo tus pies mientras las raíces se apartan en la bodega. ¿Qué compartimiento vas a revisar?", view=vista, ephemeral=True)

    @app_commands.command(name="pt-restock", description="(Oficial) Rellena el stock de todas las tiendas")
    @check_oficial()
    async def restock(self, interaction: discord.Interaction):
        archivos = [f for f in os.listdir(COMPARTIMIENTOS_PATH) if f.endswith('.json')]
        tiendas_actualizadas = 0
        
        for archivo in archivos:
            ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo)
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for obj in data['objetos']:
                obj['stock_actual'] = obj['stock_maximo']
                
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            tiendas_actualizadas += 1
            
        await interaction.response.send_message(f"📦 ¡Restock completo! Las raíces han reabastecido **{tiendas_actualizadas}** compartimientos al máximo.")

    # Manejo de errores de permisos para el comando pt-restock
    @restock.error
    async def restock_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"🏴‍☠️ ¡Atrás, grumete! Necesitas el rol de **{ROL_OFICIAL}** o ser Administrador para solicitar un reabastecimiento.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tiendas(bot))