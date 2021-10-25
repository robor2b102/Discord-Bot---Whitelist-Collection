import discord
import yaml
import openpyxl
from io import BytesIO
import re
from discord.ext import commands
from typing import Union
import sqlite3
conn = sqlite3.connect('database.db', timeout=5.0)
c = conn.cursor()
conn.row_factory = sqlite3.Row

c.execute('''CREATE TABLE IF NOT EXISTS whitelist (`discord_id` INT PRIMARY KEY, `email` TEXT, `eth_wallet` TEXT, `mint_amount` INT)''')


with open("config.yml", "r") as stream:
    yaml_data = yaml.safe_load(stream)

client = commands.Bot(command_prefix="/", help_command=None)

email_regex = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}')
eth_wallet_regex = re.compile(r'^(0x)?[0-9a-fA-F]{40}$')

def get_workbook() -> openpyxl.Workbook:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet["A1"] = "Discord ID"
    sheet["B1"] = "Email Address"
    sheet["C1"] = "ETH Wallet"
    sheet["D1"] = "Mint Amount"
    c.execute("SELECT * FROM whitelist")
    for i,(discord_id,email,eth_wallet,mint_amount) in enumerate(c.fetchall()):
        sheet[f"A{i + 2}"] = str(discord_id)
        sheet[f"B{i + 2}"] = email
        sheet[f"C{i + 2}"] = eth_wallet
        sheet[f"D{i + 2}"] = str(mint_amount)
    return workbook


def is_valid_email(email: str) -> bool:
    return re.match(email_regex,email) is not None

def is_valid_wallet(wallet: str) -> bool:
    return re.match(eth_wallet_regex,wallet) is not None

async def send_message(ctx: Union[discord.TextChannel,discord.User,discord.Member,commands.Context], data: Union[str,dict], file: openpyxl.Workbook = None, file_name: str = "data.xlsx",**vars_for_data) -> discord.Message:
    try:
        newdata = data.copy()
    except AttributeError:
        newdata = str(data)
    if file:
        with BytesIO() as f:
            file.save(f)
            f.seek(0)
            file = discord.File(fp=f, filename=file_name)
    if isinstance(newdata,str):
        return await ctx.send(newdata.format(**vars_for_data),file=file)
    else:
        if "description" in newdata.keys():
            newdata["description"] = newdata["description"].format(**vars_for_data)
        if "title" in newdata.keys():
            newdata["title"] = newdata["title"].format(**vars_for_data)
        embed = discord.Embed(**newdata)
        if "fields" in newdata.keys():
            for field in newdata["fields"]:
                embed.add_field(**field)
        return await ctx.send(embed=embed,file=file)

async def get_email(ctx:commands.Context) -> str:
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    await send_message(ctx,yaml_data["messages"]["email"])
    while True:
        message = await client.wait_for('message',check=check)
        if is_valid_email(message.content):
            return message.content
        await send_message(ctx, yaml_data["messages"]["invalid_email"])

async def get_wallet(ctx:commands.Context) -> str:
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    await send_message(ctx,yaml_data["messages"]["wallet"])
    while True:
        message = await client.wait_for('message',check=check)
        if is_valid_wallet(message.content):
            return message.content
        await send_message(ctx, yaml_data["messages"]["invalid_wallet"])

async def get_mint_amount(ctx:commands.Context) -> int:
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    await send_message(ctx, yaml_data["messages"]["mint_amount"])
    while True:
        message = await client.wait_for('message',check=check)
        if message.content.isnumeric() and int(message.content) in yaml_data["possible_mint_amounts"]:
            return int(message.content)
        await send_message(ctx, yaml_data["messages"]["invalid_mint_amount"])

async def get_data(ctx: commands.Context) -> tuple[str,str,int]:
    wallet = await get_wallet(ctx)
    email = await get_email(ctx)
    mint_amount = await get_mint_amount(ctx)
    return wallet,email,mint_amount

async def data_confirmed(ctx: commands.Context) -> bool:
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in [yaml_data["confirm_text"],yaml_data["deny_text"]]
    await send_message(ctx,yaml_data["messages"]["confirm_or_deny"])
    message = await client.wait_for('message',check=check)
    if message.content == yaml_data["confirm_text"]:
        return True
    return False

@client.command()
async def whitelist(ctx):
    confirmed = False
    while not confirmed:
        wallet,email,mint_amount = await get_data(ctx)
        await send_message(ctx,yaml_data["messages"]["check_data"],user=ctx.author,email=email,wallet=wallet,mint_amount=mint_amount)
        confirmed = await data_confirmed(ctx)
    c.execute("REPLACE INTO whitelist VALUES (?,?,?,?)",(ctx.author.id,email,wallet,mint_amount))
    await send_message(ctx,yaml_data["messages"]["data_submitted"],user=ctx.author)
    conn.commit()

@client.command()
@commands.has_permissions(administrator=True)
async def viewdata(ctx):
    await send_message(ctx,yaml_data["messages"]["data"],file=get_workbook())

@client.event
async def on_ready():
    print("Bot Started!")


client.run(yaml_data["Token"])
