import discord
import math
import random
import time

from datetime import datetime

# Import classes from our files
from Player import Player
from Servers import Servers
from Song import Song


def pront(content, lvl="DEBUG", end="\n") -> None:
    """
    A custom logging method that acts as a wrapper for print().

    Parameters
    ----------
    content : `any`
        The value to print.
    lvl : `str`, optional
        The level to raise the value at.
        Accepted values and their respective colors are as follows:

        LOG : None
        DEBUG : Pink
        OKBLUE : Blue
        OKCYAN : Cyan
        OKGREEN : Green
        WARNING : Yellow
        ERROR : Red
        NONE : Resets ANSI color sequences
    end : `str` = `\\n` (optional)
        The character(s) to end the statement with, passes to print().
    """
    colors = {
        "LOG": "",
        "DEBUG": "\033[1;95m",
        "OKBLUE": "\033[94m",
        "OKCYAN": "\033[96m",
        "OKGREEN": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "NONE": "\033[0m"
    }
    # if type(content) != str and type(content) != int and type(content) != float:
    #    content = sep.join(content)
    print(colors[lvl] + "{" + datetime.now().strftime("%x %X") +
          "} " + lvl + ": " + str(content) + colors["NONE"], end=end)  # sep.join(list())


# makes a ascii song progress bar
def get_progress_bar(song: Song) -> str:
    """
    Creates an ASCII progress bar from a provided Song.
    
    This is calculated from a time delta counted within the song.

    Parameters
    ----------
    song : `Song`
        The Song object to create the progress bar from.
    
    Returns
    -------
    `str`:
        A string containing a visual representation of how far the song has played.
    """
    # if the song is None or the song has been has not been started ( - 100000 is an arbitrary number)
    if song is None or song.get_elapsed_time() > time.time() - 100000 or song.duration is None:
        return ''
    percent_duration = (song.get_elapsed_time() / song.duration)*100

    if percent_duration > 100:#percent duration cant be greater than 100
        percent_duration = 100
    
    ret = f'{song.parse_duration_short_hand(math.floor(song.get_elapsed_time()))}/{song.parse_duration_short_hand(song.duration)}'
    ret += f' [{(math.floor(percent_duration / 4) * "▬")}{">" if percent_duration < 100 else ""}{((math.floor((100 - percent_duration) / 4)) * "    ")}]'
    return ret

@DeprecationWarning
def progress_bar(begin: int, end: int, current_val: int) -> str:
    """
    A deprecated method for producing progress bars that do not 
    """
    percent_duration = (current_val / end) * 100

    if percent_duration > 100:#percent duration cant be greater than 100
        percent_duration = 100

    ret = f'{current_val}/{end}'
    ret += f' [{(math.floor(percent_duration / 4) * "▬")}{">" if percent_duration < 100 else ""}{((math.floor((100 - percent_duration) / 4)) * "    ")}]'
    return ret

# Returns a random hex code
def get_random_hex(seed = None) -> int:
    """
    Returns a random hexidecimal color code.
    
    Parameters
    ----------
    seed : `int` | `float` | `str` | `bytes` | `bytearray` (optional)
        The seed to generate the color from.
        None or no argument seeds from current time or from an operating system specific randomness source if available.

    Returns
    -------
    `int`:
        The integer representing the hexidecimal code.
    """
    random.seed(seed)
    return random.randint(0, 16777215)


# Creates a standard Embed object
def get_embed(interaction, title='', content='', url=None, color='', progress: bool = True) -> discord.Embed:
    """
    Quick and easy method to create a discord.Embed that allows for easier keeping of a consistent style

    TODO change the content parameter to be named description to allow it to align easier with the standard discord.Embed() constructor.

    Parameters
    ----------
    interaction : `discord.Interaction`
        The Interaction to draw author information from.
    title : `str` (optional)
        The title of the embed. Can only be up to 256 characters.
    content : `str` (optional)
        The description of the embed. Can only be up to 4096 characters.
    url : `str` | `None` (optional)
        The URL of the embed.
    color : `int` (optional)
        The color of the embed.
    progress : `bool` = `True` (optional)
        Whether get_embed should try to automatically add the progress bar and now-playing information.

    Returns
    -------
    discord.Embed:
        The embed generated by the parameters.
    """
    if color == '':
        color = get_random_hex(interaction.user.id)
    embed = discord.Embed(
        title=title,
        description=content,
        url=url,
        color=color
    )
    embed.set_author(name=interaction.user.display_name,
                     icon_url=interaction.user.display_avatar.url)

    # If the calling method wants the progress bar
    if progress:
        player = Servers.get_player(interaction.guild_id)
        if player and player.song:
            footer_message = f'{"🔂 " if player.looping else ""}{"🔁 " if player.queue_looping else ""}{"♾ " if player.true_looping else ""}\n{get_progress_bar(player.song)}'

            embed.set_footer(text=footer_message,
                             icon_url=player.song.thumbnail)
    return embed


