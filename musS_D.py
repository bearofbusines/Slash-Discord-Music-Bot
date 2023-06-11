import math
import os
import random
import traceback
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

# importing other classes from other files
import Utils
from Pages import Pages
from Player import Player
from Servers import Servers
from Song import Song
from YTDLInterface import YTDLInterface

# imports for error type checking
import yt_dlp
# needed to add it to a var bc of pylint on my laptop but i delete it right after
XX = '''
#-fnt stands for finished not tested
#-f is just finished
TODO:
    6-fnt alert user when songs were unable to be added inside _playlist()
    -make more commands
        1- create add-at(?) (merge with playtop? ask for int instead of bool?)
        1- help #bear //done but needs to be updated
        1- settings #bear
        1- option to decide if __send_np goes into vc.channel or song.channel
        1- remove author's songs from queue when author leaves vc #sming //can't be done until we have settings
        1- move command #bear 
        1- remove_duplicates #bear
    -other
        9- add info on permissions to help
        7-fnt DJ role to do most bot functions, users without can still queue songs (! top), join bot to channel, etc.
        5- rename get_embed's content argument to description
        ^^^ player.queue.top() is not always == player.song, player.queue.top() exists before player.song is uninitialized, make this swap with care
        ^^^ it's likely fine but still, race conditions.
        


DONE:
    9-f make listener for player.start returning to call clean() // found alternative that probably works better
    9-f fix automatic now_playing messages
    8-f make forceskip admin-only
    8-f make play and playlist only join VC if the provided queries are valid (prevents bot from joining to just do nothing)
    8-f make YTDLInterface.query_link calls cognizant of entries[] and able to handle it's appearance
    8-f likewise, make query_search able to handle a lack of entries[] // Never going to happen; (hopefully) a non issue
    7-fnt create general on_error event method
     - make more commands
        9-f pause #bear //vc.pause() and vc.resume()
        9-f resume #bear
        9-f now #bear
        9-f skip (force skip) #sming
        8-f search #sming
        8-f queue #bear
        8-f remove #bear
        8-f play_top #bear
        7-f remove user's songs from queue
        7-f play_list #sming
        7-f play_list_shuffle #sming
        6-f clear #bear
        5-f shuffle #bear
        4-f loop (queue, song) #bear
        1-f fix queue emojis being backwards

     - Be able to play music from youtube
        - play music
        - stop music
    (kind but found a better way)- get downloading to work
     - Be able to join vc and play sound
        - join vc
        - leave vc
        - play sound
    - other
        9-f footer that states the progress of the song #bear
        8-f author doesn't need to vote to skip#sming
        8-f fix auto now playing messages not deleting //found why, it's because the player.wait_until_termination() returns instantly once we tell the player to close
        8-f auto-leave VC if bot is alone #sming
        7-f only generate a player when audio is playing, remove the player_event, force initialization with a Song or Queue
        6-f Implement discord.Button with queue
        5-f access currently playing song via player.song rather than player.queue.top() (maybe remove current song from queue while we're at it?)
        4-f remove unneeded async defs
        3-f make it multi server #bear

'''
del XX

load_dotenv()  # getting the key from the .env file
key = os.environ.get('key')


class Bot(commands.Bot):  # initiates the bots intents and on_ready event
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="mb.", help_command=None)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}.")

    async def on_ready(self):
        #await tree.sync()  # please dont remove just in case i need to sync
        Utils.pront("Bot is ready", lvl="OKGREEN")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name=f"you in {len(bot.guilds):,} Servers."))
    
    async def on_command_error(self, ctx, error) -> None:
        print(error)
        await ctx.reply(f"```{error}```", ephemeral=True)


# Global Variables
bot = Bot()
#tree = discord.app_commands.CommandTree(bot)



## EVENT LISTENERS ##


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    # If we don't care that a voice state was updated
    if member.guild.voice_client is None:
        return

    # If the author was in the same VC as the bot
    if before.channel == member.guild.voice_client.channel:
        # If the bot is now alone
        if len(before.channel.members) == 1:
            player = Servers.get_player(member.guild.id)
            if player is None:
                member.guild.voice_client.disconnect()
            else:
                await Utils.clean(player)


## COMMANDS ##


