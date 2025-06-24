import discord
import os
import re
import json
from discord.ui import View, Button
from MeshNodes.shared.AdditionalNodeInfo import additional_info_questions

async def total_nodes(self, ctx):
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

async def list_my_nodes(mesh_nodes, ctx, user: discord.User = None):
    """Retrieve a list of nodes owned by a user."""

    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

    if not user:
        # Default to the author if no user is mentioned
        user = ctx.author

    user_id = str(user.id)
    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized")
        return

    nodes = []
    try:
        with mesh_nodes.connect_db() as conn:
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

def is_valid_maidenhead(self, locator: str) -> bool:
    """Checks if a string matches the Maidenhead Locator (Grid Square) format."""
    pattern = r"^[A-R]{2}[0-9]{2}([A-X]{2}([0-9]{2})?)?$"
    return bool(re.fullmatch(pattern, locator.strip().upper()))

def _get_node_details_embed(mesh_nodes, node_row):
    """
    Helper to build a Discord embed for full node info from a database row.
    Shows basic info and any additional info fields present in the node's JSON.
    """
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
        for q in additional_info_questions:
            key = q.json_name
            if key in extra:
                value = extra[key]
                # Show grid link if this is the maidenhead field and valid
                if key.strip().lower() == maidenhead_key.lower() and mesh_nodes.is_valid_maidenhead(str(value)):
                    grid_url = grid_url_template.format(value)
                    value = f"[{value}]({grid_url})"
                embed.add_field(name=q.human_name, value=str(value), inline=True)
    except Exception as e:
        embed.add_field(name="Error", value=f"Failed to parse extra data: {e}", inline=False)
    return embed

async def run_nodefull_on_interaction(mesh_nodes, interaction: discord.Interaction, identifier: str):
    """Runs the nodefull command on behalf of the user who clicked the button, using the new database."""
    loading_message = await interaction.channel.send(mesh_nodes.get_random_loading_message())
    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    node_row = None
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            # Try by node_id (exact or partial from end)
            cursor.execute(
                "SELECT * FROM nodes WHERE UPPER(node_id) = ? OR UPPER(substr(node_id, -?)) = ?",
                (identifier.upper(), len(identifier), identifier.upper())
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

    embed = _get_node_details_embed(mesh_nodes, node_row)
    await loading_message.edit(content=None, embed=embed)


async def node_info(mesh_nodes, ctx, *identifier: str):
    """Find the owner of a node by Longname, Shortname, or Node ID (supports partial Node ID from the end)."""
    if not identifier:
        await ctx.send("Please provide a Node ID, Longname, or Shortname.")
        return

    identifier = " ".join(identifier).strip()

    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    matches = []
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            # Node ID: match from the end (last N chars)
            if len(identifier) <= 8:
                cursor.execute(
                    "SELECT node_id, short_name, long_name, discord_id FROM nodes WHERE UPPER(substr(node_id, -?)) = ?",
                    (len(identifier), identifier.upper())
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
                await run_nodefull_on_interaction(mesh_nodes, interaction, node_id)
            return button_callback
        button.callback = await make_callback()
        view.add_item(button)

    await loading_message.edit(content=None, embed=embed, view=view)



async def full_node_info(mesh_nodes, ctx, *identifier: str):
    """Displays full details of a node by Longname or Node ID using the new database."""
    if not identifier:
        await ctx.send("Please provide a Node ID or Longname.")
        return

    identifier = " ".join(identifier).strip()
    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())
    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    node_row = None
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            # Try by node_id (exact or partial from end)
            cursor.execute(
                "SELECT * FROM nodes WHERE UPPER(node_id) = ? OR UPPER(substr(node_id, -?)) = ?",
                (identifier.upper(), len(identifier), identifier.upper())
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

    embed = _get_node_details_embed(mesh_nodes, node_row)
    await loading_message.edit(content=None, embed=embed)