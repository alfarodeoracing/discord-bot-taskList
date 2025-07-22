import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
import os

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# File to store task lists
TASKS_FILE = 'tasks.json'

def load_tasks():
    """Load tasks from JSON file"""
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    """Save tasks to JSON file"""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

class EditTaskListModal(Modal):
    def __init__(self, guild_id, old_name):
        super().__init__(title="Edit Task List")
        self.guild_id = str(guild_id)
        self.old_name = old_name
        
        tasks = load_tasks()
        current_data = tasks[self.guild_id][old_name]
        
        self.name_input = TextInput(
            label="Task List Name",
            placeholder="Enter new task list name",
            default=current_data['name'],
            max_length=100,
            required=True
        )
        self.description_input = TextInput(
            label="Description (Optional)",
            placeholder="Enter new description",
            default=current_data.get('description', ''),
            max_length=500,
            required=False,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.name_input)
        self.add_item(self.description_input)
    
    async def on_submit(self, interaction):
        tasks = load_tasks()
        new_name = self.name_input.value.strip()
        new_description = self.description_input.value.strip()
        
        # Check if new name already exists (and it's different from the old name)
        if new_name != self.old_name and new_name in tasks[self.guild_id]:
            await interaction.response.send_message(
                f"A task list named '{new_name}' already exists!", 
                ephemeral=True
            )
            return
        
        # Update the task list
        task_list_data = tasks[self.guild_id][self.old_name]
        task_list_data['name'] = new_name
        task_list_data['description'] = new_description
        
        # If name changed, move to new key and delete old
        if new_name != self.old_name:
            tasks[self.guild_id][new_name] = task_list_data
            del tasks[self.guild_id][self.old_name]
        
        save_tasks(tasks)
        
        await interaction.response.send_message(
            f"Task list updated successfully!\n"
            f"**Name**: {new_name}\n"
            f"**Description**: {new_description or 'None'}", 
            ephemeral=True
        )

class EditTaskModal(Modal):
    def __init__(self, guild_id, list_name, task_index):
        super().__init__(title="Edit Task")
        self.guild_id = str(guild_id)
        self.list_name = list_name
        self.task_index = task_index
        
        tasks = load_tasks()
        current_task = tasks[self.guild_id][list_name]['tasks'][task_index]
        
        self.task_input = TextInput(
            label="Task Name",
            placeholder="Enter new task name",
            default=current_task['name'],
            max_length=200,
            required=True
        )
        
        self.add_item(self.task_input)
    
    async def on_submit(self, interaction):
        tasks = load_tasks()
        new_task_name = self.task_input.value.strip()
        
        if not new_task_name:
            await interaction.response.send_message(
                "Task name cannot be empty!", 
                ephemeral=True
            )
            return
        
        # Update the task name
        old_name = tasks[self.guild_id][self.list_name]['tasks'][self.task_index]['name']
        tasks[self.guild_id][self.list_name]['tasks'][self.task_index]['name'] = new_task_name
        
        save_tasks(tasks)
        
        await interaction.response.send_message(
            f"Task updated successfully!\n"
            f"**Old**: {old_name}\n"
            f"**New**: {new_task_name}", 
            ephemeral=True
        )