@ bot.hybrid_command(name="ping", with_app_command = True, description="The ping command (^-^)")
async def _ping(ctx: commands.Context) -> None:
    await ctx.defer(ephemeral=True)
    await ctx.reply('Pong!', ephemeral=True)

@ bot.hybrid_command(name="wimput", with_app_command = True, description="The wimput command (^-^)")
async def _wimput(ctx: commands.Context, link: str) -> None:
    await ctx.defer(ephemeral=True)
    await ctx.reply(f'wimput {link}', ephemeral=True)

@ bot.hybrid_command(name="join", description="Adds the MaBalls to the voice channel you are in")
async def _join(ctx: commands.Context) -> None:
    if ctx.author.voice is None:  # checks if the author is in a voice channel
        await ctx.reply('You are not in a voice channel', ephemeral=True)
        return
    if ctx.guild.voice_client is not None:  # checks if the bot is in a voice channel
        await ctx.reply('I am already in a voice channel', ephemeral=True)
        return
    # Connect to the voice channel
    await ctx.author.voice.channel.connect(self_deaf=True)
    await Utils.send(ctx, title='Joined!', content=':white_check_mark:', progress=False)


@ bot.hybrid_command(name="leave", description="Removes the MaBalls from the voice channel you are in")
async def _leave(ctx: commands.Context) -> None:
    if not await Utils.Pretests.voice_channel(ctx):
        return

    # Clean up if needed
    if Servers.get_player(ctx.guild_id) is not None:
        await Utils.clean(Servers.get_player(ctx.guild_id))
    # Otherwise, just leave VC
    else:
        await ctx.guild.voice_client.disconnect()
    await Utils.send(ctx, title='Left!', content=':white_check_mark:', progress=False)


