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
    SlashCommandBuilder,
    REST,
    Routes
} = require('discord.js');
const dotenv = require('dotenv');
const axios = require('axios');
const express = require('express');

dotenv.config();

// ==================== VERIFICAR VARIABLES DE ENTORNO ====================
console.log('🔍 Verificando configuración...');
console.log(`DISCORD_TOKEN: ${process.env.DISCORD_TOKEN ? '✓ Configurado' : '✗ FALTA'}`);
console.log(`CLIENT_ID: ${process.env.CLIENT_ID ? '✓ Configurado' : '✗ FALTA'}`);

if (!process.env.DISCORD_TOKEN || !process.env.CLIENT_ID) {
    console.error('❌ ERROR: Faltan variables de entorno. Revisa tu archivo .env');
    process.exit(1);
}

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
                <p>${new Date().toLocaleString()}</p>
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

// Tasas de cambio
const fallbackRates = {
    'MX': 17.50, 'AR': 820.00, 'CL': 950.00, 'CO': 4000.00, 'PE': 3.80,
    'US': 1.00, 'ES': 0.92, 'BR': 5.05, 'VE': 36.00, 'UY': 39.00,
    'CR': 530.00, 'DO': 58.00, 'PA': 1.00, 'PY': 7300.00, 'BO': 6.90
};

const currencyMap = {
    'MX': 'MXN', 'AR': 'ARS', 'CL': 'CLP', 'CO': 'COP', 'PE': 'PEN',
    'US': 'USD', 'ES': 'EUR', 'BR': 'BRL', 'VE': 'VES', 'UY': 'UYU',
    'CR': 'CRC', 'DO': 'DOP', 'PA': 'PAB', 'PY': 'PYG', 'BO': 'BOB'
};

// ==================== REGISTRAR COMANDOS ====================
async function registerCommands() {
    const commands = [
        new SlashCommandBuilder()
            .setName('panel')
            .setDescription('Muestra el panel de tickets para comprar Robux')
    ];

    const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

    try {
        console.log('🔄 Registrando comandos slash...');
        await rest.put(
            Routes.applicationCommands(process.env.CLIENT_ID),
            { body: commands.map(cmd => cmd.toJSON()) }
        );
        console.log('✅ Comandos slash registrados globalmente');
    } catch (error) {
        console.error('❌ Error registrando comandos:', error);
    }
}

// ==================== EVENTO READY ====================
client.once('ready', async () => {
    console.log('✅ BOT CONECTADO EXITOSAMENTE!');
    console.log(`📊 Información del Bot:`);
    console.log(`   • Usuario: ${client.user.tag}`);
    console.log(`   • ID: ${client.user.id}`);
    console.log(`   • Servidores: ${client.guilds.cache.size}`);
    
    await registerCommands();
    
    client.user.setActivity('/panel | Tickets 24/7', { type: 3 });
    console.log('🎫 Bot listo para usar!');
});

// ==================== FUNCIONES ====================
async function getExchangeRate(countryCode) {
    try {
        const currency = currencyMap[countryCode] || 'USD';
        const response = await axios.get(`https://api.exchangerate-api.com/v4/latest/USD`);
        return response.data.rates[currency] || fallbackRates[countryCode] || 1;
    } catch (error) {
        console.log('Usando tasa de cambio local');
        return fallbackRates[countryCode] || 1;
    }
}

async function getOrCreateCategory(guild) {
    let category = guild.channels.cache.find(c => c.name === '📋 TICKETS' && c.type === 4);
    
    if (!category) {
        try {
            category = await guild.channels.create({
                name: '📋 TICKETS',
                type: 4
            });
        } catch (error) {
            console.error('Error creando categoría:', error);
            return null;
        }
    }
    return category;
}

