import discord
import math
import random
import time

from datetime import datetime
from discord.ext import commands
# Import classes from our files
from Player import Player
from Servers import Servers
from Song import Song


def pront(content, lvl="DEBUG", end="\n") -> None:
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
    # if the song is None or the song has been has not been started ( - 100000 is an arbitrary number)
    if song is None or song.get_elapsed_time() > time.time() - 100000 or song.duration is None:
        return ''
    percent_duration = (song.get_elapsed_time() / song.duration)*100
    ret = f'{song.parse_duration_short_hand(math.floor(song.get_elapsed_time()))}/{song.parse_duration_short_hand(song.duration)}'
    ret += f' [{(math.floor(percent_duration / 4) * "▬")}{">" if percent_duration < 100 else ""}{((math.floor((100 - percent_duration) / 4)) * "    ")}]'
    return ret


# Returns a random hex code
def get_random_hex(seed) -> int:
    random.seed(seed)
    return random.randint(0, 16777215)


# Creates a standard Embed object
def get_embed(ctx, title='', content='', url=None, color='', progress: bool = True) -> discord.Embed:
    if color == '':
        color = get_random_hex(ctx.author.id)
    embed = discord.Embed(
        title=title,
        description=content,
        url=url,
        color=color
    )
    embed.set_author(name=ctx.author.display_name,
                     icon_url=ctx.author.display_avatar.url)

    # If the calling method wants the progress bar
    if progress:
        player = Servers.get_player(ctx.guild_id)
        if player is not None and player.queue.get():
            footer_message = f'{"🔂 " if player.looping else ""}{"🔁 " if player.queue_looping else ""}{"♾ " if player.true_looping else ""}\n{get_progress_bar(player.song)}'

            embed.set_footer(text=footer_message,
                             icon_url=player.song.thumbnail)
    return embed


# Creates and sends an Embed message
async def send(ctx: commands.Context, title='', content='', url='', color='', ephemeral: bool = False, progress: bool = True) -> None:
    embed = get_embed(ctx, title, content, url, color, progress)
    await ctx.response.send_message(embed=embed, ephemeral=ephemeral)


def get_now_playing_embed(player: Player, progress: bool = False) -> discord.Embed:
    title_message = f'Now Playing:\t{":repeat_one: " if player.looping else ""}{":repeat: " if player.queue_looping else ""}'
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
    player.player_task.cancel()
    # Delete a to-be defunct now_playing message
    if player.last_np_message:
        await player.last_np_message.delete()
    player.queue.clear()
    await player.vc.disconnect()
    Servers.remove(player)


def progress_bar(begin: int, end: int, current_val: int) -> str:
    percent_duration = (current_val / end) * 100
    ret = f'{current_val}/{end}'
    ret += f' [{(math.floor(percent_duration / 4) * "▬")}{">" if percent_duration < 100 else ""}{((math.floor((100 - percent_duration) / 4)) * "    ")}]'
    return ret[:32]  # hot fix for embeds being too long

# Moved the logic for skip into here to be used by NowPlayingButtons


