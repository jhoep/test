const { 
    Client, 
    GatewayIntentBits, 
    EmbedBuilder, 
    ActionRowBuilder, 
    ButtonBuilder, 
    ButtonStyle,
    ModalBuilder,
    TextInputBuilder,
    TextInputStyle,
    SlashCommandBuilder
} = require('discord.js');
const dotenv = require('dotenv');
const axios = require('axios');
const express = require('express');

dotenv.config();

// ==================== CONFIGURACIÓN ====================
const TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.CLIENT_ID;
const GUILD_ID = process.env.GUILD_ID;

// Tasas de cambio aproximadas (fallback)
const fallbackRates = {
    'MX': 17.50, // Peso Mexicano
    'AR': 820.00, // Peso Argentino
    'CL': 950.00, // Peso Chileno
    'CO': 4000.00, // Peso Colombiano
    'PE': 3.80, // Sol Peruano
    'US': 1.00, // Dólar
    'ES': 0.92, // Euro
    'BR': 5.05, // Real Brasileño
    'VE': 36.00, // Bolívar
    'UY': 39.00, // Peso Uruguayo
    'CR': 530.00, // Colón Costarricense
    'DO': 58.00, // Peso Dominicano
    'PA': 1.00, // Balboa (igual que USD)
    'PY': 7300.00, // Guaraní
    'BO': 6.90 // Boliviano
};

// Mapa de códigos de país a moneda
const currencyMap = {
    'MX': 'MXN', 'AR': 'ARS', 'CL': 'CLP', 'CO': 'COP', 'PE': 'PEN',
    'US': 'USD', 'ES': 'EUR', 'BR': 'BRL', 'VE': 'VES', 'UY': 'UYU',
    'CR': 'CRC', 'DO': 'DOP', 'PA': 'PAB', 'PY': 'PYG', 'BO': 'BOB'
};

// ==================== SERVIDOR WEB (para Render) ====================
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
    res.send(`
        <html>
            <head><title>Discord Bot</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>🤖 Bot de Discord está funcionando!</h1>
                <p>El bot de tickets está activo 24/7</p>
                <p>🟢 Estado: ONLINE</p>
            </body>
        </html>
    `);
});

app.listen(PORT, () => {
    console.log(`✅ Servidor web iniciado en puerto ${PORT}`);
});

// ==================== CONFIGURACIÓN DEL BOT ====================
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

// ==================== COMANDOS SLASH ====================
const commands = [
    new SlashCommandBuilder()
        .setName('panel')
        .setDescription('Muestra el panel de tickets para comprar Robux')
];

// ==================== FUNCIONES ====================

// Obtener tasa de cambio
async function getExchangeRate(countryCode) {
    try {
        const currency = currencyMap[countryCode] || 'USD';
        const response = await axios.get(`https://api.exchangerate-api.com/v4/latest/USD`);
        return response.data.rates[currency] || fallbackRates[countryCode] || 1;
    } catch (error) {
        console.log('Usando tasa de cambio local:', error.message);
        return fallbackRates[countryCode] || 1;
    }
}

// Obtener o crear categoría de tickets
async function getOrCreateCategory(guild) {
    let category = guild.channels.cache.find(c => c.name === '📋 TICKETS' && c.type === 4);
    
    if (!category) {
        try {
            category = await guild.channels.create({
                name: '📋 TICKETS',
                type: 4 // GUILD_CATEGORY
            });
        } catch (error) {
            console.error('Error creando categoría:', error);
            return null;
        }
    }
    return category;
}

// ==================== MANEJADOR DE COMANDOS ====================
client.once('ready', async () => {
    console.log(`✅ Bot conectado como ${client.user.tag}`);
    
    try {
        await client.application.commands.set(commands);
        console.log('✅ Comandos slash registrados globalmente');
    } catch (error) {
        console.error('Error registrando comandos:', error);
    }
    
    client.user.setActivity('/panel | Tickets 24/7', { type: 3 });
    console.log('🎫 Bot listo para usar!');
});

