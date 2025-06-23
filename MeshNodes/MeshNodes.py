import discord
from discord.ui import Button, View
from redbot.core import commands, app_commands
from google.oauth2 import service_account
from googleapiclient.discovery import build
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
        self.service = self.authenticate_google_sheets()

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

    def authenticate_google_sheets(self):
        """Authenticate with Google Sheets API using a service account."""
        credentials_path = self.config.get("CREDENTIALS_PATH")
        if not credentials_path:
            logger.error("CREDENTIALS_PATH is missing in the configuration file.")
            return None

        credentials_path = os.path.join(self.base_dir, credentials_path)  # Ensure correct path
        logger.debug(f"Checking Google Sheets credentials file at: {credentials_path}")

        if not os.path.exists(credentials_path):
            logger.error(f"Google Sheets credentials file not found at: {credentials_path}")
            return None

        try:
            creds = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
            )
            logger.info("Google Sheets authentication successful.")
            return build("sheets", "v4", credentials=creds)
        except FileNotFoundError:
            logger.error(f"Google Sheets credentials file missing at: {credentials_path}.")
        except Exception as e:
            logger.error(f"Google Sheets authentication failed: {e}", exc_info=True)
        return None

    def get_sheet_data(self):
        """Fetches data from the Google Sheet."""
        if not self.service:
            logger.error("Google Sheets service not initialized.")
            return []

        sheet_id = self.config.get("GOOGLE_SHEET_ID")
        if not sheet_id:
            logger.error("Missing Google Sheet ID in the configuration.")
            return []

        range_name = "Form Responses 1"  # Adjust if needed
        try:
            result = self.service.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_name).execute()
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Failed to retrieve sheet data: {e}", exc_info=True)
            return []


    def find_nodes(self, key, value):
        """Finds nodes by a key-value pair."""
        data = self.get_sheet_data()
        if not data:
            logger.warning("No data found in the sheet.")
            return []

        headers = data[0]  # First row as headers
        result = []
        for row in data[1:]:  # Loop through the data, skipping the header
            node = dict(zip(headers, row))
            if str(node.get(key, "")).lower() == value.lower():
                result.append(node)

        if result:
            logger.info(f"Found {len(result)} node(s) matching {key} = {value}.")
        else:
            logger.warning(f"No nodes found matching {key} = {value}.")
        return result



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
        
        # Send loading message
        loading_message = await ctx.send(self.get_random_loading_message())
        
        if not user:
            # Default to the author if no user is mentioned
            user = ctx.author
        
        user_id = str(user.id)
        nodes = self.find_nodes("Your Discord User ID", user_id)
        
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
        """Find the owner of a node by Longname or Node ID."""
        if not identifier:
            await ctx.send("Please provide a Node ID or Longname.")
            return
        
        identifier = " ".join(identifier).strip()
        logger.debug(f"Processing !node command for identifier: '{identifier}'")
        
        # Send loading message
        loading_message = await ctx.send(self.get_random_loading_message())

        # Fetch node data
        nodes = self.find_nodes("Node ID", identifier) or self.find_nodes("Node Longname", identifier) or self.find_nodes("Node Shortname", identifier)
        
        if not nodes:
            await loading_message.edit(
                content=(
                    f"Node not found: `{identifier}`\n"
                    "If this node is yours, please run `!paperwork` so we can have it in the database!"
                )
            )

            return
        
        node = nodes[0]
        owner_id = node.get("Your Discord User ID")
        embed = discord.Embed(title=f"Node Info: {node.get('Node Longname')}", color=discord.Color.green())
        embed.add_field(name="Shortname", value=node.get("Node Shortname"), inline=True)
        embed.add_field(name="Node ID", value=node.get("Node ID"), inline=True)
        embed.add_field(name="Owner", value=f"<@{owner_id}>", inline=False)
        #embed.add_field(name="Owner", value=f"<@!{owner_id}>", inline=False) #!{owner_id} renders as nickname, without ! is username

        # Create a button that will trigger the nodefull command
        view = View()
        button = Button(label="View Full Node Info", custom_id=f"nodefull_{identifier}")
        view.add_item(button)

        # Send the embed and attach the button
        await loading_message.edit(content=None, embed=embed, view=view)

        # Handle the button click
        async def button_callback(interaction: discord.Interaction):
            # Acknowledge the button interaction
            await interaction.response.defer()  # This acknowledges the button click
            
            # Re-run the !nodefull command by invoking it programmatically
            await self.run_nodefull_on_interaction(interaction, identifier)
        
        button.callback = button_callback

    #nodefull stuff here. Not a @command
    async def run_nodefull_on_interaction(self, interaction: discord.Interaction, identifier: str):
        """Runs the nodefull command on behalf of the user who clicked the button."""
        # Send loading message for the nodefull command
        loading_message = await interaction.channel.send(self.get_random_loading_message())

        # Fetch node data
        nodes = self.find_nodes("Node ID", identifier) or self.find_nodes("Node Longname", identifier) or self.find_nodes("Node Shortname", identifier)
        
        if not nodes:
            await loading_message.edit(content=f"Node not found: `{identifier}`")
            return
        
        node = nodes[0]
        excluded_keys = {
            "your discord username",
            "timestamp",
            "your discord user id",
            "should your previous form entry be deleted, because you are submitting a new one to update old information?",
            "column 8",
            "adjustednodeid"
        }
        embed = discord.Embed(title=f"Full Node Info: {node.get('Node Longname')}", color=discord.Color.blue())
        
        for key, value in node.items():
            # Clean the key for case-insensitivity and extra spaces
            cleaned_key = key.strip().lower()

            if cleaned_key not in excluded_keys:
                embed.add_field(name=key, value=value, inline=True)
        
        owner_id = node.get("Your Discord User ID")
        if owner_id:
            embed.add_field(name="Owner", value=f"<@!{owner_id}>", inline=True)
        
        await loading_message.edit(content=None, embed=embed)  # Edit loading message with the final embed



    @commands.command(name="nodefull")
    async def nodefull(self, ctx, *identifier: str):
        """Displays full details of a node by Longname or Node ID."""
        if not identifier:
            await ctx.send("Please provide a Node ID or Longname.")
            return
        
        identifier = " ".join(identifier).strip()

        # Send loading message
        loading_message = await ctx.send(self.get_random_loading_message())

        # Fetch node data
        nodes = self.find_nodes("Node ID", identifier) or self.find_nodes("Node Longname", identifier) or self.find_nodes("Node Shortname", identifier)
        
        if not nodes:
            await loading_message.edit(content=f"Node not found: `{identifier}`")
            return
        
        node = nodes[0]
        excluded_keys = {
            "your discord username",
            "timestamp",
            "your discord user id",
            "should your previous form entry be deleted, because you are submitting a new one to update old information?",
            "column 8",
            "adjustednodeid"
        }

        embed = discord.Embed(title=f"Full Node Info: {node.get('Node Longname')}", color=discord.Color.blue())

        maidenhead_key = "If a permanent install, where is this node placed?"
        grid_url_template = "https://www.levinecentral.com/ham/grid_square.php?&Grid={}&Zoom=13&sm=y"

        for key, value in node.items():
            # Clean the key for case-insensitivity and extra spaces
            cleaned_key = key.strip().lower()

            if cleaned_key not in excluded_keys:
                if cleaned_key == maidenhead_key.lower() and self.is_valid_maidenhead(value):
                    # Format the Maidenhead grid link
                    grid_url = grid_url_template.format(value)
                    value = f"[{value}]({grid_url})"  # Create a clickable link
                
                embed.add_field(name=key, value=value, inline=True)
        
        owner_id = node.get("Your Discord User ID")
        if owner_id:
            embed.add_field(name="Owner", value=f"<@!{owner_id}>", inline=True)
        
        await loading_message.edit(content=None, embed=embed)  # Edit loading message with the final embed
        


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

    
    @commands.command(name="paperwork")
    async def paperwork(self, ctx, user: discord.User = None):
        """Send the paperwork link to a user's DMs with their Discord ID prefilled."""
        loading_message = await ctx.send(self.get_random_loading_message())

        if not user:
            user = ctx.author

        encoded_username = user.name.replace(" ", "+")
        discord_user_id = user.id

        form_url = (
            "https://docs.google.com/forms/d/e/1FAIpQLSeQdIK8RXZZeXpXt1xYNik3xLlr2JwegyrL83X4RjXc_1EG1Q/viewform"
            f"?usp=pp_url&entry.2013736315={encoded_username}&entry.1056677804={discord_user_id}"
        )

        embed = discord.Embed(
            title="Paperwork Information",
            description="This URL is unique to you! It prefills some information.\n"
                        "If you want to do paperwork, please run `!paperwork` yourself.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Paperwork Form",
            value=f"[Click here to fill out the paperwork]({form_url})",
            inline=False
        )
        embed.set_footer(text="Thank you for doing your part!")

        try:
            await user.send(embed=embed)
            await loading_message.edit(content="📬 Link has been sent, check your DMs! 💌")
        except discord.Forbidden:
            await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")



    @commands.command(name="nodetotal")
    async def nodetotal(self, ctx):
        """Counts the total number of node entries and breaks them down by General Location."""
        
        # Send loading message
        loading_message = await ctx.send("Calculating total node entries...")

        # Fetch all node data
        data = self.get_sheet_data()
        if not data or len(data) < 2:
            await loading_message.edit(content="No nodes found in the database.")
            return
        
        headers = data[0]  # First row as headers
        rows = data[1:]    # Remaining rows are actual data
        total_entries = len(rows)

        # Find the index of "General Location" column
        try:
            location_index = headers.index("General Location")
        except ValueError:
            await loading_message.edit(content="Error: 'General Location' column not found in the sheet.")
            return

        # Count entries per General Location
        location_counts = {}
        for row in rows:
            location = row[location_index] if location_index < len(row) else "Unknown"
            location_counts[location] = location_counts.get(location, 0) + 1

        # Construct the response message
        embed = discord.Embed(title="Node Entry Totals", color=discord.Color.green())
        embed.add_field(name="Total Entries", value=str(total_entries), inline=False)

        for location, count in location_counts.items():
            embed.add_field(name=location, value=str(count), inline=True)
        
        await loading_message.edit(content=None, embed=embed)



# Add this cog to the bot


async def setup(bot):
    await bot.add_cog(MeshNodes(bot))