async def skip_logic(player: Player, ctx: commands.Context):
    # Get a complex embed for votes
    async def skip_msg(title: str = '', content: str = '', present_tense: bool = True, ephemeral: bool = False) -> None:

        embed = get_embed(ctx, title, content,
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
        await ctx.response.send_message(embed=embed, ephemeral=ephemeral)

    # If there's not enough people for it to make sense to call a vote in the first place
    # or if this user has authority
    if len(player.vc.channel.members) <= 3 or Pretests.has_song_authority(ctx, player.song):
        player.vc.stop()
        await send(ctx, "Skipped!", ":white_check_mark:")
        return

    votes_required = len(player.vc.channel.members) // 2

    if player.song.vote is None:
        # Create new Vote
        player.song.create_vote(ctx.author)
        await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")
        return

    # If user has already voted to skip
    if ctx.author in player.song.vote.get():
        await skip_msg("You have already voted to skip!", ":octagonal_sign:", ephemeral=True)
        return

    # Add vote
    player.song.vote.add(ctx.author)

    # If vote succeeds
    if len(player.song.vote) >= votes_required:
        await skip_msg("Skip vote succeeded! :tada:", present_tense=False)
        player.song.vote = None
        player.vc.stop()
        return

    await skip_msg("Vote added.", f"{votes_required - len(player.song.vote)}/{votes_required} votes to skip.")

# Code for buttons on now_playing messages


class NowPlayingButtons(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="⏪")
    async def rewind_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        self.player.queue.add_at(self.player.song, 0)
        self.player.vc.stop()
        self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
        await ctx.response.send_message(embed=get_embed(ctx, title="⏪ Rewound"))

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="⏸")
    async def pause_play_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        if self.player.vc.is_paused():
            self.player.vc.resume()
            self.player.song.resume()
            button.emoji = "⏸"
            self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
            await ctx.response.send_message(embed=get_embed(ctx, title="▶ Resumed"))
            return
        self.player.vc.pause()
        self.player.song.pause()
        button.emoji = "▶"
        self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
        await ctx.response.send_message(embed=get_embed(ctx, title="⏸ Paused"))

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="⏩")
    async def skip(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        await skip_logic(self.player, ctx)

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="🔂")
    async def loop_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        self.player.set_loop(not self.player.looping)
        self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
        await ctx.response.send_message(ephemeral=True, embed=get_embed(ctx, title='🔂 Looped.' if self.player.looping else 'Loop disabled.'))

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="🔁")
    async def queue_loop_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        self.player.set_queue_loop(not self.player.queue_looping)
        self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
        await ctx.response.send_message(ephemeral=True, embed=get_embed(ctx, title='🔁 Queue looped.' if self.player.queue_looping else 'Queue loop disabled.'))

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji='♾')
    async def true_loop_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        self.player.set_true_loop(not self.player.true_looping)
        self.player.last_np_message = await self.player.last_np_message.edit(embed=get_now_playing_embed(self.player, progress=True), view=self)
        await ctx.response.send_message(ephemeral=True, embed=get_embed(ctx, title='♾ True looped.' if self.player.true_looping else 'True loop disabled.'))

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="🔀")
    async def shuffle_button(self, ctx: commands.Context, button: discord.ui.Button) -> None:
        self.player.queue.shuffle()
        await ctx.response.send_message(embed=get_embed(ctx, title='🔀 Queue shuffled'))


# Makes things more organized by being able to access Utils.Pretests.[name of pretest]
class Pretests:

    # To be used with control over the Player as a whole
    def has_discretionary_authority(ctx: commands.Context) -> bool:
        if len(ctx.author.voice.channel.members) <= 3:
            return True
        for role in ctx.author.roles:
            if role.name.lower() == 'dj':
                return True
            if role.permissions.manage_channels or role.permissions.administrator:
                return True
        # Force discretionary authority for developers
        if ctx.author.id == 369999044023549962 or ctx.author.id == 311659410109759488:
            return True
        return False

    # To be used for control over a specific song
    def has_song_authority(ctx: commands.Context, song: Song) -> bool:
        if song.requester == ctx.author:
            return True

        return Pretests.has_discretionary_authority(ctx)

    # Checks if voice channel states are right
    async def voice_channel(ctx: commands.Context) -> bool:
        if ctx.guild.voice_client is None:
            await ctx.response.send_message("MaBalls is not in a voice channel", ephemeral=True)
            return False

        if ctx.author.voice.channel != ctx.guild.voice_client.channel:
            await ctx.response.send_message("You must be connected to the same voice channel as MaBalls", ephemeral=True)
            return False
        return True

    # Expanded test for if a Player exists
    async def player_exists(ctx: commands.Context) -> bool:
        if not await Pretests.voice_channel(ctx):
            return False
        if Servers.get_player(ctx.guild_id) is None:
            await ctx.response.send_message("This command can only be used while a queue exists", ephemeral=True)
            return False
        return True

    # Expanded test for if audio is currently playing from a Player
    async def playing_audio(ctx: commands.Context) -> bool:
        if not await Pretests.player_exists(ctx):
            return False
        if not Servers.get_player(ctx.guild_id).is_playing():
            await ctx.response.send_message("This command can only be used while a song is playing.")
            return False
        return True
