import discord
from discord.ui import Button, View, Modal, TextInput
from redbot.core import commands, app_commands
import sqlite3
import json
import os
import logging
import random
import re

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MeshNodes(commands.Cog):
    """Mesh Node Management Cog"""

    CONFIG_FILE = "config.json"
    
    def is_valid_maidenhead(self, locator: str) -> bool:
        """Checks if a string matches the Maidenhead Locator (Grid Square) format."""
        pattern = r"^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$"
        return bool(re.fullmatch(pattern, locator.strip().upper()))

    def __init__(self, bot):
        self.bot = bot
        self.base_dir = os.path.abspath(os.path.dirname(__file__))  # Ensure paths work across OS
        logger.debug(f"Initializing MeshNodes Cog... (Base Directory: {self.base_dir})")

        self.config_path = os.path.join(self.base_dir, self.CONFIG_FILE)
        self.ensure_config()
        self.config = self.load_config()

        # This can be changed in the future, just want to be extra careful with who can access the database
        self.database_admin_ids = {196412468262600707, 173669080388075528}

    def ensure_config(self):
        """Ensures the configuration file exists and has valid values."""
        logger.debug(f"Checking if configuration file exists at: {self.config_path}")
        if not os.path.exists(self.config_path):
            default_config = {
                "BOT_SECRET": "your-bot-token-here",
                "CREDENTIALS_PATH": "path/to/your/credentials.json",
                "GOOGLE_SHEET_ID": "your-google-sheet-id"
            }
            try:
                with open(self.config_path, "w") as f:
                    json.dump(default_config, f, indent=4)
                logger.info(f"Default configuration file created at {self.config_path}. Please update it with real values.")
            except Exception as e:
                logger.error(f"Failed to create configuration file at {self.config_path}: {e}", exc_info=True)
        else:
            logger.info("Configuration file already exists.")

    def load_config(self):
        """Loads the configuration file."""
        logger.debug(f"Loading configuration file from: {self.config_path}")
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            logger.info("Configuration file loaded successfully.")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found at: {self.config_path}.")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file at {self.config_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading configuration file: {e}", exc_info=True)
        return {}




    def get_random_loading_message(self):
        """Get a random loading message from a text file."""
        self.loading_messages_path = os.path.join(self.base_dir, "loading_messages.txt")
        logger.debug(f"Loading random message from: {self.loading_messages_path}")

        if not os.path.exists(self.loading_messages_path):
            logger.warning(f"Loading messages file not found at: {self.loading_messages_path}. Creating a default one.")
            default_messages = [
                "Loading, please wait... ⏳",
                "Almost there! 🚀",
                "Just a moment... ⏱️"
            ]
            try:
                with open(self.loading_messages_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(default_messages))
                logger.info(f"Default loading messages file created at {self.loading_messages_path}.")
            except Exception as e:
                logger.error(f"Failed to create loading messages file: {e}", exc_info=True)
            return default_messages[0]  # Return the first default message

        try:
            with open(self.loading_messages_path, "r", encoding="utf-8") as f:
                messages = [line.strip() for line in f if line.strip()]
            
            if messages:
                message = random.choice(messages)
                logger.info("Successfully retrieved a random loading message.")
                return message
            else:
                logger.warning("Loading messages file is empty. Using default message.")
        except Exception as e:
            logger.error(f"Unexpected error loading messages: {e}", exc_info=True)

        return "Loading, please wait... ⏳"  # Default message in case of failure


                
    @commands.command(name="nodelist")
    async def nodelist(self, ctx, user: discord.User = None):
        """Retrieve a list of nodes owned by a user."""

        loading_message = await ctx.send(self.get_random_loading_message())

        if not user:
            # Default to the author if no user is mentioned
            user = ctx.author

        user_id = str(user.id)
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized")
            return

        nodes = []
        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT node_id, short_name, long_name FROM nodes WHERE discord_id = ?",
                    (user_id,)
                )
                rows = cursor.fetchall()
                for row in rows:
                    nodes.append({
                        "Node ID": row[0],
                        "Node Shortname": row[1],
                        "Node Longname": row[2]
                    })
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

        if not nodes:
            await loading_message.edit(content=f"No nodes found for {user.display_name}.")
            return

        embed = discord.Embed(
            title=f"Nodes owned by {user.display_name}",
            color=discord.Color.green()
        )

        for node in nodes:
            embed.add_field(
                name=node.get("Node Longname", "Unknown Node"),
                value=f"**Shortname:** {node.get('Node Shortname', 'N/A')}\n**Node ID:** {node.get('Node ID', 'N/A')}",
                inline=False
            )

        await loading_message.edit(content=None, embed=embed)


    @commands.command(name="whohas", aliases=["node", "nodeinfo"])
    async def node(self, ctx, *identifier: str):
        """Find the owner of a node by Longname, Shortname, or Node ID (supports partial Node ID from the end)."""
        if not identifier:
            await ctx.send("Please provide a Node ID, Longname, or Shortname.")
            return

        identifier = " ".join(identifier).strip()
        logger.debug(f"Processing !node command for identifier: '{identifier}'")

        loading_message = await ctx.send(self.get_random_loading_message())

        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        matches = []
        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                # Node ID: match from the end (last N chars)
                if len(identifier) <= 8:
                    cursor.execute(
                        "SELECT node_id, short_name, long_name, discord_id FROM nodes WHERE substr(node_id, -?) = ?",
                        (len(identifier), identifier)
                    )
                    matches += cursor.fetchall()
                # Shortname and Longname: case-insensitive match
                cursor.execute(
                    "SELECT node_id, short_name, long_name, discord_id FROM nodes WHERE lower(short_name) = ? OR lower(long_name) = ?",
                    (identifier.lower(), identifier.lower())
                )
                matches += [row for row in cursor.fetchall() if row not in matches]
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

        if not matches:
            await loading_message.edit(
                content=(
                    f"Node not found: `{identifier}`\n"
                    "If this node is yours, please run `!paperwork` so we can have it in the database!"
                )
            )
            return

        embed = discord.Embed(
            title=f"Node Info Results ({len(matches)})",
            color=discord.Color.green()
        )

        view = View()
        for idx, (node_id, short_name, long_name, owner_id) in enumerate(matches):
            embed.add_field(
                name=long_name,
                value=f"**Shortname:** {short_name}\n**Node ID:** {node_id}\n**Owner:** <@{owner_id}>",
                inline=False
            )
            # Add a button for each node
            button = Button(
                label=f"View Full Node Info ({long_name})",
                custom_id=f"nodefull_{node_id}_{idx}"
            )
            async def make_callback(node_id=node_id):
                async def button_callback(interaction: discord.Interaction):
                    await interaction.response.defer()
                    await self.run_nodefull_on_interaction(interaction, node_id)
                return button_callback
            button.callback = await make_callback()
            view.add_item(button)

        await loading_message.edit(content=None, embed=embed, view=view)

    def _get_node_details_embed(self, node_row):
        """
        Helper to build a Discord embed for full node info from a database row.
        """
        excluded_keys = {
            "your discord username",
            "timestamp",
            "your discord user id",
            "should your previous form entry be deleted, because you are submitting a new one to update old information?",
            "column 8",
            "adjustednodeid"
        }
        # node_row: (node_id, discord_id, timestamp, short_name, long_name, additional_node_data_json)
        node_id, discord_id, timestamp, short_name, long_name, additional_node_data_json = node_row

        embed = discord.Embed(title=f"Full Node Info: {long_name}", color=discord.Color.blue())
        embed.add_field(name="Node ID", value=node_id, inline=True)
        embed.add_field(name="Shortname", value=short_name, inline=True)
        embed.add_field(name="Longname", value=long_name, inline=True)
        embed.add_field(name="Owner", value=f"<@!{discord_id}>", inline=True)

        # Parse additional_node_data_json for extra fields
        try:
            extra = json.loads(additional_node_data_json)
            maidenhead_key = "If a permanent install, where is this node placed?"
            grid_url_template = "https://www.levinecentral.com/ham/grid_square.php?&Grid={}&Zoom=13&sm=y"
            for key, value in extra.items():
                cleaned_key = key.strip().lower()
                if cleaned_key not in excluded_keys:
                    if cleaned_key == maidenhead_key.lower() and self.is_valid_maidenhead(str(value)):
                        grid_url = grid_url_template.format(value)
                        value = f"[{value}]({grid_url})"
                    embed.add_field(name=key, value=str(value), inline=True)
        except Exception as e:
            embed.add_field(name="Error", value=f"Failed to parse extra data: {e}", inline=False)
        return embed

    #nodefull stuff here. Not a @command
    # TODO Update this to use the new sqlite database
    async def run_nodefull_on_interaction(self, interaction: discord.Interaction, identifier: str):
        """Runs the nodefull command on behalf of the user who clicked the button, using the new database."""
        loading_message = await interaction.channel.send(self.get_random_loading_message())
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        node_row = None
        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                # Try by node_id (exact or partial from end)
                cursor.execute(
                    "SELECT * FROM nodes WHERE node_id = ? OR substr(node_id, -?) = ?",
                    (identifier, len(identifier), identifier)
                )
                node_row = cursor.fetchone()
                if not node_row:
                    # Try by long_name or short_name (case-insensitive)
                    cursor.execute(
                        "SELECT * FROM nodes WHERE lower(long_name) = ? OR lower(short_name) = ?",
                        (identifier.lower(), identifier.lower())
                    )
                    node_row = cursor.fetchone()
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

        if not node_row:
            await loading_message.edit(content=f"Node not found: `{identifier}`")
            return

        embed = self._get_node_details_embed(node_row)
        await loading_message.edit(content=None, embed=embed)

    @commands.command(name="nodefull")
    async def nodefull(self, ctx, *identifier: str):
        """Displays full details of a node by Longname or Node ID using the new database."""
        if not identifier:
            await ctx.send("Please provide a Node ID or Longname.")
            return

        identifier = " ".join(identifier).strip()
        loading_message = await ctx.send(self.get_random_loading_message())
        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        node_row = None
        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                # Try by node_id (exact or partial from end)
                cursor.execute(
                    "SELECT * FROM nodes WHERE node_id = ? OR substr(node_id, -?) = ?",
                    (identifier, len(identifier), identifier)
                )
                node_row = cursor.fetchone()
                if not node_row:
                    # Try by long_name or short_name (case-insensitive)
                    cursor.execute(
                        "SELECT * FROM nodes WHERE lower(long_name) = ? OR lower(short_name) = ?",
                        (identifier.lower(), identifier.lower())
                    )
                    node_row = cursor.fetchone()
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

        if not node_row:
            await loading_message.edit(content=f"Node not found: `{identifier}`")
            return

        embed = self._get_node_details_embed(node_row)
        await loading_message.edit(content=None, embed=embed)
        


    @commands.command(name="id")
    async def user_id(self, ctx, user: discord.User = None):
        """Return your Discord User ID or the ID of the mentioned user."""
        # Send loading message
        loading_message = await ctx.send(self.get_random_loading_message())

        if not user:
            # No argument, return your own ID
            user = ctx.author
            #await loading_message.edit(content=f"Your Discord User ID is: `{user.id}`")
            await loading_message.edit(content=f"`{user.id}`")
        else:
            # Argument provided, check if it's a valid user mention
            if isinstance(user, discord.User):
                #await loading_message.edit(content=f"{user.display_name}'s Discord User ID is: `{user.id}`")
                await loading_message.edit(content=f"`{user.id}`")
            else:
                await loading_message.edit(content="Error: Invalid argument. Please mention a valid user or provide no argument to get your own ID.")

    # TODO update this to use discord models 
    @commands.command(name="paperwork")
    async def paperwork(self, ctx, user: discord.User = None):
        """Send a Discord Modal to a user's DMs to fill out node info (node_id, short_name, long_name)."""
        loading_message = await ctx.send(self.get_random_loading_message())

        if not user:
            user = ctx.author

        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        # Modal definition
        class NodePaperworkModal(Modal, title="Node Paperwork Submission"):
            node_id = TextInput(label="Node ID", placeholder="Enter Node ID (e.g. 1A2B3C4D)", required=True, min_length=8, max_length=8)
            short_name = TextInput(label="Short Name", placeholder="Short name (e.g. MSP)", required=True, min_length=1, max_length=4)
            long_name = TextInput(label="Long Name", placeholder="Long descriptive name", required=True, min_length=1, max_length=64)

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    with self_view.cog.connect_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT OR REPLACE INTO nodes (node_id, discord_id, short_name, long_name, additional_node_data_json) VALUES (?, ?, ?, ?, ?)",
                            (
                                self.node_id.value.strip(),
                                str(user.id),
                                self.short_name.value.strip(),
                                self.long_name.value.strip(),
                                "{}"
                            )
                        )
                        conn.commit()
                    await interaction.response.send_message("✅ Node paperwork submitted and saved!", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Failed to save node: {e}", ephemeral=True)

        # Hack to pass self into the modal for DB access
        self_view = type("SelfView", (), {})()
        self_view.cog = self

        # View with a button to trigger the modal
        class PaperworkButtonView(View):
            def __init__(self, timeout=180):
                super().__init__(timeout=timeout)
                self.add_item(self.PaperworkButton())

            class PaperworkButton(Button):
                def __init__(self):
                    super().__init__(label="Fill Out Node Paperwork", style=discord.ButtonStyle.primary)

                async def callback(self, interaction: discord.Interaction):
                    modal = NodePaperworkModal()
                    await interaction.response.send_modal(modal)

        try:
            dm = await user.create_dm()
            await dm.send(
                "Please click the button below to fill out the node paperwork form:",
                view=PaperworkButtonView()
            )
            await loading_message.edit(content="📬 Button sent! Check your DMs and click the button to fill out the form. 💌")
        except discord.Forbidden:
            await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
        except Exception as e:
            await loading_message.edit(content=f"❌ Failed to send DM: {e}")

    @commands.command(name="nodetotal")
    async def nodetotal(self, ctx):
        """Counts the total number of unique node IDs in the database."""
        loading_message = await ctx.send("Calculating total node entries...")

        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(DISTINCT node_id) FROM nodes")
                result = cursor.fetchone()
                total_entries = result[0] if result else 0
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

        embed = discord.Embed(title="Node Entry Totals", color=discord.Color.green())
        embed.add_field(name="Total Unique Node IDs", value=str(total_entries), inline=False)
        await loading_message.edit(content=None, embed=embed)


    def get_db_path(self):
        """Returns the path to the SQLite database file."""
        return os.path.join(self.base_dir, "meshnodes.db")

    def connect_db(self):
        """Connects to the SQLite database."""
        return sqlite3.connect(self.get_db_path())


    
    async def double_confirm(self, ctx, step1_text, step2_text, cancel_text):
        view1 = ConfirmView(ctx.author.id, "Are you sure?")
        msg = await ctx.send(step1_text, view=view1)
        await view1.wait()
        if not view1.confirmed:
            await msg.edit(content=cancel_text, view=None)
            return False

        view2 = ConfirmView(ctx.author.id, "Are you REALLY sure?")
        await msg.edit(content=step2_text, view=view2)
        await view2.wait()
        if not view2.confirmed:
            await msg.edit(content=cancel_text, view=None)
            return False

        return msg
    
    @commands.command(name="insertnodes")
    @commands.has_permissions(administrator=True)
    async def insertnodes(self, ctx):
        if ctx.author.id not in self.database_admin_ids:
            await ctx.send("You do not have permission to perform this action.")
            return

        db_path = self.get_db_path()
        if not os.path.exists(db_path):
            await ctx.send("Database not initialized.")
            return

        fake_nodes = [
            {
                "node_id": f"{random.randint(0, 0xFFFFFFFF):08X}",
                "discord_id": str(ctx.author.id),
                "short_name": "ABCD",
                "long_name": "Test Node Alpha",
                "additional_node_data_json": "{}"
            },
            {
                "node_id": f"{random.randint(0, 0xFFFFFFFF):08X}",
                "discord_id": str(ctx.author.id),
                "short_name": "EFG",
                "long_name": "Test Node Beta",
                "additional_node_data_json": "{}"
            },
            {
                "node_id": f"{random.randint(0, 0xFFFFFFFF):08X}",
                "discord_id": str(ctx.author.id),
                "short_name": "HIJ",
                "long_name": "Test Node Gamma",
                "additional_node_data_json": "{}"
            }
        ]

        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                for node in fake_nodes:
                    cursor.execute(
                        "INSERT OR IGNORE INTO nodes (node_id, discord_id, short_name, long_name, additional_node_data_json) VALUES (?, ?, ?, ?, ?)",
                        (
                            node["node_id"],
                            node["discord_id"],
                            node["short_name"],
                            node["long_name"],
                            node["additional_node_data_json"]
                        )
                    )
                conn.commit()
            await ctx.send("Inserted 3 fake nodes.")
        except Exception as e:
            await ctx.send(f"Failed to insert fake nodes: {e}")

    @commands.command(name="createdb")
    @commands.has_permissions(administrator=True)
    async def createdb(self, ctx):
        if ctx.author.id not in self.database_admin_ids:
            await ctx.send("You do not have permission to perform this action.")
            return

        msg = await self.double_confirm(ctx,
            "This will create the database. Please confirm.",
            "Final confirmation required.",
            "Database creation cancelled."
        )
        if not msg:
            return

        db_path = self.get_db_path()
        try:
            with self.connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        node_id TEXT PRIMARY KEY,
                        discord_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        short_name TEXT NOT NULL,
                        long_name TEXT NOT NULL,
                        additional_node_data_json TEXT NOT NULL
                    )
                """)
                conn.commit()
            await msg.edit(content=f"Database created at `{db_path}`.", view=None)
        except Exception as e:
            await msg.edit(content=f"Failed to create database: {e}", view=None)

    @commands.command(name="dropdb")
    @commands.has_permissions(administrator=True)
    async def dropdb(self, ctx):
        if ctx.author.id not in self.database_admin_ids:
            await ctx.send("You do not have permission to perform this action.")
            return

        msg = await self.double_confirm(ctx,
            "This will drop the database. Please confirm.",
            "Final confirmation required.",
            "Database drop cancelled."
        )
        if not msg:
            return

        db_path = self.get_db_path()
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
                await msg.edit(content=f"Database at `{db_path}` has been dropped.", view=None)
            else:
                await msg.edit(content="Database file does not exist.", view=None)
        except Exception as e:
            await msg.edit(content=f"Failed to drop database: {e}", view=None)



class ConfirmView(View):
    def __init__(self, author_id, label):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.confirmed = False
        self.add_item(self.ConfirmButton(label, self))

    class ConfirmButton(Button):
        def __init__(self, label, parent):
            super().__init__(label=label, style=discord.ButtonStyle.danger)
            self.parent = parent

        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.parent.author_id:
                await interaction.response.send_message("You can't confirm this action.", ephemeral=True)
                return
            self.parent.confirmed = True
            await interaction.response.defer()
            self.parent.stop()


# Add this cog to the bot
async def setup(bot):
    await bot.add_cog(MeshNodes(bot))

