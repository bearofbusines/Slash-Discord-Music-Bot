import discord
import math
import os
import random
import traceback
from dotenv import load_dotenv
from discord.ext import commands

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


class Bot(discord.Client):  # initiates the bots intents and on_ready event
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents, command_prefix="mb.", help_command=None)

    async def setup_hook(self):
        return await super().setup_hook()

    async def on_ready(self):
        await tree.sync()  # please dont remove just in case i need to sync
        Utils.pront("Bot is ready", lvl="OKGREEN")
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching, name=f"you in {len(bot.guilds):,} Servers."))
    
    async def on_command_error(self, ctx, error):
        await ctx.reply(f"```{error}```", ephemeral=True)


# Global Variables
bot = Bot()
tree = discord.app_commands.CommandTree(bot)



## EVENT LISTENERS ##


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    # If we don't care that a voice state was updated
    if member.guild.voice_client is None:
        return

    # If the user was in the same VC as the bot
    if before.channel == member.guild.voice_client.channel:
        # If the bot is now alone
        if len(before.channel.members) == 1:
            player = Servers.get_player(member.guild.id)
            if player is None:
                member.guild.voice_client.disconnect()
            else:
                await Utils.clean(player)


## COMMANDS ##


@ commands.hybrid_command(name="ping", description="The ping command (^-^)")
async def _ping(ctx: commands.Context) -> None:
    await ctx.defer(ephemeral=True)
    await ctx.reply('Pong!', ephemeral=True)


@ tree.command(name="join", description="Adds the MaBalls to the voice channel you are in")
async def _join(interaction: discord.Interaction) -> None:
    if interaction.user.voice is None:  # checks if the user is in a voice channel
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return
    if interaction.guild.voice_client is not None:  # checks if the bot is in a voice channel
        await interaction.response.send_message('I am already in a voice channel', ephemeral=True)
        return
    # Connect to the voice channel
    await interaction.user.voice.channel.connect(self_deaf=True)
    await Utils.send(interaction, title='Joined!', content=':white_check_mark:', progress=False)


