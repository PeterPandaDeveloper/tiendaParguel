import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import random
from datetime import date

EMOTE = "<:ricomacpato:1514136285584031784>"
ROL_OFICIAL_ID = 0  # CAMBIA AQUÍ

def check_oficial():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if any(rol.id == ROL_OFICIAL_ID for rol in interaction.user.roles):
            return True
        return False
    return app_commands.check(predicate)


class Economia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/pauliales.db"

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    user_id INTEGER PRIMARY KEY,
                    pauliales INTEGER DEFAULT 0
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventarios (
                    user_id INTEGER,
                    item_id TEXT,
                    nombre_item TEXT,
                    cantidad INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, item_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS diario (
                    user_id INTEGER PRIMARY KEY,
                    ultima_recompensa DATE
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tipo TEXT,
                    cantidad INTEGER,
                    saldo_despues INTEGER,
                    detalles TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
        print("✅ Base de datos de economía lista (sin trabajo, saldo inicial 5)")

    async def registrar_auditoria(self, user_id: int, tipo: str, cantidad: int, saldo_despues: int, detalles: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO auditoria (user_id, tipo, cantidad, saldo_despues, detalles)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, tipo, cantidad, saldo_despues, detalles))
            await db.commit()

    async def asegurar_usuario(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT 1 FROM usuarios WHERE user_id = ?', (user_id,)) as cursor:
                if not await cursor.fetchone():
                    # Saldo inicial: 5 pauliales
                    await db.execute('INSERT INTO usuarios (user_id, pauliales) VALUES (?, ?)', (user_id, 5))
                    await db.commit()
                    return 5
        return 0

    async def obtener_balance(self, user_id: int):
        await self.asegurar_usuario(user_id)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT pauliales FROM usuarios WHERE user_id = ?', (user_id,)) as cursor:
                fila = await cursor.fetchone()
                return fila[0] if fila else 0

    async def actualizar_balance(self, user_id: int, cantidad: int, tipo: str = "desconocido", detalles: str = ""):
        await self.asegurar_usuario(user_id)
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
        if tipo != "desconocido":
            await self.registrar_auditoria(user_id, tipo, cantidad, nuevo_saldo, detalles)
        return nuevo_saldo

    # --------------------- COMANDOS PÚBLICOS ---------------------
    @app_commands.command(name="pt-billetera", description="Revisa cuántos pauliales tienes")
    async def cartera(self, interaction: discord.Interaction):
        saldo = await self.obtener_balance(interaction.user.id)
        await interaction.response.send_message(f"🪵 Tienes **{saldo}** {EMOTE} pauliales guardados.", ephemeral=True)

    @app_commands.command(name="pt-transferir", description="Transfiere pauliales a otro jugador")
    async def transferir(self, interaction: discord.Interaction, receptor: discord.Member, cantidad: int):
        if cantidad <= 0:
            return await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        saldo = await self.obtener_balance(interaction.user.id)
        if saldo < cantidad:
            return await interaction.response.send_message(f"❌ No tienes suficientes. Tienes {saldo} {EMOTE}.", ephemeral=True)
        await self.actualizar_balance(interaction.user.id, -cantidad, "transferencia_salida", f"Envió {cantidad} a {receptor.id}")
        await self.actualizar_balance(receptor.id, cantidad, "transferencia_entrada", f"Recibió {cantidad} de {interaction.user.id}")
        await interaction.response.send_message(f"💸 Transferiste **{cantidad}** {EMOTE} a {receptor.mention}.")

    @app_commands.command(name="pt-inventario", description="Muestra tu mochila")
    async def inventario(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT nombre_item, cantidad FROM inventarios WHERE user_id = ? AND cantidad > 0', (interaction.user.id,)) as cursor:
                items = await cursor.fetchall()
        if not items:
            return await interaction.response.send_message("🕸️ Tu mochila está vacía. Ve a la tienda.", ephemeral=True)
        embed = discord.Embed(title=f"🎒 Inventario de {interaction.user.display_name}", color=discord.Color.dark_gold())
        for nombre, cantidad in items:
            embed.add_field(name=nombre, value=f"Cantidad: **x{cantidad}**", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pt-diario", description="Reclama tu recompensa diaria")
    async def diario(self, interaction: discord.Interaction):
        hoy = date.today()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT ultima_recompensa FROM diario WHERE user_id = ?', (interaction.user.id,)) as cursor:
                fila = await cursor.fetchone()
            if fila and fila[0] == hoy.isoformat():
                return await interaction.response.send_message("❌ Ya reclamaste hoy. Vuelve mañana.", ephemeral=True)
            recompensa = 100 + random.randint(0, 50)
            await self.actualizar_balance(interaction.user.id, recompensa, "diario", f"Recompensa diaria {recompensa}")
            if fila:
                await db.execute('UPDATE diario SET ultima_recompensa = ? WHERE user_id = ?', (hoy.isoformat(), interaction.user.id))
            else:
                await db.execute('INSERT INTO diario (user_id, ultima_recompensa) VALUES (?, ?)', (interaction.user.id, hoy.isoformat()))
            await db.commit()
        saldo = await self.obtener_balance(interaction.user.id)
        await interaction.response.send_message(f"📅 ¡Recompensa diaria! Has recibido **{recompensa}** {EMOTE}. Ahora tienes **{saldo}** {EMOTE}.", ephemeral=False)

    @app_commands.command(name="pt-ranking", description="Top 10 más ricos")
    async def ranking(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT user_id, pauliales FROM usuarios ORDER BY pauliales DESC LIMIT 10') as cursor:
                top = await cursor.fetchall()
        if not top:
            return await interaction.response.send_message("No hay nadie en el ranking.", ephemeral=True)
        embed = discord.Embed(title="💰 Ranking de Pauliales", color=discord.Color.gold())
        desc = ""
        for i, (uid, saldo) in enumerate(top, 1):
            user = self.bot.get_user(uid)
            nombre = user.display_name if user else f"Usuario {uid}"
            desc += f"{i}. **{nombre}** → {saldo} {EMOTE}\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pt-historial", description="Tus últimas transacciones")
    async def historial(self, interaction: discord.Interaction, limite: int = 5):
        if limite > 20:
            limite = 20
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT tipo, cantidad, saldo_despues, detalles, timestamp
                FROM auditoria WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (interaction.user.id, limite)) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message("Sin transacciones.", ephemeral=True)
        embed = discord.Embed(title="📜 Bitácora", color=discord.Color.blue())
        for tipo, cantidad, saldo, detalles, ts in rows:
            emoji = "➕" if cantidad > 0 else "➖"
            embed.add_field(name=f"{emoji} {tipo} - {ts[:16]}", value=f"Cantidad: {cantidad} | Saldo: {saldo}\n{detalles[:50]}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------- OFICIALES ---------------------
    @app_commands.command(name="pt-dar-pauliales", description="(Oficial) Otorga pauliales")
    @check_oficial()
    async def dar(self, interaction: discord.Interaction, jugador: discord.Member, cantidad: int):
        nuevo = await self.actualizar_balance(jugador.id, cantidad, "donacion_oficial", f"Oficial {interaction.user.id} dio {cantidad}")
        await interaction.response.send_message(f"✅ Se dieron **{cantidad}** {EMOTE} a {jugador.mention}. Nuevo saldo: **{nuevo}**.")

    @app_commands.command(name="pt-remover-pauliales", description="(Oficial) Quita pauliales")
    @check_oficial()
    async def remover(self, interaction: discord.Interaction, jugador: discord.Member, cantidad: int):
        nuevo = await self.actualizar_balance(jugador.id, -cantidad, "remocion_oficial", f"Oficial {interaction.user.id} quitó {cantidad}")
        await interaction.response.send_message(f"🔨 Se quitaron **{cantidad}** {EMOTE} a {jugador.mention}. Nuevo saldo: **{nuevo}**.")

    @app_commands.command(name="pt-auditoria-usuario", description="(Oficial) Ver historial de un usuario")
    @check_oficial()
    async def auditoria_usuario(self, interaction: discord.Interaction, usuario: discord.Member, limite: int = 10):
        if limite > 30:
            limite = 30
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT tipo, cantidad, saldo_despues, detalles, timestamp
                FROM auditoria WHERE user_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (usuario.id, limite)) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            return await interaction.response.send_message(f"{usuario.mention} no tiene transacciones.", ephemeral=True)
        embed = discord.Embed(title=f"📜 Auditoría de {usuario.display_name}", color=discord.Color.red())
        for tipo, cantidad, saldo, detalles, ts in rows:
            emoji = "➕" if cantidad > 0 else "➖"
            embed.add_field(name=f"{emoji} {tipo} - {ts}", value=f"Cantidad: {cantidad} | Saldo: {saldo}\n{detalles[:60]}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dar.error
    @remover.error
    @auditoria_usuario.error
    async def permisos_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"🏴‍☠️ Necesitas el rol **Tesorero** o ser Administrador.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Economia(bot))