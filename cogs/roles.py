import discord
from discord import app_commands
from discord.ext import commands
from utils.database import get_conn

PERM_TEMPLATES = {
    "member": {
        "send_messages": True,
        "read_messages": True,
        "connect": True,
        "speak": True,
    },
    "moderator": {
        "kick_members": True,
        "ban_members": True,
        "manage_messages": True,
        "mute_members": True,
        "deafen_members": True,
        "move_members": True,
        "view_audit_log": True,
    },
    "admin": {
        "administrator": True,
    },
    "muted": {
        "send_messages": False,
        "speak": False,
        "add_reactions": False,
    },
    "bot": {
        "read_messages": True,
        "send_messages": True,
        "connect": True,
        "speak": True,
        "read_message_history": True,
    },
}


class RoleSelect(discord.ui.Select):
    def __init__(self, roles: list[discord.Role]):
        options = []
        for role in roles[:25]:
            options.append(
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    emoji="🔘",
                )
            )
        super().__init__(
            placeholder="Select roles to toggle...",
            min_values=1,
            max_values=len(options) if options else 1,
            options=options,
            custom_id="role_panel_select",
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)


class RolePanelView(discord.ui.View):
    def __init__(self, roles: list[discord.Role]):
        super().__init__(timeout=None)
        self.add_item(RoleSelect(roles))
        self.assign_button = discord.ui.Button(
            label="Apply Changes",
            style=discord.ButtonStyle.primary,
            custom_id="role_panel_apply",
        )

        async def apply_callback(interaction: discord.Interaction):
            select = None
            for child in self.children:
                if isinstance(child, RoleSelect):
                    select = child
                    break
            if not select or not select.values:
                await interaction.response.send_message("Select at least one role.", ephemeral=True)
                return
            added = []
            removed = []
            for role_id_str in select.values:
                role = interaction.guild.get_role(int(role_id_str))
                if not role:
                    continue
                if role in interaction.user.roles:
                    await interaction.user.remove_roles(role, reason="Role panel toggle")
                    removed.append(role.name)
                else:
                    await interaction.user.add_roles(role, reason="Role panel toggle")
                    added.append(role.name)
            parts = []
            if added:
                parts.append(f"Added: {', '.join(added)}")
            if removed:
                parts.append(f"Removed: {', '.join(removed)}")
            msg = "\n".join(parts) if parts else "No changes."
            await interaction.response.send_message(msg, ephemeral=True)

        self.assign_button.callback = apply_callback
        self.add_item(self.assign_button)


