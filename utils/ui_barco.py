import discord
import json
import os
import aiosqlite
import asyncio

EMOTE = "<:ricomacpato:1514136285584031784>"
DB_PATH = "data/pauliales.db"
COMPARTIMIENTOS_PATH = "data/compartimientos/"

class SelectorCompra(discord.ui.Select):
    def __init__(self, archivo_tienda, bot):
        self.archivo_tienda = archivo_tienda
        self.bot = bot
        ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo_tienda)
        with open(ruta, 'r', encoding='utf-8') as f:
            self.datos_tienda = json.load(f)

        opciones = []
        lista_objetos = self.datos_tienda.get('objetos') or self.datos_tienda.get('objects', [])
        for obj in lista_objetos:
            if obj['stock_actual'] > 0:
                info_desc = obj.get('description') or obj.get('descripcion', "Sin descripción.")
                opciones.append(discord.SelectOption(
                    label=f"{obj['nombre']} ({obj['precio']} pauliales)",
                    description=f"Stock: {obj['stock_actual']} | {info_desc[:40]}...",
                    value=obj['id']
                ))
        if not opciones:
            opciones.append(discord.SelectOption(label="Agotado", description="Sin stock", value="agotado"))
        super().__init__(placeholder="🛒 Elige un tesoro...", min_values=1, max_values=1, options=opciones)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        if item_id == "agotado":
            return await interaction.response.send_message("❌ No queda stock en esta bodega.", ephemeral=True)

        lista_objetos = self.datos_tienda.get('objetos') or self.datos_tienda.get('objects', [])
        obj_comprar = next((o for o in lista_objetos if o['id'] == item_id), None)
        if not obj_comprar:
            return await interaction.response.send_message("❌ Error: objeto no encontrado.", ephemeral=True)

        economia_cog = self.bot.get_cog("Economia")
        if not economia_cog:
            return await interaction.response.send_message("❌ Error interno: sistema de economía no disponible.", ephemeral=True)

        saldo_actual = await economia_cog.obtener_balance(interaction.user.id)
        if saldo_actual < obj_comprar['precio']:
            return await interaction.response.send_message(f"❌ Fondos insuficientes. Cuesta **{obj_comprar['precio']}** pauliales y tienes **{saldo_actual}** {EMOTE}.", ephemeral=True)

        # Transacción atómica con lock
        async with asyncio.Lock():
            # 1. Descontar dinero (auditoría incluida)
            nuevo_saldo = await economia_cog.actualizar_balance(
                interaction.user.id,
                -obj_comprar['precio'],
                "compra",
                f"Compró {obj_comprar['nombre']} en {self.archivo_tienda}"
            )

            # 2. Si es restock especial
            if item_id == "restock_tienda":
                for obj in lista_objetos:
                    obj['stock_actual'] = obj['stock_maximo']
                ruta = os.path.join(COMPARTIMIENTOS_PATH, self.archivo_tienda)
                with open(ruta, 'w', encoding='utf-8') as f:
                    json.dump(self.datos_tienda, f, indent=4, ensure_ascii=False)
                return await interaction.response.send_message(
                    f"⚡ {interaction.user.mention} ha comprado un **RESTOCK DE TIENDA** por **{obj_comprar['precio']}** pauliales.\n"
                    "🌿 *Las enredaderas de El Brote Hundido se agitan violentamente y la bodega se ha reabastecido por completo.*"
                )

            # 3. Añadir al inventario
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute('SELECT cantidad FROM inventarios WHERE user_id = ? AND item_id = ?', (interaction.user.id, item_id)) as cur:
                    fila = await cur.fetchone()
                    if fila:
                        await db.execute('UPDATE inventarios SET cantidad = ? WHERE user_id = ? AND item_id = ?', (fila[0] + 1, interaction.user.id, item_id))
                    else:
                        await db.execute('INSERT INTO inventarios (user_id, item_id, nombre_item, cantidad) VALUES (?, ?, ?, 1)', (interaction.user.id, item_id, obj_comprar['nombre']))
                await db.commit()

            # 4. Reducir stock en JSON
            obj_comprar['stock_actual'] -= 1
            ruta = os.path.join(COMPARTIMIENTOS_PATH, self.archivo_tienda)
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(self.datos_tienda, f, indent=4, ensure_ascii=False)

        await interaction.response.send_message(
            f"🎉 ¡Has adquirido **{obj_comprar['nombre']}** por **{obj_comprar['precio']}** pauliales!\n"
            f"📦 Guardado en tu `/pt-inventario`. Ahora tienes **{nuevo_saldo}** {EMOTE}.",
            ephemeral=False
        )

class VistaTienda(discord.ui.View):
    def __init__(self, archivo_tienda, bot):
        super().__init__(timeout=180)
        self.add_item(SelectorCompra(archivo_tienda, bot))