from discord.ext import commands


class Vote:
    def __init__(self, initiator: commands.Context.author):
        self.initiator = initiator
        self.voters = [initiator]

    def __len__(self) -> int:
        return len(self.voters)

    def add(self, member: commands.Context.author) -> None:
        self.voters.append(member)
        return

    def get(self) -> list[commands.Context.author]:
        return self.voters
