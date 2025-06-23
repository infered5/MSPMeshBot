import discord
from discord.ui import Button, View, Modal, TextInput
import os


async def register_node(mesh_nodes, ctx, user: discord.User = None):
    """Send a Discord Modal to a user's DMs to fill out node info (node_id, short_name, long_name)."""
    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

    if not user:
        user = ctx.author

    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    # Modal definition
    class NodePaperworkModal(Modal, title="Node Paperwork Submission"):
        node_id = TextInput(label="Node ID", placeholder="Enter Node ID (e.g. 1A2B3C4D)", required=True, min_length=8, max_length=8)
        short_name = TextInput(label="Short Name", placeholder="Short name (e.g. MSP)", required=True, min_length=1, max_length=4)
        long_name = TextInput(label="Long Name", placeholder="Long descriptive name", required=True, min_length=1, max_length=64)

        async def on_submit(self, interaction: discord.Interaction):
            node_id_val = self.node_id.value.strip().upper()
            # Check if node already exists
            try:
                with self_view.cog.connect_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT 1 FROM nodes WHERE node_id = ?",
                        (node_id_val,)
                    )
                    exists = cursor.fetchone()
                    if exists:
                        await interaction.response.send_message(
                            f"❌ Node with ID `{node_id_val}` already exists in the database. Please use a different Node ID or use `!editnode` to update.",
                            ephemeral=True
                        )
                        return
                    cursor.execute(
                        "INSERT INTO nodes (node_id, discord_id, short_name, long_name, additional_node_data_json) VALUES (?, ?, ?, ?, ?)",
                        (
                            node_id_val,
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
    self_view.cog = mesh_nodes

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


async def transfer_node(self, ctx, node_id: str, new_owner: discord.User):
    """
    Transfer ownership of a node you own to another user.
    Usage: !transfer <node_id> @username
    """
    loading_message = await ctx.send(self.get_random_loading_message())

    node_id = node_id.strip().upper()
    if len(node_id) != 8:
        await loading_message.edit(content="Node ID must be exactly 8 characters.")
        return

    db_path = self.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    try:
        with self.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT discord_id FROM nodes WHERE node_id = ?",
                (node_id,)
            )
            row = cursor.fetchone()
            if not row:
                await loading_message.edit(content=f"No node found with ID `{node_id}`.")
                return
            owner_id = row[0]
            if str(ctx.author.id) != str(owner_id):
                await loading_message.edit(content="You do not own this node.")
                return
            cursor.execute(
                "UPDATE nodes SET discord_id = ? WHERE node_id = ?",
                (str(new_owner.id), node_id)
            )
            conn.commit()
        await loading_message.edit(content=f"✅ Node `{node_id}` ownership transferred to {new_owner.mention}.")
    except Exception as e:
        await loading_message.edit(content=f"❌ Failed to transfer node: {e}")

async def edit_node(mesh_nodes, ctx, node_id: str):
    """
    Edit the short and/or long name of a node you own by Node ID (must be exactly 8 characters).
    """
    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

    node_id = node_id.strip().upper()
    if len(node_id) != 8:
        await loading_message.edit(content="Node ID must be exactly 8 characters.")
        return

    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return

    # Check ownership
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT short_name, long_name, discord_id FROM nodes WHERE node_id = ?",
                (node_id,)
            )
            row = cursor.fetchone()
            if not row:
                await loading_message.edit(content=f"No node found with ID `{node_id}`.")
                return
            short_name, long_name, owner_id = row
            if str(ctx.author.id) != str(owner_id):
                await loading_message.edit(content="You do not own this node.")
                return
    except Exception as e:
        await loading_message.edit(content=f"Database error: {e}")
        return

    # Modal definition
    class EditNodeModal(Modal):
        def __init__(self, short_name_val, long_name_val):
            super().__init__(title=f"Edit Node {node_id}")
            self.short_name = TextInput(
                label="Short Name (leave blank to keep unchanged)",
                placeholder=f"Current: {short_name_val}",
                required=False,
                min_length=0,
                max_length=4
            )
            self.long_name = TextInput(
                label="Long Name (leave blank to keep unchanged)",
                placeholder=f"Current: {long_name_val}",
                required=False,
                min_length=0,
                max_length=64
            )
            self.add_item(self.short_name)
            self.add_item(self.long_name)

        async def on_submit(self, interaction: discord.Interaction):
            updates = []
            params = []
            if self.short_name.value.strip():
                updates.append("short_name = ?")
                params.append(self.short_name.value.strip())
            if self.long_name.value.strip():
                updates.append("long_name = ?")
                params.append(self.long_name.value.strip())
            if not updates:
                await interaction.response.send_message("No changes provided. Node not updated.", ephemeral=True)
                return
            params.append(node_id)
            try:
                with self_view.cog.connect_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"UPDATE nodes SET {', '.join(updates)} WHERE node_id = ?",
                        params
                    )
                    conn.commit()
                await interaction.response.send_message("✅ Node updated successfully!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to update node: {e}", ephemeral=True)

    # Hack to pass self into the modal for DB access
    self_view = type("SelfView", (), {})()
    self_view.cog = mesh_nodes

    # View with a button to trigger the modal
    class EditNodeButtonView(View):
        def __init__(self, short_name_val, long_name_val, timeout=180):
            super().__init__(timeout=timeout)
            self.add_item(self.EditNodeButton(short_name_val, long_name_val))

        class EditNodeButton(Button):
            def __init__(self, short_name_val, long_name_val):
                super().__init__(label="Edit Node Info", style=discord.ButtonStyle.primary)
                self.short_name_val = short_name_val
                self.long_name_val = long_name_val

            async def callback(self, interaction: discord.Interaction):
                modal = EditNodeModal(self.short_name_val, self.long_name_val)
                await interaction.response.send_modal(modal)

    try:
        dm = await ctx.author.create_dm()
        await dm.send(
            f"Click the button below to edit your node `{node_id}`:",
            view=EditNodeButtonView(short_name, long_name)
        )
        await loading_message.edit(content="📬 Button sent! Check your DMs and click the button to edit your node. 💌")
    except discord.Forbidden:
        await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
    except Exception as e:
        await loading_message.edit(content=f"❌ Failed to send DM: {e}")
