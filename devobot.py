import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from datetime import timedelta, datetime
import asyncio
import random
import json
import os # Import os for environment variables
import aiohttp
from typing import Optional
from bs4 import BeautifulSoup

# Load configuration
try:
    with open('config.json') as f:
        config = json.load(f)
except FileNotFoundError:
    print("config.json not found. Please create one with 'mod_roles', 'guild_id', and 'log_channel_id'.")
    exit()

# Bot Token (Ideally, load this from environment variables)
# For example: TOKEN = os.getenv('DISCORD_BOT_TOKEN')
TOKEN = config.get("token", "") # Get token from config, or default to empty string

# Server ID (You can also get this from config.json if preferred)
GUILD_ID = config.get("guild_id", 1192254741359628378) # Default to your provided ID if not in config

# Bot Intents
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.guilds = True
intents.message_content = True

# Bot Prefix
client = commands.Bot(command_prefix='!', intents=intents)

# Check if user has a moderator role
def is_mod_check():
    async def predicate(interaction: Interaction):
        if not interaction.guild: # Ensure it's in a guild
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        
        mod_roles = config.get("mod_roles", [])
        if not mod_roles:
            await interaction.response.send_message("❌ Moderator roles are not configured in config.json.", ephemeral=True)
            return False

        if any(role.id in mod_roles for role in interaction.user.roles):
            return True
        else:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False
    return app_commands.check(predicate)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        # Force sync slash commands to the specific guild
        synced = await client.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f'Force-synced {len(synced)} slash command(s) to guild ID {GUILD_ID}.')
        for cmd in synced:
            print(f'- /{cmd.name}: {cmd.description}')
    except Exception as e:
        print(f'Sync failed: {e}')
    # Start background tasks
    try:
        game_update_feed.start()
    except Exception as e:
        print(f'Failed to start game_update_feed: {e}')

# Time Converter
def convert_time(time_str):
    time_str = time_str.lower()
    if not time_str or not time_str[-1].isalpha():
        return None # Invalid format if no unit

    time_unit = time_str[-1]
    try:
        time_value = int(time_str[:-1])
    except ValueError:
        return None # Invalid format if value isn't an integer

    if time_unit == 's':
        return time_value
    elif time_unit == 'm':
        return time_value * 60
    elif time_unit == 'h':
        return time_value * 3600
    elif time_unit == 'd':
        return time_value * 86400
    elif time_unit == 'w':
        return time_value * 604800
    else:
        return None
    
## General Commands

@client.tree.command(name='ping', description="Check the bot's latency", guild=discord.Object(id=GUILD_ID))
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'Pong! {round(client.latency * 1000)}ms')

@client.tree.command(name='groupinfo', description='Get information about the group', guild=discord.Object(id=GUILD_ID))
async def group(interaction:discord.Interaction):
    await interaction.response.send_message("🔧 **DevoStudio**, is a Roblox dev group! Check out our game: [The Souls](https://www.roblox.com/games/16449443653/The-Souls-UNDER-DEVELOPMENT)")

@client.tree.command(name='rules', description='Get the rules of the group', guild=discord.Object(id=GUILD_ID))
async def rules(interaction:discord.Interaction):
    await interaction.response.send_message(
        "📜 **Group Rules**:"
        "\n1. Be respectful to all members."
        "\n2. No spamming or flooding the chat."
        "\n3. No advertising other groups or games without permission."
        "\n4. Follow Roblox's TOS and Community Standards."
        "\n5. No inappropriate content or language."
        "\n6. Use the appropriate channels for discussions."
        "\n7. Report any issues via the <#1192271261921968211> channel."
        "\n8. Please read our TOS, COC, PP, and EULA on our Website (this can be found in my bio)."
        "\n9. Have fun and enjoy being part of the community!"
    )

@client.tree.command(name='roles', description='Get roles information (Server Roles)', guild=discord.Object(id=GUILD_ID))
async def roles(interaction: discord.Interaction):
    # Filter out @everyone and sort roles by position (highest first)
    role_list = sorted(
        [role for role in interaction.guild.roles if role.name != "@everyone"],
        key=lambda r: r.position, reverse=True
    )
    role_names = "\n".join([f"- {role.name}" for role in role_list])
    await interaction.response.send_message(f"**Server Roles:**\n{role_names}")

## Giveaway Command

