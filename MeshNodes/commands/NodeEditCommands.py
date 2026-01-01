import os
import json
from MeshNodes.shared.ParsingTools import filter_node_ids_length, parse_csv_string
import discord

from discord.ui import Button, View, Modal, TextInput, Select
from MeshNodes.shared.AdditionalNodeInfo import (
    AdditionalInfoQuestion,
    StringQuestion,
    BooleanQuestion,
    NumberQuestion,
    ChoiceQuestion,
    additional_info_questions,
)

async def import_csv(mesh_nodes, ctx, user: discord.User = None):
    loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

    if not user:
        user = ctx.author
    
    db_path = mesh_nodes.get_db_path()
    if not os.path.exists(db_path):
        await loading_message.edit(content="Database not initialized.")
        return
    
    # Find the first CSV attachment
    attachments = ctx.message.attachments
    csv_attachment = next((a for a in attachments if a.filename.endswith('.csv')), None)
    if not csv_attachment:
        await ctx.send("No CSV file found in the message.")
        return

    # respond with the content of the CSV file
    csv_content = await csv_attachment.read()
    csv_string = csv_content.decode('utf-8')
    parsed_data = parse_csv_string(csv_string)
    filtered_data = filter_node_ids_length(parsed_data)

    # Insert or overwrite into database
    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            for entry in filtered_data:
                # Map core fields
                node_id = entry["node_id"].strip().upper()
                discord_id = entry["discord_id"].strip()
                short_name = entry["short_name"].strip()
                long_name = entry["long_name"].strip()

                # All other fields go into JSON
                extra_fields = {
                    k: v for k, v in entry.items()
                    if k not in ("node_id", "discord_id", "short_name", "long_name")
                }

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO nodes
                    (node_id, discord_id, short_name, long_name, additional_node_data_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        discord_id,
                        short_name,
                        long_name,
                        json.dumps(extra_fields),
                    ),
                )
            conn.commit()
        await loading_message.edit(
            content=f"✅ Imported {len(filtered_data)} nodes (from {len(parsed_data)} total rows)."
        )
    except Exception as e:
        await loading_message.edit(content=f"❌ Failed to import CSV: {e}")


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
        node_id = TextInput(
            label="Node ID", placeholder="Enter Node ID (e.g. 1A2B3C4D)", required=True, min_length=8, max_length=9
        )
        short_name = TextInput(
            label="Short Name", placeholder="Short name (e.g. MSP)", required=True, min_length=1, max_length=4
        )
        long_name = TextInput(
            label="Long Name", placeholder="Long descriptive name", required=True, min_length=1, max_length=64
        )

        async def on_submit(self, interaction: discord.Interaction):
            node_id_id = self.node_id.value.strip()
            #drop ! if present and 9 max
            if raw_node_id.startswith("!"):
                raw_node_id = raw_node_id[1:]
            node_id_val = raw_node_id.upper()
            # Check if node already exists
            try:
                with self_view.cog.connect_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM nodes WHERE UPPER(node_id) = ?", (node_id_val.upper(),))
                    exists = cursor.fetchone()
                    if exists:
                        await interaction.response.send_message(
                            f"❌ Node with ID `{node_id_val}` already exists in the database. Please use a different Node ID or use `!editnode` to update.",
                            ephemeral=True,
                        )
                        return
                    cursor.execute(
                        "INSERT INTO nodes (node_id, discord_id, short_name, long_name, additional_node_data_json) VALUES (?, ?, ?, ?, ?)",
                        (node_id_val, str(user.id), self.short_name.value.strip(), self.long_name.value.strip(), "{}"),
                    )
                    conn.commit()
                await interaction.response.send_message("✅ Node paperwork submitted and saved!", ephemeral=True)
                # Call edit_additional_node_info after successful registration
                await edit_additional_node_info(mesh_nodes, ctx, node_id_val, is_automatic_edit=True)
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
        await dm.send("Please click the button below to fill out the node paperwork form:", view=PaperworkButtonView())
        await loading_message.edit(content="📬 Button sent! Check your DMs and click the button to fill out the form. 💌")
    except discord.Forbidden:
        await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
    except Exception as e:
        await loading_message.edit(content=f"❌ Failed to send DM: {e}")


