import os
import random
import sqlite3
import logging
import discord

from redbot.core import commands

from .commands.NodeEditCommands import (
    edit_node,
    import_csv,
    transfer_node,
    register_node,
    edit_additional_node_info,
    clear_additional_node_info,
)
from .commands.InfoCommands import list_my_nodes, total_nodes, full_node_info, node_info
from .commands.DatabaseCommands import drop_database, create_database, delete_node


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MeshNodes(commands.Cog):
    """Mesh Node Management Cog"""

    def get_db_path(self):
        """Returns the path to the SQLite database file."""
        return os.path.join(self.base_dir, "meshnodes.db")

    def connect_db(self):
        """Connects to the SQLite database."""
        return sqlite3.connect(self.get_db_path())

    def __init__(self, bot):
        self.bot = bot
        self.base_dir = os.path.abspath(os.path.dirname(__file__))  # Ensure paths work across OS
        logger.debug(f"Initializing MeshNodes Cog... (Base Directory: {self.base_dir})")

        # This can be changed in the future, just want to be extra careful with who can access the database
        self.database_admin_ids = {196412468262600707, 173669080388075528}

    def get_random_loading_message(self):
        """Get a random loading message from a text file."""
        self.loading_messages_path = os.path.join(self.base_dir, "loading_messages.txt")
        logger.debug(f"Loading random message from: {self.loading_messages_path}")

        if not os.path.exists(self.loading_messages_path):
            logger.warning(f"Loading messages file not found at: {self.loading_messages_path}. Creating a default one.")
            default_messages = ["Loading, please wait... ⏳", "Almost there! 🚀", "Just a moment... ⏱️"]
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

    #############################
    # Node Information Commands #
    #############################
    @commands.command(name="nodetotal", aliases=["totalnodes"])
    async def nodetotal(self, ctx):
        await total_nodes(self, ctx)

    @commands.command(name="nodelist", aliases=["lsn"])
    async def nodelist(self, ctx, user: discord.User = None):
        await list_my_nodes(self, ctx, user)

    @commands.command(name="whohas", aliases=["node", "nodeinfo"])
    async def node(self, ctx, *identifier: str):
        await node_info(self, ctx, *identifier)

    @commands.command(name="nodefull")
    async def nodefull(self, ctx, *identifier: str):
        await full_node_info(self, ctx, *identifier)

    #############################
    # Node Information Commands #
    #############################

    #########################
    # Node Editing Commands #
    #########################
    @commands.command(name="paperwork")
    async def paperwork(self, ctx, user: discord.User = None):
        await register_node(self, ctx, user)

    @commands.command(name="editnode")
    async def editnode(self, ctx, node_id: str):
        await edit_node(self, ctx, node_id)

    @commands.command(name="editnodeinfo")
    async def editnode(self, ctx, node_id: str):
        await edit_additional_node_info(self, ctx, node_id)

    @commands.command(name="clearinfo")
    async def clearinfo(self, ctx, node_id: str):
        await clear_additional_node_info(self, ctx, node_id)

    @commands.command(name="transfer")
    async def transfer(self, ctx, node_id: str, new_owner: discord.User):
        await transfer_node(self, ctx, node_id, new_owner)

    #########################
    # Node Editing Commands #
    #########################

    ################################
    # Database management commands #
    ################################
    @commands.command(name="createdb")
    @commands.has_permissions(administrator=True)
    async def createdb(self, ctx):
        await create_database(self, ctx)

    @commands.command(name="dropdb")
    @commands.has_permissions(administrator=True)
    async def dropdb(self, ctx):
        await drop_database(self, ctx)

    @commands.command(name="deletenode")
    #@commands.has_permissions(administrator=True)
    async def deletenode(self, ctx, node_id: str):
        await delete_node(self, ctx, node_id)
    
    @commands.command(name="importnodes")
    @commands.has_permissions(administrator=True)
    async def import_nodes(self, ctx, user: discord.User = None):
        await import_csv(self, ctx, user)

    ################################
    # Database management commands #
    ################################


# Add this cog to the bot
async def setup(bot):
    await bot.add_cog(MeshNodes(bot))