@client.tree.command(name='giveaway', description="Create a giveaway", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(duration='Duration of the giveaway (e.g. 10m, 2h)', prize='Prize name', winners='Number of winners')
@is_mod_check() # Only moderators can start giveaways
async def giveaway(interaction: Interaction, duration: str, prize:str, winners: int = 1):
    await interaction.response.send_message("🎉 **Giveaway is starting...**", ephemeral=True)

    seconds = convert_time(duration)
    if seconds is None:
        await interaction.followup.send("❌ Invalid time format! Use s, m, h, d, or w (e.g. 10m, 2h).", ephemeral=True)
        return
    
    # Calculate end time
    end_time = datetime.utcnow() + timedelta(seconds=seconds)

    embed = discord.Embed(
        title="🎉 Giveaway!",
        description=f"**Prize:** {prize}\nReact with 🎉 to enter!\n**Ends:** <t:{int(end_time.timestamp())}:R>", # Use Discord's relative timestamp
        color=0x00ff00
    )
    embed.set_footer(text=f"Hosted by: {interaction.user.display_name}")
    embed.timestamp = datetime.utcnow() # Add timestamp to the embed

    message = await interaction.channel.send(embed=embed)
    await message.add_reaction("🎉")

    await asyncio.sleep(seconds)

    # Fetch the message again to get updated reactions
    try:
        message = await interaction.channel.fetch_message(message.id)
    except discord.NotFound:
        await interaction.channel.send("❌ Giveaway message was deleted.")
        return

    # Get all users who reacted with 🎉
    reaction_users = []
    for reaction in message.reactions:
        if str(reaction.emoji) == "🎉":
            # Fetch all users who reacted with this emoji
            # `flatten()` is used to get a list of User/Member objects
            reaction_users = [user for user in await reaction.users().flatten() if not user.bot]
            break # We only care about the 🎉 reaction

    if not reaction_users: # Check if the list is empty
        await interaction.channel.send("❌ No one entered the giveaway!")
        return
    
    # Ensure winners count does not exceed the number of participants
    chosen_winners_count = min(winners, len(reaction_users))
    chosen = random.sample(reaction_users, chosen_winners_count)
    winners_mentions = ', '.join([winner.mention for winner in chosen])

    if chosen_winners_count > 0:
        await interaction.channel.send(f"🎊 Congratulations {winners_mentions}! You won **{prize}**!")
    else:
        await interaction.channel.send(f"❌ No eligible winners could be chosen for **{prize}**.")

## Moderation Commands

@client.tree.command(name='ban', description='Ban a member', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member='The member to ban', reason='Reason for ban')
@is_mod_check() # Apply moderator check
async def ban(interaction: Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("🚫 You cannot ban yourself!", ephemeral=True)
        return
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("🚫 You cannot ban someone with a higher or equal role to yourself unless you are the server owner.", ephemeral=True)
        return
    
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 {member.display_name} has been banned. Reason: {reason}")
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have the necessary permissions to ban this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)


@client.tree.command(name='unban', description='Unban a user by ID', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user_id='The ID of the user to unban')
@is_mod_check() # Apply moderator check
async def unban(interaction: Interaction, user_id: int):
    try:
        user = await client.fetch_user(user_id)
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"✅ {user.display_name} has been unbanned.")
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="✅ User Unbanned", color=discord.Color.green())
                embed.add_field(name="User", value=user.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.NotFound:
        await interaction.response.send_message(f"❌ User with ID {user_id} not found in the ban list.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have the necessary permissions to unban this user.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name='kick', description='Kick a member', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member='The member to kick', reason='Reason for kick')
@is_mod_check() # Apply moderator check
async def kick(interaction: Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("🚫 You cannot kick yourself!", ephemeral=True)
        return
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("🚫 You cannot kick someone with a higher or equal role to yourself unless you are the server owner.", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member.display_name} has been kicked. Reason: {reason}")
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have the necessary permissions to kick this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name='mute', description='Mute a member for a duration', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member='Member to mute', duration='Duration (e.g., 10m, 1h)', reason='Reason for mute')
@is_mod_check() # Apply moderator check
async def mute(interaction: Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if member.id == interaction.user.id:
        await interaction.response.send_message("🚫 You cannot mute yourself!", ephemeral=True)
        return
    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("🚫 You cannot mute someone with a higher or equal role to yourself unless you are the server owner.", ephemeral=True)
        return

    seconds = convert_time(duration)
    if seconds is None:
        await interaction.response.send_message("❌ Invalid time format! Use s, m, h, d, or w (e.g., 10m, 2h).", ephemeral=True)
        return

    # Calculate the timeout expiration time using discord.utils.utcnow()
    timeout_until = discord.utils.utcnow() + timedelta(seconds=seconds)

    try:
        await member.timeout(timeout_until, reason=reason)
        await interaction.response.send_message(f"🔇 {member.display_name} has been muted for {duration}. Reason: {reason}")
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.dark_orange())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.add_field(name="Duration", value=duration, inline=False)
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have the necessary permissions to mute this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name='unmute', description='Unmute a member', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member='Member to unmute')
@is_mod_check() # Apply moderator check
async def unmute(interaction: Interaction, member: discord.Member):
    try:
        await member.timeout(None) # Setting timeout to None removes it
        await interaction.response.send_message(f"🔊 {member.display_name} has been unmuted.")
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="🔊 Member Unmuted", color=discord.Color.blue())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have the necessary permissions to unmute this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name='clear', description='Clear messages', guild=discord.Object(id=GUILD_ID))
@app_commands.describe(amount='Number of messages to delete')
@is_mod_check() # Apply moderator check
async def clear(interaction: Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("Please specify a number greater than 0.", ephemeral=True)
        return
    
    try:
        await interaction.channel.purge(limit=amount + 1) # +1 to also delete the command message
        await interaction.response.send_message(f"🧹 Cleared {amount} messages.", ephemeral=False, delete_after=5) # Not ephemeral, deletes after 5 seconds
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="🧹 Messages Cleared", color=discord.Color.light_grey())
                embed.add_field(name="Channel", value=interaction.channel.mention, inline=False)
                embed.add_field(name="Amount", value=amount, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to clear messages in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"❌ An error occurred while clearing messages: {e}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@client.tree.command(name="warn", description="Warn a user", guild=discord.Object(id=GUILD_ID)) # Use GUILD_ID directly
@app_commands.describe(member="User to warn", reason="Reason for warning")
@is_mod_check() # This already includes the permission check
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if member.id == interaction.user.id:
        await interaction.response.send_message("🚫 You cannot warn yourself!", ephemeral=True)
        return
    
    # Save to warnings.json
    try:
        with open("warnings.json", "r") as f:
            warnings = json.load(f)
    except FileNotFoundError:
        warnings = {}
    except json.JSONDecodeError:
        warnings = {} # Handle empty or corrupt JSON file

    user_id = str(member.id)
    if user_id not in warnings:
        warnings[user_id] = []

    warnings[user_id].append({
        "reason": reason,
        "moderator": interaction.user.name,
        "moderator_id": interaction.user.id, # Store moderator ID too
        "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })

    try:
        with open("warnings.json", "w") as f:
            json.dump(warnings, f, indent=4)
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not save warning data: {e}", ephemeral=True)
        return

    # Logging
    log_channel_id = config.get("log_channel_id")
    if log_channel_id:
        log_channel = client.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(title="⚠️ User Warned", color=discord.Color.orange())
            embed.add_field(name="User", value=member.mention, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.timestamp = datetime.utcnow()
            await log_channel.send(embed=embed)
        else:
            print(f"Warning: Log channel with ID {log_channel_id} not found.")

    await interaction.response.send_message(f"✅ {member.mention} has been warned for: **{reason}**")

@client.tree.command(name="warnings", description="View warnings for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to view warnings for")
@is_mod_check() # Only moderators can view warnings
async def warnings(interaction: discord.Interaction, member: discord.Member):
    try:
        with open("warnings.json", "r") as f:
            warnings_data = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("No warnings found.", ephemeral=True)
        return
    except json.JSONDecodeError:
        await interaction.response.send_message("Error loading warnings data. The file might be corrupted.", ephemeral=True)
        return

    user_id = str(member.id)
    if user_id not in warnings_data or not warnings_data[user_id]:
        await interaction.response.send_message(f"✅ {member.display_name} has no warnings.", ephemeral=True)
        return

    user_warnings = warnings_data[user_id]
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.display_name}",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

    for i, warning in enumerate(user_warnings):
        reason = warning.get("reason", "No reason provided")
        moderator = warning.get("moderator", "Unknown")
        date = warning.get("date", "Unknown date")
        embed.add_field(name=f"Warning #{i+1}", value=f"**Reason:** {reason}\n**Moderator:** {moderator}\n**Date:** {date}", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="clear_warnings", description="Clear all warnings for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to clear warnings for")
@is_mod_check() # Only moderators can clear warnings
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):
    try:
        with open("warnings.json", "r") as f:
            warnings_data = json.load(f)
    except FileNotFoundError:
        await interaction.response.send_message("No warnings found to clear.", ephemeral=True)
        return
    except json.JSONDecodeError:
        await interaction.response.send_message("Error loading warnings data. The file might be corrupted.", ephemeral=True)
        return

    user_id = str(member.id)
    if user_id in warnings_data:
        del warnings_data[user_id]
        with open("warnings.json", "w") as f:
            json.dump(warnings_data, f, indent=4)
        
        # Log the action
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = client.get_channel(log_channel_id)
            if log_channel:
                embed = discord.Embed(title="✅ Warnings Cleared", color=discord.Color.dark_green())
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                embed.timestamp = datetime.utcnow()
                await log_channel.send(embed=embed)

        await interaction.response.send_message(f"✅ All warnings for {member.mention} have been cleared.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ {member.display_name} has no warnings to clear.", ephemeral=True)

# --- Game Status Tracker ---
@client.tree.command(name="gamestatus", description="Check the current game status", guild=discord.Object(id=GUILD_ID))
async def gamestatus(interaction: discord.Interaction):
    url = "https://yourwebsite.com/index.html"  # Change to your actual index.html URL
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    # --- EDIT THIS SELECTOR TO MATCH YOUR BAR ---
                    # Example: bar_div = soup.find('div', {'id': 'bar'})
                    bar_div = soup.find('div', {'id': 'bar'})
                    bar_value = bar_div.text.strip() if bar_div else 'N/A'
                    await interaction.response.send_message(f"Game Progress Bar: {bar_value}")
                else:
                    await interaction.response.send_message("Failed to fetch game status.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# --- Bug Report Command ---
@client.tree.command(name="bugreport", description="Report a bug", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(description="Describe the bug")
async def bugreport(interaction: discord.Interaction, description: str):
    bug_channel_id = 1380005045843660951
    channel = client.get_channel(bug_channel_id)
    if channel:
        embed = discord.Embed(title="🐞 Bug Report", description=description, color=discord.Color.red())
        embed.set_footer(text=f"Reported by {interaction.user}")
        await channel.send(embed=embed)
    await interaction.response.send_message("✅ Bug report submitted!", ephemeral=True)

# --- Suggestion Command ---
@client.tree.command(name="suggestion", description="Submit a suggestion", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(description="Your suggestion")
async def suggestion(interaction: discord.Interaction, description: str):
    suggestion_channel_id = 1380005045843660951
    channel = client.get_channel(suggestion_channel_id)
    if channel:
        embed = discord.Embed(title="💡 Suggestion", description=description, color=discord.Color.green())
        embed.set_footer(text=f"Suggested by {interaction.user}")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
    await interaction.response.send_message("✅ Suggestion submitted!", ephemeral=True)

# --- Live Game Update Feed ---
@tasks.loop(minutes=5)
async def game_update_feed():
    update_channel_id = config.get("game_update_channel_id")
    last_update_file = "last_update.txt"
    url = "https://devostudio.vercel.app"  # Change to your actual update feed
    if update_channel_id:
        channel = client.get_channel(update_channel_id)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latest = data[0] if data else None
                        if latest:
                            last_id = None
                            if os.path.exists(last_update_file):
                                with open(last_update_file, "r") as f:
                                    last_id = f.read().strip()
                            if latest["id"] != last_id:
                                embed = discord.Embed(title="📰 Game Update", description=latest["desc"], color=discord.Color.blue())
                                embed.add_field(name="Version", value=latest["version"])
                                embed.timestamp = datetime.utcnow()
                                await channel.send(embed=embed)
                                with open(last_update_file, "w") as f:
                                    f.write(str(latest["id"]))
            except Exception:
                pass

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    try:
        # Force sync slash commands to the specific guild
        synced = await client.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f'Force-synced {len(synced)} slash command(s) to guild ID {GUILD_ID}.')
        for cmd in synced:
            print(f'- /{cmd.name}: {cmd.description}')
    except Exception as e:
        print(f'Sync failed: {e}')
    # Start background tasks
    try:
        game_update_feed.start()
    except Exception as e:
        print(f'Failed to start game_update_feed: {e}')

# --- Chat with NPC / Dev Help AI (simple keyword-based) ---
@client.tree.command(name="npcchat", description="Chat with an NPC", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message="Your message to the NPC")
async def npcchat(interaction: discord.Interaction, message: str):
    # Simple keyword-based responses
    responses = {
        "hello": "Hello, traveler! How can I help you today?",
        "help": "I'm here to assist you. Ask me anything about the game!",
        "bye": "Goodbye! See you in the game!"
    }
    reply = next((v for k, v in responses.items() if k in message.lower()), "I'm not sure how to respond to that. Try asking something else!")
    await interaction.response.send_message(reply)

# --- Code Snippet Share ---
@client.tree.command(name="sharecode", description="Share a code snippet", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(language="Programming language", code="Your code snippet")
async def sharecode(interaction: discord.Interaction, language: str, code: str):
    embed = discord.Embed(title=f"📄 {language.title()} Code Snippet", description=f"```{language}\n{code}\n```", color=discord.Color.purple())
    embed.set_footer(text=f"Shared by {interaction.user}")
    await interaction.response.send_message(embed=embed)

# --- Release Countdown ---
@client.tree.command(name="releasecountdown", description="Show countdown to next release", guild=discord.Object(id=GUILD_ID))
async def releasecountdown(interaction: discord.Interaction):
    # Set your next release date here
    release_date = datetime(2025, 7, 1, 18, 0, 0)  # Example: July 1, 2025, 18:00 UTC
    now = datetime.utcnow()
    if now >= release_date:
        await interaction.response.send_message("🎉 The release is live!")
    else:
        delta = release_date - now
        days, seconds = delta.days, delta.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        await interaction.response.send_message(f"⏳ Release in {days}d {hours}h {minutes}m!")

# --- Task Manager ---
TASKS_FILE = "tasks.json"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=4)

@client.tree.command(name="taskadd", description="Add a new task", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(description="Task description")
async def taskadd(interaction: discord.Interaction, description: str):
    tasks = load_tasks()
    user_id = str(interaction.user.id)
    if user_id not in tasks:
        tasks[user_id] = []
    tasks[user_id].append({"desc": description, "done": False})
    save_tasks(tasks)
    await interaction.response.send_message("✅ Task added!", ephemeral=True)

@client.tree.command(name="tasklist", description="List your tasks", guild=discord.Object(id=GUILD_ID))
async def tasklist(interaction: discord.Interaction):
    tasks = load_tasks()
    user_id = str(interaction.user.id)
    user_tasks = tasks.get(user_id, [])
    if not user_tasks:
        await interaction.response.send_message("You have no tasks.", ephemeral=True)
        return
    msg = "\n".join([f"{i+1}. {'[x]' if t['done'] else '[ ]'} {t['desc']}" for i, t in enumerate(user_tasks)])
    await interaction.response.send_message(f"**Your Tasks:**\n{msg}", ephemeral=True)

@client.tree.command(name="taskdone", description="Mark a task as done", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task_number="Task number to mark as done")
async def taskdone(interaction: discord.Interaction, task_number: int):
    tasks = load_tasks()
    user_id = str(interaction.user.id)
    user_tasks = tasks.get(user_id, [])
    if 0 < task_number <= len(user_tasks):
        user_tasks[task_number-1]["done"] = True
        save_tasks(tasks)
        await interaction.response.send_message("✅ Task marked as done!", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid task number.", ephemeral=True)

# --- Meeting Reminder ---
@client.tree.command(name="remindmeeting", description="Set a meeting reminder", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(time="Time in minutes from now", description="Meeting description")
async def remindmeeting(interaction: discord.Interaction, time: int, description: str):
    await interaction.response.send_message(f"⏰ Meeting reminder set for {time} minutes from now!", ephemeral=True)
    await asyncio.sleep(time * 60)
    await interaction.channel.send(f"🔔 Meeting Reminder: {description} (set by {interaction.user.mention})")

# Run the bot
client.run(TOKEN)