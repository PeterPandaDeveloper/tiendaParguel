import discord
import json
import os
import aiosqlite

EMOTE = "<:ricomacpato:AQUI_PONES_EL_ID>" # Asegúrate de poner tu ID aquí
DB_PATH = "data/pauliales.db"
COMPARTIMIENTOS_PATH = "data/compartimientos/"

class SelectorCompra(discord.ui.Select):
    def __init__(self, archivo_tienda):
        self.archivo_tienda = archivo_tienda
        
        ruta = os.path.join(COMPARTIMIENTOS_PATH, archivo_tienda)
        with open(ruta, 'r', encoding='utf-8') as f:
            self.datos_tienda = json.load(f)
            
        opciones = []
        # Soporta tanto "objetos" como "objects" por si hay diferencias en los JSON
        lista_objetos = self.datos_tienda.get('objetos') or self.datos_tienda.get('objects', [])
        
        for obj in lista_objetos:
            if obj['stock_actual'] > 0:
                # Busca de forma segura cualquier variante de la descripción
                info_desc = obj.get('description') or obj.get('descripcion') or "Sin descripción disponible."
                
                opciones.append(discord.SelectOption(
                    label=f"{obj['nombre']} ({obj['precio']} pauliales)",
                    description=f"Stock: {obj['stock_actual']} | {info_desc[:40]}...",
                    value=obj['id']
                ))
        
        if not opciones:
            opciones.append(discord.SelectOption(label="Agotado", description="Esta bodega no tiene stock.", value="agotado"))
            
        super().__init__(placeholder="🛒 Elige un tesoro para adquirir...", min_values=1, max_values=1, options=opciones)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        if item_id == "agotado":
            return await interaction.response.send_message("❌ Las raíces están vacías, no queda stock.", ephemeral=True)
            
        lista_objetos = self.datos_tienda.get('objetos') or self.datos_tienda.get('objects', [])
        obj_comprar = next((o for o in lista_objetos if o['id'] == item_id), None)
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT pauliales FROM usuarios WHERE user_id = ?', (interaction.user.id,)) as cursor:
                fila = await cursor.fetchone()
                saldo = fila[0] if fila else 0
                
            if saldo < obj_comprar['precio']:
                return await interaction.response.send_message(f"❌ Fondos insuficientes. Cuesta **{obj_comprar['precio']}** pauliales y tienes **{saldo}** {EMOTE}.", ephemeral=True)
                
            # Cobrar el dinero
            nuevo_saldo = saldo - obj_comprar['precio']
            await db.execute('UPDATE usuarios SET pauliales = ? WHERE user_id = ?', (nuevo_saldo, interaction.user.id))
            
            # LÓGICA ESPECIAL: Si compra el Restock de Tienda
            if item_id == "restock_tienda":
                for obj in lista_objetos:
                    obj['stock_actual'] = obj['stock_maximo']
                
                await db.commit()
                
                ruta = os.path.join(COMPARTIMIENTOS_PATH, self.archivo_tienda)
                with open(ruta, 'w', encoding='utf-8') as f:
                    json.dump(self.datos_tienda, f, indent=4, ensure_ascii=False)
                
                return await interaction.response.send_message(f"⚡ {interaction.user.mention} ha comprado un **RESTOCK DE TIENDA** por **600** pauliales.\n🌿 *Las enredaderas de El Brote Hundido se agitan violentamente y la bodega se ha reabastecido por completo al Máximo.*")

            # Lógica normal para añadir a la mochila
            async with db.execute('SELECT cantidad FROM inventarios WHERE user_id = ? AND item_id = ?', (interaction.user.id, item_id)) as cur_inv:
                inv_fila = await cur_inv.fetchone()
                if inv_fila:
                    await db.execute('UPDATE inventarios SET cantidad = ? WHERE user_id = ? AND item_id = ?', (inv_fila[0] + 1, interaction.user.id, item_id))
                else:
                    await db.execute('INSERT INTO inventarios (user_id, item_id, nombre_item, cantidad) VALUES (?, ?, ?, 1)', (interaction.user.id, item_id, obj_comprar['nombre']))
            await db.commit()
            
        # Reducir stock del objeto comprado y guardar
        obj_comprar['stock_actual'] -= 1
        ruta = os.path.join(COMPARTIMIENTOS_PATH, self.archivo_tienda)
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(self.datos_tienda, f, indent=4, ensure_ascii=False)
            
        await interaction.response.send_message(f"🎉 ¡Has adquirido **{obj_comprar['nombre']}** por **{obj_comprar['precio']}** pauliales!\n📦 Guardado en tu `/pt-inventario`.", ephemeral=False)

class VistaTienda(discord.ui.View):
    def __init__(self, archivo_tienda):
        super().__init__(timeout=180)
        self.add_item(SelectorCompra(archivo_tienda))