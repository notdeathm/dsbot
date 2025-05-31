import discord
from discord.ext import commands
import os

# Discord Bot Token
TOKEN = 'MTI1Mjk4OTg4NTE0NTY3Nzg1NQ.G40kVl.F-YUaG5pAspbLVPOj1sMalZ4_bbCfyB5uQmgc8' # Replace this!

# Define intents. Intents tell Discord which events your bot wants to receive.
# For this basic bot, we need default intents and the message content intent.
intents = discord.Intents.default()
intents.message_content = True # Required to read message content for commands

# Create a Bot instance.
# command_prefix defines what characters your bot will listen for to identify commands.
# For example, if command_prefix='!', then you'd type !hello to trigger the hello command.
# If you want to use slash commands, the prefix is less critical for command invocation,
# but still useful for traditional text commands.
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Bot Events ---

@bot.event
async def on_ready():
    """
    This event fires when the bot successfully connects to Discord.
    It's a good place to confirm your bot is online.
    """
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    # You can set the bot's activity here, e.g., "Playing The Souls"
    await bot.change_presence(activity=discord.Game(name="The Souls"))

@bot.event
async def on_message(message):
    """
    This event fires whenever a message is sent in any channel the bot can see.
    It's useful for logging or reacting to specific keywords.
    """
    # Don't let the bot respond to its own messages to prevent infinite loops
    if message.author == bot.user:
        return

    # Example: If someone says "hello" (case-insensitive)
    if "hello" in message.content.lower():
        # You could add a fun response here, maybe about Devo Studio!
        await message.channel.send(f"Hey there, {message.author.display_name}! Glad to see you.")

    # Process commands. This line is crucial for your commands to work.
    await bot.process_commands(message)

# --- Bot Commands ---

@bot.command(name='hello')
async def hello_command(ctx):
    """
    A simple command that makes the bot say hello.
    Usage: !hello
    """
    await ctx.send(f'Hello, {ctx.author.display_name}!')

@bot.command(name='echo')
async def echo_command(ctx, *, message_to_echo: str):
    """
    A command that echoes back whatever you say after it.
    Usage: !echo Your message here
    The '*' before message_to_echo makes it capture all subsequent arguments.
    """
    await ctx.send(f'You said: {message_to_echo}')

@bot.command(name='soulsinfo')
async def souls_info_command(ctx):
    """
    Provides some information about The Souls game.
    Usage: !soulsinfo
    """
    info_message = (
        "The Souls is a game created by Death and I2hs2 they are the Owners of DevoStudio.\n"
        "Explore, conquer, and have fun! What would you like to know about it?"
    )
    await ctx.send(info_message)

# --- Run the Bot ---
if __name__ == '__main__':
    # It's best practice to load the token from an environment variable for security.
    # If you're just testing, you can uncomment the line below and put your token directly.
    # Make sure to replace 'YOUR_BOT_TOKEN_HERE' with your actual token.
    # TOKEN = 'YOUR_BOT_TOKEN_HERE' # Uncomment and replace for direct use

    if TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("WARNING: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token.")
        print("You can get it from the Discord Developer Portal under your bot's settings.")
    else:
        try:
            bot.run(TOKEN)
        except discord.LoginFailure:
            print("ERROR: Invalid bot token. Please check your token in the Discord Developer Portal.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
