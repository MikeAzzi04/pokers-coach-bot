# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from openai import OpenAI

client_ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Track active sessions
active_sessions = {}

# NEW: memory per user
user_memory = {}

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

    # NEW: initialize memory
    user_memory[user.id] = []

    await interaction.response.send_message(
        f"Your private coach session is ready: {channel.mention}",
        ephemeral=True
    )

    # NEW: welcome message
    await channel.send(
        f"Hey {user.name} 👋\n\n"
        "I’m your poker coach.\n"
        "Ask me anything about poker, blackjack, or strategy.\n"
        "Let’s improve your game."
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

    # NEW: delete memory
    if user.id in user_memory:
        del user_memory[user.id]

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

    if user_id in active_sessions and message.channel.id == active_sessions[user_id]:

        await message.channel.typing()

        # NEW: build memory
        history = user_memory.get(user_id, [])

        history.append({"role": "user", "content": message.content})

        # limit memory
        history = history[-15:]

        try:
            response = None

            for attempt in range(3):  # retry system
                try:
                    await asyncio.sleep(0.3)

                    response = client_ai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": """You are a smart, natural poker coach.

Behave like ChatGPT.

Understand slang, greetings, typos, weird inputs (like "hellozzz", "yo", "thx").

Respond naturally.

If message is even slightly related to poker/gambling → answer.

If casual (hi, thanks, etc) → respond normally.

ONLY reject if completely unrelated:
"I focus on poker, blackjack, and strategy."

Style:
- friendly
- confident
- not robotic
"""
                            }
                        ] + history
                    )

                    break

                except Exception as e:
                    print(f"Retry {attempt+1} failed:", e)
                    await asyncio.sleep(1)

            if response is None:
                await message.channel.send("Try again in a second.")
                return

            reply = response.choices[0].message.content

            await message.channel.send(reply)

            # NEW: save assistant reply
            history.append({"role": "assistant", "content": reply})
            user_memory[user_id] = history

        except Exception as e:
            print("FINAL ERROR:", e)
            await message.channel.send("Something went wrong. Try again.")

    await bot.process_commands(message)

bot.run(os.environ["TOKEN"])