@ tree.command(name="leave", description="Removes the MaBalls from the voice channel you are in")
async def _leave(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.voice_channel(interaction):
        return

    # Clean up if needed
    if Servers.get_player(interaction.guild_id) is not None:
        await Utils.clean(Servers.get_player(interaction.guild_id))
    # Otherwise, just leave VC
    else:
        await interaction.guild.voice_client.disconnect()
    await Utils.send(interaction, title='Left!', content=':white_check_mark:', progress=False)


@ tree.command(name="play", description="Plays a song from youtube(or other sources somtimes) in the voice channel you are in")
async def _play(interaction: discord.Interaction, link: str, top: bool = False) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    # create song
    scrape = await YTDLInterface.scrape_link(link)
    song = Song(interaction, link, scrape)

    # Check if song didn't initialize properly via scrape
    if song.title is None:
        # If it didn't, query the link instead (resolves searches in the link field)
        query = await YTDLInterface.query_link(link)
        song = Song(interaction, query.get('original_url'), query)

    # If not in a VC, join
    if interaction.guild.voice_client is None:
        await interaction.user.voice.channel.connect(self_deaf=True)

    # If player does not exist, create one.
    if Servers.get_player(interaction.guild_id) is None:
        Servers.add(interaction.guild_id, Player(
            interaction.guild.voice_client, song))
        position = 1
    # If it does, add the song to queue
    elif top:
        if not Utils.Pretests.has_discretionary_authority(interaction):
            await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
        Servers.get_player(interaction.guild_id).queue.add_at(song, 0)
        position = 1
    else:
        Servers.get_player(interaction.guild_id).queue.add(song)
        position = len(Servers.get_player(interaction.guild_id).queue.get())
        

    embed = Utils.get_embed(
        interaction,
        title=f'[{position}] Added to Queue:',
        url=song.original_url,
        color=Utils.get_random_hex(song.id)
    )
    embed.add_field(name=song.uploader, value=song.title, inline=False)
    embed.add_field(name='Requested by:', value=song.requester.mention)
    embed.add_field(name='Duration:', value=Song.parse_duration(song.duration))
    embed.set_thumbnail(url=song.thumbnail)
    await interaction.followup.send(embed=embed)


@ tree.command(name="skip", description="Skips the currently playing song")
async def _skip(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return

    player = Servers.get_player(interaction.guild_id)

    await Utils.skip_logic(player, interaction)


@ tree.command(name="forceskip", description="Skips the currently playing song without having a vote. (Requires Manage Channels permission.)")
async def _force_skip(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return

    # If there's enough users in vc for it to make sense check perms
    if len(Servers.get_player(interaction.guild_id).vc.channel.members) > 3:
        # Check song authority
        if not Utils.Pretests.has_song_authority(interaction, Servers.get_player(interaction.guild_id).song):
            await Utils.send(interaction, title='Insufficient permissions!', 
                            content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
        
    Servers.get_player(interaction.guild_id).vc.stop()
    await Utils.send(interaction, "Skipped!", ":white_check_mark:")

# Button handling for _queue
class __QueueButtons(discord.ui.View):
    def __init__(self, *, timeout=180, page=1):
        self.page = page
        super().__init__(timeout=timeout)

    def get_queue_embed(self, interaction: discord.Interaction):
        player = Servers.get_player(interaction.guild_id)
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

        embed = Utils.get_embed(interaction, title='Queue', color=Utils.get_random_hex(
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
    async def button_left(self,interaction:discord.Interaction,button:discord.ui.Button):
        self.page -= 1
        await interaction.response.edit_message(embed=self.get_queue_embed(interaction), view=self)
        
    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="➡")
    async def button_right(self,interaction:discord.Interaction,button:discord.ui.Button):
        self.page += 1
        await interaction.response.edit_message(embed=self.get_queue_embed(interaction), view=self)

@ tree.command(name="queue", description="Shows the current queue")
async def _queue(interaction: discord.Interaction, page: int = 1) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    # Convert page into non-user friendly (woah scary it starts at 0)(if only we were using lua)
    page -= 1
    player = Servers.get_player(interaction.guild_id)
    if not player.queue.get():
        await Utils.send(interaction, title='Queue is empty!', ephemeral=True)
        return

    qb = __QueueButtons(page=page)

    await interaction.response.send_message(embed=qb.get_queue_embed(interaction), view=qb)


@ tree.command(name="replay", description="Restarts the current song")
async def _replay(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return
    
    player = Servers.get_player(interaction.guild_id)

    if not Utils.Pretests.has_song_authority(interaction, player.song):
        await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return
    
    player = Servers.get_player(interaction.guild_id)
    # Just add it to the top of the queue and skip to it
    # Dirty, but it works.
    player.queue.add_at(player.song, 0)
    player.vc.stop()
    await Utils.send(interaction, title='⏪ Rewound')


@ tree.command(name="now", description="Shows the current song")
async def _now(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    if (Servers.get_player(interaction.guild_id).song is None):
        await Utils.send(interaction, title="Nothing is playing", content="You should add something", progress=False)
        return
    await interaction.response.send_message(embed=Utils.get_now_playing_embed(Servers.get_player(interaction.guild_id), progress=True))


@ tree.command(name="remove", description="Removes a song from the queue")
async def _remove(interaction: discord.Interaction, number_in_queue: int) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    # Convert to non-human-readable
    number_in_queue -= 1
    song = Servers.get_player(interaction.guild_id).queue.get(number_in_queue)

    if song is None:
        await Utils.send(interaction, "Queue index does not exist.")
        return
    
    if not Utils.Pretests.has_song_authority(interaction, song):
        await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return

    removed_song = Servers.get_player(
        interaction.guild_id).queue.remove(number_in_queue)
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
        await interaction.response.send_message(embed=embed)


@ tree.command(name="removeuser", description="Removes all of the songs added by a specific user")
async def _remove_user(interaction: discord.Interaction, member: discord.Member):
    if not await Utils.Pretests.player_exists(interaction):
        return
    
    if not Utils.Pretests.has_discretionary_authority(interaction):
        await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return
    
    queue = Servers.get_player(interaction.guild.id).queue

    # TODO either make this an int or fill out the send embed more
    removed = []
    i = 0
    while i < len(queue.get()):
        if queue.get(i).requester == member:
            removed.append(queue.remove(i))
            continue

        # Only increment i when song.requester != member
        i += 1

    await Utils.send(interaction,
                     title=f'Removed {len(removed)} songs.')


@ tree.command(name="playlist", description="Adds a playlist to the queue")
async def _playlist(interaction: discord.Interaction, link: str, shuffle: bool = False) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    playlist = await YTDLInterface.scrape_link(link)

    if playlist.get('_type') != "playlist":
        await interaction.followup.send(embed=Utils.get_embed(interaction, "Not a playlist."), ephemeral=True)
        return

    # Might not proc, there for extra protection
    if len(playlist.get("entries")) == 0:
        await interaction.followup.send("Playlist Entries [] empty.")

    # Detect if this is a Mix
    if playlist.get("uploader") is None:
        # Truncate the playlist to just the top 50 Songs or fewer if there are less
        playlist.update({"playlist_count": 50})
        playlist.update({"entries": playlist.get("entries")[:50]})

    # If not in a VC, join
    if interaction.guild.voice_client is None:
        await interaction.user.voice.channel.connect(self_deaf=True)

    # Shuffle the entries[] within playlist before processing them
    if shuffle:
        random.shuffle(playlist.get("entries"))

    for entry in playlist.get("entries"):

        # Feed the Song the entire entry, saves time by not needing to create and fill a dict
        song = Song(interaction, link, entry)

        # If player does not exist, create one.
        if Servers.get_player(interaction.guild_id) is None:
            Servers.add(interaction.guild_id, Player(
                interaction.guild.voice_client, song))
        # If it does, add the song to queue
        else:
            Servers.get_player(interaction.guild_id).queue.add(song)

    embed = Utils.get_embed(
        interaction,
        title='Added playlist to Queue:',
        url=playlist.get('original_url'),
        color=Utils.get_random_hex(playlist.get('id'))
    )
    embed.add_field(name=playlist.get('uploader'), value=playlist.get('title'))
    embed.add_field(
        name='Length:', value=f'{playlist.get("playlist_count")} songs')
    embed.add_field(name='Requested by:', value=interaction.user.mention)

    # Get the highest resolution thumbnail available
    if playlist.get('thumbnails'):
        thumbnail = playlist.get('thumbnails')[-1].get('url')
    else:
        thumbnail = playlist.get('entries')[0].get('thumbnails')[-1].get('url')
    embed.set_thumbnail(url=thumbnail)

    await interaction.followup.send(embed=embed)


# Button handling for __search
class __SearchSelection(discord.ui.View):
    def __init__(self, query_result, *, timeout=180):
        self.query_result = query_result
        super().__init__(timeout=timeout)
    
    # All the buttons will call this method to add the song to queue
    async def __selector(self, index: int, interaction: discord.Interaction) -> None:
        entry = self.query_result.get('entries')[index]
        song = Song(interaction, entry.get('original_url'), entry)

        # If not in a VC, join
        if interaction.guild.voice_client is None:
            await interaction.user.voice.channel.connect(self_deaf=True)

        # If player does not exist, create one.
        if Servers.get_player(interaction.guild_id) is None:
            Servers.add(interaction.guild_id, Player(
                interaction.guild.voice_client, song))
        # If it does, add the song to queue
        else:
            Servers.get_player(interaction.guild_id).queue.add(song)

        # Create embed to go along with it
        embed = Utils.get_embed(
            interaction,
            title=f'[{len(Servers.get_player(interaction.guild_id).queue.get())} Added to Queue:',
            url=song.original_url,
            color=Utils.get_random_hex(song.id)
        )
        embed.add_field(name=song.uploader, value=song.title, inline=False)
        embed.add_field(name='Requested by:', value=song.requester.mention)
        embed.add_field(name='Duration:',
                        value=Song.parse_duration(song.duration))
        embed.set_thumbnail(url=song.thumbnail)
        await interaction.response.send_message(embed=embed)


    @discord.ui.button(label="1",style=discord.ButtonStyle.blurple)
    async def button_one(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.__selector(0, interaction)

    @discord.ui.button(label="2",style=discord.ButtonStyle.blurple)
    async def button_two(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.__selector(1, interaction)

    @discord.ui.button(label="3",style=discord.ButtonStyle.blurple)
    async def button_three(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.__selector(2, interaction)

    @discord.ui.button(label="4",style=discord.ButtonStyle.blurple)
    async def button_four(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.__selector(3, interaction)

    @discord.ui.button(label="5",style=discord.ButtonStyle.blurple)
    async def button_five(self,interaction:discord.Interaction,button:discord.ui.Button):
        await self.__selector(4, interaction)


@ tree.command(name="search", description="Searches YouTube for a given query")
async def _search(interaction: discord.Interaction, query: str) -> None:
    # Check if author is in VC
    if interaction.user.voice is None:
        await interaction.response.send_message('You are not in a voice channel', ephemeral=True)
        return

    # Check if author is in the *right* vc if it applies
    if interaction.guild.voice_client is not None and interaction.user.voice.channel != interaction.guild.voice_client.channel:
        await interaction.response.send_message("You must be in the same voice channel in order to use MaBalls", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    query_result = await YTDLInterface.scrape_search(query)

    embeds = []
    embeds.append(Utils.get_embed(interaction,
                                  title="Search results:",
                                  ))
    for i, entry in enumerate(query_result.get('entries')):
        embed = Utils.get_embed(interaction,
                                title=f'`[{i+1}]`  {entry.get("title")} -- {entry.get("channel")}',
                                url=entry.get('url'),
                                color=Utils.get_random_hex(
                                    entry.get("id"))
                                )
        embed.add_field(name='Duration:', value=Song.parse_duration(
            entry.get('duration')), inline=True)
        embed.set_thumbnail(url=entry.get('thumbnails')[-1].get('url'))
        embeds.append(embed)

    await interaction.followup.send(embeds=embeds, view=__SearchSelection(query_result))


@ tree.command(name="clear", description="Clears the queue")
async def _clear(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    
    if not Utils.Pretests.has_discretionary_authority(interaction):
        await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
        return

    Servers.get_player(interaction.guild_id).queue.clear()
    await interaction.response.send_message('💥 Queue cleared')


@ tree.command(name="shuffle", description="Shuffles the queue")
async def _shuffle(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    player = Servers.get_player(interaction.guild_id)
    # If there's enough people, require authority to shuffle
    if len(player.vc.channel.members) > 4:
        if not Utils.Pretests.has_discretionary_authority(interaction):
            await Utils.send(interaction, title='Insufficient permissions!', 
                        content="You don't have the correct permissions to use this command!  Please refer to /help for more information.")
            return
            
    player.queue.shuffle()
    await interaction.response.send_message('🔀 Queue shuffled')


@ tree.command(name="pause", description="Pauses the current song")
async def _pause(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    Servers.get_player(interaction.guild_id).vc.pause()
    Servers.get_player(interaction.guild_id).song.pause()
    await Utils.send(interaction, title='⏸ Paused')


@ tree.command(name="resume", description="Resumes the current song")
async def _resume(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.playing_audio(interaction):
        return
    Servers.get_player(interaction.guild_id).vc.resume()
    Servers.get_player(interaction.guild_id).song.resume()
    await Utils.send(interaction, title='▶ Resumed')


@ tree.command(name="loop", description="Loops the current song")
async def _loop(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    player = Servers.get_player(interaction.guild.id)
    player.set_loop(not player.looping)
    await Utils.send(interaction, title='🔂 Looped.' if player.looping else 'Loop disabled.')

@ tree.command(name="queueloop", description="Loops the queue")
async def _queue_loop(interaction: discord.Interaction) -> None:
    if not await Utils.Pretests.player_exists(interaction):
        return
    player = Servers.get_player(interaction.guild.id)
    player.set_queue_loop(not player.queue_looping)
    await Utils.send(interaction, title='🔁 Queue looped.' if player.queue_looping else 'Queue loop disabled.')

@ tree.command(name="trueloop", description="Loops and adds songs to a random position in queue")
async def _true_loop(interaction: discord.Interaction) -> None:
    player = Servers.get_player(interaction.guild.id)
    player.set_true_loop(not player.queue_looping)
    await Utils.send(interaction, title='♾ True looped.' if player.true_looping else 'True loop disabled.')

@ tree.command(name="help", description="Shows the help menu")
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
async def _help(interaction: discord.Interaction, commands: discord.app_commands.Choice[str] = "") -> None:
    if not commands:
        main_embed = Pages.main_page
        embed = Utils.get_embed(
            interaction, title=main_embed["title"], content=main_embed["description"])
        for field in main_embed["fields"]:
            embed.add_field(name=field["name"], value=field["value"])
        await interaction.response.send_message(embed=embed)
        return
    command_embed_dict = Pages.get_page(commands.value)
    embed = Utils.get_embed(
        interaction, title=command_embed_dict["title"], content=command_embed_dict["description"])
    for field in command_embed_dict["fields"]:
        embed.add_field(name=field["name"], value=field["value"])
    await interaction.response.send_message(embed=embed)

# Custom error handler


async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):

    # If a yt_dlp DownloadError was raised
    if isinstance(error.original, yt_dlp.utils.DownloadError):
        await interaction.followup.send(embed=Utils.get_embed(interaction, "An error occurred while trying to parse the link.",
                                                              content=f'```ansi\n{error.original.exc_info[1]}```'))
        # Return here because we don't want to print an obvious error like this.
        return

    # Fallback default error
    await interaction.followup.send(embed=Utils.get_embed(interaction, title="MaBalls ran into Ma issue.", content=f'```ansi\n{error}```'))
    # Allows entire error to be printed without raising an exception
    # (would create an infinite loop as it would be caught by this function)
    traceback.print_exc()
tree.on_error = on_tree_error

bot.run(key)
