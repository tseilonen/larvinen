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
from info_messages import *

client = discord.Client()
db = firestore.Client()

development = False

default_plot_hours = 24.0
pad_hours = 96.0
points_per_hour = 60
default_mass = 80
default_sex = 'm'
first_dose_drinking_time_minutes = 20
async_wait_seconds = 1

doses = {}
users = {}

basic_drinks = {'%olut': [4.7, 33],
                '%aolut': [5.5, 33],
                '%viini': [15.0, 16],
                '%viina': [40.0, 4],
                '%siideri': [4.8, 33]}

special_drinks = {'%juoma': [None, None],
                  '%sama': [None, None]}

plot_path = os.getcwd()+'/plot.png'

# Males have 75% of their weight worth water, females 66%
water_multiplier = {'m': 0.75, 'f': 0.66}


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

    # Get user dict, if there is no entry in db, then user = None
    user = get_user_dict(message.author.id)
    params = parse_params(msg)

    if msg.startswith('%alkoholin_vaikutukset'):
        await message.channel.send(alco_info_message())

    elif msg.startswith('%help'):
        await send_help(message)

    elif msg.startswith('%menu'):
        drink_list, _ = generate_drink_list()
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
        await cancel_dose(message)

    elif msg.startswith('%annokset'):
        await send_doses(message, params)

    else:
        drink_ref = db.collection('basic_drinks').document(
            params[0]).get().to_dict()

        if drink_ref != None or sum([msg.startswith(drink) for drink in list(special_drinks.keys())]) == 1:
            user, success = add_dose(message, user)

            if not success:
                await message.author.send('Juoman lisääminen epäonnistui')
            else:
                if not isinstance(message.channel, discord.channel.DMChannel):
                    await message.delete()
            await asyncio.sleep(async_wait_seconds)
            await send_per_milles(message, user)


def get_user_dict(uid):
    """A function to get user dict from the database

    Args:
        uid (int): An int representing the user id

    Returns:
        dict: A dictionary representing the user
    """

    # returns None if there is no entry in db
    user = db.collection('users').document(str(uid)).get().to_dict()
    return user


def parse_recommend(msg):
    """A function to parse space separated keyed parameters from message

    Args:
        msg (str): A string containing the message that triggered the event

    Returns:
        dict: A dictionary of the parameters
    """

    params = msg.split(' ')
    params_list = list(DRINK_QUERY_PARAMS.keys())
    params_dict = {}

    for param in params:
        for drink_param in params_list:
            if param.startswith(drink_param):
                params_dict[drink_param] = param.split(
                    drink_param)[1].replace(':', '')

    return params_dict


def parse_params(msg):
    """A function to parse space separated parameters from the message

    Args:
        msg (str): A string containing the message that triggered the event

    Returns:
        list: A list of parameters
    """

    msg_list = msg.split(' ')
    attributes = [None]*5

    for i in range(min(len(msg_list), len(attributes))):
        attributes[i] = msg_list[i]

    return attributes


def delete_collection(coll_ref, batch_size):
    """A recursive function to delete a specified collection

    Args:
        coll_ref (firestore.collection): Reference to the collection to be deletet
        batch_size (int): An int specifying the batch size

    """

    docs = coll_ref.limit(batch_size).stream()
    deleted = 0

    for doc in docs:
        print(f'Deleting doc {doc.id} => {doc.to_dict()}')
        doc.reference.delete()
        deleted = deleted + 1

    if deleted >= batch_size:
        return delete_collection(coll_ref, batch_size)


def generate_drink_list():
    """A function that sends a list of doses one has enjoyed to user requesting them

    Returns:
        str: A string containing all the drinks formatted to a table
        list: A list containing all the drinks in the database
    """

    drinks_ref = db.collection('basic_drinks').stream()
    drink_string = ''
    drink_list = []
    for drink in drinks_ref:
        drink_dict = drink.to_dict()
        drink_string += f'{drink.id}\t\t{drink_dict["volume"]:.1f} cl \t\t{drink_dict["alcohol"]:.1f} %\n'
        drink_list.append(drink.id)

    return drink_string, drink_list


