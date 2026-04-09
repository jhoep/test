import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Tuple
import asyncio
import datetime
import os
import aiohttp
import time as _time
import json
import logging
import shutil
from keep_alive import keep_alive

# ============================================================
#  LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("robux-bot")

# ============================================================
#  CONFIGURACIÓN
# ============================================================
BOT_TOKEN           = os.environ.get("BOT_TOKEN", "")
_GUILD_ID_RAW       = os.environ.get("GUILD_ID", "").strip()
GUILD_ID            = int(_GUILD_ID_RAW) if _GUILD_ID_RAW else None
CATEGORY_TICKETS_ID = int(os.environ["CATEGORY_TICKETS_ID"]) if os.environ.get("CATEGORY_TICKETS_ID") else None
STAFF_ROLE_ID       = int(os.environ["STAFF_ROLE_ID"])       if os.environ.get("STAFF_ROLE_ID")       else None
LOG_CHANNEL_ID      = int(os.environ["LOG_CHANNEL_ID"])      if os.environ.get("LOG_CHANNEL_ID")      else None
OWNER_ID            = int(os.environ.get("OWNER_ID", "0"))

MAX_TICKETS_POR_USUARIO = 3

def es_admin_o_owner(interaction: discord.Interaction) -> bool:
    """Devuelve True si el usuario es el owner o tiene permisos de administrador."""
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

# ============================================================
#  TABLA DE PRECIOS DEL VENDEDOR
# ============================================================
TASA_USD_POR_ROBUX = 0.005

PRECIOS_ROBUX = {
    1_000:   5.00,
    2_000:  10.00,
    3_000:  15.00,
    5_000:  25.00,
    7_000:  35.00,
   10_000:  50.00,
   15_000:  75.00,
   20_000: 100.00,
   25_000: 125.00,
   30_000: 150.00,
}
CANTIDADES_DISPONIBLES = sorted(PRECIOS_ROBUX.keys())

def precio_usd_aproximado(robux: int) -> float:
    if robux in PRECIOS_ROBUX:
        return PRECIOS_ROBUX[robux]
    return round(robux * TASA_USD_POR_ROBUX, 2)

# ============================================================
#  TASAS DE CAMBIO EN TIEMPO REAL
# ============================================================
_tasas_cache: dict = {}
_tasas_ts: float   = 0.0
_CACHE_TTL: int    = 3600

async def obtener_tasas_live():
    global _tasas_cache, _tasas_ts
    if _tasas_cache and (_time.time() - _tasas_ts) < _CACHE_TTL:
        return _tasas_cache
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                data = await r.json()
                if data.get("result") == "success":
                    _tasas_cache = data["rates"]
                    _tasas_ts    = _time.time()
                    logger.info("✅ Tasas de cambio actualizadas")
                    return _tasas_cache
    except Exception as e:
        logger.warning(f"⚠️ Error obteniendo tasas: {e}")
    return {}

