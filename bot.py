import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import os
from keep_alive import keep_alive

# ============================================================
#  CONFIGURACIÓN — variables de entorno (Render.com)
# ============================================================
BOT_TOKEN           = os.environ.get("BOT_TOKEN", "")
GUILD_ID            = int(os.environ.get("GUILD_ID", "0"))
CATEGORY_TICKETS_ID = int(os.environ["CATEGORY_TICKETS_ID"]) if os.environ.get("CATEGORY_TICKETS_ID") else None
STAFF_ROLE_ID       = int(os.environ["STAFF_ROLE_ID"])       if os.environ.get("STAFF_ROLE_ID")       else None
LOG_CHANNEL_ID      = int(os.environ["LOG_CHANNEL_ID"])      if os.environ.get("LOG_CHANNEL_ID")      else None

# ============================================================
#  PRECIOS DE ROBUX  (USD por 100 robux)
# ============================================================
PRECIO_USD_POR_100_ROBUX = 1.25       # precio base en USD

# Tipos de cambio aproximados (USD → moneda local)
# Actualiza según necesites o intégralos con una API de tasas
TASAS_CAMBIO = {
    "MX": {"nombre": "México",       "moneda": "MXN", "simbolo": "$",  "tasa": 17.50},
    "AR": {"nombre": "Argentina",    "moneda": "ARS", "simbolo": "$",  "tasa": 900.0},
    "CO": {"nombre": "Colombia",     "moneda": "COP", "simbolo": "$",  "tasa": 4000.0},
    "CL": {"nombre": "Chile",        "moneda": "CLP", "simbolo": "$",  "tasa": 930.0},
    "PE": {"nombre": "Perú",         "moneda": "PEN", "simbolo": "S/", "tasa": 3.75},
    "VE": {"nombre": "Venezuela",    "moneda": "USD", "simbolo": "$",  "tasa": 1.0},
    "EC": {"nombre": "Ecuador",      "moneda": "USD", "simbolo": "$",  "tasa": 1.0},
    "BO": {"nombre": "Bolivia",      "moneda": "BOB", "simbolo": "Bs", "tasa": 6.90},
    "PY": {"nombre": "Paraguay",     "moneda": "PYG", "simbolo": "₲",  "tasa": 7300.0},
    "UY": {"nombre": "Uruguay",      "moneda": "UYU", "simbolo": "$",  "tasa": 38.50},
    "BR": {"nombre": "Brasil",       "moneda": "BRL", "simbolo": "R$", "tasa": 5.00},
    "ES": {"nombre": "España",       "moneda": "EUR", "simbolo": "€",  "tasa": 0.92},
    "US": {"nombre": "Estados Unidos","moneda": "USD","simbolo": "$",  "tasa": 1.0},
    "GT": {"nombre": "Guatemala",    "moneda": "GTQ", "simbolo": "Q",  "tasa": 7.80},
    "SV": {"nombre": "El Salvador",  "moneda": "USD", "simbolo": "$",  "tasa": 1.0},
    "HN": {"nombre": "Honduras",     "moneda": "HNL", "simbolo": "L",  "tasa": 24.70},
    "NI": {"nombre": "Nicaragua",    "moneda": "NIO", "simbolo": "C$", "tasa": 36.60},
    "CR": {"nombre": "Costa Rica",   "moneda": "CRC", "simbolo": "₡",  "tasa": 520.0},
    "PA": {"nombre": "Panamá",       "moneda": "USD", "simbolo": "$",  "tasa": 1.0},
    "DO": {"nombre": "Rep. Dominicana","moneda": "DOP","simbolo": "RD$","tasa": 57.0},
    "CU": {"nombre": "Cuba",         "moneda": "CUP", "simbolo": "$",  "tasa": 24.0},
    "PR": {"nombre": "Puerto Rico",  "moneda": "USD", "simbolo": "$",  "tasa": 1.0},
}

# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Almacena tickets en memoria  {canal_id: {datos}}
tickets_activos: dict = {}
ticket_counter: int = 0


# ──────────────────────────────────────────────
#  UTILIDADES
# ──────────────────────────────────────────────

def calcular_precio(robux: int, codigo_pais: str) -> tuple[float, str]:
    """Retorna (precio_local, texto_formateado)."""
    info   = TASAS_CAMBIO.get(codigo_pais.upper())
    if not info:
        return None, None
    usd    = (robux / 100) * PRECIO_USD_POR_100_ROBUX
    local  = usd * info["tasa"]
    texto  = f"{info['simbolo']}{local:,.2f} {info['moneda']}"
    return local, texto


def opciones_paises():
    return [
        app_commands.Choice(name=f"{v['nombre']} ({v['moneda']})", value=k)
        for k, v in TASAS_CAMBIO.items()
    ]


# ──────────────────────────────────────────────
#  MODAL — formulario de compra
# ──────────────────────────────────────────────

class FormularioRobux(discord.ui.Modal, title="🛒 Comprar Robux"):
    pais = discord.ui.TextInput(
        label="Código de tu país (ej: MX, AR, CO, ES…)",
        placeholder="MX",
        min_length=2,
        max_length=2,
        required=True,
    )
    cantidad = discord.ui.TextInput(
        label="¿Cuántos Robux quieres?",
        placeholder="100, 400, 800, 1700…",
        min_length=1,
        max_length=6,
        required=True,
    )
    usuario_roblox = discord.ui.TextInput(
        label="Tu usuario de Roblox",
        placeholder="NombreEnRoblox",
        required=True,
    )
    metodo_pago = discord.ui.TextInput(
        label="Método de pago preferido",
        placeholder="PayPal, transferencia, Binance, Nequi…",
        required=True,
    )
    notas = discord.ui.TextInput(
        label="Notas adicionales (opcional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter

        codigo = self.pais.value.strip().upper()
        if codigo not in TASAS_CAMBIO:
            await interaction.response.send_message(
                f"❌ Código de país **{codigo}** no reconocido.\n"
                f"Códigos disponibles: {', '.join(TASAS_CAMBIO.keys())}",
                ephemeral=True,
            )
            return

        try:
            robux = int(self.cantidad.value.strip())
            if robux <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Ingresa una cantidad válida de Robux (número entero positivo).",
                ephemeral=True,
            )
            return

        precio_local, precio_texto = calcular_precio(robux, codigo)
        usd = (robux / 100) * PRECIO_USD_POR_100_ROBUX
        info_pais = TASAS_CAMBIO[codigo]

        # ── Crear canal de ticket ──
        guild    = interaction.guild
        ticket_counter += 1
        nombre_canal = f"ticket-{ticket_counter:04d}-{interaction.user.name.lower()[:10]}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }

        # Agregar rol de staff si está configurado
        if STAFF_ROLE_ID:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

        categoria = guild.get_channel(CATEGORY_TICKETS_ID) if CATEGORY_TICKETS_ID else None
        canal = await guild.create_text_channel(
            nombre_canal,
            overwrites=overwrites,
            category=categoria,
            topic=f"Ticket de {interaction.user} | {robux} Robux | {info_pais['nombre']}",
        )

        # Guardar en memoria
        tickets_activos[canal.id] = {
            "autor_id":     interaction.user.id,
            "robux":        robux,
            "pais":         codigo,
            "precio_usd":   usd,
            "precio_local": precio_local,
            "precio_texto": precio_texto,
            "usuario_roblox": self.usuario_roblox.value.strip(),
            "metodo_pago":  self.metodo_pago.value.strip(),
            "notas":        self.notas.value.strip(),
            "abierto":      True,
            "creado_en":    datetime.datetime.utcnow(),
        }

        # ── Embed dentro del canal ──
        embed = discord.Embed(
            title="🎮 Nuevo Ticket de Compra de Robux",
            description=f"Hola {interaction.user.mention}, tu solicitud fue registrada.\n"
                        f"Un staff te atenderá en breve. ⚡",
            color=0x00BFFF,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Roblox_Logo_2022.svg/512px-Roblox_Logo_2022.svg.png")
        embed.add_field(name="👤 Comprador",       value=interaction.user.mention,                inline=True)
        embed.add_field(name="🌍 País",            value=f"{info_pais['nombre']} ({info_pais['moneda']})", inline=True)
        embed.add_field(name="🎲 Robux solicitados", value=f"**{robux:,} R$**",                  inline=True)
        embed.add_field(name="💵 Precio USD",      value=f"${usd:.2f} USD",                      inline=True)
        embed.add_field(name="💰 Precio local",    value=f"**{precio_texto}**",                  inline=True)
        embed.add_field(name="💳 Método de pago",  value=self.metodo_pago.value.strip(),         inline=True)
        embed.add_field(name="🎮 Usuario Roblox",  value=self.usuario_roblox.value.strip(),      inline=False)
        if self.notas.value.strip():
            embed.add_field(name="📝 Notas",       value=self.notas.value.strip(),               inline=False)
        embed.set_footer(text=f"Ticket #{ticket_counter:04d} • Tasa aprox. 1 USD = {info_pais['tasa']} {info_pais['moneda']}")

        vista_ticket = VistaTicket()
        await canal.send(
            content=f"{interaction.user.mention} {'<@&' + str(STAFF_ROLE_ID) + '>' if STAFF_ROLE_ID else ''}",
            embed=embed,
            view=vista_ticket,
        )

        # Log
        if LOG_CHANNEL_ID:
            log_canal = guild.get_channel(LOG_CHANNEL_ID)
            if log_canal:
                log_embed = discord.Embed(
                    title="📋 Ticket creado",
                    description=f"**Usuario:** {interaction.user}\n**Canal:** {canal.mention}\n"
                                f"**Robux:** {robux:,} | **Precio:** {precio_texto}",
                    color=0x2ECC71,
                    timestamp=datetime.datetime.utcnow(),
                )
                await log_canal.send(embed=log_embed)

        await interaction.response.send_message(
            f"✅ Tu ticket fue creado: {canal.mention}",
            ephemeral=True,
        )


# ──────────────────────────────────────────────
#  VISTA DENTRO DEL TICKET
# ──────────────────────────────────────────────

class VistaTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Marcar como pagado", style=discord.ButtonStyle.success, custom_id="ticket_pagado")
    async def pagado(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = tickets_activos.get(interaction.channel_id)
        if not datos:
            await interaction.response.send_message("❌ No encontré datos de este ticket.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Pago confirmado",
            description=f"El pago de **{datos['robux']:,} Robux** fue marcado como recibido.\n"
                        f"Usuario Roblox: **{datos['usuario_roblox']}**\n"
                        f"Los Robux serán enviados pronto. 🎮",
            color=0x2ECC71,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.set_footer(text=f"Confirmado por {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🔒 Cerrar ticket", style=discord.ButtonStyle.danger, custom_id="ticket_cerrar")
    async def cerrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🔒 Cerrando ticket en **5 segundos**…", ephemeral=False
        )

        if interaction.channel_id in tickets_activos:
            tickets_activos[interaction.channel_id]["abierto"] = False

        if LOG_CHANNEL_ID:
            log_canal = interaction.guild.get_channel(LOG_CHANNEL_ID)
            if log_canal:
                datos = tickets_activos.get(interaction.channel_id, {})
                log_embed = discord.Embed(
                    title="🔒 Ticket cerrado",
                    description=f"**Canal:** {interaction.channel.name}\n"
                                f"**Cerrado por:** {interaction.user}\n"
                                f"**Robux:** {datos.get('robux', '?'):,}",
                    color=0xE74C3C,
                    timestamp=datetime.datetime.utcnow(),
                )
                await log_canal.send(embed=log_embed)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para eliminar el canal.", ephemeral=True)

    @discord.ui.button(label="📋 Ver resumen", style=discord.ButtonStyle.secondary, custom_id="ticket_resumen")
    async def resumen(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = tickets_activos.get(interaction.channel_id)
        if not datos:
            await interaction.response.send_message("❌ No hay datos guardados para este ticket.", ephemeral=True)
            return
        info_pais = TASAS_CAMBIO.get(datos["pais"], {})
        embed = discord.Embed(title="📋 Resumen del ticket", color=0x9B59B6)
        embed.add_field(name="Robux",          value=f"{datos['robux']:,} R$",        inline=True)
        embed.add_field(name="País",           value=info_pais.get("nombre", "?"),    inline=True)
        embed.add_field(name="Precio USD",     value=f"${datos['precio_usd']:.2f}",   inline=True)
        embed.add_field(name="Precio local",   value=datos["precio_texto"],           inline=True)
        embed.add_field(name="Usuario Roblox", value=datos["usuario_roblox"],         inline=True)
        embed.add_field(name="Método de pago", value=datos["metodo_pago"],            inline=True)
        embed.add_field(name="Estado",         value="🟢 Abierto" if datos["abierto"] else "🔴 Cerrado", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ──────────────────────────────────────────────
#  VISTA DEL PANEL PRINCIPAL
# ──────────────────────────────────────────────

class VistaPanelPrincipal(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎮 Comprar Robux",
        style=discord.ButtonStyle.primary,
        custom_id="panel_comprar_robux",
        emoji="💎",
    )
    async def comprar_robux(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FormularioRobux())

    @discord.ui.button(
        label="💱 Ver precios",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_ver_precios",
        emoji="📊",
    )
    async def ver_precios(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📊 Tabla de precios de Robux",
            description=f"Precio base: **${PRECIO_USD_POR_100_ROBUX} USD** por cada 100 Robux\n\u200b",
            color=0xF1C40F,
        )
        tabla = ""
        cantidades = [100, 400, 800, 1700, 4500, 10000]
        for pais_code, info in list(TASAS_CAMBIO.items())[:10]:   # muestra solo 10
            fila = f"**{info['nombre']}** ({info['moneda']})\n"
            fila += " | ".join(
                f"{r}R$={info['simbolo']}{(r/100*PRECIO_USD_POR_100_ROBUX*info['tasa']):.0f}"
                for r in [100, 800, 1700]
            )
            tabla += fila + "\n"
        embed.add_field(name="Ejemplos rápidos (100 / 800 / 1700 R$)", value=tabla, inline=False)
        embed.set_footer(text="Tasas aproximadas. Usa /precio para un cálculo exacto.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="❓ Ayuda / FAQ",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_ayuda",
        emoji="📖",
    )
    async def ayuda(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❓ Preguntas frecuentes",
            color=0x1ABC9C,
        )
        embed.add_field(name="¿Cómo compro Robux?",
                        value="Haz clic en **🎮 Comprar Robux**, completa el formulario y espera a un staff.", inline=False)
        embed.add_field(name="¿Cuánto tiempo tarda?",
                        value="Normalmente entre 5 y 30 minutos según disponibilidad del staff.", inline=False)
        embed.add_field(name="¿Qué métodos de pago aceptan?",
                        value="PayPal, transferencia bancaria, Binance Pay, Nequi, MercadoPago, entre otros.", inline=False)
        embed.add_field(name="¿Es seguro?",
                        value="Sí, nuestro staff verificado gestiona cada transacción manualmente.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ──────────────────────────────────────────────
#  SLASH COMMANDS
# ──────────────────────────────────────────────

@tree.command(name="panel", description="📌 Envía el panel principal de compra de Robux", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(administrator=True)
async def cmd_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Tienda de Robux",
        description=(
            "¡Bienvenido a nuestra tienda de **Robux**! 💎\n\n"
            "Puedes comprar Robux de forma rápida y segura.\n"
            "El precio se calcula automáticamente en la **moneda de tu país**.\n\n"
            "👇 Elige una opción:"
        ),
        color=0x00BFFF,
    )
    embed.set_image(url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Roblox_Logo_2022.svg/512px-Roblox_Logo_2022.svg.png")
    embed.set_footer(text="Tienda oficial • Precios en moneda local")
    await interaction.channel.send(embed=embed, view=VistaPanelPrincipal())
    await interaction.response.send_message("✅ Panel enviado.", ephemeral=True)


@tree.command(name="precio", description="💰 Calcula el precio de Robux en tu moneda local", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(robux="Cantidad de Robux", pais="Código de tu país (MX, AR, CO…)")
async def cmd_precio(interaction: discord.Interaction, robux: int, pais: str):
    codigo = pais.strip().upper()
    if codigo not in TASAS_CAMBIO:
        await interaction.response.send_message(
            f"❌ Código **{codigo}** no reconocido. Usa alguno de: {', '.join(TASAS_CAMBIO.keys())}",
            ephemeral=True,
        )
        return
    if robux <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return

    info = TASAS_CAMBIO[codigo]
    usd  = (robux / 100) * PRECIO_USD_POR_100_ROBUX
    _, precio_texto = calcular_precio(robux, codigo)

    embed = discord.Embed(title="💰 Calculadora de Robux", color=0xF39C12)
    embed.add_field(name="Robux",       value=f"{robux:,} R$",   inline=True)
    embed.add_field(name="País",        value=info["nombre"],     inline=True)
    embed.add_field(name="Precio USD",  value=f"${usd:.2f}",      inline=True)
    embed.add_field(name="Precio local",value=f"**{precio_texto}**", inline=True)
    embed.add_field(name="Tasa usada",  value=f"1 USD = {info['tasa']} {info['moneda']}", inline=True)
    embed.set_footer(text="Tasas aproximadas. El precio final lo confirma el staff.")
    await interaction.response.send_message(embed=embed)


@tree.command(name="tickets", description="📋 Lista los tickets activos (solo staff)", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_tickets(interaction: discord.Interaction):
    activos = {k: v for k, v in tickets_activos.items() if v.get("abierto")}
    if not activos:
        await interaction.response.send_message("No hay tickets activos.", ephemeral=True)
        return
    embed = discord.Embed(title=f"📋 Tickets activos: {len(activos)}", color=0x3498DB)
    for canal_id, datos in list(activos.items())[:10]:
        canal = interaction.guild.get_channel(canal_id)
        nombre_canal = canal.mention if canal else f"#{canal_id}"
        embed.add_field(
            name=nombre_canal,
            value=f"<@{datos['autor_id']}> | {datos['robux']:,} R$ | {datos['precio_texto']}",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="cerrar", description="🔒 Cierra el ticket actual", guild=discord.Object(id=GUILD_ID))
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_cerrar(interaction: discord.Interaction):
    if interaction.channel_id not in tickets_activos:
        await interaction.response.send_message("❌ Este canal no es un ticket.", ephemeral=True)
        return
    await interaction.response.send_message("🔒 Cerrando en 5 segundos…")
    tickets_activos[interaction.channel_id]["abierto"] = False
    await asyncio.sleep(5)
    await interaction.channel.delete(reason=f"Cerrado por {interaction.user}")


# ──────────────────────────────────────────────
#  EVENTOS
# ──────────────────────────────────────────────

@bot.event
async def on_ready():
    bot.add_view(VistaPanelPrincipal())
    bot.add_view(VistaTicket())
    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ {len(synced)} comandos sincronizados en el servidor {GUILD_ID}")
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
    print(f"🤖 Bot listo: {bot.user} ({bot.user.id})")


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Error: {error}", ephemeral=True)


# ──────────────────────────────────────────────
keep_alive()
bot.run(BOT_TOKEN)
