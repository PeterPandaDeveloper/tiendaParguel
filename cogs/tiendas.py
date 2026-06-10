import discord
from discord.ext import commands
from discord import app_commands
import os
import json
from utils.ui_barco import VistaTienda

COMPARTIMIENTOS_PATH = "data/compartimientos/"
ROL_OFICIAL_ID = 0  # ¡CAMBIA AQUÍ! Mismo ID que en economia.py

def check_oficial():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if any(rol.id == ROL_OFICIAL_ID for rol in interaction.user.roles):
            return True
        return False
    return app_commands.check(predicate)

class Tiendas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        if not os.path.exists(COMPARTIMIENTOS_PATH):
            os.makedirs(COMPARTIMIENTOS_PATH, exist_ok=True)
            print(f"📁 Creada carpeta {COMPARTIMIENTOS_PATH}")

    @app_commands.command(name="pt-elegir-tienda", description="Abre la bodega de carga de El Brote Hundido")
    async def abrir_tienda(self, interaction: discord.Interaction):
        if not os.path.exists(COMPARTIMIENTOS_PATH):
            return await interaction.response.send_message("📁 La bodega aún no tiene compartimientos. Contacta a un oficial.", ephemeral=True)

        archivos = [f for f in os.listdir(COMPARTIMIENTOS_PATH) if f.endswith('.json')]
        if not archivos:
            return await interaction.response.send_message("🪵 Las compuertas están selladas. No hay bodegas disponibles.", ephemeral=True)

        opciones = []
        for archivo in archivos:
            ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo)
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
                desc = data.get('descripcion') or data.get('description', 'Sin descripción')
                opciones.append(discord.SelectOption(
                    label=data['nombre_tienda'],
                    description=desc[:50],
                    emoji=data['emoji'],
                    value=archivo
                ))

        class SelectorCompartimientos(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="⚓ Inspeccionar bodegas...", min_values=1, max_values=1, options=opciones)

            async def callback(self, inter: discord.Interaction):
                archivo_seleccionado = self.values[0]
                ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo_seleccionado)
                with open(ruta, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                embed = discord.Embed(
                    title=f"{data['emoji']} {data['nombre_tienda']}",
                    description=f"*{data.get('descripcion') or data.get('description', '')}*\n\nRevisa los suministros disponibles abajo.",
                    color=discord.Color.dark_green()
                )
                objetos = data.get('objetos') or data.get('objects', [])
                if objetos:
                    texto = ""
                    for obj in objetos[:5]:
                        texto += f"• **{obj['nombre']}** - {obj['precio']} pauliales (stock: {obj['stock_actual']}/{obj['stock_maximo']})\n"
                    if len(objetos) > 5:
                        texto += f"... y {len(objetos)-5} más."
                    embed.add_field(name="Algunos tesoros", value=texto, inline=False)
                await inter.response.send_message(embed=embed, view=VistaTienda(archivo_seleccionado, self.bot), ephemeral=True)

        vista = discord.ui.View()
        vista.add_item(SelectorCompartimientos())
        await interaction.response.send_message("🌊 **Has abordado 'El Brote Hundido'.**\nLa madera cruje bajo tus pies mientras las raíces se apartan en la bodega. ¿Qué compartimiento vas a revisar?", view=vista, ephemeral=True)

    @app_commands.command(name="pt-restock", description="(Oficial) Rellena el stock de todas las tiendas")
    @check_oficial()
    async def restock(self, interaction: discord.Interaction):
        if not os.path.exists(COMPARTIMIENTOS_PATH):
            return await interaction.response.send_message("No existe la carpeta de tiendas.", ephemeral=True)
        archivos = [f for f in os.listdir(COMPARTIMIENTOS_PATH) if f.endswith('.json')]
        tiendas_actualizadas = 0
        for archivo in archivos:
            ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo)
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
            objetos = data.get('objetos') or data.get('objects', [])
            for obj in objetos:
                obj['stock_actual'] = obj['stock_maximo']
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            tiendas_actualizadas += 1
        await interaction.response.send_message(f"📦 ¡Restock completo! Se reabastecieron **{tiendas_actualizadas}** compartimientos.")

    @app_commands.command(name="pt-tienda-info", description="Muestra detalles de una tienda sin entrar a comprar")
    async def tienda_info(self, interaction: discord.Interaction, nombre_tienda: str):
        if not os.path.exists(COMPARTIMIENTOS_PATH):
            return await interaction.response.send_message("No hay tiendas registradas.", ephemeral=True)
        archivos = [f for f in os.listdir(COMPARTIMIENTOS_PATH) if f.endswith('.json')]
        encontrado = None
        for archivo in archivos:
            ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo)
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if nombre_tienda.lower() in data['nombre_tienda'].lower():
                    encontrado = data
                    break
        if not encontrado:
            return await interaction.response.send_message("No encontré esa tienda. Usa `/pt-elegir-tienda` para ver las disponibles.", ephemeral=True)
        embed = discord.Embed(title=f"{encontrado['emoji']} {encontrado['nombre_tienda']}", color=discord.Color.blue())
        embed.description = encontrado.get('descripcion') or encontrado.get('description', 'Sin descripción')
        objetos = encontrado.get('objetos') or encontrado.get('objects', [])
        for obj in objetos:
            embed.add_field(name=obj['nombre'], value=f"Precio: {obj['precio']} pauliales\nStock: {obj['stock_actual']}/{obj['stock_maximo']}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @restock.error
    async def restock_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"🏴‍☠️ Necesitas el rol **Tesorero** o ser Administrador para reabastecer.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tiendas(bot))