import os
import discord
from discord.ui import Button, View
from MeshNodes.shared.ParsingTools import filter_node_ids_length, parse_csv_string


async def double_confirm(ctx, step1_text, step2_text, cancel_text):
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


async def create_database(mesh_nodes, ctx):
    if ctx.author.id not in mesh_nodes.database_admin_ids:
        await ctx.send("You do not have permission to perform this action.")
        return

    msg = await double_confirm(
        ctx, "This will create the database. Please confirm.", "Final confirmation required.", "Database creation cancelled."
    )
    if not msg:
        return

    db_path = mesh_nodes.get_db_path()
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    discord_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    short_name TEXT NOT NULL,
                    long_name TEXT NOT NULL,
                    additional_node_data_json TEXT NOT NULL
                )
            """
            )
            conn.commit()
        await msg.edit(content=f"Database created at `{db_path}`.", view=None)
    except Exception as e:
        await msg.edit(content=f"Failed to create database: {e}", view=None)


async def drop_database(mesh_nodes, ctx):
    if ctx.author.id not in mesh_nodes.database_admin_ids:
        await ctx.send("You do not have permission to perform this action.")
        return

    msg = await double_confirm(
        ctx, "This will drop the database. Please confirm.", "Final confirmation required.", "Database drop cancelled."
    )
    if not msg:
        return

    db_path = mesh_nodes.get_db_path()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            await msg.edit(content=f"Database at `{db_path}` has been dropped.", view=None)
        else:
            await msg.edit(content="Database file does not exist.", view=None)
    except Exception as e:
        await msg.edit(content=f"Failed to drop database: {e}", view=None)


async def delete_node(mesh_nodes, ctx, node_id: str):
    await ctx.send(node_id)
    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT discord_id FROM nodes WHERE LOWER(node_id) = LOWER(?)", (node_id,))
            row = cursor.fetchone()
            if not row:
                await loading_message.edit(content="No node found with node_id `{node_id}`.")
                return

            owner_id = row[0]
            # Allow if user is owner OR an admin
            if str(ctx.author.id) != str(owner_id) or ctx.author.id not in mesh_nodes.database_admin_ids:
                await loading_message.edit(content="You do not have permission to perform this action.")
                return

            cursor.execute("DELETE FROM nodes WHERE LOWER(node_id) = LOWER(?)", (node_id,))
            conn.commit()
            await loading_message.edit(content="Node with node_id `{node_id}` has been deleted from the database.")
    except Exception as e:
        await loading_message.edit(content="Failed to delete node: {e}")



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
