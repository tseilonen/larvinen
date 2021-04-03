import discord
import os
import matplotlib.pyplot as plt
import datetime
import numpy as np
import sys
import signal
import asyncio
from dateutil import tz
from google.cloud import firestore
from scipy import interpolate

from alko import Alko, DRINK_QUERY_PARAMS
from user import User
from info_messages import *
from util import *
from plotting import create_plot, PLOT_PATH

client = discord.Client()
db = firestore.Client()

development = False

default_plot_hours = 24.0
async_wait_seconds = 1
alko = None

doses = {}
users = {}

basic_drinks = {'%olut': [4.7, 33],
                '%aolut': [5.5, 33],
                '%viini': [15.0, 16],
                '%viina': [40.0, 4],
                '%siideri': [4.8, 33]}

special_drinks = {'%juoma': [None, None],
                  '%sama': [None, None]}


@client.event
async def on_ready():
    print(f'Logattu sisään {client.user}')
    await message_channels('Olen kuulolla')


@client.event
async def on_message(message):
    # Return immediately if message is from self
    if message.author == client.user:
        return

    capital_params = parse_params(message.content)
    message.content = message.content.lower()
    msg = message.content

    # Get user object
    user = User(db, message.author.id)
    params = parse_params(msg)

    if msg.startswith('%alkoholin_vaikutukset'):
        await message.channel.send(alco_info_message())

    elif msg.startswith('%help'):
        await send_help(message)

    elif msg.startswith('%menu'):
        drink_list, _ = generate_drink_list(db)
        await message.channel.send(f'{drink_list}')

    elif msg.startswith('%tiedot'):
        await user_info_handling(message, user, params)

    elif msg.startswith('%kuvaaja'):
        await send_plot(message, user, params, capital_params)

    elif msg.startswith('%humala'):
        if user != None:
            await send_per_milles(message, user)
        else:
            await message.channel.send('Et ole aiemmin käyttänyt palvelujani. Et voi tiedustella humalatilaasi.')

    elif msg.startswith('%suosittele'):
        await send_recommendation(message)

    elif msg.startswith('%peruuta'):
        await cancel_dose(message, user)

    elif msg.startswith('%annokset'):
        await send_doses(message, user, params)

    else:
        drink_ref = db.collection('basic_drinks').document(
            params[0]).get().to_dict()

        if drink_ref != None or sum([msg.startswith(drink) for drink in list(special_drinks.keys())]) == 1:
            success = user.add_dose(db, message, params)

            if not success:
                await message.author.send('Juoman lisääminen epäonnistui')
            else:
                if not isinstance(message.channel, discord.channel.DMChannel):
                    await message.delete()
            await asyncio.sleep(async_wait_seconds)
            await send_per_milles(message, user)


async def send_doses(message, user, params):
    """A function that sends a list of doses one has enjoyed to user requesting them

    Args:
        message (discord.message): The message that triggered the event
        params (list): A list of lower cased params

    """

    now = datetime.datetime.now()
    date = datetime.datetime.fromisoformat(
        params[1]) if params[1] != None else datetime.datetime.fromtimestamp(now.timestamp()-7*24*60*60)
    since = (now.timestamp()-date.timestamp())
    doses = user.get_doses(db, since)
    len_str = len(str(doses))
    no_messages = int(len_str/2000.0+1)

    keys_per_message = int(len(doses)/no_messages)
    keys = list(doses.keys())

    for i in range(no_messages-1):
        doses_to_send = {
            key: doses[key] for key in keys[i*keys_per_message:(i+1)*keys_per_message]}
        await message.author.send(f'{doses_to_send}')

    doses_to_send = {
        key: doses[key] for key in keys[(no_messages-1)*keys_per_message:len(keys)]}
    await message.author.send(f'{doses_to_send}\n\nAnnoksia: {len(doses_to_send)}')


async def cancel_dose(message, user):
    """A function that removes a dose from the user. The dose must have been enjoyed within an hour

    Args:
        message (discord.message): The message that triggered the event

    """

    dose = user.get_previous_dose(db)
    if (dose != None) and ((datetime.datetime.now().timestamp() - dose[list(dose.keys())[0]]['timestamp'])/60/60 < 1):
        db.collection('users').document(user.id).collection(
            'doses').document(list(dose.keys())[0]).delete()
        await message.channel.send('Annos poistettu')
    else:
        await message.channel.send('Ei löydetty annosta mitä poistaa')


