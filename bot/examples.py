# @bot.tree.command(name="test1")
# @app_commands.describe(c_status='Enable/Disable Command')
# async def joined(interaction: discord.Interaction, c_status: SettingSwitcher, b: bool = None):
"""Says when a member joined."""
# If no member is explicitly provided then we use the command user here
# The format_dt function formats the date time into a human readable representation in the official client
# await interaction.response.send_message(f'You chose option: {c_status}. {b} Are you happy now? ')

# A Context Menu command is an app command that can be run on a member or on a message by
# accessing a menu within the client, usually via right clicking.
# It always takes an interaction as its first parameter and a Member or Message as its second parameter.

# This context menu command only works on members
# @bot.tree.context_menu(name='Show Join Date')
# async def show_join_date(interaction: discord.Interaction, member: discord.Member):
#     # The format_dt function formats the date time into a human readable representation in the official client
#     await interaction.response.send_message(f'{member} joined at {discord.utils.format_dt(member.joined_at)}')