async def send_doses(message, params):
    """A function that sends a list of doses one has enjoyed to user requesting them

    Args:
        message (discord.message): The message that triggered the event
        params (list): A list of lower cased params

    """

    now = datetime.datetime.now()
    date = datetime.datetime.fromisoformat(
        params[1]) if params[1] != None else datetime.datetime.fromtimestamp(now.timestamp()-7*24*60*60)
    since = (now.timestamp()-date.timestamp())
    doses = get_user_doses(message.author.id, since)
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
    await message.author.send(f'{doses_to_send}')


async def cancel_dose(message):
    """A function that removes a dose from the user. The dose must have been enjoyed within an hour

    Args:
        message (discord.message): The message that triggered the event

    """

    dose = get_user_previous_dose(message.author.id)
    if (dose != None) and ((datetime.datetime.now().timestamp() - dose[list(dose.keys())[0]]['timestamp'])/60/60 < 1):
        db.collection('users').document(str(message.author.id)).collection(
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

    if user != None or (user == None and params[2] != 'false'):
        try:
            date_high = datetime.datetime.fromisoformat(
                capital_params[3])
        except:
            date_high = datetime.datetime.now()

        date_high = round_date_to_minutes(date_high)

        create_plot(message, int(
            params[1] or default_plot_hours), capital_params[2], date_high)

        await message.channel.send(file=discord.File(open(plot_path, 'rb'), 'larvit.png'))
    else:
        await message.channel.send('Et ole käyttänyt palvelujani aiemmin. Et voi plotata omaa humalatilaasi.')


def round_date_to_minutes(date):
    """This function rounds datetime object to whole minutes

    Args:
        date (datetime): Date to be rounded

    Returns:
        datetime: A datetime object rounded to whole minutes

    """

    timestamp = date.timestamp()
    timestamp = int(timestamp/60)*60
    return datetime.datetime.fromtimestamp(timestamp)


async def user_info_handling(message, user, params):
    """This function takes care of user info event handling

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to be processed
        params (list): A list describing the params given from discord

    """

    if params[1] == 'aseta':
        user = set_personal_info(message, params, user)
    elif params[1] == 'poista' and user != None:
        if params[2] == None:
            await message.author.send(f'Mikäli haluat poistaa kaikki tietosi tietokannasta, vastaa tähän viestiin "%tiedot poista {user["id"]}"')
        elif params[2] == str(message.author.id):
            doses_ref = db.collection('users').document(
                user['id']).collection('doses')
            delete_collection(doses_ref, 16)

            db.collection('users').document(user['id']).delete()
            await asyncio.sleep(async_wait_seconds)
            user = get_user_dict(message.author.id)
        else:
            await message.author.send('Komento on väärin kirjoitettu, tietoja ei poistettu')

    if user != None:
        await message.author.send(f'Nimi: {user["name"]}\nMassa: {user["mass"]:.0f}\nSukupuoli: {user["sex"]}')
    else:
        await message.author.send('Et ole aiemmin käyttänyt palvelujani. Jos haluat asettaa tietosi, lähetä "%tiedot aseta <massa> [m/f]", esim. 80kg mies: "%tiedot aseta 80 m"')

    if not isinstance(message.channel, discord.channel.DMChannel):
        await message.delete()


def set_personal_info(message, params, user):
    """Updates user's personal info

    Args:
        message (discord.message): The message that triggered the event
        params (list): A list having the lower cased params from the message
        user (dict): A dictionary describing the user to be updated

    Returns:
        dict: A dictionary representing the user

    """

    if user == None:
        user = add_user(message, user)

    # print([float(params[2]), params[3]])
    update_user_base_info(message, user, [float(params[2]), params[3]])
    update_user_guild_info(message, user)

    return user


def user_name_or_nick(message, user):
    """Returns users nick if one is set for guild. Otherwise returns name.

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to update

    Returns:
        str: User's name or nick

    """

    if isinstance(message.author, discord.Member):
        try:
            return (user['guilds'][str(message.guild.id)]['nick'] or user['name'])
        except:
            pass

    return user['name']


async def send_per_milles(message, user):
    """Sends user's per milles to the channel the command was sent from

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user whose state is to be calculated

    """

    per_milles, sober_in = per_mille(user)
    name = user_name_or_nick(message, user)

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


def get_guild_users(gid, duration_seconds, timestamp_high, user_list=None):
    """Gets guild's users that have had a dose of alcohol before timestamp_high until duration_seconds

    Args:
        gid (int): An integer describing the guild's id
        duration_seconds (int): An int defining the duration in which user has had to have a dose
        timestamp_high (int): An int having the timestamp of last moment when user has had to have a dose
        user_list (list): A list of guild users to be checked
            (default is None)

    Returns:
        lsit: A list of user id's that have had a dose in the defined time period

    """
    users = []
    users_with_doses = []

    if user_list != None:
        nick_ref = db.collection('users').where(
            f'guilds.`{gid}`.nick', 'in', user_list).stream()

        for user in nick_ref:
            users.append(user.id)

        # Only one in, not-in, array_contains_any per query
        name_ref = db.collection('users').where(f'guilds.`{gid}`.member', '==', True).where(
            f'guilds.`{gid}`.nick', '==', None).where('name', 'in', user_list).stream()

        for user in name_ref:
            if user.id not in users:
                users.append(user.id)
    else:
        users_ref = db.collection('users').where(
            f'guilds.`{gid}`.member', '==', True).stream()

        for user in users_ref:
            users.append(user.id)

    for uid in users:
        dose_in_range = get_user_previous_dose(
            int(uid), timestamp_high-duration_seconds, timestamp_high)

        if dose_in_range != None and len(dose_in_range) == 1:
            users_with_doses.append(uid)

    return users_with_doses


def create_plot(message, duration, plot_users, date_high=None):
    """Creates plot of the drunkness state

    Args:
        message (discord.message): The message that triggered the event
        duration (int): An int describing the timespan to plot in hours
        plot_users (str): A string describing the list of users to be plotted
        date_hihg (datetime): A datetime object defining the last timestamp to plot

    """

    date_high = round_date_to_minutes(
        datetime.datetime.now()) if date_high == None else date_high
    vals = {}
    duration_seconds = duration*60*60

    num_points = int(duration*points_per_hour)

    # Interpolate to 1 second before date_high
    t_vals = np.arange(-num_points, 1)*60+date_high.timestamp()

    dt_first = datetime.datetime.fromtimestamp(t_vals[0])
    dt_last = datetime.datetime.fromtimestamp(t_vals[-1])
    if dt_first.day != dt_last.day or dt_first.month != dt_last.month:
        title_date = dt_first.strftime(
            '%d.%m.%Y') + ' - ' + dt_last.strftime('%d.%m.%Y')
    else:
        title_date = dt_first.strftime('%d.%m.%Y')

    plt.clf()
    plt.figure(figsize=(12, 8))
    plt.title(f'Käyttäjien humalatilat {title_date}')
    plt.ylabel('Humalan voimakkuus [‰]')
    plt.xlabel('Aika')

    if isinstance(message.author, discord.Member):
        if plot_users != None and plot_users.find('[') != -1 and plot_users.find(']') != -1:
            guild_users = get_guild_users(message.guild.id, duration_seconds, date_high.timestamp(), plot_users.replace(
                '[', '').replace(']', '').split(','))
        else:
            guild_users = get_guild_users(
                message.guild.id, duration_seconds, date_high.timestamp())
    else:
        guild_users = [str(message.author.id)]

    for uid in guild_users:
        uid = int(uid)
        user = get_user_dict(uid)
        vals[uid], doses, t_doses = per_mille_values(
            user, duration_seconds, date_high, t_vals)
        if sum(vals[uid]) > 0:
            ind_doses = np.searchsorted(t_vals, t_doses, side='right')-1
            ind_doses = np.unique(ind_doses[ind_doses >= 0])
            plt.plot(t_vals, vals[uid], '-o', markevery=ind_doses,
                     label=user_name_or_nick(message, user))

    plt.legend()
    plt.grid()

    spacing_minutes = (duration_seconds)/6/60

    if spacing_minutes > 60:
        spacing_minutes = int(spacing_minutes/60)*60
    elif spacing_minutes > 30:
        spacing_minutes = 30
    elif spacing_minutes > 15:
        spacing_minutes = 15
    elif spacing_minutes > 10:
        spacing_minutes = 10
    else:
        spacing_minutes = 5

    spacing = spacing_minutes*60

    num_labels = int(duration_seconds/(spacing))

    locs = []  # t_vals[locs_ind]
    labels = []  # *len(locs)

    for i in range(len(t_vals)):
        date = datetime.datetime.fromtimestamp(
            t_vals[i], tz=tz.gettz('Europe/Helsinki'))
        if (date.second+date.minute*60+date.hour*60*60) % spacing == 0:
            labels.append(date.strftime('%H:%M'))
            locs.append(t_vals[i])

    plt.xticks(locs, labels, rotation=0)
    plt.tight_layout()
    plt.savefig(plot_path)


def update_user_base_info(message, user_dict, params=[None, None]):
    """Updates user's base information

    Args:
        message (discord.message): The message that triggered the event
        user_dict (dict): A dictionary describing the user to update
        params (list): A dictionary having the info to update. 0=mass, 1=sex['m'/'f']
            (default [None, None])

    Returns:
        dict: A dictionary representing the user

    """

    uid = message.author.id
    user_modified = False

    if (user_dict['name'] != message.author.name):
        user_dict['name'] = message.author.name
        user_modified = True

    if ((params[0] != None) and (params[0] != user_dict['mass'])):
        user_dict['mass'] = float(params[0])
        user_modified = True

    if ((params[1] != None) and (params[0] != user_dict['sex'])):
        user_dict['sex'] = params[1]
        user_modified = True

    if user_modified:
        user_ref = db.collection('users').document(str(uid))
        user_ref.update(
            {'name': user_dict['name'], 'mass': user_dict['mass'], 'sex': user_dict['sex']})

    return user_dict


def update_user_guild_info(message, user):
    """Updates user's guild information

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to update

    Returns:
        dict: A dictionary representing the user

    """

    uid = message.author.id

    # If message is sent from a dm channel, author is instance of user, not member. User doesn't have nick attribute
    if (isinstance(message.author, discord.Member)):
        gid = message.author.guild.id
        sgid = str(gid)

        user_modified = False
        if sgid not in user['guilds']:
            user['guilds'][sgid] = {}
            user['guilds'][sgid]['nick'] = message.author.nick
            user['guilds'][sgid]['member'] = True
            user['guilds'][sgid]['guildname'] = message.guild.name
            user_modified = True

        if (message.author.nick != user['guilds'][sgid]['nick']) or (message.guild.name != user['guilds'][sgid]['guildname']):
            user['guilds'][sgid]['nick'] = message.author.nick
            user_modified = True

        if user_modified:
            db.collection('users').document(
                str(uid)).update({'guilds': user['guilds']})

    return user


def add_user(message, user):
    """Adds user to database and updates user's info

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user to add or update

    Returns:
        dict: A dictionary representing the user

    """
    uid = message.author.id

    if user == None:
        user = {}
        user['guilds'] = {}
        user['name'] = None
        user['sex'] = None
        user['mass'] = None
        user['id'] = str(uid)
        db.collection('users').document(str(uid)).set(user)

    update_user_base_info(message, user)
    update_user_guild_info(message, user)

    return user


def get_user_doses(uid, duration_seconds, date_high=None):
    """Gets user's all doses before date_high until duration_seconds has passed

    Args:
        uid (int): Id of the user being queried for
        duration_seconds (int): An int describing the length of the query in seconds
        date_high (datetime): A datetime object defining the upper limit for the dose timestamps
            (default None)

    Returns:
        dict: A dictionary representing the user's doses in the time interval

    """

    date_high = datetime.datetime.now() if date_high == None else date_high
    doses_ref = db.collection('users').document(str(uid)).collection('doses').where(
        'timestamp', '>', date_high.timestamp()-duration_seconds).where('timestamp', '<', date_high.timestamp()).stream()
    doses = {}

    for dose in doses_ref:
        doses[dose.id] = dose.to_dict()

    return doses


def get_user_previous_dose(uid, time_low=0, time_high=90000000000):
    """Gets users previous dose of alcohol

    Args:
        uid (int): Id of the user being queried for
        time_low (int): An int describing the earliest valid timestamp for the previous dose
        time_high (int): An int describing the latest valid timestamp for the previous dose

    Returns:
        dict: A dictionary representing the user's previous dose

    """

    doses_ref = db.collection('users').document(str(uid)).collection('doses').where('timestamp', '>=', time_low).where('timestamp', '<=', time_high).order_by(
        'timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()

    doses = {}
    for dose in doses_ref:
        doses[dose.id] = dose.to_dict()

    return doses


def add_dose(message, user):
    """Adds as dose for user to the database

    Args:
        message (discord.message): The message that triggered the event
        user (dict): A dictionary describing the user

    Returns:
        dict: A dictionary representing the user
        bool: A boolean describing the success of adding a drink

    """

    user = add_user(message, user)
    attributes = parse_params(message.content)
    drink = db.collection('basic_drinks').document(
        attributes[0]).get().to_dict()

    if drink != None:
        new_dose = float(attributes[1] or drink['volume']) * \
            float((attributes[2] or drink['alcohol']))/100
    else:
        drink = {'volume': None, 'alcohol': None}

        if ((attributes[0] == '%juoma') and (attributes[1] != None) and (attributes[2] != None)):
            new_dose = float(attributes[1])*float(attributes[2])/100

            if attributes[3] != None:
                drink_name = '%' + attributes[3].replace('%', '')
                attributes[0] = drink_name
                db.collection('basic_drinks').document(drink_name).set(
                    {'alcohol': float(attributes[2]), 'volume': float(attributes[1])})

        elif (attributes[0] == '%sama'):
            previous_dose = list(get_user_previous_dose(
                message.author.id).values())[-1]
            if previous_dose == None:
                return user, 0
            else:
                attributes[0] = previous_dose['drink']
                attributes[1] = previous_dose['volume']
                attributes[2] = previous_dose['alcohol']
                new_dose = previous_dose['pure_alcohol']
        else:
            return user, 0

    # Convert to int first to get rid of decimals
    db.collection('users').document(str(message.author.id)).collection(
        'doses').document(str(int(message.created_at.timestamp()))).set({'drink': attributes[0], 'volume': (attributes[1] or drink['volume']), 'alcohol': (attributes[2] or drink['alcohol']), 'pure_alcohol': new_dose, 'timestamp': int(message.created_at.timestamp())})
    return user, 1


def per_mille(user):
    """Gets users blood alcohol content at the current timestamp

    Args:
        user (dict): A dictionary representing the user

    Returns:
        float: A float describing the current state of the user
        float: A float describing the time in hours it takes the user to get sober 

    """
    mass = (user['mass'] or default_mass)

    g_alcohol, _, _ = get_user_alcohol_grams(user, datetime.datetime.now())
    if np.any(g_alcohol == None):
        g_alcohol = [0]

    return g_alcohol[-1]/water_multiplier[(user['sex'] or default_sex)]/mass, g_alcohol[-1]/0.1/mass


def per_mille_values(user, duration_seconds, now, t_interp):
    """Gets user's per mille values interpolated to t_interp timestamps

    Args:
        user (dict): A dictionary representing the user whose state is being queried
        duration_seconds (int): An int used to define the duration of the interpolation
        now (datetime): A datetime object defining the last moment of interpolation
        t_interp (np.array): A numpy array defining the interpolation points

    Returns:
        np.array: An array having the interpolated points
        np.array: An array having the points used for interpolation
        list: A list having the timestamps of interpolation points

    """
    mass = (user['mass'] or default_mass)

    values, t_doses, zeros_to_insert = get_user_alcohol_grams(
        user, now, duration_seconds)

    if np.any(values == None):
        return [0], [0], [0]

    for i in range(len(zeros_to_insert)):
        t_doses.insert(zeros_to_insert[i][0]+i, zeros_to_insert[i][1])
        values = np.insert(values, zeros_to_insert[i][0]+i, 0.0)

    if t_interp[0] < t_doses[0]:
        t_doses.insert(0, t_interp[0]-1)
        values = np.insert(values, 0, 0.0)

    f = interpolate.interp1d(t_doses, values, kind='linear')
    interp_values = f(t_interp)

    return interp_values/water_multiplier[(user['sex'] or default_sex)]/mass, values[1:-1], t_doses[1:-1]


# https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
# Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
# Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
# Naisilla vettä painosta = 0,66*massa
# Miehillä vettä painosta = 0,75*massa
# Nyrkkisääntö alkoholin palamiselle ilman tietoja, 0,1 g/h/kg


def get_user_alcohol_grams(user, now, duration_seconds=86400):
    """Gets a single user's body alcohol content in grams, timestamps and zeros to insert for plotting

    Args:
        user (dict): A dictionary representing the user whose doses are being queried
        now (datetime): A datetime object representing the last moment in time, to get the body alcohol content
        duration_seconds (int): Int determining the period of querying the data before now
            (default is 86400 seconds = 24 hours)

    Returns:
        np.array: an array of values representing the body alcohol content at specific times
        list: a list that has the timestamps of the values
        list: a list of timestamps and indices to insert zeros for when the alcohol content has reached zero
    """

    user_doses = get_user_doses(
        user['id'], duration_seconds+pad_hours*60*60, now)

    if user_doses == None or len(user_doses) == 0:
        return [None]*3

    mass = (user['mass'] or default_mass)

    t_doses = list(user_doses.keys())
    # Make last datapoint to be at current timestamp
    t_doses.append(int(now.timestamp()))
    user_doses[str(int(now.timestamp()))] = {'pure_alcohol': 0.0}
    t_doses = [int(t) for t in t_doses]

    g_alcohol = 0.0
    values = np.zeros(len(t_doses), dtype=float)
    zeros_to_insert = []

    for i in range(len(t_doses)):
        if i == 0:
            absorption_time = first_dose_drinking_time_minutes*60
        else:
            absorption_time = min(
                first_dose_drinking_time_minutes*60, t_doses[i]-t_doses[i-1])

            g_alcohol -= 0.1*mass*(max(t_doses[i]-t_doses[i-1], 1))/60/60

        if g_alcohol <= 0:
            if int(t_doses[i]-absorption_time) < int(t_doses[i] + g_alcohol/0.1/mass*60*60):
                zeros_to_insert.append([i, int(t_doses[i]-absorption_time)])
                if i != 0:
                    zeros_to_insert.append(
                        [i, int(t_doses[i] + g_alcohol/0.1/mass*60*60)])
            else:
                zeros_to_insert.append(
                    [i, int(t_doses[i] + g_alcohol/0.1/mass*60*60)])

                if i < (len(t_doses)-1):
                    zeros_to_insert.append(
                        [i, int(t_doses[i]-absorption_time)])

            g_alcohol = 0.0

        g_alcohol += user_doses[str(t_doses[i])]['pure_alcohol']*7.9

        g_alcohol = max(g_alcohol, 0.0)
        values[i] = g_alcohol

    return values, t_doses, zeros_to_insert


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