class TaskView(View):
    def __init__(self, list_name, guild_id):
        super().__init__(timeout=None)
        self.list_name = list_name
        self.guild_id = str(guild_id)
        self.update_buttons()
    
    def update_buttons(self):
        """Update the buttons based on current task states"""
        self.clear_items()
        tasks = load_tasks()
        
        if self.guild_id not in tasks or self.list_name not in tasks[self.guild_id]:
            return
        
        task_list = tasks[self.guild_id][self.list_name]
        
        for i, task in enumerate(task_list['tasks']):
            # Create button with checkmark or empty checkbox
            if task['completed']:
                button = Button(
                    label=f"✅ {task['name']}", 
                    style=discord.ButtonStyle.success,
                    custom_id=f"task_{self.list_name}_{i}",
                    row=min(i // 5, 3)  # Max 4 rows, 5 buttons per row
                )
            else:
                button = Button(
                    label=f"☐ {task['name']}", 
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"task_{self.list_name}_{i}",
                    row=min(i // 5, 3)
                )
            
            button.callback = self.create_callback(i)
            self.add_item(button)
        
        # Add edit buttons in the last row
        if len(task_list['tasks']) < 20:  # Only show edit buttons if we have room
            edit_list_button = Button(
                label="✏️ Edit List",
                style=discord.ButtonStyle.primary,
                custom_id=f"edit_list_{self.list_name}",
                row=4
            )
            edit_list_button.callback = self.edit_list_callback
            self.add_item(edit_list_button)
    
    def create_callback(self, task_index):
        """Create a callback function for a specific task button"""
        async def callback(interaction):
            await self.toggle_task(interaction, task_index)
        return callback
    
    async def edit_list_callback(self, interaction):
        """Show modal to edit the task list"""
        tasks = load_tasks()
        
        # Check if user is the creator or has admin permissions
        if (self.guild_id in tasks and 
            self.list_name in tasks[self.guild_id]):
            task_list = tasks[self.guild_id][self.list_name]
            if (str(interaction.user.id) != task_list['created_by'] and 
                not interaction.user.guild_permissions.manage_messages):
                await interaction.response.send_message(
                    "You can only edit task lists you created!", 
                    ephemeral=True
                )
                return
        
        modal = EditTaskListModal(interaction.guild.id, self.list_name)
        await interaction.response.send_modal(modal)
    
    async def toggle_task(self, interaction, task_index):
        """Toggle task completion status"""
        tasks = load_tasks()
        
        if (self.guild_id not in tasks or 
            self.list_name not in tasks[self.guild_id] or 
            task_index >= len(tasks[self.guild_id][self.list_name]['tasks'])):
            await interaction.response.send_message("Task not found!", ephemeral=True)
            return
        
        task = tasks[self.guild_id][self.list_name]['tasks'][task_index]
        task['completed'] = not task['completed']
        
        # Record who completed the task
        if task['completed']:
            task['completed_by'] = str(interaction.user.id)
            status_msg = f"marked as complete by {interaction.user.mention}"
        else:
            task['completed_by'] = None
            status_msg = f"marked as incomplete by {interaction.user.mention}"
        
        save_tasks(tasks)
        
        # Update the view with new button states
        self.update_buttons()
        
        # Create updated embed
        embed = self.create_task_embed(tasks[self.guild_id][self.list_name])
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Send a brief status message
        await interaction.followup.send(
            f"Task '{task['name']}' {status_msg}", 
            ephemeral=True
        )
    
    def create_task_embed(self, task_list):
        """Create an embed displaying the task list"""
        embed = discord.Embed(
            title=f"📋 {task_list['name']}", 
            description=task_list.get('description', 'No description'),
            color=discord.Color.blue()
        )
        
        completed_count = sum(1 for task in task_list['tasks'] if task['completed'])
        total_count = len(task_list['tasks'])
        
        embed.add_field(
            name="Progress", 
            value=f"{completed_count}/{total_count} tasks completed", 
            inline=False
        )
        
        if task_list['tasks']:
            task_status = []
            for task in task_list['tasks']:
                if task['completed']:
                    completed_by = task.get('completed_by')
                    if completed_by:
                        user_mention = f"<@{completed_by}>"
                        task_status.append(f"✅ ~~{task['name']}~~ (by {user_mention})")
                    else:
                        task_status.append(f"✅ ~~{task['name']}~~")
                else:
                    task_status.append(f"☐ {task['name']}")
            
            embed.add_field(
                name="Tasks", 
                value="\n".join(task_status), 
                inline=False
            )
        
        embed.set_footer(text="Click buttons to toggle tasks • Click '✏️ Edit List' to edit the list")
        return embed

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Add persistent views for existing task lists
    tasks = load_tasks()
    for guild_id, guild_tasks in tasks.items():
        for list_name in guild_tasks:
            view = TaskView(list_name, int(guild_id))
            bot.add_view(view)

@bot.command(name='create_tasklist')
async def create_task_list(ctx, list_name, *, description=""):
    """Create a new task list
    Usage: !create_tasklist "Project Alpha" This is our main project tasks
    """
    if not list_name:
        await ctx.send("Please provide a name for the task list!")
        return
    
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if guild_id not in tasks:
        tasks[guild_id] = {}
    
    if list_name in tasks[guild_id]:
        await ctx.send(f"Task list '{list_name}' already exists!")
        return
    
    tasks[guild_id][list_name] = {
        'name': list_name,
        'description': description,
        'created_by': str(ctx.author.id),
        'tasks': []
    }
    
    save_tasks(tasks)
    
    embed = discord.Embed(
        title=f"📋 {list_name}",
        description=description or "No description",
        color=discord.Color.green()
    )
    embed.add_field(name="Progress", value="0/0 tasks completed", inline=False)
    embed.add_field(name="Tasks", value="No tasks yet. Use `!add_task` to add some!", inline=False)
    embed.set_footer(text="Task list created successfully!")
    
    view = TaskView(list_name, ctx.guild.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name='add_task')
async def add_task(ctx, list_name, *, task_name):
    """Add a task to an existing task list
    Usage: !add_task "Project Alpha" Complete the documentation
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found! Create it first with `!create_tasklist`")
        return
    
    task = {
        'name': task_name,
        'completed': False,
        'completed_by': None,
        'added_by': str(ctx.author.id)
    }
    
    tasks[guild_id][list_name]['tasks'].append(task)
    save_tasks(tasks)
    
    await ctx.send(f"Added task '{task_name}' to '{list_name}'!")

@bot.command(name='edit_task')
async def edit_task(ctx, list_name, task_number: int):
    """Edit a specific task name
    Usage: !edit_task "Project Alpha" 1
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found!")
        return
    
    task_list = tasks[guild_id][list_name]['tasks']
    
    if task_number < 1 or task_number > len(task_list):
        await ctx.send(f"Invalid task number! Use a number between 1 and {len(task_list)}")
        return
    
    task_index = task_number - 1
    modal = EditTaskModal(ctx.guild.id, list_name, task_index)
    
    # Since this is a text command, we need to create a temporary view with a button
    # that triggers the modal
    class EditTaskView(View):
        def __init__(self):
            super().__init__(timeout=60)
        
        @discord.ui.button(label="✏️ Edit Task", style=discord.ButtonStyle.primary)
        async def edit_button(self, interaction, button):
            await interaction.response.send_modal(modal)
    
    view = EditTaskView()
    current_task = task_list[task_index]
    await ctx.send(
        f"Click the button below to edit task: **{current_task['name']}**",
        view=view
    )

@bot.command(name='edit_tasklist')
async def edit_task_list_command(ctx, list_name):
    """Edit a task list name and description
    Usage: !edit_tasklist "Project Alpha"
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found!")
        return
    
    # Check if user is the creator or has admin permissions
    task_list = tasks[guild_id][list_name]
    if (str(ctx.author.id) != task_list['created_by'] and 
        not ctx.author.guild_permissions.manage_messages):
        await ctx.send("You can only edit task lists you created!")
        return
    
    modal = EditTaskListModal(ctx.guild.id, list_name)
    
    # Create a temporary view with a button that triggers the modal
    class EditListView(View):
        def __init__(self):
            super().__init__(timeout=60)
        
        @discord.ui.button(label="✏️ Edit Task List", style=discord.ButtonStyle.primary)
        async def edit_button(self, interaction, button):
            await interaction.response.send_modal(modal)
    
    view = EditListView()
    await ctx.send(
        f"Click the button below to edit task list: **{list_name}**",
        view=view
    )

@bot.command(name='show_tasklist')
async def show_task_list(ctx, list_name):
    """Display a task list with interactive buttons
    Usage: !show_tasklist "Project Alpha"
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found!")
        return
    
    task_list = tasks[guild_id][list_name]
    view = TaskView(list_name, ctx.guild.id)
    embed = view.create_task_embed(task_list)
    
    await ctx.send(embed=embed, view=view)

@bot.command(name='list_tasklists')
async def list_task_lists(ctx):
    """Show all task lists in this server"""
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if guild_id not in tasks or not tasks[guild_id]:
        await ctx.send("No task lists found in this server!")
        return
    
    embed = discord.Embed(
        title="📋 Task Lists in this Server",
        color=discord.Color.blue()
    )
    
    for list_name, task_list in tasks[guild_id].items():
        completed = sum(1 for task in task_list['tasks'] if task['completed'])
        total = len(task_list['tasks'])
        
        embed.add_field(
            name=list_name,
            value=f"Progress: {completed}/{total}\n{task_list.get('description', 'No description')}",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='remove_task')
async def remove_task(ctx, list_name, task_index: int):
    """Remove a task from a task list
    Usage: !remove_task "Project Alpha" 1
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found!")
        return
    
    task_list = tasks[guild_id][list_name]['tasks']
    
    if task_index < 1 or task_index > len(task_list):
        await ctx.send(f"Invalid task number! Use a number between 1 and {len(task_list)}")
        return
    
    removed_task = task_list.pop(task_index - 1)
    save_tasks(tasks)
    
    await ctx.send(f"Removed task '{removed_task['name']}' from '{list_name}'!")

@bot.command(name='delete_tasklist')
async def delete_task_list(ctx, list_name):
    """Delete an entire task list (creator only)
    Usage: !delete_tasklist "Project Alpha"
    """
    tasks = load_tasks()
    guild_id = str(ctx.guild.id)
    
    if (guild_id not in tasks or list_name not in tasks[guild_id]):
        await ctx.send(f"Task list '{list_name}' not found!")
        return
    
    # Check if user is the creator or has admin permissions
    task_list = tasks[guild_id][list_name]
    if (str(ctx.author.id) != task_list['created_by'] and 
        not ctx.author.guild_permissions.manage_messages):
        await ctx.send("You can only delete task lists you created!")
        return
    
    del tasks[guild_id][list_name]
    save_tasks(tasks)
    
    await ctx.send(f"Deleted task list '{list_name}'!")

# Run the bot
from threading import Thread
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# Add this before bot.run()
keep_alive()
bot.run(os.getenv('DISCORD_TOKEN'))
