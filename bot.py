import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

from utils.database import init_db

init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True


class MorocoBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.roles")
        print("[+] Loaded cog: cogs.roles")

    async def on_ready(self):
        print(f"[-] LOGGED IN AS : {self.user.name}")
        try:
            synced = await self.tree.sync()
            print(f"[+] SYNCED {len(synced)} SLASH COMMANDS.")
        except Exception as e:
            print(f"[!] SYNC ERROR: {e}")


bot = MorocoBot()

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("[!] ERROR: No bot token found in .env")
        exit(1)
    bot.run(token)
