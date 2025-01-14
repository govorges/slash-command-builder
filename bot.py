import interactions
from interactions import Intents, listen, slash_command, SlashContext, SlashCommand
from interactions.api.events import Startup, GuildJoin, GuildLeft

from os import environ, path, mkdir, remove
import json

from dotenv import load_dotenv
dotenv_loaded = load_dotenv()

LOCAL_DIR = path.dirname(path.realpath(__file__))


BOT_TOKEN = environ.get("BOT_TOKEN")
if not dotenv_loaded and BOT_TOKEN is None: # It's possible for $BOT_TOKEN to be set without a .env being present (docker deployments and such)
    raise EnvironmentError("No environment file was found!")
if BOT_TOKEN is None:
    raise EnvironmentError("BOT_TOKEN was not set in .env")

bot = interactions.Client( 
    token = BOT_TOKEN,
    intents = Intents.GUILDS,
    delete_unused_application_cmds = False,
    disable_dm_commands = True
)

def updateGuildInteractions(id: str):
    '''A function to construct & register a list of commands defined in guilds/<id>/commands.json'''
    commandsFile = open(
        path.join(LOCAL_DIR, 'guilds', id, 'commands.json')
    ).read()
    commands: list[dict] = json.loads(commandsFile)
    if not isinstance(commands, list):
        raise ValueError(f"Guild {id} command list was improperly formatted.")

    bot.interactions_by_scope[int(id)] = {}

    for command in commands:
        command_return_text = command.pop('command_return_text', 'No response set.')
        @slash_command(**command, scopes = [int(id)])
        async def slash_command_function(context: SlashContext):
            await context.send(command_return_text)
        bot.add_command(slash_command_function)

def createGuildData(id: str):
    guildDir = path.join(LOCAL_DIR, 'guilds', id)
    commandsFilePath = path.join(guildDir, 'commands.json')

    if path.isdir(guildDir):
        return
    elif path.isfile(commandsFilePath):
        return
    
    mkdir(path.join(LOCAL_DIR, 'guilds', id))
    with open(commandsFilePath, 'w+') as guildCommandConfig:
        guildCommandConfig.write("[]")

def destroyGuildData(id: str):
    guildDir = path.join(LOCAL_DIR, 'guilds', id)
    if not path.isdir(guildDir):
        return
    remove(guildDir)

@listen(GuildJoin)
async def guild_joined(event: GuildJoin):
    if not bot.is_ready:
        return
    createGuildData(str(event.guild_id))

@listen(GuildLeft)
async def guild_left(event: GuildLeft):
    if not bot.is_ready:
        return
    destroyGuildData(str(event.guild_id))

@listen(Startup)
async def bot_started():
    for id in [guild.id for guild in bot.guilds]:
        id = str(id) # Snowflake -> str
        if path.isdir(path.join(LOCAL_DIR, 'guilds', id)):
            updateGuildInteractions(id=id)
            continue
        mkdir(path.join(LOCAL_DIR, 'guilds', id))

        # Here we're initializing the list of commands in the guild's commands.json.
        #       Equivalent to json.dumps([])
        with open(path.join(LOCAL_DIR, 'guilds', id, 'commands.json'), 'w+') as guildCommandConfig:
            guildCommandConfig.write("[]")
    await bot.synchronise_interactions(scopes = [guild.id for guild in bot.guilds])

    print("Bot started & guild interactions have been synced with Discord.")

@slash_command(name = "help", description = "List commands for this guild")
async def help_command(context: SlashContext):
    guildCommands: list[SlashCommand] = []
    for command in bot.application_commands:
        if context.guild_id not in command.scopes and 0 not in command.scopes:
            continue
        guildCommands.append(f"/{command.name} - {command.description}")
    await context.send("\n".join(guildCommands))

@slash_command(name = "reload", description = "Reload this guild's commands.")
async def reload_commands(context: SlashContext):
    updateGuildInteractions(str(context.guild_id))
    
    guildCommands: list[SlashCommand] = []
    for command in bot.application_commands:
        if context.guild_id not in command.scopes:
            continue
        guildCommands.append(command)
        
    await bot.synchronise_interactions(scopes = [context.guild_id], delete_commands = guildCommands)
    await context.send("This guild's command's have been reloaded.")

if __name__ == "__main__":   
    bot.start()