async def send_recommendation(message):
    """A function that sends a product recommendation from Alko product catalogue to channel

    Args:
        message (discord.message): The message that triggered the event

    """

    recommend_params = parse_recommend(message.content)
    random = alko.random_drink(recommend_params)

    if random != None:
        await message.channel.send(f'Tuote: {random["nimi"]}\nVahvuus: {(random["alkoholi"] or 0):.1f} %\nPullokoko: {(random["pullokoko"] or 0):.2f} l\nHinta: {random["hinta"]:.2f} €\nLinkki: https://alko.fi/tuotteet/{random["numero"]}')
    else:
        await message.channel.send('Hakuehdoilla ei löytynyt yhtään juomaa')


async def send_plot(message, user, params, capital_params):
    """A function that manages creating a plot and sending it

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to be updated
        params (list): A list having the lower cased params from the message
        capital_params (list): A list of non lower cased params

    """

    if user.in_db:
        try:
            date_high = datetime.datetime.fromisoformat(
                capital_params[3])
        except:
            date_high = datetime.datetime.now()

        date_high = round_date_to_minutes(date_high, True)

        create_plot(db, message, int(
            params[1] or default_plot_hours), capital_params[2], date_high)

        await message.channel.send(file=discord.File(open(PLOT_PATH, 'rb'), 'larvit.png'))
    else:
        await message.channel.send('Et ole käyttänyt palvelujani aiemmin. Et voi plotata humalatiloja.')


async def user_info_handling(message, user, params):
    """This function takes care of user info event handling

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to be processed
        params (list): A list describing the params given from discord

    """

    if params[1] == 'aseta':
        params_dict = {}
        if params[2] != None:
            params_dict['mass'] = float(params[2])
        if params[3] != None:
            params_dict['sex'] = params[3]

        user.update_info(db, message, params_dict)
        await asyncio.sleep(async_wait_seconds)

    elif params[1] == 'poista' and user.in_db:
        if params[2] == None:
            await message.author.send(f'Mikäli haluat poistaa kaikki tietosi tietokannasta, vastaa tähän viestiin "%tiedot poista {user.id}"')
        elif params[2] == str(message.author.id):
            user.delete_user(db)
            await asyncio.sleep(async_wait_seconds)
            user = User(db, message)
        else:
            await message.author.send('Komento on väärin kirjoitettu, tietoja ei poistettu')

    if user.in_db:
        await message.author.send(f'Nimi: {user.name}\nMassa: {user.mass:.0f}\nSukupuoli: {user.sex}')
    else:
        await message.author.send('Et ole aiemmin käyttänyt palvelujani. Jos haluat asettaa tietosi, lähetä "%tiedot aseta <massa> [m/f]", esim. 80kg mies: "%tiedot aseta 80 m"')

    if not isinstance(message.channel, discord.channel.DMChannel):
        await message.delete()


async def send_per_milles(message, user):
    """Sends user's per milles to the channel the command was sent from

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user whose state is to be calculated

    """

    per_milles, sober_in = user.per_mille(db)
    name = user.name_or_nick(message)

    await message.channel.send(f'{name}: {per_milles:.2f} promillea\n'
                               + f'Alkoholi on poistunut elimistöstäsi aikaisintaan {sober_in:.0f} tunnin {int(sober_in%1*60):.0f} minuutin kuluttua')


async def send_help(message):
    """Sends help message to channel

    Args:
        message (discord.message): The message that triggered the event

    """

    messages = help_messages()
    for msg in messages:
        await message.channel.send(msg)


async def message_channels(message):
    """Sends a message to all channels named lärvinen

    Args:
        message (str): A string having the message to broadcast
    """
    guilds = client.guilds
    for guild in guilds:
        for channel in guild.channels:
            if not development and (channel.name.lower() == 'lärvinen'):
                await channel.send(message)


async def sigterm(loop):
    """Stops asyncio.loop

    Args:
        loop (asyncio.loop): Asyncio loop to stop
    """
    await message_channels('Minut on sammutettu ylläpitoa varten')
    loop.stop()


def start(vals):
    """Initialize vatiables and start async event loop

    Args:
        vals (list): A list containing the command line parameters used
    """

    global development
    development = True if vals[-1] == 'dev' else False

    global alko
    alko = Alko()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(
        signal.SIGTERM, lambda: asyncio.create_task(sigterm(loop)))
    loop.add_signal_handler(
        signal.SIGINT, lambda: asyncio.create_task(sigterm(loop)))

    try:
        loop.run_until_complete(client.start(os.getenv('DISCORDTOKEN')))
    except:
        loop.run_until_complete(client.logout())
        # cancel all tasks lingering
    finally:
        loop.close()


if __name__ == "__main__":
    start(sys.argv)
