import discord
from discord.ext import commands
from discord.ui import View, Button
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
                    custom_id=f"task_{self.list_name}_{i}"
                )
            else:
                button = Button(
                    label=f"☐ {task['name']}", 
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"task_{self.list_name}_{i}"
                )
            
            button.callback = self.create_callback(i)
            self.add_item(button)
    
    def create_callback(self, task_index):
        """Create a callback function for a specific task button"""
        async def callback(interaction):
            await self.toggle_task(interaction, task_index)
        return callback
    
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
        
        embed.set_footer(text="Click the buttons below to toggle task completion")
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
    
    # Update the task list message if possible
    view = TaskView(list_name, ctx.guild.id)
    embed = view.create_task_embed(tasks[guild_id][list_name])
    
    await ctx.send(f"Added task '{task_name}' to '{list_name}'!")

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
from dotenv import load_dotenv
load_dotenv()
bot.run(os.getenv('DISCORD_TOKEN'))
