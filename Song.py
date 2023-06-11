import time

from discord import Member, Interaction
from discord.ext import commands
from Vote import Vote
from YTDLInterface import YTDLInterface


class Song:
    def __init__(self, ctx: commands.Context, link: str, dict: dict):
        self.link = link
        self.requester = ctx.author
        self.channel = ctx.channel
        self.vote = None

        # If there's an unexpected list of entries
        if dict.get('entries') is not None and len(dict.get('entries')) > 0:
            # Get the first result and continue as normal
            dict = dict.get('entries')[0]

        # Try to get a thumbnail
        if dict.get('thumbnails'):
            self.thumbnail = dict.get('thumbnails')[-1].get('url')
        else:
            self.thumbnail = None

        # Try different method to get URL
        if dict.get('webpage_url'):
            self.original_url = dict.get('webpage_url')
        else:
            self.original_url = dict.get('url')

        self.title = dict.get('title')
        self.uploader = dict.get('channel')
        self.audio = dict.get('url')
        self.id = dict.get('id')
        self.duration = dict.get('duration')

        # Delta time handling variables
        self.start_time = 0
        self.pause_start = 0
        self.pause_time = 0

    @classmethod
    async def from_link(cls, ctx: commands.Context, link: str):
        song = cls(ctx, link, {'webpage_url': link})
        await song.populate()
        return song

    # Populate all None fields
    async def populate(self) -> None:
        data = await YTDLInterface.scrape_link(self.original_url)
        # If there's an unexpected list of entries
        if data.get('entries') is not None and len(data.get('entries')) > 0:
            # Get the first result and continue as normal
            data = data.get('entries')[0]
        self.title = data.get('title')
        self.uploader = data.get('channel')
        self.audio = data.get('url')
        self.id = data.get('id')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.original_url = data.get('webpage_url')

    def create_vote(self, member: Member) -> None:
        self.vote = Vote(member)

    @staticmethod
    def parse_duration(duration: int | None) -> str:
        if duration is None:
            return 'Unknown'
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(f'{days} days')
        if hours > 0:
            duration.append(f'{hours} hours')
        if minutes > 0:
            duration.append(f'{minutes} minutes')
        if seconds > 0:
            duration.append(f'{seconds} seconds')

        return ', '.join(duration)

    @staticmethod
    def parse_duration_short_hand(duration: int | None) -> str:
        if duration is None:
            return '0'
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(f'{days:02d}')
        if hours > 0:
            duration.append(f'{hours:02d}')
        duration.append(f'{minutes:02d}')
        duration.append(f'{seconds:02d}')

        return ':'.join(duration)

    def start(self) -> None:
        print('Starting song timer')
        self.start_time = time.time()
        self.pause_time = 0

    def pause(self) -> None:
        self.pause_start = time.time()

    def resume(self) -> None:
        self.pause_time += time.time() - self.pause_start
        self.pause_start = 0

    def get_elapsed_time(self) -> int:
        return time.time() - (self.start_time + self.pause_time + ((time.time() - self.pause_start)if self.pause_start else 0))

    def __str__(self) -> str:
        return f'{self.title} by {self.uploader}'