class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Panel: Add role ───────────────────────────────────────────

    @app_commands.command(name="panel-add", description="Add a role to the self-assignable role panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_add(self, interaction: discord.Interaction, role: discord.Role):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM role_menu_roles WHERE guild_id = ? AND role_id = ?",
            (interaction.guild_id, role.id)
        )
        if cursor.fetchone():
            await interaction.response.send_message(f"{role.mention} is already in the panel.", ephemeral=True)
            conn.close()
            return
        cursor.execute(
            "INSERT INTO role_menu_roles (guild_id, role_id, label) VALUES (?, ?, ?)",
            (interaction.guild_id, role.id, role.name)
        )
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"Added {role.mention} to the role panel.", ephemeral=True)

    # ─── Panel: Remove role ────────────────────────────────────────

    @app_commands.command(name="panel-remove", description="Remove a role from the self-assignable role panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_remove(self, interaction: discord.Interaction, role: discord.Role):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM role_menu_roles WHERE guild_id = ? AND role_id = ?",
            (interaction.guild_id, role.id)
        )
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"Removed {role.mention} from the role panel.", ephemeral=True)

    # ─── Panel: List ───────────────────────────────────────────────

    @app_commands.command(name="panel-list", description="List all roles in the self-assignable panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_list(self, interaction: discord.Interaction):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM role_menu_roles WHERE guild_id = ?", (interaction.guild_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("No roles configured. Use `/panel-add` to add some.", ephemeral=True)
            return
        lines = []
        for r in rows:
            role = interaction.guild.get_role(r["role_id"])
            if role:
                lines.append(f"{role.mention} (`{role.name}`)")
        embed = discord.Embed(title="Self-Assignable Roles", description="\n".join(lines), color=0x00aaff)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── Panel: Create ─────────────────────────────────────────────

    @app_commands.command(name="panel-create", description="Create the role selection panel message")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_create(self, interaction: discord.Interaction):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM role_menu_roles WHERE guild_id = ?", (interaction.guild_id,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("No roles configured. Use `/panel-add` first.", ephemeral=True)
            return
        roles = []
        for r in rows:
            role = interaction.guild.get_role(r["role_id"])
            if role:
                roles.append(role)
        if not roles:
            await interaction.response.send_message("None of the configured roles exist anymore.", ephemeral=True)
            return
        embed = discord.Embed(
            title="Role Panel",
            description="Select roles from the dropdown below, then click **Apply Changes** to toggle them.",
            color=0x00aaff,
        )
        role_lines = [f"{r.mention}" for r in roles]
        embed.add_field(name="Available Roles", value="\n".join(role_lines), inline=False)
        await interaction.response.send_message(embed=embed, view=RolePanelView(roles))

    # ─── Auto-role set ─────────────────────────────────────────────

    @app_commands.command(name="autorole-set", description="Set a role to automatically assign to new members")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_set(self, interaction: discord.Interaction, role: discord.Role):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO guild_config (guild_id, autorole_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET autorole_id = ?",
            (interaction.guild_id, role.id, role.id)
        )
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"Auto-role set to {role.mention}.", ephemeral=True)

    # ─── Auto-role remove ──────────────────────────────────────────

    @app_commands.command(name="autorole-remove", description="Remove the auto-role setting")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_remove(self, interaction: discord.Interaction):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE guild_config SET autorole_id = NULL WHERE guild_id = ?",
            (interaction.guild_id,)
        )
        conn.commit()
        conn.close()
        await interaction.response.send_message("Auto-role removed.", ephemeral=True)

    # ─── Auto-role show ────────────────────────────────────────────

    @app_commands.command(name="autorole-show", description="Show the current auto-role setting")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_show(self, interaction: discord.Interaction):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT autorole_id FROM guild_config WHERE guild_id = ?", (interaction.guild_id,))
        row = cursor.fetchone()
        conn.close()
        if not row or not row["autorole_id"]:
            await interaction.response.send_message("No auto-role configured.", ephemeral=True)
            return
        role = interaction.guild.get_role(row["autorole_id"])
        if role:
            await interaction.response.send_message(f"Auto-role: {role.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("Auto-role role no longer exists.", ephemeral=True)

    # ─── Event: on_member_join ─────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT autorole_id FROM guild_config WHERE guild_id = ?", (member.guild.id,))
        row = cursor.fetchone()
        conn.close()
        if row and row["autorole_id"]:
            role = member.guild.get_role(row["autorole_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except:
                    pass

    # ─── Reaction role add ─────────────────────────────────────────

    @app_commands.command(name="reactionrole-add", description="Add a reaction-role mapping")
    @app_commands.checks.has_permissions(administrator=True)
    async def reactionrole_add(
        self, interaction: discord.Interaction,
        channel: discord.TextChannel,
        message_id: str,
        emoji: str,
        role: discord.Role,
    ):
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        try:
            msg = await channel.fetch_message(mid)
        except:
            await interaction.response.send_message("Could not find that message.", ephemeral=True)
            return
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM reaction_roles WHERE guild_id = ? AND channel_id = ? AND message_id = ? AND emoji = ?",
            (interaction.guild_id, channel.id, mid, emoji)
        )
        if cursor.fetchone():
            await interaction.response.send_message("That emoji is already mapped on this message.", ephemeral=True)
            conn.close()
            return
        cursor.execute(
            "INSERT INTO reaction_roles (guild_id, channel_id, message_id, role_id, emoji) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild_id, channel.id, mid, role.id, emoji)
        )
        conn.commit()
        conn.close()
        try:
            await msg.add_reaction(emoji)
        except:
            pass
        await interaction.response.send_message(
            f"Reaction-role set: {emoji} on {msg.jump_url} → {role.mention}", ephemeral=True
        )

    # ─── Reaction role remove ──────────────────────────────────────

    @app_commands.command(name="reactionrole-remove", description="Remove a reaction-role mapping")
    @app_commands.checks.has_permissions(administrator=True)
    async def reactionrole_remove(
        self, interaction: discord.Interaction,
        channel: discord.TextChannel,
        message_id: str,
        emoji: str,
    ):
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reaction_roles WHERE guild_id = ? AND channel_id = ? AND message_id = ? AND emoji = ?",
            (interaction.guild_id, channel.id, mid, emoji)
        )
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"Reaction-role removed: {emoji}", ephemeral=True)

    # ─── Reaction role list ────────────────────────────────────────

    @app_commands.command(name="reactionrole-list", description="List all reaction-role mappings")
    @app_commands.checks.has_permissions(administrator=True)
    async def reactionrole_list(self, interaction: discord.Interaction):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM reaction_roles WHERE guild_id = ?",
            (interaction.guild_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("No reaction roles configured.", ephemeral=True)
            return
        lines = []
        for r in rows:
            role = interaction.guild.get_role(r["role_id"])
            role_name = role.mention if role else f"Unknown ({r['role_id']})"
            channel = interaction.guild.get_channel(r["channel_id"])
            ch = channel.mention if channel else "#unknown"
            lines.append(f"{r['emoji']} → {role_name} in {ch} (`{r['message_id']}`)")
        embed = discord.Embed(title="Reaction Roles", description="\n".join(lines), color=0x00aaff)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── Event: on_raw_reaction_add ────────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member and payload.member.bot:
            return
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role_id FROM reaction_roles WHERE guild_id = ? AND channel_id = ? AND message_id = ? AND emoji = ?",
            (payload.guild_id, payload.channel_id, payload.message_id, str(payload.emoji))
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            role = guild.get_role(row["role_id"])
            if role and payload.member:
                try:
                    await payload.member.add_roles(role, reason="Reaction role")
                except:
                    pass

    # ─── Event: on_raw_reaction_remove ─────────────────────────────

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role_id FROM reaction_roles WHERE guild_id = ? AND channel_id = ? AND message_id = ? AND emoji = ?",
            (payload.guild_id, payload.channel_id, payload.message_id, str(payload.emoji))
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return
            role = guild.get_role(row["role_id"])
            if role:
                member = guild.get_member(payload.user_id)
                if member:
                    try:
                        await member.remove_roles(role, reason="Reaction role removed")
                    except:
                        pass

    # ─── Permission template ───────────────────────────────────────

    @app_commands.command(name="perm-template-apply", description="Apply a permission template to a role")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(template=[
        app_commands.Choice(name=t, value=t) for t in PERM_TEMPLATES.keys()
    ])
    async def perm_template_apply(
        self, interaction: discord.Interaction,
        role: discord.Role,
        template: str,
    ):
        if template not in PERM_TEMPLATES:
            await interaction.response.send_message(f"Unknown template: {template}", ephemeral=True)
            return
        perms = PERM_TEMPLATES[template]
        try:
            await role.edit(permissions=discord.Permissions(**perms), reason=f"Applied template: {template}")
            await interaction.response.send_message(
                f"Applied **{template}** template to {role.mention}.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to edit that role.", ephemeral=True)

    # ─── Help ──────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show all available role management commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Role Manager Bot - Help",
            description="All commands for role management:",
            color=0x00aaff,
        )
        cmds = [
            ("`/panel-add @role`", "Add a role to the self-assignable panel"),
            ("`/panel-remove @role`", "Remove a role from the panel"),
            ("`/panel-list`", "List all roles in the panel"),
            ("`/panel-create`", "Create the role selection message"),
            ("`/autorole-set @role`", "Set auto-role for new members"),
            ("`/autorole-remove`", "Remove auto-role"),
            ("`/autorole-show`", "Show current auto-role"),
            ("`/reactionrole-add`", "Add reaction-role mapping"),
            ("`/reactionrole-remove`", "Remove reaction-role mapping"),
            ("`/reactionrole-list`", "List reaction-role mappings"),
            ("`/perm-template-apply`", "Apply permission template to a role"),
        ]
        for name, desc in cmds:
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