// ==================== INTERACCIONES ====================
client.on('interactionCreate', async interaction => {
    try {
        // Comando /panel
        if (interaction.isChatInputCommand() && interaction.commandName === 'panel') {
            const embed = new EmbedBuilder()
                .setColor(0x0099FF)
                .setTitle('🎫 Sistema de Compra de Robux')
                .setDescription('Bienvenido al sistema de compra de Robux!')
                .addFields(
                    { name: '📋 Instrucciones', value: '1️⃣ Haz clic en "Crear Ticket"\n2️⃣ Completa el formulario\n3️⃣ Recibe el precio en tu moneda' },
                    { name: '💰 Países soportados', value: '🇲🇽 MX, 🇦🇷 AR, 🇨🇱 CL, 🇨🇴 CO, 🇵🇪 PE, 🇺🇸 US, 🇪🇸 ES, 🇧🇷 BR' }
                )
                .setTimestamp();

            const button = new ButtonBuilder()
                .setCustomId('crear_ticket')
                .setLabel('🎫 Crear Ticket')
                .setStyle(ButtonStyle.Success);

            const row = new ActionRowBuilder().addComponents(button);

            await interaction.reply({ embeds: [embed], components: [row] });
        }

        // Botón crear ticket
        if (interaction.isButton() && interaction.customId === 'crear_ticket') {
            const modal = new ModalBuilder()
                .setCustomId('formulario_ticket')
                .setTitle('Formulario de Compra');

            const paisInput = new TextInputBuilder()
                .setCustomId('pais')
                .setLabel('¿De qué país eres? (Ej: MX, AR, CL, CO)')
                .setStyle(TextInputStyle.Short)
                .setPlaceholder('Código de 2 letras')
                .setRequired(true)
                .setMaxLength(2);

            const robuxInput = new TextInputBuilder()
                .setCustomId('robux')
                .setLabel('¿Cuántos Robux quieres?')
                .setStyle(TextInputStyle.Short)
                .setPlaceholder('Ej: 1000')
                .setRequired(true);

            const firstRow = new ActionRowBuilder().addComponents(paisInput);
            const secondRow = new ActionRowBuilder().addComponents(robuxInput);

            modal.addComponents(firstRow, secondRow);
            await interaction.showModal(modal);
        }

        // Botón cerrar ticket
        if (interaction.isButton() && interaction.customId === 'cerrar_ticket') {
            await interaction.reply({ content: '🔒 Cerrando ticket en 5 segundos...' });
            
            setTimeout(async () => {
                try {
                    await interaction.channel.delete();
                } catch (error) {
                    console.error('Error cerrando ticket:', error);
                }
            }, 5000);
        }

        // Formulario enviado
        if (interaction.isModalSubmit() && interaction.customId === 'formulario_ticket') {
            await interaction.deferReply({ ephemeral: true });

            const pais = interaction.fields.getTextInputValue('pais').toUpperCase();
            const robux = parseInt(interaction.fields.getTextInputValue('robux'));

            // Validaciones
            if (isNaN(robux) || robux <= 0) {
                return await interaction.editReply({ content: '❌ Cantidad inválida' });
            }

            if (!currencyMap[pais]) {
                return await interaction.editReply({ 
                    content: `❌ País no soportado. Usa: ${Object.keys(currencyMap).join(', ')}` 
                });
            }

            // Calcular precio
            const rate = await getExchangeRate(pais);
            const precioUSD = (robux * 0.0125).toFixed(2);
            const precioLocal = (precioUSD * rate).toFixed(2);

            // Crear canal
            const category = await getOrCreateCategory(interaction.guild);
            const ticketChannel = await interaction.guild.channels.create({
                name: `ticket-${interaction.user.username}`,
                type: 0,
                parent: category,
                permissionOverwrites: [
                    { id: interaction.guild.id, deny: ['ViewChannel'] },
                    { id: interaction.user.id, allow: ['ViewChannel', 'SendMessages'] },
                    { id: client.user.id, allow: ['ViewChannel', 'SendMessages'] }
                ]
            });

            const embed = new EmbedBuilder()
                .setColor(0x00FF00)
                .setTitle('✅ Ticket Creado')
                .addFields(
                    { name: '📋 País', value: pais, inline: true },
                    { name: '💰 Robux', value: robux.toString(), inline: true },
                    { name: '💵 Precio local', value: `${precioLocal}`, inline: true }
                );

            const closeButton = new ButtonBuilder()
                .setCustomId('cerrar_ticket')
                .setLabel('🔒 Cerrar')
                .setStyle(ButtonStyle.Danger);

            const row = new ActionRowBuilder().addComponents(closeButton);

            await ticketChannel.send({ 
                content: `${interaction.user} ¡Bienvenido!`,
                embeds: [embed],
                components: [row]
            });

            await interaction.editReply({ 
                content: `✅ Ticket creado: ${ticketChannel}` 
            });
        }
    } catch (error) {
        console.error('Error en interacción:', error);
        if (!interaction.replied) {
            await interaction.reply({ 
                content: '❌ Error procesando solicitud', 
                ephemeral: true 
            });
        }
    }
});

// ==================== MANEJADOR DE ERRORES ====================
client.on('error', error => {
    console.error('❌ Error del cliente:', error);
});

process.on('unhandledRejection', error => {
    console.error('❌ Error no manejado:', error);
});

// ==================== INICIAR BOT ====================
console.log('🔄 Intentando conectar el bot...');
client.login(process.env.DISCORD_TOKEN).then(() => {
    console.log('🟢 Login exitoso!');
}).catch(error => {
    console.error('❌ ERROR FATAL - No se pudo conectar:');
    console.error(`   • Mensaje: ${error.message}`);
    if (error.message.includes('token')) {
        console.error('   • Solución: El token es inválido. Regenera el token en Discord Developer Portal');
    }
    process.exit(1);
});
