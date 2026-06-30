# -*- coding: utf-8 -*-
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from openai import OpenAI

# ===== CONFIG =====
client_ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TERMS_CHANNEL_ID = 1417522975514824806
PORTAL_CHANNEL_ID = 1521311652350263378
TIPS_CHANNEL_ID = 1521311587711979640    

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== DATA =====
active_sessions = {}
user_memory = {}

# ========================
# READY
# ========================
@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready: {bot.user}")
    if not daily_poker_tip.is_running():
        daily_poker_tip.start()

# ========================
# DM ON JOIN
# ========================
@bot.event
async def on_member_join(member):
    try:
        terms_channel = f"<#{TERMS_CHANNEL_ID}>"
        portal_channel = f"<#{PORTAL_CHANNEL_ID}>"

        message = f"""
Hey {member.mention}

Welcome to The Dealer.

This is a private poker community built around strategy, discipline, pressure, and respect for the game.

Every hand matters.
Every decision counts.
Every player earns their place at the table.

Complete your verification {terms_channel}, explore the server through {portal_channel}, and take your seat.

Good luck.

- The Dealer -
"""
        await member.send(message)

    except:
        print("Couldn't DM user")

# ========================
# ANNOUNCEMENT COMMAND
# ========================
@tree.command(name="send", description="Send message with media")
@app_commands.describe(channel="Channel", message="Message", media="Image or video")
async def send(interaction: discord.Interaction, channel: discord.TextChannel, message: str, media: discord.Attachment = None):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    try:
        embed = discord.Embed(description=message, color=0x0A1AFF)
        embed.set_footer(text="The Dealer")

        if media and media.content_type and media.content_type.startswith("image"):
            embed.set_image(url=media.url)

        if media and (not media.content_type or not media.content_type.startswith("image")):
            await channel.send(embed=embed, file=await media.to_file())
        else:
            await channel.send(embed=embed)

        await interaction.response.send_message("Sent", ephemeral=True)

    except Exception as e:
        print(e)
        await interaction.response.send_message("Failed", ephemeral=True)

# ========================
# COACH SYSTEM
# ========================
@tree.command(name="coach", description="Start private poker coaching session")
async def coach(interaction: discord.Interaction):

    user = interaction.user
    guild = interaction.guild

    if user.id in active_sessions:
        await interaction.response.send_message("You already have a session.", ephemeral=True)
        return

    channel_name = f"coach-{user.name}".lower().replace(" ", "-")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)

    active_sessions[user.id] = channel.id
    user_memory[user.id] = []

    await interaction.response.send_message(f"Session ready: {channel.mention}", ephemeral=True)

    await channel.send(f"Hey {user.name} 👋\nI’m your poker coach. Ask anything.")

@tree.command(name="end-coach", description="End coaching session")
async def end_coach(interaction: discord.Interaction):

    user = interaction.user

    if user.id not in active_sessions:
        await interaction.response.send_message("No active session.", ephemeral=True)
        return

    channel = bot.get_channel(active_sessions[user.id])

    if channel:
        await channel.delete()

    del active_sessions[user.id]
    if user.id in user_memory:
        del user_memory[user.id]

    await interaction.response.send_message("Session ended.", ephemeral=True)

# ========================
# AI CHAT (FIXED PROMPT)
# ========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id

    if user_id in active_sessions and message.channel.id == active_sessions[user_id]:

        await message.channel.typing()

        history = user_memory.get(user_id, [])
        history.append({"role": "user", "content": message.content})
        history = history[-15:]

        try:
            response = None

            for _ in range(3):
                try:
                    await asyncio.sleep(0.3)

                    response = client_ai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": """You are a smart, natural poker coach.

Behave like ChatGPT.

Understand slang, greetings, typos, and weird inputs (like "hellozzz", "yo", "thx").

Respond naturally and conversationally.

If the message is related to poker, blackjack, or strategy → answer clearly.

If the message is casual (hi, thanks, small talk) → respond like a normal human.

If the topic is completely unrelated:
- respond naturally
- vary your wording every time
- keep it short and casual
- do NOT repeat the same sentence

Examples of tone (do not copy exactly):
- "Not really my area — I stick to poker."
- "That’s outside my lane — got any poker questions?"
- "I can’t help much with that, but I can break down poker spots."

Style:
- human
- confident
- relaxed
- not robotic
"""
                            }
                        ] + history
                    )
                    break
                except:
                    await asyncio.sleep(1)

            if response is None:
                await message.channel.send("Try again.")
                return

            reply = response.choices[0].message.content
            await message.channel.send(reply)

            history.append({"role": "assistant", "content": reply})
            user_memory[user_id] = history

        except Exception as e:
            print(e)
            await message.channel.send("Error.")

    await bot.process_commands(message)

# ========================
# /TIP COMMAND
# ========================
@tree.command(name="tip", description="Get a poker tip")
async def tip(interaction: discord.Interaction):

    await interaction.response.defer()

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional poker coach.

Generate ONE poker tip.

Rules:
- short
- practical
- not generic
- real strategy
"""
                }
            ]
        )

        tip = response.choices[0].message.content

        await interaction.followup.send(f"♠️ Poker Tip:\n{tip}")

    except:
        await interaction.followup.send("Try again.")

# ========================
# DAILY TIP
# ========================
@tasks.loop(hours=24)
async def daily_poker_tip():
    await bot.wait_until_ready()

    channel = bot.get_channel(TIPS_CHANNEL_ID)
    if not channel:
        return

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Generate one short practical poker tip."
                }
            ]
        )

        tip = response.choices[0].message.content
        await channel.send(f"♠️ Daily Poker Tip:\n{tip}")

    except:
        await channel.send("♠️ Daily Poker Tip:\nPlay disciplined and stick to your strategy.")

# ========================
# RUN
# ========================
bot.run(os.environ["TOKEN"])
