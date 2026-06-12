# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import os
from openai import OpenAI

client_ai = OpenAI(api_key="

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Track active sessions
active_sessions = {}

# ========================
# BOT READY
# ========================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Coach bot ready: {bot.user}")

# ========================
# CREATE COACH CHANNEL
# ========================
@tree.command(name="coach", description="Start private poker coaching session")
async def coach(interaction: discord.Interaction):

    user = interaction.user
    guild = interaction.guild

    if user.id in active_sessions:
        await interaction.response.send_message(
            "You already have an active coaching session.",
            ephemeral=True
        )
        return

    channel_name = f"coach-{user.name}".lower().replace(" ", "-")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites
    )

    active_sessions[user.id] = channel.id

    await interaction.response.send_message(
        f"Your private coach session is ready: {channel.mention}",
        ephemeral=True
    )

# ========================
# END SESSION
# ========================
@tree.command(name="end-coach", description="End your coaching session")
async def end_coach(interaction: discord.Interaction):

    user = interaction.user

    if user.id not in active_sessions:
        await interaction.response.send_message(
            "You don't have an active session.",
            ephemeral=True
        )
        return

    channel_id = active_sessions[user.id]
    channel = bot.get_channel(channel_id)

    if channel:
        await channel.delete()

    del active_sessions[user.id]

    await interaction.response.send_message(
        "Coaching session ended.",
        ephemeral=True
    )

# ========================
# AI CHAT IN PRIVATE CHANNEL
# ========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id

    # Only respond inside user's coach channel
    if user_id in active_sessions and message.channel.id == active_sessions[user_id]:

        try:
            response = client_ai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
    "role": "system",
    "content": """You are a professional poker coach and gambling strategist.

Your job is to help users improve at poker, blackjack, and decision-making in gambling.

You should answer:
- Poker questions
- Blackjack questions
- Gambling strategy
- Odds and probability
- Learning poker or card games
- Mindset, discipline, and decision-making in games

If a question is even slightly related to poker, gambling, or strategy, answer it helpfully.

If unsure, assume it is related and answer.

Only reject questions if they are completely unrelated (like cars, politics, or random topics), and respond with:
"I focus on poker, blackjack, and strategy."

Keep answers:
- clear
- practical
- slightly confident
- conversational (like a real coach)
- not too long unless needed
"""
},
                    {
                        "role": "user",
                        "content": message.content
                    }
                ]
            )

            reply = response.choices[0].message.content

            await message.channel.send(reply)

        except Exception as e:
            print(e)
            await message.channel.send("Error processing request.")

    await bot.process_commands(message)

bot.run(os.getenv("TOKEN"))