# Creates and sends an Embed message
async def send(interaction: discord.Interaction, title='', content='', url='', color='', ephemeral: bool = False, progress: bool = True) -> None:
    """
    A convenient method to send a get_embed generated by its parameters.

    Parameters
    ----------
    interaction : `discord.Interaction`
        The Interaction to draw author information from.
    title : `str` (optional)
        The title of the embed. Can only be up to 256 characters.
    content : `str` (optional)
        The description of the embed. Can only be up to 4096 characters.
    url : `str` | `None` (optional)
        The URL of the embed.
    color : `int` (optional)
        The color of the embed.
    progress : `bool` = `True` (optional)
        Whether get_embed should try to automatically add the progress bar and now-playing information.
    ephemeral : `bool` = `False` (optional)
    """
    embed = get_embed(interaction, title, content, url, color, progress)
    await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


def get_now_playing_embed(player: Player, progress: bool = False) -> discord.Embed:
    """
    Gets an embed for a now-playing messge.
    Used for consistency and neatness.

    Parameters
    ----------
    player : `Player`
        The player to gather states, etc. from.
    progress : `bool`, `False`, optional
        Whether the embed should generate with a progress bar.

    Returns
    -------
    discord.Embed:
        The now-playing embed.

    """
    title_message = f'Now Playing:\t{":repeat_one: " if player.looping else ""}{":repeat: " if player.queue_looping else ""}{":infinity: " if player.true_looping else ""}'
    embed = discord.Embed(
        title=title_message,
        url=player.song.original_url,
        description=f'{player.song.title} -- {player.song.uploader}',
        color=get_random_hex(player.song.id)
    )
    embed.add_field(name='Duration:', value=player.song.parse_duration(
        player.song.duration), inline=True)
    embed.add_field(name='Requested by:', value=player.song.requester.mention)
    embed.set_image(url=player.song.thumbnail)
    embed.set_author(name=player.song.requester.display_name,
                     icon_url=player.song.requester.display_avatar.url)
    if progress:
        embed.set_footer(text=get_progress_bar(player.song))
    return embed


# Cleans up and closes a player
async def clean(player: Player) -> None:
    """
    Cleans up and closes a player.
    
    Parameters
    ----------
    player : Player
        The Player to close.
    """
    # Only disconnect if bot is connected to vc
    # (it won't be if it was disconnected by an admin)
    if player.vc.is_connected():
        await player.vc.disconnect()
    # Delete a to-be defunct now_playing message
    if player.last_np_message:
        await player.last_np_message.delete()
    player.queue.clear()
    # Needs to be after at least player.vc.disconnect() because for some
    # godawful reason it refuses to disconnect otherwise
    player.player_task.cancel()
    Servers.remove(player)

# Moved the logic for skip into here to be used by NowPlayingButtons


