# //------------------------ IMPORTS ------------------------//
from enum import member
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import random
from datetime import timedelta
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import webserver

# //------------------------ GLOBAL VARS ------------------------//
load_dotenv()
token = os.getenv("DISCORD_TOKEN")
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

admin_role = int(os.getenv("ADMIN_ROLE_ID"))
driver_role = int(os.getenv("DRIVER_ROLE_ID"))
poll_channel = int(os.getenv("POLL_CHANNEL_ID"))
standings_channel = int(os.getenv("STANDINGS_CHANNEL_ID"))
ranking_channel = int(os.getenv("RANKING_CHANNEL_ID"))
commands_channel = int(os.getenv("COMMANDS_CHANNEL_ID"))

# //------------------------ FUNCTIONS ------------------------//
async def generate_poll():
    channel = bot.get_channel(poll_channel)
    role = discord.utils.get(channel.guild.roles, id=driver_role)

    timeout = timedelta(days=7)
    participation_poll = discord.Poll("Participo en la próxima carrera", timeout)

    participation_poll.add_answer(text="Sí", emoji="✅")
    participation_poll.add_answer(text="No", emoji="❌")

    await channel.send(role.mention, poll=participation_poll)

def generate_points(quantity):
    points = os.getenv("POINT_SYSTEM").split(',')

    if quantity <= len(points):
        return points[:quantity]
    else:
        return [0] * (quantity - len(points)) + points

# //------------------------ EVENTS ------------------------//
@bot.event
async def on_ready():
    print(f'Radio check')

    scheduler = AsyncIOScheduler()
    scheduler.add_job(generate_poll, 'cron', day_of_week=0)
    scheduler.start()

@bot.event
async def on_member_join(member):
    display_name = member.display_name[:3].upper()
    await member.edit(nick=display_name)

# //------------------------ COMMANDS ------------------------//
# Generate random number between start_number and end_number to select a track
# TODO: Add exclude numbers parameter
@bot.command()
async def pista(ctx, start_number, end_number):
    try:
        start_number = int(start_number)
        end_number = int(end_number)

        if start_number >= end_number:
            start_number, end_number = end_number, start_number
        
        result = random.randint(start_number, end_number)

        selected_track = f"```ansi\n\u001b[1;2mPISTA: {result}\n```"

        await ctx.send(selected_track)
    except ValueError:
        await ctx.send("No se ha introducido un número válido.")
        
# Generate participation poll
# TODO: Add race date
@bot.command()
async def encuesta(ctx):
    await generate_poll()

# Send a decorated message in a specific channel with the given text
@bot.command()
async def resultado(ctx, standings, track):
    role = discord.utils.get(ctx.guild.roles, id=admin_role)
   
    if role in ctx.author.roles:
        channel = bot.get_channel(standings_channel)
        standings_list = standings.split(',')
        points = generate_points(len(standings_list))

        leaderboard = "```ansi\n"
        leaderboard += f"\u001b[1;2m####### 🏁 {track.upper()} 🏁 #######\n"

        for i, driver in enumerate(standings_list, 1):
            leaderboard += f"\u001b[0;31m{i}.-\u001b[0m {driver}    \u001b[0;32m+{points[-i]} pts\u001b[0m\n"
    
        leaderboard += "\n```"

        await channel.send(leaderboard)
    else:
        await ctx.send("No tienes permiso para actualizar los resultados.")

# Send a decorated message in a specific channel with the new ranking
@bot.command()
async def reiniciar(ctx):
    admin_r = discord.utils.get(ctx.guild.roles, id=admin_role)

    if admin_r in ctx.author.roles:
        channel = bot.get_channel(ranking_channel)
        driver_r = discord.utils.get(ctx.guild.roles, id=driver_role)
        drivers = [member for member in ctx.guild.members if driver_r in member.roles]
        
        leaderboard = "```ansi\n"
        leaderboard += f"\u001b[1;2m####### 🏆 RANKING {datetime.now().year} 🏆 #######\n"

        for i, driver in enumerate(drivers, 1):
            leaderboard += f"\u001b[0;31m{i}.-\u001b[0m {driver.display_name}    \u001b[0;32m0 pts\u001b[0m\n"

        leaderboard += "\n```"

        await channel.send(leaderboard)
    else:
        await ctx.send("No tienes permiso para reiniciar el ranking.")

# Calculate and show updated ranking
@bot.command()
async def actualizar(ctx, race_qty):
    try:
        role = discord.utils.get(ctx.guild.roles, id=admin_role)

        if role in ctx.author.roles:
            ranking_c = bot.get_channel(ranking_channel)
            standings_c = bot.get_channel(standings_channel)
            last_ranking_msg = [message.content async for message in ranking_c.history(limit=1)]
            last_standings_msg = [message.content async for message in standings_c.history(limit=int(race_qty))]
            standing_points = {}
            standings_list = []

            for msg in last_standings_msg:
                standings_list.extend(msg.split('\n'))

            for i, driver_line in enumerate(standings_list):
                if "pts" in driver_line.lower():
                    driver_name = driver_line.split(' ')[1]
                    driver_points = int(driver_line.split(' ')[5].replace('\u001b[0;32m+',''))
                    if driver_name in standing_points:
                        standing_points[driver_name] += driver_points
                    else:
                        standing_points[driver_name] = driver_points

            ranking_list = last_ranking_msg[0].split('\n')
            ranking_points = {}

            for i, driver_line in enumerate(ranking_list):
                if "pts" in driver_line:
                    driver_name = driver_line.split(' ')[1]
                    ranking_points[driver_name] = int(driver_line.split(' ')[5].replace('\u001b[0;32m',''))

            for i, driver in enumerate(standing_points):
                standing_points[driver] = int(standing_points[driver]) + int(ranking_points.get(driver, 0))

            print(standing_points)
            print(ranking_points)
            print(f"FP: {standing_points}")

            for i, driver in enumerate(ranking_points):
                if driver not in standing_points:
                    standing_points[driver] = ranking_points[driver]

            updated_ranking = "```ansi\n"
            updated_ranking += f"\u001b[1;2m####### 🏆 RANKING {datetime.now().year} 🏆 #######\n"

            for i, (driver, points) in enumerate(sorted(standing_points.items(), key=lambda item: item[1], reverse=True), 1):
                updated_ranking += f"\u001b[0;31m{i}.-\u001b[0m {driver}    \u001b[0;32m{points} pts\u001b[0m\n"

            updated_ranking += "\n```"

            message = [message async for message in ranking_c.history(limit=1)]
            await message[0].edit(content=updated_ranking)

        else:
            await ctx.send("No tienes permiso para actualizar el ranking.")
    except ValueError:
        await ctx.send("No se ha introducido un número válido.")

# Delete all images from a channel
@bot.command()
async def borrar(ctx):
    if ctx.channel.id != commands_channel:
        return
    
    async for message in ctx.channel.history(limit=10):
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image'):
                await message.delete()

# //------------------------ RUN BOT ------------------------//

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)

