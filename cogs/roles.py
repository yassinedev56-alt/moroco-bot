import discord
from discord import app_commands
from discord.ext import commands


class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fullpower", description="Get full administrator power on this server")
    async def fullpower(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("Only the server owner can use this command.", ephemeral=True)
            return
        await interaction.response.defer()
        role = discord.utils.get(interaction.guild.roles, name="Full Power")
        if not role:
            role = await interaction.guild.create_role(
                name="Full Power",
                permissions=discord.Permissions(administrator=True),
                reason="Full power role created"
            )
        if role in interaction.user.roles:
            await interaction.followup.send("You already have full power.")
            return
        await interaction.user.add_roles(role, reason="Full power granted")
        await interaction.followup.send(f"Full power granted! Role {role.mention} assigned.")

    @app_commands.command(name="help", description="Show available commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Role Bot - Help",
            description="**Commands:**\n`/fullpower` — Get admin power (owner only)\n`/help` — Show this message",
            color=0x00aaff,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
