# filepath: kivy-discord-bot/src/views/kivy_prompt_view.py
from discord import ui, Interaction
import logging

class KivyPromptView(ui.View):
    def __init__(self, source_message_id: int):
        super().__init__(timeout=180)
        self.source_message_id = source_message_id
        self.message = None  # Store reference to the message

    async def on_timeout(self):
        """Called when the view times out"""
        if self.message:
            try:
                # Clear all buttons when timeout occurs
                await self.message.edit(view=self.clear_items())
            except discord.HTTPException:
                pass  # Message might be deleted already

    @ui.button(label="Yes, render", style=discord.ButtonStyle.success)
    async def yes_render(
        self, interaction: Interaction, button: ui.Button
    ):
        logging.info(f"🎯 Render button clicked by {interaction.user.name} for message {self.source_message_id}")
        
        # Disable all buttons during processing
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        
        data = PENDING_SNIPPETS.get(self.source_message_id)
        if not data:
            logging.warning(f"❌ No snippet data found for message {self.source_message_id}")
            await interaction.followup.send(
                "I couldn't find the original snippet (maybe I restarted). Try again.", 
                ephemeral=True
            )
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)
            return

        code = data["code"]
        logging.info(f"📝 Retrieved code snippet: {len(code)} chars")
        
        # Validate code for security
        if not validate_code(code):
            logging.warning("🚨 Code validation failed - contains dangerous operations")
            await interaction.followup.send(
                "❌ This code contains potentially dangerous operations and cannot be rendered.",
                ephemeral=True
            )
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)
            return

        try:
            run_dir = ensure_clean_run_dir(self.source_message_id)
            await placeholder_render_call(interaction, code, run_dir)
            
            # Change button label after successful render
            button.label = "Render again"
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        finally:
            # Re-enable buttons
            for child in self.children:
                child.disabled = False
            await interaction.edit_original_response(view=self)

    @ui.button(label="Change settings", style=discord.ButtonStyle.secondary)
    async def change_settings(
        self, interaction: Interaction, button: ui.Button
    ):
        await interaction.response.send_message(
            "⚙️ Settings are coming soon. This will allow you to configure Kivy rendering options.", 
            ephemeral=True
        )

    @ui.button(label="Go away", style=discord.ButtonStyle.danger)
    async def go_away(self, interaction: Interaction, button: ui.Button):
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except discord.Forbidden:
            await interaction.followup.send(
                "I couldn't delete my message (missing permission).", ephemeral=True
            )
        except discord.HTTPException:
            pass