// ==================== INTERACCIONES ====================
client.on('interactionCreate', async interaction => {
    
    // ===== COMANDO /PANEL =====
    if (interaction.isChatInputCommand() && interaction.commandName === 'panel') {
        const embed = new EmbedBuilder()
            .setColor(0x0099FF)
            .setTitle('🎫 Sistema de Compra de Robux')
            .setDescription('Bienvenido al sistema de compra de Robux!\n\nHaz clic en el botón de abajo para crear un ticket y comprar Robux con precio en tu moneda local.')
            .addFields(
                { name: '📋 Instrucciones', value: '1️⃣ Haz clic en "Crear Ticket"\n2️⃣ Completa el formulario con tu país y cantidad\n3️⃣ Recibe el precio automático en tu moneda local\n4️⃣ Un moderador te atenderá' },
                { name: '💰 Países soportados', value: '🇲🇽 MX - México\n🇦🇷 AR - Argentina\n🇨🇱 CL - Chile\n🇨🇴 CO - Colombia\n🇵🇪 PE - Perú\n🇺🇸 US - Estados Unidos\n🇪🇸 ES - España\n🇧🇷 BR - Brasil\n🇻🇪 VE - Venezuela\n🇺🇾 UY - Uruguay' },
                { name: '💵 Precio aproximado', value: '100 Robux ≈ $1.25 USD' }
            )
            .setFooter({ text: 'Sistema Automático de Tickets' })
            .setTimestamp();

        const button = new ButtonBuilder()
            .setCustomId('crear_ticket')
            .setLabel('🎫 Crear Ticket')
            .setStyle(ButtonStyle.Success)
            .setEmoji('🎟️');

        const row = new ActionRowBuilder().addComponents(button);

        await interaction.reply({ embeds: [embed], components: [row] });
    }
    
    // ===== BOTÓN CREAR TICKET =====
    if (interaction.isButton() && interaction.customId === 'crear_ticket') {
        
        const modal = new ModalBuilder()
            .setCustomId('formulario_ticket')
            .setTitle('Formulario de Compra de Robux');

        const paisInput = new TextInputBuilder()
            .setCustomId('pais')
            .setLabel('¿De qué país eres? (Ej: MX, AR, CL, CO, US)')
            .setStyle(TextInputStyle.Short)
            .setPlaceholder('Ingresa el código de 2 letras de tu país')
            .setRequired(true)
            .setMaxLength(2)
            .setMinLength(2);

        const robuxInput = new TextInputBuilder()
            .setCustomId('robux')
            .setLabel('¿Cuántos Robux quieres comprar?')
            .setStyle(TextInputStyle.Short)
            .setPlaceholder('Ejemplo: 1000, 2000, 5000')
            .setRequired(true);

        const firstRow = new ActionRowBuilder().addComponents(paisInput);
        const secondRow = new ActionRowBuilder().addComponents(robuxInput);

        modal.addComponents(firstRow, secondRow);

        await interaction.showModal(modal);
    }
    
    // ===== BOTÓN CERRAR TICKET =====
    if (interaction.isButton() && interaction.customId === 'cerrar_ticket') {
        await interaction.reply({ content: '🔒 Cerrando ticket en **5 segundos**...' });
        
        setTimeout(async () => {
            try {
                await interaction.channel.delete();
            } catch (error) {
                console.error('Error cerrando ticket:', error);
            }
        }, 5000);
    }
    
    // ===== FORMULARIO ENVIADO =====
    if (interaction.isModalSubmit() && interaction.customId === 'formulario_ticket') {
        await interaction.deferReply({ ephemeral: true });

        const pais = interaction.fields.getTextInputValue('pais').toUpperCase().trim();
        const robuxStr = interaction.fields.getTextInputValue('robux');
        const robux = parseInt(robuxStr);

        // Validaciones
        if (isNaN(robux) || robux <= 0) {
            return await interaction.editReply({ 
                content: '❌ Error: Por favor, ingresa una cantidad válida de Robux (número positivo).' 
            });
        }

        if (robux > 100000) {
            return await interaction.editReply({ 
                content: '❌ Error: La cantidad máxima permitida es 100,000 Robux.' 
            });
        }

        if (!currencyMap[pais]) {
            return await interaction.editReply({ 
                content: `❌ Error: País no soportado. Usa uno de estos: ${Object.keys(currencyMap).join(', ')}` 
            });
        }

        // Obtener tasa de cambio
        const rate = await getExchangeRate(pais);
        const precioUSD = (robux * 0.0125).toFixed(2); // 100 Robux = $1.25 USD
        const precioLocal = (precioUSD * rate).toFixed(2);

        // Crear canal de ticket
        try {
            const category = await getOrCreateCategory(interaction.guild);
            
            const ticketChannel = await interaction.guild.channels.create({
                name: `ticket-${interaction.user.username.toLowerCase()}`,
                type: 0, // GUILD_TEXT
                parent: category,
                permissionOverwrites: [
                    {
                        id: interaction.guild.id,
                        deny: ['ViewChannel']
                    },
                    {
                        id: interaction.user.id,
                        allow: ['ViewChannel', 'SendMessages', 'ReadMessageHistory']
                    },
                    {
                        id: client.user.id,
                        allow: ['ViewChannel', 'SendMessages', 'ReadMessageHistory']
                    }
                ]
            });

            // Embed de información del ticket
            const embed = new EmbedBuilder()
                .setColor(0x00FF00)
                .setTitle('✅ Ticket Creado Correctamente')
                .setDescription(`Ticket creado por ${interaction.user}`)
                .addFields(
                    { name: '📋 País', value: `🇺🇳 ${pais}`, inline: true },
                    { name: '💰 Robux solicitados', value: `${robux.toLocaleString()} Robux`, inline: true },
                    { name: '💵 Precio en USD', value: `$${precioUSD} USD`, inline: true },
                    { name: '💱 Precio local', value: `${precioLocal} (moneda local)`, inline: true },
                    { name: '📊 Tasa de cambio', value: `1 USD = ${rate} ${currencyMap[pais]}`, inline: true },
                    { name: '👤 Usuario', value: `${interaction.user.tag}`, inline: true }
                )
                .setColor(0x0099FF)
                .setTimestamp()
                .setFooter({ text: 'Sistema de Tickets • Usa el botón para cerrar' });

            // Botón de cerrar
            const closeButton = new ButtonBuilder()
                .setCustomId('cerrar_ticket')
                .setLabel('🔒 Cerrar Ticket')
                .setStyle(ButtonStyle.Danger)
                .setEmoji('🔒');

            const row = new ActionRowBuilder().addComponents(closeButton);

            // Mensaje de bienvenida
            await ticketChannel.send({ 
                content: `${interaction.user} ¡Bienvenido a tu ticket! Un moderador te atenderá en breve.`,
                embeds: [embed],
                components: [row]
            });

            // Mensaje de confirmación
            await interaction.editReply({ 
                content: `✅ **Ticket creado exitosamente!**\n🔗 Ve a tu ticket: ${ticketChannel}` 
            });

            // Log para el servidor
            console.log(`📝 Ticket creado por ${interaction.user.tag} - ${robux} Robux (${pais})`);

        } catch (error) {
            console.error('Error creando ticket:', error);
            await interaction.editReply({ 
                content: '❌ Error al crear el ticket. Contacta a un administrador.' 
            });
        }
    }
});

// ==================== MANEJADOR DE ERRORES ====================
process.on('unhandledRejection', error => {
    console.error('❌ Error no manejado:', error);
});

// ==================== INICIAR BOT ====================
client.login(TOKEN).catch(error => {
    console.error('❌ Error al iniciar sesión:', error);
});