@ bot.hybrid_command(name="play", description="Plays a song from youtube(or other sources somtimes) in the voice channel you are in")
async def _play(ctx: commands.Context, link: str, top: bool = False) -> None:
    # Check if author is in VC
    if ctx.author.voice is None:
        await ctx.reply('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if ctx.guild.voice_client is not None and ctx.author.voice.channel != ctx.guild.voice_client.channel:
        await ctx.reply("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await ctx.defer(thinking=True)

    # create song
    scrape = await YTDLInterface.scrape_link(link)
    song = Song(ctx, link, scrape)

    # Check if song didn't initialize properly via scrape
    if song.title is None:
        # If it didn't, query the link instead (resolves searches in the link field)
        query = await YTDLInterface.query_link(link)
        song = Song(ctx, query.get('original_url'), query)

    # If not in a VC, join
    if ctx.guild.voice_client is None:
        await ctx.author.voice.channel.connect(self_deaf=True)

    # If player does not exist, create one.
    if Servers.get_player(ctx.guild_id) is None:
        Servers.add(ctx.guild_id, Player(
            ctx.guild.voice_client, song))
        position = 1
    # If it does, add the song to queue
    elif top:
        if not Utils.Pretests.has_discretionary_authority(ctx):
            await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
        Servers.get_player(ctx.guild_id).queue.add_at(song, 0)
        position = 1
    else:
        Servers.get_player(ctx.guild_id).queue.add(song)
        position = len(Servers.get_player(ctx.guild_id).queue.get())
        

    embed = Utils.get_embed(
        ctx,
        title=f'[{position}] Added to Queue:',
        url=song.original_url,
        color=Utils.get_random_hex(song.id)
    )
    embed.add_field(name=song.uploader, value=song.title, inline=False)
    embed.add_field(name='Requested by:', value=song.requester.mention)
    embed.add_field(name='Duration:', value=Song.parse_duration(song.duration))
    embed.set_thumbnail(url=song.thumbnail)
    await ctx.followup.send(embed=embed)


@ bot.hybrid_command(name="skip", description="Skips the currently playing song")
async def _skip(ctx: commands.Context) -> None:
    if not await Utils.Pretests.playing_audio(ctx):
        return

    player = Servers.get_player(ctx.guild_id)

    await Utils.skip_logic(player, ctx)


@ bot.hybrid_command(name="forceskip", description="Skips the currently playing song without having a vote. (Requires Manage Channels permission.)")
async def _force_skip(ctx: commands.Context) -> None:
    if not await Utils.Pretests.playing_audio(ctx):
        return

    # If there's enough users in vc for it to make sense check perms
    if len(Servers.get_player(ctx.guild_id).vc.channel.members) > 3:
        # Check song authority
        if not Utils.Pretests.has_song_authority(ctx, Servers.get_player(ctx.guild_id).song):
            await Utils.send(ctx, title='Insufficient permissions!', 
                            content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
        
    Servers.get_player(ctx.guild_id).vc.stop()
    await Utils.send(ctx, "Skipped!", ":white_check_mark:")

# Button handling for _queue
class __QueueButtons(discord.ui.View):
    def __init__(self, *, timeout=180, page=1):
        self.page = page
        super().__init__(timeout=timeout)

    def get_queue_embed(self, ctx: commands.Context):
        player = Servers.get_player(ctx.guild_id)
        page_size = 5
        queue_len = len(player.queue)
        max_page = math.ceil(queue_len / page_size)

        if self.page < 0:
            self.page = 0
        elif self.page > max_page:
            self.page = max_page
        

        # The index to start reading from Queue
        min_queue_index = page_size * (self.page)
        # The index to stop reading from Queue
        max_queue_index = min_queue_index + page_size

        embed = Utils.get_embed(ctx, title='Queue', color=Utils.get_random_hex(
            player.song.id), progress=False)

        # Loop through the region of songs in this page
        for i in range(min_queue_index, max_queue_index):
            if i >= queue_len:
                break
            song = player.queue.get()[i]

            embed.add_field(name=f"`{i + 1}`: {song.title}",
                            value=f"by {song.uploader}\nAdded By: {song.requester.mention}", inline=False)

        embed.set_footer(
            text=f"Page {self.page + 1}/{max_page} | {queue_len} song{'s' if queue_len != 1 else ''} in queue")
        return embed

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="⬅")
    async def button_left(self,ctx: commands.Context,button:discord.ui.Button):
        self.page -= 1
        await ctx.response.edit_message(embed=self.get_queue_embed(ctx), view=self)
        
    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="➡")
    async def button_right(self,ctx: commands.Context,button:discord.ui.Button):
        self.page += 1
        await ctx.response.edit_message(embed=self.get_queue_embed(ctx), view=self)

@ bot.hybrid_command(name="queue", description="Shows the current queue")
async def _queue(ctx: commands.Context, page: int = 1) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    # Convert page into non-user friendly (woah scary it starts at 0)(if only we were using lua)
    page -= 1
    player = Servers.get_player(ctx.guild_id)
    if not player.queue.get():
        await Utils.send(ctx, title='Queue is empty!', ephemeral=True)
        return

    qb = __QueueButtons(page=page)

    await ctx.reply(embed=qb.get_queue_embed(ctx), view=qb)


@ bot.hybrid_command(name="replay", description="Restarts the current song")
async def _replay(ctx: commands.Context) -> None:
    if not await Utils.Pretests.playing_audio(ctx):
        return
    
    player = Servers.get_player(ctx.guild_id)

    if not Utils.Pretests.has_song_authority(ctx, player.song):
        await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return
    
    player = Servers.get_player(ctx.guild_id)
    # Just add it to the top of the queue and skip to it
    # Dirty, but it works.
    player.queue.add_at(player.song, 0)
    player.vc.stop()
    await Utils.send(ctx, title='⏪ Rewound')


@ bot.hybrid_command(name="now", description="Shows the current song")
async def _now(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    if (Servers.get_player(ctx.guild_id).song is None):
        await Utils.send(ctx, title="Nothing is playing", content="You should add something", progress=False)
        return
    await ctx.reply(embed=Utils.get_now_playing_embed(Servers.get_player(ctx.guild_id), progress=True))


@ bot.hybrid_command(name="remove", description="Removes a song from the queue")
async def _remove(ctx: commands.Context, number_in_queue: int) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    # Convert to non-human-readable
    number_in_queue -= 1
    song = Servers.get_player(ctx.guild_id).queue.get(number_in_queue)

    if song is None:
        await Utils.send(ctx, "Queue index does not exist.")
        return
    
    if not Utils.Pretests.has_song_authority(ctx, song):
        await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return

    removed_song = Servers.get_player(
        ctx.guild_id).queue.remove(number_in_queue)
    # TODO, Why do we do this?
    if removed_song is not None:
        embed = discord.Embed(
            title='Removed from Queue:',
            url=removed_song.original_url,
            color=Utils.get_random_hex(removed_song.id)
        )
        embed.add_field(name=removed_song.uploader,
                        value=removed_song.title, inline=False)
        embed.add_field(name='Requested by:',
                        value=removed_song.requester.mention)
        embed.add_field(name='Duration:',
                        value=Song.parse_duration(removed_song.duration))
        embed.set_thumbnail(url=removed_song.thumbnail)
        embed.set_author(name=removed_song.requester.display_name,
                         icon_url=removed_song.requester.display_avatar.url)
        await ctx.reply(embed=embed)


@ bot.hybrid_command(name="removeuser", description="Removes all of the songs added by a specific user")
async def _remove_user(ctx: commands.Context, member: discord.Member):
    if not await Utils.Pretests.player_exists(ctx):
        return
    
    if not Utils.Pretests.has_discretionary_authority(ctx):
        await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return
    
    queue = Servers.get_player(ctx.guild.id).queue

    # TODO either make this an int or fill out the send embed more
    removed = []
    i = 0
    while i < len(queue.get()):
        if queue.get(i).requester == member:
            removed.append(queue.remove(i))
            continue

        # Only increment i when song.requester != member
        i += 1

    await Utils.send(ctx,
                     title=f'Removed {len(removed)} songs.')


@ bot.hybrid_command(name="playlist", description="Adds a playlist to the queue")
async def _playlist(ctx: commands.Context, link: str, shuffle: bool = False) -> None:
    # Check if author is in VC
    if ctx.author.voice is None:
        await ctx.reply('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if ctx.guild.voice_client is not None and ctx.author.voice.channel != ctx.guild.voice_client.channel:
        await ctx.reply("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await ctx.defer(thinking=True)

    playlist = await YTDLInterface.scrape_link(link)

    if playlist.get('_type') != "playlist":
        await ctx.followup.send(embed=Utils.get_embed(ctx, "Not a playlist."), ephemeral=True)
        return

    # Might not proc, there for extra protection
    if len(playlist.get("entries")) == 0:
        await ctx.followup.send("Playlist Entries [] empty.")

    # Detect if this is a Mix
    if playlist.get("uploader") is None:
        # Truncate the playlist to just the top 50 Songs or fewer if there are less
        playlist.update({"playlist_count": 50})
        playlist.update({"entries": playlist.get("entries")[:50]})

    # If not in a VC, join
    if ctx.guild.voice_client is None:
        await ctx.author.voice.channel.connect(self_deaf=True)

    # Shuffle the entries[] within playlist before processing them
    if shuffle:
        random.shuffle(playlist.get("entries"))

    for entry in playlist.get("entries"):

        # Feed the Song the entire entry, saves time by not needing to create and fill a dict
        song = Song(ctx, link, entry)

        # If player does not exist, create one.
        if Servers.get_player(ctx.guild_id) is None:
            Servers.add(ctx.guild_id, Player(
                ctx.guild.voice_client, song))
        # If it does, add the song to queue
        else:
            Servers.get_player(ctx.guild_id).queue.add(song)

    embed = Utils.get_embed(
        ctx,
        title='Added playlist to Queue:',
        url=playlist.get('original_url'),
        color=Utils.get_random_hex(playlist.get('id'))
    )
    embed.add_field(name=playlist.get('uploader'), value=playlist.get('title'))
    embed.add_field(
        name='Length:', value=f'{playlist.get("playlist_count")} songs')
    embed.add_field(name='Requested by:', value=ctx.author.mention)

    # Get the highest resolution thumbnail available
    if playlist.get('thumbnails'):
        thumbnail = playlist.get('thumbnails')[-1].get('url')
    else:
        thumbnail = playlist.get('entries')[0].get('thumbnails')[-1].get('url')
    embed.set_thumbnail(url=thumbnail)

    await ctx.followup.send(embed=embed)


# Button handling for __search
class __SearchSelection(discord.ui.View):
    def __init__(self, query_result, *, timeout=180):
        self.query_result = query_result
        super().__init__(timeout=timeout)
    
    # All the buttons will call this method to add the song to queue
    async def __selector(self, index: int, ctx: commands.Context) -> None:
        entry = self.query_result.get('entries')[index]
        song = Song(ctx, entry.get('original_url'), entry)

        # If not in a VC, join
        if ctx.guild.voice_client is None:
            await ctx.author.voice.channel.connect(self_deaf=True)

        # If player does not exist, create one.
        if Servers.get_player(ctx.guild_id) is None:
            Servers.add(ctx.guild_id, Player(
                ctx.guild.voice_client, song))
        # If it does, add the song to queue
        else:
            Servers.get_player(ctx.guild_id).queue.add(song)

        # Create embed to go along with it
        embed = Utils.get_embed(
            ctx,
            title=f'[{len(Servers.get_player(ctx.guild_id).queue.get())} Added to Queue:',
            url=song.original_url,
            color=Utils.get_random_hex(song.id)
        )
        embed.add_field(name=song.uploader, value=song.title, inline=False)
        embed.add_field(name='Requested by:', value=song.requester.mention)
        embed.add_field(name='Duration:',
                        value=Song.parse_duration(song.duration))
        embed.set_thumbnail(url=song.thumbnail)
        await ctx.reply(embed=embed)


    @discord.ui.button(label="1",style=discord.ButtonStyle.blurple)
    async def button_one(self,ctx: commands.Context,button:discord.ui.Button):
        await self.__selector(0, ctx)

    @discord.ui.button(label="2",style=discord.ButtonStyle.blurple)
    async def button_two(self,ctx: commands.Context,button:discord.ui.Button):
        await self.__selector(1, ctx)

    @discord.ui.button(label="3",style=discord.ButtonStyle.blurple)
    async def button_three(self,ctx: commands.Context,button:discord.ui.Button):
        await self.__selector(2, ctx)

    @discord.ui.button(label="4",style=discord.ButtonStyle.blurple)
    async def button_four(self,ctx: commands.Context,button:discord.ui.Button):
        await self.__selector(3, ctx)

    @discord.ui.button(label="5",style=discord.ButtonStyle.blurple)
    async def button_five(self,ctx: commands.Context,button:discord.ui.Button):
        await self.__selector(4, ctx)


@ bot.hybrid_command(name="search", description="Searches YouTube for a given query")
async def _search(ctx: commands.Context, query: str) -> None:
    # Check if author is in VC
    if ctx.author.voice is None:
        await ctx.reply('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if ctx.guild.voice_client is not None and ctx.author.voice.channel != ctx.guild.voice_client.channel:
        await ctx.reply("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await ctx.defer(thinking=True)

    query_result = await YTDLInterface.scrape_search(query)

    embeds = []
    embeds.append(Utils.get_embed(ctx,
                                  title="Search results:",
                                  ))
    for i, entry in enumerate(query_result.get('entries')):
        embed = Utils.get_embed(ctx,
                                title=f'`[{i+1}]`  {entry.get("title")} -- {entry.get("channel")}',
                                url=entry.get('url'),
                                color=Utils.get_random_hex(
                                    entry.get("id"))
                                )
        embed.add_field(name='Duration:', value=Song.parse_duration(
            entry.get('duration')), inline=True)
        embed.set_thumbnail(url=entry.get('thumbnails')[-1].get('url'))
        embeds.append(embed)

    await ctx.followup.send(embeds=embeds, view=__SearchSelection(query_result))


@ bot.hybrid_command(name="clear", description="Clears the queue")
async def _clear(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    
    if not Utils.Pretests.has_discretionary_authority(ctx):
        await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return

    Servers.get_player(ctx.guild_id).queue.clear()
    await ctx.reply('💥 Queue cleared')


@ bot.hybrid_command(name="shuffle", description="Shuffles the queue")
async def _shuffle(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    player = Servers.get_player(ctx.guild_id)
    # If there's enough people, require authority to shuffle
    if len(player.vc.channel.members) > 4:
        if not Utils.Pretests.has_discretionary_authority(ctx):
            await Utils.send(ctx, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
            
    player.queue.shuffle()
    await ctx.reply('🔀 Queue shuffled')


@ bot.hybrid_command(name="pause", description="Pauses the current song")
async def _pause(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    Servers.get_player(ctx.guild_id).vc.pause()
    Servers.get_player(ctx.guild_id).song.pause()
    await Utils.send(ctx, title='⏸ Paused')


@ bot.hybrid_command(name="resume", description="Resumes the current song")
async def _resume(ctx: commands.Context) -> None:
    if not await Utils.Pretests.playing_audio(ctx):
        return
    Servers.get_player(ctx.guild_id).vc.resume()
    Servers.get_player(ctx.guild_id).song.resume()
    await Utils.send(ctx, title='▶ Resumed')


@ bot.hybrid_command(name="loop", description="Loops the current song")
async def _loop(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    player = Servers.get_player(ctx.guild.id)
    player.set_loop(not player.looping)
    await Utils.send(ctx, title='🔂 Looped.' if player.looping else 'Loop disabled.')

@ bot.hybrid_command(name="queueloop", description="Loops the queue")
async def _queue_loop(ctx: commands.Context) -> None:
    if not await Utils.Pretests.player_exists(ctx):
        return
    player = Servers.get_player(ctx.guild.id)
    player.set_queue_loop(not player.queue_looping)
    await Utils.send(ctx, title='🔁 Queue looped.' if player.queue_looping else 'Queue loop disabled.')

@ bot.hybrid_command(name="trueloop", description="Loops and adds songs to a random position in queue")
async def _true_loop(ctx: commands.Context) -> None:
    player = Servers.get_player(ctx.guild.id)
    player.set_true_loop(not player.queue_looping)
    await Utils.send(ctx, title='♾ True looped.' if player.true_looping else 'True loop disabled.')

@ bot.hybrid_command(name="help", description="Shows the help menu")
@ discord.app_commands.describe(commands="choose a command to see more info")
@ discord.app_commands.choices(commands=[
    discord.app_commands.Choice(name="ping", value="ping"),
    discord.app_commands.Choice(name="help", value="help"),
    discord.app_commands.Choice(name="join", value="join"),
    discord.app_commands.Choice(name="leave", value="leave"),
    discord.app_commands.Choice(name="play", value="play"),
    discord.app_commands.Choice(name="skip", value="skip"),
    discord.app_commands.Choice(name="forceskip", value="forceskip"),
    discord.app_commands.Choice(name="queue", value="queue"),
    discord.app_commands.Choice(name="now", value="now"),
    discord.app_commands.Choice(name="remove", value="remove"),
    discord.app_commands.Choice(name="removeuser", value="removeuser"),
    discord.app_commands.Choice(name="playlist", value="playlist"),
    discord.app_commands.Choice(name="search", value="search"),
    discord.app_commands.Choice(name="clear", value="clear"),
    discord.app_commands.Choice(name="shuffle", value="shuffle"),
    discord.app_commands.Choice(name="pause", value="pause"),
    discord.app_commands.Choice(name="resume", value="resume"),
    discord.app_commands.Choice(name="loop", value="loop"),
    discord.app_commands.Choice(name="queueloop", value="queueloop")
])
async def _help(ctx: commands.Context, commands: discord.app_commands.Choice[str] = "") -> None:
    if not commands:
        main_embed = Pages.main_page
        embed = Utils.get_embed(
            ctx, title=main_embed["title"], content=main_embed["description"])
        for field in main_embed["fields"]:
            embed.add_field(name=field["name"], value=field["value"])
        await ctx.reply(embed=embed)
        return
    command_embed_dict = Pages.get_page(commands.value)
    embed = Utils.get_embed(
        ctx, title=command_embed_dict["title"], content=command_embed_dict["description"])
    for field in command_embed_dict["fields"]:
        embed.add_field(name=field["name"], value=field["value"])
    await ctx.reply(embed=embed)

# Custom error handler

'''
async def on_tree_error(ctx: commands.Context, error: discord.app_commands.AppCommandError):

    # If a yt_dlp DownloadError was raised
    if isinstance(error.original, yt_dlp.utils.DownloadError):
        await ctx.followup.send(embed=Utils.get_embed(ctx, "An error occurred while trying to parse the link.",
                                                              content=f'```ansi\n{error.original.exc_info[1]}```'))
        # Return here because we don't want to print an obvious error like this.
        return

    # Fallback default error
    await ctx.followup.send(embed=Utils.get_embed(ctx, title="MaBalls ran into Ma issue.", content=f'```ansi\n{error}```'))
    # Allows entire error to be printed without raising an exception
    # (would create an infinite loop as it would be caught by this function)
    traceback.print_exc()
'''
bot.run(key)