async def transfer_node(mesh_nodes, ctx, node_id: str, new_owner: discord.User):
    """
    Transfer ownership of a node you own to another user.
    Usage: !transfer <node_id> @username
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

    try:
        with mesh_nodes.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT discord_id FROM nodes WHERE UPPER(node_id) = ?", (node_id.upper(),))
            row = cursor.fetchone()
            if not row:
                await loading_message.edit(content=f"No node found with ID `{node_id}`.")
                return
            owner_id = row[0]
            if str(ctx.author.id) != str(owner_id):
                await loading_message.edit(content="You do not own this node.")
                return
            cursor.execute("UPDATE nodes SET discord_id = ? WHERE UPPER(node_id) = ?", (str(new_owner.id), node_id.upper()))
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
            cursor.execute("SELECT short_name, long_name, discord_id FROM nodes WHERE UPPER(node_id) = ?", (node_id.upper(),))
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
                max_length=4,
            )
            self.long_name = TextInput(
                label="Long Name (leave blank to keep unchanged)",
                placeholder=f"Current: {long_name_val}",
                required=False,
                min_length=0,
                max_length=64,
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
                        f"UPDATE nodes SET {', '.join(updates)} WHERE UPPER(node_id) = ?",
                        params[:-1] + [node_id.upper()],
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
        await dm.send(f"Click the button below to edit your node `{node_id}`:", view=EditNodeButtonView(short_name, long_name))
        await loading_message.edit(content="📬 Button sent! Check your DMs and click the button to edit your node. 💌")
    except discord.Forbidden:
        await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
    except Exception as e:
        await loading_message.edit(content=f"❌ Failed to send DM: {e}")


class QuestionView(View):
    def __init__(self, ctx, question, finish_callback):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.question = question
        self.finish_callback = finish_callback
        self.answer = None

        if isinstance(question, ChoiceQuestion):
            select = Select(
                placeholder=question.question,
                options=[discord.SelectOption(label=choice, value=choice) for choice in question.choices],
            )
            select.callback = self.on_select
            self.add_item(select)

        elif isinstance(question, BooleanQuestion):
            yes_btn = Button(label="Yes", style=discord.ButtonStyle.green)
            no_btn = Button(label="No", style=discord.ButtonStyle.red)
            yes_btn.callback = self.make_choice(True)
            no_btn.callback = self.make_choice(False)
            self.add_item(yes_btn)
            self.add_item(no_btn)

        elif isinstance(question, (StringQuestion, NumberQuestion)):
            input_btn = Button(label="Enter Answer", style=discord.ButtonStyle.blurple)
            input_btn.callback = self.open_modal
            self.add_item(input_btn)

        skip_btn = Button(label="Skip", style=discord.ButtonStyle.gray)
        skip_btn.callback = self.skip
        self.add_item(skip_btn)

    async def on_select(self, interaction: discord.Interaction):
        self.answer = interaction.data["values"][0]
        await self.finish(interaction)

    def make_choice(self, value):
        async def inner(interaction: discord.Interaction):
            self.answer = value
            await self.finish(interaction)

        return inner

    async def open_modal(self, interaction: discord.Interaction):
        class InputModal(Modal, title=self.question.human_name):
            user_input = TextInput(label=self.question.question[:45])

            async def on_submit(modal_self, interaction: discord.Interaction):
                val = modal_self.user_input.value.strip()
                if isinstance(self.question, NumberQuestion):
                    try:
                        val = int(val)
                        if not (self.question.min_value <= val <= self.question.max_value):
                            raise ValueError
                    except:
                        await interaction.response.send_message("Invalid number input.", ephemeral=True)
                        return
                elif isinstance(self.question, StringQuestion):
                    if not (self.question.min_length <= len(val) <= self.question.max_length):
                        await interaction.response.send_message("Input length out of bounds.", ephemeral=True)
                        return

                self.answer = val
                # Respond to the modal interaction so Discord doesn't error
                await interaction.response.send_message("Answer received!", ephemeral=True)
                await self.finish(interaction)

        await interaction.response.send_modal(InputModal())

    async def skip(self, interaction: discord.Interaction):
        self.answer = None
        await self.finish(interaction)

    async def finish(self, interaction: discord.Interaction):
        await interaction.message.delete()
        await self.finish_callback(self.answer)


async def edit_additional_node_info(
    mesh_nodes,
    ctx,
    node_id: str,
    questions: list[AdditionalInfoQuestion] = additional_info_questions,
    is_automatic_edit: bool = False,
):
    if is_automatic_edit:
        existing_data = {}
        print("test")
    else:
        loading_message = await ctx.send(mesh_nodes.get_random_loading_message())

        node_id = node_id.strip().upper()
        if len(node_id) != 8:
            await loading_message.edit(content="Node ID must be exactly 8 characters.")
            return

        db_path = mesh_nodes.get_db_path()
        if not os.path.exists(db_path):
            await loading_message.edit(content="Database not initialized.")
            return

        # Check ownership and get current additional_node_data_json
        try:
            with mesh_nodes.connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT short_name, long_name, discord_id, additional_node_data_json FROM nodes WHERE UPPER(node_id) = ?",
                    (node_id.upper(),),
                )
                row = cursor.fetchone()
                if not row:
                    await loading_message.edit(content=f"No node found with ID `{node_id}`.")
                    return
                short_name, long_name, owner_id, additional_node_data_json = row
                if str(ctx.author.id) != str(owner_id):
                    await loading_message.edit(content="You do not own this node.")
                    return
                try:
                    existing_data = json.loads(additional_node_data_json) if additional_node_data_json else {}
                except Exception:
                    existing_data = {}
        except Exception as e:
            await loading_message.edit(content=f"Database error: {e}")
            return

    try:
        dm = await ctx.author.create_dm()
    except Exception:
        if not is_automatic_edit:
            await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
        return

    if not is_automatic_edit:
        await loading_message.edit(content="📬 Questions sent! Check your DMs and answer the questions. 💌")

    answers = {}

    async def handle_question(index: int, is_mobile_node: bool):
        if index >= len(questions):
            # Done: merge and update DB
            result_json = {k: v for k, v in answers.items() if v is not None}
            merged_data = {**existing_data, **result_json}
            try:
                with mesh_nodes.connect_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE nodes SET additional_node_data_json = ? WHERE UPPER(node_id) = ?",
                        (json.dumps(merged_data), node_id.upper()),
                    )
                    conn.commit()
                await dm.send("✅ Additional node info updated successfully!")
            except Exception as e:
                await dm.send(f"❌ Failed to update additional node info: {e}")
            return

        q = questions[index]

        # Skip question if is_mobile_node and q.hide_if_mobile is True
        if is_mobile_node and q.hide_if_mobile:
            await handle_question(index + 1, is_mobile_node)
            return

        async def callback(answer):
            nonlocal is_mobile_node
            if answer is not None:
                answers[q.json_name] = answer
                if q.json_name == "node_type" and answer in ["Pocket", "Vehicle"]:
                    is_mobile_node = True
                if q.json_name == "node_role" and answer in ["Client_Mute"]:
                    is_mobile_node = True
            await handle_question(index + 1, is_mobile_node)

        view = QuestionView(ctx, q, callback)
        await dm.send(q.question, view=view)

    await handle_question(0, False)


class ConfirmClearView(View):
    def __init__(self, on_confirm, on_cancel, timeout=60):
        super().__init__(timeout=timeout)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.add_item(self.ConfirmButton())
        self.add_item(self.CancelButton())

    class ConfirmButton(Button):
        def __init__(self):
            super().__init__(label="Confirm", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: discord.Interaction):
            await self.view.on_confirm(interaction)

    class CancelButton(Button):
        def __init__(self):
            super().__init__(label="Cancel", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            await self.view.on_cancel(interaction)


async def clear_additional_node_info(mesh_nodes, ctx, node_id: str):
    """
    Clear the additional_node_data_json for a node you own.
    Usage: !clear_additional <node_id>
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
            cursor.execute("SELECT discord_id FROM nodes WHERE UPPER(node_id) = ?", (node_id.upper(),))
            row = cursor.fetchone()
            if not row:
                await loading_message.edit(content=f"No node found with ID `{node_id}`.")
                return
            owner_id = row[0]
            if str(ctx.author.id) != str(owner_id):
                await loading_message.edit(content="You do not own this node.")
                return
    except Exception as e:
        await loading_message.edit(content=f"Database error: {e}")
        return

    try:
        dm = await ctx.author.create_dm()
    except Exception:
        await loading_message.edit(content="❌ I couldn't DM you! Please enable DMs from server members.")
        return

    await loading_message.edit(content="📬 Confirmation sent! Check your DMs.")

    async def on_confirm(interaction):
        try:
            with mesh_nodes.connect_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE nodes SET additional_node_data_json = ? WHERE UPPER(node_id) = ?", ("{}", node_id.upper())
                )
                conn.commit()
            await interaction.response.send_message("✅ Additional node info cleared.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to clear additional node info: {e}", ephemeral=True)
        await interaction.message.delete()

    async def on_cancel(interaction):
        await interaction.response.send_message("❌ Clear cancelled.", ephemeral=True)
        await interaction.message.delete()

    view = ConfirmClearView(on_confirm, on_cancel)
    await dm.send(f"Are you sure you want to clear all additional info for node `{node_id}`?", view=view)
