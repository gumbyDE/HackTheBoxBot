import requests
from os import getenv, system

from dotenv import load_dotenv
import datetime
import discord
from discord.ext import commands, tasks
from typing import Optional


TASK_CREATE_CHANNEL_TIME = datetime.time(hour=17, minute=0)
PRIVILEGED_IDS = [398942762357096449]


class HackTheBoxMachine:
    def __init__(self, json_data: dict):
        if json_data.get("name"):
            self.name = json_data["name"]

        if json_data.get("difficultyText"):
            self.difficulty = json_data["difficultyText"]
        if json_data.get("difficulty_text"):
            self.difficulty = json_data["difficulty_text"]

        if hasattr(self, "difficulty"):
            if self.difficulty == "Easy":
                self.difficulty_emoji = ":green_circle:"
            elif self.difficulty == "Medium":
                self.difficulty_emoji = ":orange_circle:"
            elif self.difficulty == "Hard":
                self.difficulty_emoji = ":red_circle:"
            else:
                self.difficulty_emoji = ":white_circle:"

        if json_data.get("release"):
            self.release_date_string = json_data["release"]
            self.release_date_date = datetime.datetime.strptime(self.release_date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
            self.release_date = self.release_date_date.strftime("%Y-%m-%d")

        if json_data.get("os"):
            self.os = json_data["os"]
            if self.os == "Windows":
                self.os_emoji = ":window:"
            elif self.os == "Linux" or self.os == "FreeBSD" or self.os == "OpenBSD":
                self.os_emoji = ":penguin:"
            else:
                self.os_emoji = ":question:"

        self.maker = []
        if json_data.get("maker") and json_data.get("maker").get("name"):
            self.maker.append(json_data["maker"]["name"])
        if json_data.get("maker2") and json_data.get("maker2").get("name"):
            self.maker.append(json_data["maker2"]["name"])
        if json_data.get("firstCreator"):
            for creator in json_data["firstCreator"]:
                self.maker.append(creator["name"])
        if json_data.get("coCreators"):
            for creator in json_data["coCreators"]:
                self.maker.append(creator["name"])
        if json_data.get("info_status"):
            self.info_status = json_data["info_status"]

        if json_data.get("retiring"):
            self.retiring = json_data["retiring"]["name"]

    def to_discord_string(self, include_name: bool = True) -> str:
        result = []

        if include_name:
            result.append(f"Name: {self.name}")

        if hasattr(self, "release_date"):
            result.append(f'Release date: {self.release_date}')

        if hasattr(self, "os"):
            result.append(f'OS: {self.os} {self.os_emoji}')

        if hasattr(self, "difficulty"):
            result.append(f'Difficulty: {self.difficulty} {self.difficulty_emoji}')

        if len(self.maker) > 0:
            result.append(f"Box creator: {', '.join(self.maker)}")

        if hasattr(self, "retiring"):
            result.append(f"Retiring: {self.retiring}")

        return ' | '.join(result)

    def to_discord_short_string(self) -> str:
        result = ""
        result += f"{self.name} {self.os_emoji} {self.difficulty_emoji} "

        if len(self.maker) > 0:
            result += f"({', '.join(self.maker)})"

        return result

    def __repr__(self) -> str:
        return f'HackTheBoxMachine("{self.name} | {self.to_discord_string()}")'


class HackTheBox:
    URL_BASE = "https://labs.hackthebox.com/api/v4"
    URL_UPCOMING_MACHINES = f"{URL_BASE}/machine/unreleased"
    URL_ACTIVE_MACHINES = f"{URL_BASE}/machine/paginated?per_page=100"
    URL_RUNNING_MACHINE = f"{URL_BASE}/machine/active"
    URL_MACHINE_INFO = f"{URL_BASE}/machine/profile/"

    def __init__(self, token):
        self.token = token
        self.headers = {
            "User-Agent": "Discordbot",
            "Authorization": f"Bearer {self.token}"
        }

    def get_active_machine(self) -> Optional[HackTheBoxMachine]:
        result = requests.get(self.URL_RUNNING_MACHINE, headers=self.headers)
        result_json = result.json()

        if result_json.get("info") is None:
            return None
        else:
            result = requests.get(self.URL_MACHINE_INFO + result_json["info"]["name"], headers=self.headers)
            result_json = result.json()
            return HackTheBoxMachine(result_json["info"])

    def get_list_of_upcoming_machines(self) -> list[HackTheBoxMachine]:
        result = requests.get(self.URL_UPCOMING_MACHINES, headers=self.headers)
        result_json = result.json()

        machines = []
        for machine in result_json["data"]:
            machines.append(HackTheBoxMachine(machine))
        return machines

    def get_list_of_active_machines(self) -> list[HackTheBoxMachine]:
        result = requests.get(self.URL_ACTIVE_MACHINES, headers=self.headers)
        result_json = result.json()

        machines = []
        for machine in result_json["data"]:
            machines.append(HackTheBoxMachine(machine))
        return machines


class DiscordBot(commands.Bot):
    saturday_night_panorama_category = None

    def __init__(self, command_prefix, self_bot, intents):
        commands.Bot.__init__(self, command_prefix=command_prefix, self_bot=self_bot, intents=intents)
        self.htb = HackTheBox(getenv("HACKTHEBOX_TOKEN"))
        self.add_commands()

    def get_saturday_night_panorama(self) -> discord.CategoryChannel:
        if self.saturday_night_panorama_category:
            return self.saturday_night_panorama_category

        for guild in self.guilds:
            for category in guild.categories:
                if category.name == "saturday-night-panorama-bar":
                    self.saturday_night_panorama_category = category
                    return category

    async def on_ready(self) -> None:
        await self.change_presence(status=discord.Status.online)
        if not self.create_upcoming_channels.is_running():
            self.create_upcoming_channels.start()

    @tasks.loop(time=TASK_CREATE_CHANNEL_TIME)
    async def create_upcoming_channels(self) -> None:
        await self.command_upcoming_boxes()

    async def command_running_box(self) -> str:
        machine = self.htb.get_active_machine()
        if machine is None:
            text = "No machine running :("
        else:
            text = "The following machine is running:\n"
            text += machine.to_discord_string()

        return text

    async def command_upcoming_boxes(self) -> str:
        machines = self.htb.get_list_of_upcoming_machines()
        category = self.get_saturday_night_panorama()
        category_id = category.id
        channels = []

        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.category_id == category_id:
                    channels.append(channel.name)

        text = ""
        if len(machines) > 0:
            text = "The following machines are upcoming:\n"
            for m in machines:
                channel_created = False
                for channel in channels:
                    if channel.casefold() == m.name.casefold():
                        channel_created = True
                icon = ":white_check_mark:" if channel_created else ":x:"
                text += f"\n- {m.to_discord_string()} (Channel {icon})"

                if not channel_created:
                    channel_new = await category.guild.create_text_channel(m.name, category=category, topic=m.to_discord_string(False))
                    if len(m.info_status) > 0:
                        await channel_new.send(f"```{m.info_status}```")
        else:
            text = "Currently no upcoming machines :("
        return text

    async def command_active_boxes(self) -> str:
        machines = self.htb.get_list_of_active_machines()

        text = ""
        if len(machines) > 0:
            text = "The following machines are currently active:\n"
            for m in machines:
                text += f"\n- {m.to_discord_short_string()}"
        return text

    def add_commands(self) -> None:
        @self.command(name="upcoming", pass_context=True)
        async def upcoming(ctx) -> None:
            text = await self.command_upcoming_boxes()
            await ctx.channel.send(text)

        @self.command(name="active", pass_context=True)
        async def active(ctx) -> None:
            text = await self.command_active_boxes()
            await ctx.channel.send(text)

        @self.command(name="running", pass_context=True)
        async def running(ctx) -> None:
            print(ctx.author.id)
            text = await self.command_running_box()
            await ctx.channel.send(text)

        @self.command(name="update", pass_context=True)
        async def update(ctx) -> None:
            if ctx.author.id not in PRIVILEGED_IDS:
                await ctx.channel.send("Access denied")
                return

            await ctx.channel.send("Updating bot from GitHub and restarting the service...")
            # for this to work run the bot in /home/bot/HackTheBoxBot/ as user bot and install discordbot.service in systemd
            # then install sudo and put sudoers_discordbot into /etc/sudoers.d/discordbot
            system("/usr/bin/git -C /home/bot/HackTheBoxBot/ pull && /usr/bin/sudo /usr/bin/systemctl restart discordbot")


if __name__ == "__main__":
    load_dotenv()
    intents = discord.Intents.default()
    intents.message_content = True
    bot = DiscordBot(intents=intents, command_prefix=".", self_bot=False)
    bot.run(getenv("DISCORD_TOKEN"))
    # htb.get_active_machine()
    # htb.get_list_of_active_machines()
    # htb.get_list_of_upcoming_machines()
