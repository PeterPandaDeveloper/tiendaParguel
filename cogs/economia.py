import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite

# ⚠️ Configuración de tu bot
EMOTE = "<:ricomacpato:AQUI_PONES_EL_ID>" 
ROL_OFICIAL = "Tesorero" # El nombre exacto del rol que podrá usar comandos de admin

# Candado de seguridad personalizado para Oficiales del Barco
def check_oficial():
    def predicate(interaction: discord.Interaction) -> bool:
        # Pasa si es administrador de Discord
        if interaction.user.guild_permissions.administrator:
            return True
        # Pasa si tiene el rol específico
        if any(rol.name.lower() == ROL_OFICIAL.lower() for rol in interaction.user.roles):
            return True
        return False
    return app_commands.check(predicate)


class Economia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/pauliales.db"

    # Se ejecuta al encender el bot para preparar las tablas
    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Tabla de dinero
            await db.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    user_id INTEGER PRIMARY KEY,
                    pauliales INTEGER DEFAULT 0
                )
            ''')
            # NUEVA: Tabla de inventarios (Mochilas de los jugadores)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventarios (
                    user_id INTEGER,
                    item_id TEXT,
                    nombre_item TEXT,
                    cantidad INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_id)
                )
            ''')
            await db.commit()

    # Funciones internas para el dinero
    async def actualizar_balance(self, user_id: int, cantidad: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT pauliales FROM usuarios WHERE user_id = ?', (user_id,)) as cursor:
                fila = await cursor.fetchone()
                if fila:
                    nuevo_saldo = max(0, fila[0] + cantidad)
                    await db.execute('UPDATE usuarios SET pauliales = ? WHERE user_id = ?', (nuevo_saldo, user_id))
                else:
                    nuevo_saldo = max(0, cantidad)
                    await db.execute('INSERT INTO usuarios (user_id, pauliales) VALUES (?, ?)', (user_id, nuevo_saldo))
            await db.commit()
            return nuevo_saldo

    async def obtener_balance(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT pauliales FROM usuarios WHERE user_id = ?', (user_id,)) as cursor:
                fila = await cursor.fetchone()
                return fila[0] if fila else 0

    # ---------------- COMANDOS DE TRIPULACIÓN (PÚBLICOS) ----------------

    @app_commands.command(name="pt-billetera", description="Revisa cuántos pauliales tienes en tus bolsillos")
    async def cartera(self, interaction: discord.Interaction):
        saldo = await self.obtener_balance(interaction.user.id)
        await interaction.response.send_message(f"🪵 Tienes **{saldo}** {EMOTE} pauliales guardados.", ephemeral=True)

    @app_commands.command(name="pt-transferir", description="Transfiere pauliales a otro jugador")
    async def transferir(self, interaction: discord.Interaction, receptor: discord.Member, cantidad: int):
        if cantidad <= 0:
            return await interaction.response.send_message("❌ Debes transferir una cantidad mayor a 0.", ephemeral=True)
        
        saldo_emisor = await self.obtener_balance(interaction.user.id)
        if saldo_emisor < cantidad:
            return await interaction.response.send_message(f"❌ No tienes suficientes pauliales. Tienes **{saldo_emisor}** {EMOTE}.", ephemeral=True)
            
        await self.actualizar_balance(interaction.user.id, -cantidad)
        await self.actualizar_balance(receptor.id, cantidad)
        await interaction.response.send_message(f"💸 Has transferido **{cantidad}** {EMOTE} pauliales a {receptor.mention}.")

    @app_commands.command(name="pt-inventario", description="Abre tu mochila y mira tus tesoros comprados")
    async def inventario(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT nombre_item, cantidad FROM inventarios WHERE user_id = ? AND cantidad > 0', (interaction.user.id,)) as cursor:
                items = await cursor.fetchall()
        
        if not items:
            return await interaction.response.send_message("🕸️ Tu mochila está vacía. Ve a la tienda de Barba Enraizada a comprar algo.", ephemeral=True)
            
        embed = discord.Embed(title=f"🎒 Inventario de {interaction.user.display_name}", color=discord.Color.dark_gold())
        for item in items:
            nombre, cantidad = item
            embed.add_field(name=nombre, value=f"Cantidad: **x{cantidad}**", inline=False)
            
        await interaction.response.send_message(embed=embed)

    # ---------------- COMANDOS DE OFICIALES (ADMINS/TESOREROS) ----------------

    @app_commands.command(name="pt-dar-pauliales", description="(Oficial) Otorga pauliales a un jugador")
    @check_oficial()
    async def dar(self, interaction: discord.Interaction, jugador: discord.Member, cantidad: int):
        nuevo_saldo = await self.actualizar_balance(jugador.id, cantidad)
        await interaction.response.send_message(f"✅ Se han otorgado **{cantidad}** {EMOTE} a {jugador.mention}. Su nuevo saldo es: **{nuevo_saldo}**.")

    @app_commands.command(name="pt-remover-pauliales", description="(Oficial) Quita pauliales a un jugador")
    @check_oficial()
    async def remover(self, interaction: discord.Interaction, jugador: discord.Member, cantidad: int):
        nuevo_saldo = await self.actualizar_balance(jugador.id, -cantidad)
        await interaction.response.send_message(f"🔨 Se han retirado **{cantidad}** {EMOTE} a {jugador.mention}. Su nuevo saldo es: **{nuevo_saldo}**.")

    # Manejo de errores por si alguien sin permiso intenta usar comandos de oficial
    @dar.error
    @remover.error
    async def permisos_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"🏴‍☠️ ¡Atrás, grumete! Necesitas el rol de **{ROL_OFICIAL}** o ser Administrador para usar esto.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economia(bot))