async def skip_logic(player: Player, interaction: discord.Interaction):
    """
    Performs all of the complex logic for permitting or denying skips.
    
    Placed here for use in both PlaybackManagement and NowPlayingButtons
    
    Parameters
    ----------
    player : Player
        The player the song belongs to.
    interaction : discord.Interaction
        The message Interaction.

    """
    # Get a complex embed for votes
    async def skip_msg(title: str = '', content: str = '', present_tense: bool = True, ephemeral: bool = False) -> None:

        embed = get_embed(interaction, title, content,
                          color=get_random_hex(player.song.id),
                          progress=present_tense)
        embed.set_thumbnail(url=player.song.thumbnail)

        users = ''
        for user in player.song.vote.get():
            users = f'{user.name}, {users}'
        users = users[:-2]
        if present_tense:
            # != 1 because if for whatever reason len(skip_vote) == 0 it will still make sense
            voter_message = f"User{'s who have' if len(player.song.vote) != 1 else ' who has'} voted to skip:"
            song_message = "Song being voted on:"
        else:
            voter_message = f"Vote passed by:"
            song_message = "Song that was voted on:"

        embed.add_field(name="Initiated by:",
                        value=player.song.vote.initiator.mention)
        embed.add_field(name=song_message,
                        value=player.song.title, inline=True)
        embed.add_field(name=voter_message, value=users, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

    # If there's not enough people for it to make sense to call a vote in the first place
    # or if this user has authority
    if len(player.vc.channel.members) <= 3 or Pretests.has_song_authority(interaction, player.song):
        player.vc.stop()
        await send(interaction, "Skipped!", ":white_check_mark:")
        return

    votes_required = len(player.vc.channel.members) // 2

    if player.song.vote is None:
        # Create new Vote
        player.song.create_vote(interaction.user)
        await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")
        return

    # If user has already voted to skip
    if interaction.user in player.song.vote.get():
        await skip_msg("You have already voted to skip!", ":octagonal_sign:", ephemeral=True)
        return

    # Add vote
    player.song.vote.add(interaction.user)

    # If vote succeeds
    if len(player.song.vote) >= votes_required:
        await skip_msg("Skip vote succeeded! :tada:", present_tense=False)
        player.song.vote = None
        player.vc.stop()
        return

    await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")

# Makes things more organized by being able to access Utils.Pretests.[name of pretest]
class Pretests:
    """
    A static class containing methods for pre-run state tests.

    ...

    Methods
    -------
    has_discretionary_authority(interaction: `discord.Interaction`):
        Checks if the interaction.user has discretionary authority in the current scenario.
    has_song_authority(interaction: `discord.Interaction`, `song: Song`):
        Checks if the interaction.user has authority over the given song.
    voice_channel(interaction: `discord.Interaction`)
        Checks if all voice channel states are correct.
    player_exists(interaction: `discord.Interaction`):
        Checks if there is a Player registered for the current guild and if voice channel states are correct.
    playing_audio(interaction: `discord.Interaction`)
        Checks if audio is playing in a player for that guild and voice channel states are correct.
    """
    # To be used with control over the Player as a whole
    def has_discretionary_authority(interaction: discord.Interaction) -> bool:
        """
        Checks if the interaction.user has discretionary authority in the current scenario.
        
        Parameters
        ----------
        interaction : `discord.Interaction`
            The interaction to pull interaction.user from.

        Returns
        -------
        `bool`:
            Whether the interaction.user should have discretionary authority.
        """
        if len(interaction.user.voice.channel.members) <= 3:
            return True
        for role in interaction.user.roles:
            if role.name.lower() == 'dj':
                return True
            if role.permissions.manage_channels or role.permissions.administrator:
                return True
        # Force discretionary authority for developers
        if interaction.user.id == 369999044023549962 or interaction.user.id == 311659410109759488:
            return True
        return False

    # To be used for control over a specific song
    def has_song_authority(interaction: discord.Interaction, song: Song) -> bool:
        """
        Checks if the interaction.user has authority over the given song.
        
        Parameters
        ----------
        interaction : `discord.Interaction`
            The interaction to pull interaction.user from.
        song : `Song`
            The song to compare interaction.user to.

        Returns
        -------
        `bool`:
            Whether the interaction.user should have authority over the song.
        """
        if song.requester == interaction.user:
            return True

        return Pretests.has_discretionary_authority(interaction)

    # Checks if voice channel states are right
    async def voice_channel(interaction: discord.Interaction) -> bool:
        """
        Checks if all voice channel states are correct.

        Specifically, this checks if MaBalls is in a voice channel and if the person executing the command is in the same channel.
        
        Parameters
        ----------
        interaction : `discord.Interaction`
            The interaction to check and respond in.

        Returns
        -------
        `True`:
            Will return true in the event that all checks pass.
        `False`:
            Will return false in the event one or more checks fail, this will also use interaction.response to send a response to the message.
        """
        if interaction.guild.voice_client is None:
            await interaction.response.send_message("MaBalls is not in a voice channel", ephemeral=True)
            return False

        if interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.response.send_message("You must be connected to the same voice channel as MaBalls", ephemeral=True)
            return False
        return True

    # Expanded test for if a Player exists
    async def player_exists(interaction: discord.Interaction) -> bool:
        """
        Checks if there is a Player registered for the current guild and if voice channel states are correct.

        Specifically, this checks if voice_channel returns True then checks if the Player exists for that guild.
        
        Parameters
        ----------
        interaction : `discord.Interaction`
            The interaction to check and respond in.

        Returns
        -------
        `True`:
            Will return true in the event that all checks pass.
        `False`:
            Will return false in the event one or more checks fail, this will also use interaction.response to send a response to the message.
        """
        if not await Pretests.voice_channel(interaction):
            return False
        if Servers.get_player(interaction.guild_id) is None:
            await interaction.response.send_message("This command can only be used while a queue exists", ephemeral=True)
            return False
        return True

    # Expanded test for if audio is currently playing from a Player
    async def playing_audio(interaction: discord.Interaction) -> bool:
        """
        Checks if audio is playing in a player for that guild and voice channel states are correct.

        Specifically, this checks if player_exists and subsequently voice_channel returns True then checks if player.is_playing is True.
        
        Parameters
        ----------
        interaction : `discord.Interaction`
            The interaction to check and respond in.

        Returns
        -------
        `True`:
            Will return true in the event that all checks pass.
        `False`:
            Will return false in the event one or more checks fail, this will also use interaction.response to send a response to the message.
        """
        if not await Pretests.player_exists(interaction):
            return False
        if not Servers.get_player(interaction.guild_id).is_playing():
            await interaction.response.send_message("This command can only be used while a song is playing.")
            return False
        return True
    