TASAS_CAMBIO = {
    "MX": {"nombre": "Mexico",         "moneda": "MXN", "simbolo": "$",   "tasa": 19.46},
    "AR": {"nombre": "Argentina",      "moneda": "ARS", "simbolo": "$",   "tasa": 1900.0},
    "CO": {"nombre": "Colombia",       "moneda": "COP", "simbolo": "$",   "tasa": 4200.0},
    "CL": {"nombre": "Chile",          "moneda": "CLP", "simbolo": "$",   "tasa": 4200.0},
    "PE": {"nombre": "Peru",           "moneda": "PEN", "simbolo": "S/",  "tasa": 3.75},
    "VE": {"nombre": "Venezuela",      "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
    "EC": {"nombre": "Ecuador",        "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
    "BO": {"nombre": "Bolivia",        "moneda": "BOB", "simbolo": "Bs",  "tasa": 6.90},
    "PY": {"nombre": "Paraguay",       "moneda": "PYG", "simbolo": "₲",   "tasa": 7300.0},
    "UY": {"nombre": "Uruguay",        "moneda": "UYU", "simbolo": "$",   "tasa": 38.50},
    "BR": {"nombre": "Brasil",         "moneda": "BRL", "simbolo": "R$",  "tasa": 5.00},
    "ES": {"nombre": "España",         "moneda": "EUR", "simbolo": "€",   "tasa": 0.92},
    "US": {"nombre": "Estados Unidos", "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
    "GT": {"nombre": "Guatemala",      "moneda": "GTQ", "simbolo": "Q",   "tasa": 7.80},
    "SV": {"nombre": "El Salvador",    "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
    "HN": {"nombre": "Honduras",       "moneda": "HNL", "simbolo": "L",   "tasa": 24.70},
    "NI": {"nombre": "Nicaragua",      "moneda": "NIO", "simbolo": "C$",  "tasa": 36.60},
    "CR": {"nombre": "Costa Rica",     "moneda": "CRC", "simbolo": "₡",   "tasa": 520.0},
    "PA": {"nombre": "Panama",         "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
    "DO": {"nombre": "Rep. Dominicana","moneda": "DOP", "simbolo": "RD$", "tasa": 57.0},
    "CU": {"nombre": "Cuba",           "moneda": "CUP", "simbolo": "$",   "tasa": 24.0},
    "PR": {"nombre": "Puerto Rico",    "moneda": "USD", "simbolo": "$",   "tasa": 1.0},
}

# ============================================================
#  GRUPOS DE ROBLOX
# ============================================================
GRUPOS_ROBLOX = [
    {
        "nombre": "Mxdes UGC",
        "url": "https://www.roblox.com/communities/32455154/Mxdes-UGC#!/about"
    },
    {
        "nombre": "Experimental",
        "url": "https://www.roblox.com/communities/33314312/Experimental#!/about"
    },
    {
        "nombre": "ZillaKamii",
        "url": "https://www.roblox.com/communities/13262547/ZillaKamii#!/about"
    },
    {
        "nombre": "n0ctu",
        "url": "https://www.roblox.com/communities/34005810/n0ctu#!/about"
    }
]

# ============================================================
#  PERSISTENCIA (JSON)
# ============================================================
DATA_FILE = "data.json"
tickets_activos: dict       = {}
ticket_counter: int         = 0
autoroles_registrados: dict = {}
ticket_lock = asyncio.Lock()

def cargar_datos():
    global tickets_activos, ticket_counter, autoroles_registrados
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            tickets_activos       = {}
            for k, v in data.get("tickets", {}).items():
                # Convertir creado_en de string a datetime
                if "creado_en" in v and isinstance(v["creado_en"], str):
                    try:
                        v["creado_en"] = datetime.datetime.fromisoformat(v["creado_en"])
                    except:
                        v["creado_en"] = datetime.datetime.utcnow()
                tickets_activos[int(k)] = v
            
            ticket_counter        = data.get("counter", 0)
            autoroles_registrados = {int(k): v for k, v in data.get("autoroles", {}).items()}
            logger.info(
                f"Datos cargados: {len(tickets_activos)} tickets, "
                f"counter={ticket_counter}, {len(autoroles_registrados)} autoroles"
            )
    except FileNotFoundError:
        logger.info("Archivo de datos no encontrado — iniciando desde cero")
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error cargando datos: {e}")

def guardar_datos():
    try:
        data = {
            "tickets":   {},
            "counter":   ticket_counter,
            "autoroles": {str(k): v for k, v in autoroles_registrados.items()},
            "version":   "1.0",
            "last_save": datetime.datetime.utcnow().isoformat()
        }
        for k, v in tickets_activos.items():
            copia = dict(v)
            if "creado_en" in copia and isinstance(copia["creado_en"], datetime.datetime):
                copia["creado_en"] = copia["creado_en"].isoformat()
            data["tickets"][str(k)] = copia
        
        # Escribir a archivo temporal primero
        temp_file = DATA_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        
        # Reemplazar archivo original
        os.replace(temp_file, DATA_FILE)
        logger.debug("Datos guardados exitosamente")
        
    except Exception as e:
        logger.error(f"❌ Error crítico guardando datos: {e}")
        # Intentar guardar en archivo de emergencia
        try:
            emergency_file = f"data_emergency_{int(_time.time())}.json"
            with open(emergency_file, "w") as f:
                json.dump(data, f)
            logger.warning(f"⚠️ Datos guardados en archivo de emergencia: {emergency_file}")
        except:
            pass

# ============================================================
#  BACKUP AUTOMÁTICO
# ============================================================
async def backup_automatico():
    """Crea backup del archivo de datos cada hora"""
    await asyncio.sleep(60)  # Esperar 1 minuto antes del primer backup
    while True:
        await asyncio.sleep(3600)  # 1 hora
        try:
            if not os.path.exists(DATA_FILE):
                continue
                
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"data_backup_{timestamp}.json"
            shutil.copy2(DATA_FILE, backup_name)
            logger.info(f"✅ Backup creado: {backup_name}")
            
            # Mantener solo los últimos 24 backups
            import glob
            backups = sorted(glob.glob("data_backup_*.json"))
            if len(backups) > 24:
                for old_backup in backups[:-24]:
                    try:
                        os.remove(old_backup)
                        logger.debug(f"Backup antiguo eliminado: {old_backup}")
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error en backup automático: {e}")

# ============================================================
#  BOT
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def guild_obj() -> Optional[discord.Object]:
    return discord.Object(id=GUILD_ID) if GUILD_ID else None

# ============================================================
#  ESTADOS Y COLORES
# ============================================================
ESTADOS = {
    "abierto":   {"emoji": "🟢", "texto": "Abierto",                   "color": 0x00BFFF},
    "pendiente": {"emoji": "🟡", "texto": "Pendiente de verificacion", "color": 0xF39C12},
    "entregado": {"emoji": "✅", "texto": "Robux entregados",           "color": 0x2ECC71},
    "cerrado":   {"emoji": "🔴", "texto": "Cerrado",                   "color": 0xE74C3C},
}

DESCRIPCIONES_ESTADO = {
    "abierto":   "Un staff te atendera en breve. ⚡",
    "pendiente": "💳 **Pago marcado como realizado.** Esperando verificacion del staff…",
    "entregado": "✅ **Los Robux han sido entregados.** ¡Gracias por tu compra!",
    "cerrado":   "🔴 Este ticket ha sido cerrado.",
}

# ============================================================
#  UTILIDADES
# ============================================================

async def calcular_precio(robux: int, codigo_pais: str) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    info = TASAS_CAMBIO.get(codigo_pais.upper())
    if not info:
        raise ValueError(f"País {codigo_pais} no soportado")
    
    usd   = precio_usd_aproximado(robux)
    rates = await obtener_tasas_live()
    tasa  = rates.get(info["moneda"], info["tasa"]) if rates else info["tasa"]
    local = usd * tasa
    texto = f"{info['simbolo']}{local:,.2f} {info['moneda']}"
    return local, texto, usd

def opciones_paises():
    return [
        app_commands.Choice(name=f"{v['nombre']} ({v['moneda']})", value=k)
        for k, v in TASAS_CAMBIO.items()
    ]

def es_staff(member: discord.Member) -> bool:
    if member.guild_permissions.manage_channels or member.guild_permissions.administrator:
        return True
    if STAFF_ROLE_ID:
        staff_role = member.guild.get_role(STAFF_ROLE_ID)
        if staff_role and staff_role in member.roles:
            return True
    return False

def crear_embed_ticket(datos: dict) -> discord.Embed:
    estado_key  = datos.get("estado", "abierto")
    estado_info = ESTADOS.get(estado_key, ESTADOS["abierto"])
    info_pais   = TASAS_CAMBIO.get(datos.get("pais", ""), {})
    numero      = datos.get("numero", 0)

    embed = discord.Embed(
        title=f"🎮 Ticket #{numero:04d} — {estado_info['emoji']} {estado_info['texto']}",
        description=(
            f"Ticket de <@{datos['autor_id']}>.\n"
            f"{DESCRIPCIONES_ESTADO.get(estado_key, '')}"
        ),
        color=estado_info["color"],
        timestamp=datetime.datetime.utcnow(),
    )
    embed.set_thumbnail(
        url="https://upload.wikimedia.org/wikipedia/commons/thumb/"
            "6/6e/Roblox_Logo_2022.svg/512px-Roblox_Logo_2022.svg.png"
    )
    embed.add_field(name="👤 Comprador",         value=f"<@{datos['autor_id']}>",              inline=True)
    embed.add_field(
        name="🌍 Pais",
        value=f"{info_pais.get('nombre', '?')} ({info_pais.get('moneda', '?')})",
        inline=True,
    )
    embed.add_field(name="🎲 Robux solicitados", value=f"**{datos['robux']:,} R$**",               inline=True)
    embed.add_field(name="💵 Precio USD",        value=f"**${datos.get('precio_usd', 0):.2f} USD**", inline=True)
    embed.add_field(name="💰 Precio local",      value=f"**{datos.get('precio_texto', '?')}**",     inline=True)
    embed.add_field(name="💳 Metodo de pago",    value=datos.get("metodo_pago", "?"),               inline=True)
    embed.add_field(name="🎮 Usuario Roblox",    value=datos.get("usuario_roblox", "?"),            inline=False)

    if datos.get("notas"):
        embed.add_field(name="📝 Notas", value=datos["notas"], inline=False)

    embed.add_field(
        name="📊 Estado",
        value=f"{estado_info['emoji']} **{estado_info['texto']}**",
        inline=False,
    )

    if estado_key == "pendiente" and datos.get("pagado_por"):
        embed.add_field(name="💳 Pago marcado por", value=f"<@{datos['pagado_por']}>",  inline=True)
    if estado_key == "entregado" and datos.get("entregado_por"):
        embed.add_field(name="📦 Entregado por",    value=f"<@{datos['entregado_por']}>", inline=True)

    embed.set_footer(text=f"Ticket #{numero:04d}")
    return embed

async def construir_embed_tabla(titulo: str, descripcion: str, color: int) -> discord.Embed:
    rates  = await obtener_tasas_live()
    cantidades = list(PRECIOS_ROBUX.keys())

    embed = discord.Embed(
        title=titulo,
        description=f"{descripcion}\n\u200b",
        color=color,
    )

    # Columna USD
    col_usd = ""
    for r in cantidades:
        p = precio_usd_aproximado(r)
        col_usd += f"✅ `{r:>6,}` → **${p:.2f}**\n"
    embed.add_field(name="💵 USD", value=col_usd, inline=True)

    # Columnas monedas locales (máximo 4 para no exceder límite)
    for codigo in ["MX", "AR", "CO", "ES"]:
        info_p = TASAS_CAMBIO[codigo]
        moneda = info_p["moneda"]
        tasa = info_p["tasa"] if codigo in ("MX", "CO", "AR") else rates.get(moneda, info_p["tasa"]) if rates else info_p["tasa"]
        col = ""
        for r in cantidades:
            local = precio_usd_aproximado(r) * tasa
            col += f"`{r:>6,}` → {info_p['simbolo']}{local:,.0f}\n"
        embed.add_field(
            name=f"🌍 {info_p['nombre']} ({moneda})",
            value=col,
            inline=True,
        )

    return embed

async def log_accion(guild: discord.Guild, tipo: str, descripcion: str, color: int):
    """Función centralizada para logs"""
    if not LOG_CHANNEL_ID:
        return
    
    log_ch = guild.get_channel(LOG_CHANNEL_ID)
    if not log_ch:
        return
    
    embed = discord.Embed(
        title=tipo,
        description=descripcion,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    
    try:
        await log_ch.send(embed=embed)
    except Exception as e:
        logger.error(f"Error enviando log: {e}")

# ============================================================
#  MODAL — FORMULARIO DE COMPRA
# ============================================================

class FormularioRobux(discord.ui.Modal, title="🛒 Comprar Robux"):
    pais = discord.ui.TextInput(
        label="Codigo de tu pais (ej: MX, AR, CO, ES…)",
        placeholder="MX",
        min_length=2, max_length=2, required=True,
    )
    cantidad = discord.ui.TextInput(
        label="¿Cuantos Robux quieres?",
        placeholder="1000, 2000, 3000, 5000, 7000, 10000…",
        min_length=1, max_length=6, required=True,
    )
    usuario_roblox = discord.ui.TextInput(
        label="Tu usuario de Roblox",
        placeholder="NombreEnRoblox",
        required=True,
    )
    metodo_pago = discord.ui.TextInput(
        label="Metodo de pago preferido",
        placeholder="PayPal, transferencia, Binance, Nequi…",
        required=True,
    )
    notas = discord.ui.TextInput(
        label="Notas adicionales (opcional)",
        style=discord.TextStyle.paragraph,
        required=False, max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter

        codigo = self.pais.value.strip().upper()
        if codigo not in TASAS_CAMBIO:
            await interaction.response.send_message(
                f"❌ Codigo de pais **{codigo}** no reconocido.\n"
                f"Codigos disponibles: {', '.join(TASAS_CAMBIO.keys())}",
                ephemeral=True,
            )
            return

        try:
            robux = int(self.cantidad.value.strip())
            if robux <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Ingresa una cantidad valida de Robux (numero entero positivo).",
                ephemeral=True,
            )
            return
        if robux > 30_000:
            await interaction.response.send_message(
                "❌ La cantidad maxima es **30,000 Robux** por ticket.",
                ephemeral=True,
            )
            return

        # Validar usuario de Roblox
        usuario_roblox = self.usuario_roblox.value.strip()
        if not usuario_roblox.replace("_", "").isalnum():
            await interaction.response.send_message(
                "❌ El nombre de usuario de Roblox solo puede contener letras, números y guiones bajos.",
                ephemeral=True
            )
            return

        tickets_del_usuario = sum(
            1 for t in tickets_activos.values()
            if t.get("autor_id") == interaction.user.id
            and t.get("estado") in ("abierto", "pendiente")
        )
        if tickets_del_usuario >= MAX_TICKETS_POR_USUARIO:
            await interaction.response.send_message(
                f"❌ Ya tienes **{tickets_del_usuario}** tickets abiertos. "
                f"Cierra uno antes de abrir otro (max {MAX_TICKETS_POR_USUARIO}).",
                ephemeral=True,
            )
            return

        try:
            precio_local, precio_texto, usd = await calcular_precio(robux, codigo)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return

        info_pais = TASAS_CAMBIO[codigo]
        guild = interaction.guild
        
        async with ticket_lock:
            ticket_counter += 1
            numero = ticket_counter
            guardar_datos()  # Guardar inmediatamente

        nombre_canal = f"ticket-{numero:04d}-{interaction.user.name.lower()[:10]}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user:   discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }
        if STAFF_ROLE_ID:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )

        categoria = guild.get_channel(CATEGORY_TICKETS_ID) if CATEGORY_TICKETS_ID else None

        try:
            canal = await guild.create_text_channel(
                nombre_canal,
                overwrites=overwrites,
                category=categoria,
                topic=f"Ticket de {interaction.user} | {robux} Robux | {info_pais['nombre']}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No tengo permisos para crear canales. Verifica mis permisos.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            logger.error(f"Error creando canal de ticket: {e}")
            await interaction.response.send_message(
                f"❌ Error al crear el ticket: {e}", ephemeral=True
            )
            return

        datos_ticket = {
            "autor_id":       interaction.user.id,
            "numero":         numero,
            "robux":          robux,
            "pais":           codigo,
            "precio_usd":     usd,
            "precio_local":   precio_local,
            "precio_texto":   precio_texto,
            "usuario_roblox": usuario_roblox,
            "metodo_pago":    self.metodo_pago.value.strip(),
            "notas":          self.notas.value.strip() if self.notas.value else "",
            "estado":         "abierto",
            "creado_en":      datetime.datetime.utcnow(),
            "pagado_por":     None,
            "entregado_por":  None,
        }
        tickets_activos[canal.id] = datos_ticket
        guardar_datos()

        embed = crear_embed_ticket(datos_ticket)
        vista = VistaTicket()

        await canal.send(
            content=(
                f"{interaction.user.mention} "
                f"{'<@&' + str(STAFF_ROLE_ID) + '>' if STAFF_ROLE_ID else ''}"
            ),
            embed=embed,
            view=vista,
        )

        await log_accion(
            guild,
            "📋 Ticket creado",
            (
                f"**Usuario:** {interaction.user}\n"
                f"**Canal:** {canal.mention}\n"
                f"**Robux:** {robux:,} | **Precio:** {precio_texto}"
            ),
            0x2ECC71
        )

        await interaction.response.send_message(
            f"✅ Tu ticket fue creado: {canal.mention}", ephemeral=True
        )

# ============================================================
#  VISTA DENTRO DEL TICKET
# ============================================================

class VistaTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💳 Marcar como pagado",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_pagado",
    )
    async def pagado(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = tickets_activos.get(interaction.channel_id)
        if not datos:
            await interaction.response.send_message("❌ No encontre datos de este ticket.", ephemeral=True)
            return

        estado = datos.get("estado", "abierto")
        if estado == "pendiente":
            await interaction.response.send_message("⚠️ Este ticket ya esta marcado como **pendiente de verificacion**.", ephemeral=True)
            return
        if estado == "entregado":
            await interaction.response.send_message("⚠️ Los Robux ya fueron **entregados** en este ticket.", ephemeral=True)
            return
        if estado == "cerrado":
            await interaction.response.send_message("⚠️ Este ticket esta **cerrado**.", ephemeral=True)
            return

        datos["estado"]     = "pendiente"
        datos["pagado_por"] = interaction.user.id
        guardar_datos()

        notif = discord.Embed(
            title="💳 Pago marcado como realizado",
            description=(
                f"{interaction.user.mention} ha marcado el pago como **realizado**.\n"
                f"**{datos['robux']:,} R$** — {datos['precio_texto']}\n\n"
                f"⏳ Esperando que un **staff** verifique y confirme la entrega…"
            ),
            color=0xF39C12,
            timestamp=datetime.datetime.utcnow(),
        )
        staff_ping = f"<@&{STAFF_ROLE_ID}>" if STAFF_ROLE_ID else ""
        await interaction.response.send_message(content=staff_ping, embed=notif)

        try:
            if interaction.message:
                await interaction.message.edit(embed=crear_embed_ticket(datos))
        except Exception as e:
            logger.warning(f"Error editando embed del ticket: {e}")

        await log_accion(
            interaction.guild,
            "💳 Pago marcado",
            (
                f"**Canal:** {interaction.channel.mention}\n"
                f"**Marcado por:** {interaction.user}\n"
                f"**Robux:** {datos['robux']:,}"
            ),
            0xF39C12
        )

    @discord.ui.button(
        label="📦 Confirmar entrega",
        style=discord.ButtonStyle.success,
        custom_id="ticket_entrega",
    )
    async def confirmar_entrega(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not es_staff(interaction.user):
            await interaction.response.send_message("❌ Solo el **staff** puede confirmar la entrega de Robux.", ephemeral=True)
            return

        datos = tickets_activos.get(interaction.channel_id)
        if not datos:
            await interaction.response.send_message("❌ No encontre datos de este ticket.", ephemeral=True)
            return

        estado = datos.get("estado", "abierto")
        if estado == "abierto":
            await interaction.response.send_message("⚠️ El comprador aun no ha marcado el pago. Estado: **Abierto**.", ephemeral=True)
            return
        if estado == "entregado":
            await interaction.response.send_message("⚠️ Los Robux ya fueron **entregados**.", ephemeral=True)
            return
        if estado == "cerrado":
            await interaction.response.send_message("⚠️ Este ticket esta **cerrado**.", ephemeral=True)
            return

        datos["estado"]        = "entregado"
        datos["entregado_por"] = interaction.user.id
        guardar_datos()

        notif = discord.Embed(
            title="✅ ¡Robux Entregados!",
            description=(
                f"**{datos['robux']:,} Robux** han sido enviados a "
                f"**{datos['usuario_roblox']}**.\n"
                f"Entregado por: {interaction.user.mention}\n\n"
                f"¡Gracias por tu compra! 🎮"
            ),
            color=0x2ECC71,
            timestamp=datetime.datetime.utcnow(),
        )
        await interaction.response.send_message(embed=notif)

        try:
            if interaction.message:
                await interaction.message.edit(embed=crear_embed_ticket(datos))
        except Exception as e:
            logger.warning(f"Error editando embed del ticket: {e}")

        await log_accion(
            interaction.guild,
            "✅ Robux entregados",
            (
                f"**Canal:** {interaction.channel.mention}\n"
                f"**Staff:** {interaction.user}\n"
                f"**Robux:** {datos['robux']:,}\n"
                f"**Roblox:** {datos['usuario_roblox']}"
            ),
            0x2ECC71
        )

    @discord.ui.button(
        label="🔒 Cerrar ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_cerrar",
    )
    async def cerrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = tickets_activos.get(interaction.channel_id)

        if datos:
            es_autor = interaction.user.id == datos.get("autor_id")
            if not es_autor and not es_staff(interaction.user):
                await interaction.response.send_message(
                    "❌ Solo el **staff** o el creador del ticket pueden cerrarlo.", ephemeral=True
                )
                return

        await interaction.response.send_message("🔒 Cerrando ticket en **5 segundos**…")

        await log_accion(
            interaction.guild,
            "🔒 Ticket cerrado",
            (
                f"**Canal:** {interaction.channel.name}\n"
                f"**Cerrado por:** {interaction.user}\n"
                f"**Robux:** {datos.get('robux', 0):,}" if datos else ""
            ),
            0xE74C3C
        )

        await asyncio.sleep(5)
        tickets_activos.pop(interaction.channel_id, None)
        guardar_datos()

        try:
            await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("❌ No tengo permisos para eliminar el canal.", ephemeral=True)

    @discord.ui.button(
        label="📋 Ver resumen",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_resumen",
    )
    async def resumen(self, interaction: discord.Interaction, button: discord.ui.Button):
        datos = tickets_activos.get(interaction.channel_id)
        if not datos:
            await interaction.response.send_message("❌ No hay datos guardados para este ticket.", ephemeral=True)
            return

        info_pais   = TASAS_CAMBIO.get(datos.get("pais", ""), {})
        estado_info = ESTADOS.get(datos.get("estado", "abierto"), ESTADOS["abierto"])

        embed = discord.Embed(title="📋 Resumen del ticket", color=estado_info["color"])
        embed.add_field(name="Robux",          value=f"{datos['robux']:,} R$",              inline=True)
        embed.add_field(name="Pais",           value=info_pais.get("nombre", "?"),          inline=True)
        embed.add_field(name="Precio USD",     value=f"${datos.get('precio_usd', 0):.2f}", inline=True)
        embed.add_field(name="Precio local",   value=datos.get("precio_texto", "?"),        inline=True)
        embed.add_field(name="Usuario Roblox", value=datos.get("usuario_roblox", "?"),      inline=True)
        embed.add_field(name="Metodo de pago", value=datos.get("metodo_pago", "?"),         inline=True)
        embed.add_field(name="Estado",         value=f"{estado_info['emoji']} {estado_info['texto']}", inline=True)
        if datos.get("pagado_por"):
            embed.add_field(name="Pago marcado por", value=f"<@{datos['pagado_por']}>",  inline=True)
        if datos.get("entregado_por"):
            embed.add_field(name="Entregado por",    value=f"<@{datos['entregado_por']}>", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
#  VISTA DEL PANEL PRINCIPAL
# ============================================================

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
        embed = await construir_embed_tabla(
            titulo="📊 Precios de Robux",
            descripcion="Precios **oficiales** directos del vendedor:",
            color=0xF1C40F,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="💳 Metodos de pago",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_metodos_pago",
        emoji="💰",
    )
    async def metodos_pago(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💳 Metodos de Pago Disponibles",
            description=(
                "<:crypto:1354333736539525211> **Crypto**\n"
                "<:cashapp:1374105112930422804> **CashApp**\n"
                "<:paypal:1354334198751821875> **PayPal**\n"
                "<:nequi:1374103599885586452> **Nequi**\n"
                "🏦 **Transferencia**\n"
                "<:yape:1387915801390219468> **Yape**\n"
                "<:bancolombia:1374103741313319073> **Bancolombia**\n"
                "<:oxxo:1374105071415201944> **OXXO**\n"
                "🏦 **Transferencia Mexicana**\n"
                "🛒 **MercadoPago**"
            ),
            color=0x2ECC71,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="❓ Ayuda / FAQ",
        style=discord.ButtonStyle.secondary,
        custom_id="panel_ayuda",
        emoji="📖",
    )
    async def ayuda(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="❓ Preguntas frecuentes", color=0x1ABC9C)
        embed.add_field(name="¿Como compro Robux?",       value="Haz clic en **🎮 Comprar Robux**, completa el formulario y espera a un staff.", inline=False)
        embed.add_field(name="¿Cuanto tiempo tarda?",     value="Normalmente entre 5 y 30 minutos segun disponibilidad del staff.", inline=False)
        embed.add_field(name="¿Que metodos de pago aceptan?", value="Crypto, CashApp, PayPal, Nequi, Bancolombia, OXXO, Transferencia, Yape, MercadoPago y mas.", inline=False)
        embed.add_field(name="¿Es seguro?",               value="Si, nuestro staff verificado gestiona cada transaccion manualmente.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============================================================
#  PANEL DE AUTOROLES
# ============================================================

class ModalAgregarRol(discord.ui.Modal, title="➕ Agregar Autorol"):
    role_id_input = discord.ui.TextInput(
        label="ID del rol",
        placeholder="Ej: 123456789012345678",
        min_length=15, max_length=20, required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden agregar autoroles.", ephemeral=True)
            return

        try:
            role_id = int(self.role_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ La ID del rol debe ser un numero valido.", ephemeral=True)
            return

        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(f"❌ No encontre ningun rol con la ID `{role_id}` en este servidor.", ephemeral=True)
            return

        if role_id in autoroles_registrados:
            await interaction.response.send_message(f"⚠️ El rol **{role.name}** ya esta registrado como autorol.", ephemeral=True)
            return

        autoroles_registrados[role_id] = role.name
        guardar_datos()
        await interaction.response.send_message(f"✅ Rol **{role.name}** agregado a los autoroles correctamente.", ephemeral=True)

class VistaAutorolSelect(discord.ui.View):
    def __init__(self, roles_disponibles: list):
        super().__init__(timeout=120)
        opciones = [
            discord.SelectOption(label=nombre, value=str(rid))
            for rid, nombre in roles_disponibles
        ]
        select = discord.ui.Select(
            placeholder="Selecciona un rol para obtenerlo o quitarlo…",
            options=opciones,
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        role    = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ No se encontro el rol. Puede que haya sido eliminado.", ephemeral=True)
            return

        # Verificar jerarquía de roles
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "❌ No puedo asignar ese rol porque está por encima del mío en la jerarquía.",
                ephemeral=True
            )
            return

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Autorol quitado")
                await interaction.response.send_message(f"➖ Se te quito el rol **{role.name}**.", ephemeral=True)
            else:
                await interaction.user.add_roles(role, reason="Autorol asignado")
                await interaction.response.send_message(f"✅ Se te asigno el rol **{role.name}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No tengo permisos para asignar ese rol. Asegurate de que mi rol este por encima.", ephemeral=True
            )

class VistaPanelAutoroles(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Agregar rol",    style=discord.ButtonStyle.success, custom_id="panel2_agregar_rol")
    async def agregar_rol(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo los administradores pueden agregar autoroles.", ephemeral=True)
            return
        await interaction.response.send_modal(ModalAgregarRol())

    @discord.ui.button(label="Obtener autorol", style=discord.ButtonStyle.primary, custom_id="panel2_obtener_autorol")
    async def obtener_autorol(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not autoroles_registrados:
            await interaction.response.send_message("❌ No hay autoroles configurados aun. Un admin debe agregar roles primero.", ephemeral=True)
            return

        roles_validos = [
            (rid, nombre)
            for rid, nombre in autoroles_registrados.items()
            if interaction.guild.get_role(rid) is not None
        ]
        if not roles_validos:
            await interaction.response.send_message("❌ Los roles registrados ya no existen en el servidor.", ephemeral=True)
            return

        roles_validos = roles_validos[:25]

        embed = discord.Embed(
            title="🎭 Autoroles disponibles",
            description="Selecciona un rol para obtenerlo.\nSi ya lo tienes, te sera **quitado**.",
            color=0x9B59B6,
        )
        for rid, nombre in roles_validos:
            role  = interaction.guild.get_role(rid)
            tiene = "✅" if role in interaction.user.roles else "➖"
            embed.add_field(name=f"{tiene} {nombre}", value=f"<@&{rid}>", inline=True)

        vista = VistaAutorolSelect(roles_validos)
        await interaction.response.send_message(embed=embed, view=vista, ephemeral=True)

# ============================================================
#  COMANDOS SLASH
# ============================================================

@tree.command(
    name="panel",
    description="📌 Envia el panel principal de compra de Robux",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Tienda de Robux",
        description=(
            "¡Bienvenido a nuestra tienda de **Robux**! 💎\n\n"
            "Puedes comprar Robux de forma rapida y segura.\n"
            "El precio se calcula automaticamente en la **moneda de tu pais**.\n\n"
            "👇 Elige una opcion:"
        ),
        color=0x00BFFF,
    )
    embed.set_image(
        url="https://upload.wikimedia.org/wikipedia/commons/thumb/"
            "6/6e/Roblox_Logo_2022.svg/512px-Roblox_Logo_2022.svg.png"
    )
    await interaction.channel.send(embed=embed, view=VistaPanelPrincipal())
    await interaction.response.send_message("✅ Panel enviado.", ephemeral=True)

@tree.command(
    name="panel2",
    description="🛡️ Envia el panel de autoroles",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_panel2(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Panel de Autoroles",
        description=(
            "Aqui puedes gestionar los **autoroles** del servidor.\n\n"
            "**Agregar rol** — Registra un rol por su ID *(solo admins)*\n"
            "**Obtener autorol** — Elige un rol para asignartelo o quitartelo\n"
        ),
        color=0x9B59B6,
    )
    await interaction.channel.send(embed=embed, view=VistaPanelAutoroles())
    await interaction.response.send_message("✅ Panel de autoroles enviado.", ephemeral=True)

@tree.command(
    name="precio",
    description="💰 Calcula el precio de Robux en tu moneda local",
    guild=guild_obj(),
)
@app_commands.describe(robux="Cantidad de Robux", pais="Codigo de tu pais")
@app_commands.choices(pais=opciones_paises())
async def cmd_precio(interaction: discord.Interaction, robux: int, pais: str):
    codigo = pais.strip().upper()
    if codigo not in TASAS_CAMBIO:
        await interaction.response.send_message(
            f"❌ Codigo **{codigo}** no reconocido. Usa alguno de: {', '.join(TASAS_CAMBIO.keys())}",
            ephemeral=True,
        )
        return
    if robux <= 0 or robux > 30_000:
        await interaction.response.send_message("❌ La cantidad debe ser entre 1 y 30,000 Robux.", ephemeral=True)
        return

    info = TASAS_CAMBIO[codigo]
    try:
        precio_local, precio_texto, usd = await calcular_precio(robux, codigo)
    except ValueError as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        return

    rates       = await obtener_tasas_live()
    moneda_code = info["moneda"]
    tasa_usada  = rates.get(moneda_code, info["tasa"]) if rates else info["tasa"]
    fuente_tasa = (
        "🌐 Tasa en tiempo real"
        if (rates and moneda_code in rates)
        else "📌 Tasa estatica (fallback)"
    )

    embed = discord.Embed(title="💰 Calculadora de Robux", color=0xF39C12)
    embed.add_field(name="🎲 Robux",        value=f"**{robux:,} R$**",   inline=True)
    embed.add_field(name="🌍 Pais",         value=info["nombre"],        inline=True)
    embed.add_field(name="💵 Precio USD",   value=f"**${usd:.2f}**",    inline=True)
    embed.add_field(name="💰 Precio local", value=f"**{precio_texto}**", inline=True)
    embed.add_field(
        name="📈 Tasa usada",
        value=f"1 USD = {tasa_usada:,.4f} {moneda_code}\n*{fuente_tasa}*",
        inline=True,
    )
    await interaction.response.send_message(embed=embed)

@tree.command(
    name="tickets",
    description="📋 Lista los tickets activos (solo staff)",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_tickets(interaction: discord.Interaction):
    activos = {
        k: v for k, v in tickets_activos.items()
        if v.get("estado") in ("abierto", "pendiente")
    }
    if not activos:
        await interaction.response.send_message("No hay tickets activos.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📋 Tickets activos: {len(activos)}", color=0x3498DB)
    for canal_id, datos in list(activos.items())[:10]:
        canal        = interaction.guild.get_channel(canal_id)
        nombre_canal = canal.mention if canal else f"#{canal_id}"
        estado_info  = ESTADOS.get(datos.get("estado", "abierto"), ESTADOS["abierto"])
        embed.add_field(
            name=f"{estado_info['emoji']} {nombre_canal}",
            value=(
                f"<@{datos['autor_id']}> | {datos['robux']:,} R$ | "
                f"{datos.get('precio_texto', '?')} | **{estado_info['texto']}**"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(
    name="cerrar",
    description="🔒 Cierra el ticket actual",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_cerrar(interaction: discord.Interaction):
    if interaction.channel_id not in tickets_activos:
        await interaction.response.send_message("❌ Este canal no es un ticket.", ephemeral=True)
        return

    await interaction.response.send_message("🔒 Cerrando en 5 segundos…")

    datos = tickets_activos.get(interaction.channel_id, {})
    await log_accion(
        interaction.guild,
        "🔒 Ticket cerrado",
        (
            f"**Canal:** {interaction.channel.name}\n"
            f"**Cerrado por:** {interaction.user}\n"
            f"**Robux:** {datos.get('robux', 0):,}" if datos else ""
        ),
        0xE74C3C
    )

    await asyncio.sleep(5)
    tickets_activos.pop(interaction.channel_id, None)
    guardar_datos()
    try:
        await interaction.channel.delete(reason=f"Cerrado por {interaction.user}")
    except discord.Forbidden:
        await interaction.followup.send("❌ No tengo permisos para eliminar el canal.", ephemeral=True)

@tree.command(
    name="send",
    description="📊 Envia la tabla de precios de Robux al canal (solo staff)",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_send(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = await construir_embed_tabla(
        titulo="📊 Tabla de precios de Robux",
        descripcion="Precios **oficiales** directos del vendedor:",
        color=0x00BFFF,
    )
    await interaction.channel.send(embed=embed)
    await interaction.followup.send("✅ Tabla enviada.", ephemeral=True)

@tree.command(
    name="send2",
    description="💳 Envia el embed de metodos de pago al canal",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_send2(interaction: discord.Interaction):
    embed = discord.Embed(
        title="💳 Metodos de Pago Disponibles",
        description=(
            "<:crypto:1354333736539525211> **Crypto**\n"
            "<:cashapp:1374105112930422804> **CashApp**\n"
            "<:paypal:1354334198751821875> **PayPal**\n"
            "<:nequi:1374103599885586452> **Nequi**\n"
            "🏦 **Transferencia**\n"
            "<:yape:1387915801390219468> **Yape**\n"
            "<:bancolombia:1374103741313319073> **Bancolombia**\n"
            "<:oxxo:1374105071415201944> **OXXO**\n"
            "🏦 **Transferencia Mexicana**\n"
            "🛒 **MercadoPago**"
        ),
        color=0x2ECC71,
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Metodos de pago enviados.", ephemeral=True)

@tree.command(
    name="send3",
    description="🎮 Envia los grupos de Roblox",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_send3(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 Nuestros Grupos de Roblox",
        description="¡Únete a nuestras comunidades oficiales!\n\u200b",
        color=0xE74C3C,
    )
    
    # Agregar cada grupo
    grupos_texto = ""
    for grupo in GRUPOS_ROBLOX:
        grupos_texto += f"**[{grupo['nombre']}]({grupo['url']})**\n"
    
    embed.add_field(
        name="📋 Grupos Disponibles",
        value=grupos_texto,
        inline=False
    )
    
    embed.set_thumbnail(
        url="https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Roblox_Logo_2022.svg/512px-Roblox_Logo_2022.svg.png"
    )
    
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Grupos enviados.", ephemeral=True)

@tree.command(
    name="stats",
    description="📊 Estadísticas del bot (solo staff)",
    guild=guild_obj(),
)
@app_commands.check(es_admin_o_owner)
async def cmd_stats(interaction: discord.Interaction):
    total_tickets = len(tickets_activos)
    tickets_abiertos = sum(1 for t in tickets_activos.values() if t.get("estado") == "abierto")
    tickets_pendientes = sum(1 for t in tickets_activos.values() if t.get("estado") == "pendiente")
    tickets_entregados = sum(1 for t in tickets_activos.values() if t.get("estado") == "entregado")
    
    total_robux = sum(t.get("robux", 0) for t in tickets_activos.values())
    
    embed = discord.Embed(title="📊 Estadísticas del Bot", color=0x3498DB)
    embed.add_field(name="Tickets Totales", value=str(total_tickets), inline=True)
    embed.add_field(name="🟢 Abiertos", value=str(tickets_abiertos), inline=True)
    embed.add_field(name="🟡 Pendientes", value=str(tickets_pendientes), inline=True)
    embed.add_field(name="✅ Entregados", value=str(tickets_entregados), inline=True)
    embed.add_field(name="💎 Robux Totales", value=f"{total_robux:,} R$", inline=True)
    embed.add_field(name="🎫 Contador", value=str(ticket_counter), inline=True)
    embed.add_field(name="🎭 Autoroles", value=str(len(autoroles_registrados)), inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(
    name="cleanup",
    description="🧹 Elimina tickets cerrados antiguos (solo admins)",
    guild=guild_obj(),
)
@app_commands.describe(dias="Días de antigüedad mínima (default: 7)")
@app_commands.check(es_admin_o_owner)
async def cmd_cleanup(interaction: discord.Interaction, dias: int = 7):
    await interaction.response.defer(ephemeral=True)
    
    eliminados = 0
    ahora = datetime.datetime.utcnow()
    
    for canal_id, datos in list(tickets_activos.items()):
        if datos.get("estado") == "cerrado":
            creado = datos.get("creado_en")
            if isinstance(creado, str):
                try:
                    creado = datetime.datetime.fromisoformat(creado)
                except:
                    creado = ahora
            
            if (ahora - creado).days > dias:
                canal = interaction.guild.get_channel(canal_id)
                if canal:
                    try:
                        await canal.delete(reason="Cleanup automático")
                        eliminados += 1
                    except:
                        pass
                tickets_activos.pop(canal_id, None)
    
    guardar_datos()
    await interaction.followup.send(
        f"✅ Limpieza completada. {eliminados} tickets eliminados.",
        ephemeral=True
    )

# ============================================================
#  EVENTOS
# ============================================================

@bot.event
async def on_ready():
    cargar_datos()

    bot.add_view(VistaPanelPrincipal())
    bot.add_view(VistaTicket())
    bot.add_view(VistaPanelAutoroles())

    try:
        if GUILD_ID:
            synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
            logger.info(f"✅ Bot listo: {bot.user} | {len(synced)} comandos sincronizados en guild {GUILD_ID}")
        else:
            synced = await tree.sync()
            logger.info(f"✅ Bot listo: {bot.user} | {len(synced)} comandos sincronizados GLOBALMENTE")
    except Exception as e:
        logger.warning(f"⚠️ Error sincronizando comandos: {e}")

    try:
        await obtener_tasas_live()
    except Exception as e:
        logger.warning(f"⚠️ No se pudieron cargar tasas live: {e}")
    
    # Iniciar backup automático
    bot.loop.create_task(backup_automatico())

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
        msg = "❌ No tienes permisos para usar este comando."
    else:
        msg = f"❌ Error: {error}"
        logger.error(f"Error en comando: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

# ============================================================
#  ARRANQUE
# ============================================================
keep_alive()

if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN no configurado")
    exit(1)

if GUILD_ID:
    logger.info(f"🏠 Modo guild: comandos registrados en servidor {GUILD_ID}")
else:
    logger.info("🌐 Modo global: comandos registrados en todos los servidores (tarda ~1 hora en aparecer)")

bot.run(BOT_TOKEN, log_handler=None)
