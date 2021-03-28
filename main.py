import discord
import os
import matplotlib.pyplot as plt
import datetime
import numpy as np
import pickle
import sys
import signal
from dateutil import tz
from google.cloud import firestore
from scipy import interpolate

client = discord.Client()
db = firestore.Client()

default_plot_hours = 24.0
pad_hours = 96.0
points_per_hour = 20
default_mass = 80
default_sex = 'm'
first_dose_drinking_time_minutes = 20

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


@client.event
async def on_message(message):
    # Return immediately if message is from self
    if message.author == client.user:
        return

    message.content = message.content.lower()
    msg = message.content

    # Get user dict, if there is no entry in db, then user = None
    user = get_user_dict(message.author.id)
    params = parse_params(msg)

    if msg.startswith('%alkoholin vaikutukset'):
        await message.channel.send(alco_info())

    elif msg.startswith('%kuvaaja'):

        create_plot(message, float(
            params[1] or default_plot_hours), params[2] != 'false')
        await message.channel.send(file=discord.File(open(plot_path, 'rb'), 'larvit.png'))

    elif msg.startswith('%humala'):
        await send_per_milles(message, user)

    elif msg.startswith('%help'):
        await send_help(message)

    elif msg.startswith('%tiedot'):

        if params[1] == 'aseta':
            user = set_personal_info(message, params, user)

        if user != None:
            await message.author.send(f'Nimi: {user["name"]}\nMassa: {user["mass"]:.0f}\nSukupuoli: {user["sex"]}')
        else:
            await message.author.send('Et ole aiemmin käyttänyt palvelujani. Jos haluat asettaa tietosi, lähetä "%tiedot aseta <massa[kg]> <sukupuoli[m/f]>"')

    elif msg.startswith('%menu'):
        drink_list, _ = generate_drink_list()
        await message.channel.send(f'{drink_list}')

    else:
        drink_ref = db.collection('basic_drinks').document(
            params[0]).get().to_dict()

        if drink_ref != None or sum([msg.startswith(drink) for drink in list(special_drinks.keys())]) == 1:
            success = add_dose(message, user)

            if not success:
                await message.author.send('Juoman lisääminen epäonnistui')
            else:
                if not isinstance(message.channel, discord.channel.DMChannel):
                    await message.delete()
                await send_per_milles(message, user)


def get_user_dict(uid):
    # returns None if there is no entry in db
    user = db.collection('users').document(str(uid)).get().to_dict()
    return user


def generate_drink_list():
    drinks_ref = db.collection('basic_drinks').stream()
    drink_string = ''
    drink_list = []
    for drink in drinks_ref:
        drink_dict = drink.to_dict()
        drink_string += f'{drink.id}\t\t{drink_dict["volume"]:.1f} cl \t\t{drink_dict["alcohol"]:.1f} %\n'
        drink_list.append(drink.id)

    return drink_string, drink_list


def set_personal_info(message, params, user):
    if user == None:
        user = add_user(message, user)

    # print([float(params[2]), params[3]])
    update_user_base_info(message, user, [float(params[2]), params[3]])
    update_user_guild_info(message, user)

    return user


def user_name_or_nick(message, user, uid=None):
    if isinstance(message.author, discord.Member):
        try:
            return (user['guilds'][str(message.guild.id)]['nick'] or user['name'])
        except:
            pass

    return user['name']


async def send_per_milles(message, user):
    per_milles, sober_in = per_mille(user)
    name = user_name_or_nick(message, user)

    await message.channel.send(f'{name}: {per_milles:.2f} promillea\n'
                               + f'Alkoholi on poistunut elimistöstäsi aikaisintaan {sober_in:.0f} tunnin {int(sober_in%1*60):.0f} minuutin kuluttua')


async def send_help(message):
    drink_list, _ = generate_drink_list()
    help = f'''%alkoholin vaikutukset: \t Antaa tietoa humalatilan vaikutuksista.\n
%kuvaaja <h> <plot_all>: \t Plottaa kuvaajan viimeisen <h> tunnin aikana humalassa olleiden humalatilan. <h> oletusarvo on 24h. <plot_all> on boolean, joka määrittää plotataanko kaikki käyttäjät, vai vain komennon suorittaja. Oletusarvoisesti true.\n
%humala: \t Lärvinen lähettää sinulle humalatilasi voimakkuuden, ja arvion selviämisajankohdasta.\n
%olut/%aolut/%viini/%viina/%siideri <cl> <vol>: \t Lisää  <cl> senttilitraa <%-vol> vahvuista juomaa nautittujen annosten listaasi. <cl> ja <vol> ovat vapaaehtoisia. Käytä desimaalierottimena pistettä. Esim: "%olut 40 7.2" tai "%viini"\n
Oletusarvot
Juoma\tTilavuus\tAlkoholipitoisuus(%-vol)
{drink_list}
%juoma <cl> <vol>: \t Lisää cl senttilitraa %-vol vahvuista juomaa nautittujen annosten listaasi. Molemmat parametrit ovat pakollisia\n
%sama: \t Lisää nautittujen annosten listaasi saman juoman, kuin edellinen\n
%menu: \t Tulostaa mahdollisten juomien listan\n
%tiedot <aseta massa sukupuoli>: \t Lärvinen lähettää sinulle omat tietosi. Komennolla "%tiedot aseta <massa> <m/f>" saat asetettua omat tietosi botille. Oletuksena kaikki ovat 80 kg miehiä.\n
%help: \t Tulostaa tämän tekstin'''

    await message.channel.send(help)


def get_guild_users(gid):
    users_ref = db.collection('guilds').document(str(gid)).get()
    return users_ref.to_dict()['members']


def create_plot(message, duration, plot_all):
    vals = {}
    points = int(duration*points_per_hour)
    t_deltas = np.linspace(-duration*60*60, 0, points+1)
    now = datetime.datetime.now(tz.gettz('Europe/Helsinki'))
    times = [(now+datetime.timedelta(seconds=t)).strftime('%d.%m.%Y %H:%M:%S')
             for t in t_deltas]

    plt.clf()
    plt.figure(figsize=(12, 8))
    plt.title('Käyttäjien humalatilat')
    plt.ylabel('Humalan voimakkuus [‰]')
    plt.xlabel('Aika')

    if plot_all and isinstance(message.author, discord.Member):
        guild_users = get_guild_users(message.guild.id)
        for uid in guild_users:
            uid = int(uid)
            user = get_user_dict(uid)
            vals[uid] = per_mille_values_new(user, duration)
            if sum(vals[uid]) > 0:
                plt.plot(vals[uid], label=user_name_or_nick(message, user))
    else:
        uid = message.author.id
        user = get_user_dict(uid)
        vals[uid] = per_mille_values_new(user, duration)
        plt.plot(vals[uid], label=user_name_or_nick(message, user))

    plt.legend()
    plt.grid()

    locs = [0]*6
    labels = ['']*6
    for i in range(6):
        labels[i] = times[int(i*points/5)]
        locs[i] = int(i*points/5)

    plt.xticks(locs, labels, rotation=0)
    plt.tight_layout()
    plt.savefig(plot_path)


def update_user_base_info(message, user_dict, params=[None, None]):
    uid = message.author.id

    if (user_dict['name'] != message.author.name) or ((params[0] != None) and (params[0] != user_dict['mass'])) or ((params[1] != None) and (params[0] != user_dict['sex'])):
        user_ref = db.collection('users').document(str(uid))
        user_ref.update({'name': message.author.name, 'mass': float(
            params[0] or user_dict['mass']), 'sex': (params[1] or user_dict['sex'])})

        user_dict['name'] = message.author.name
        user_dict['mass'] = float(params[0] or user_dict['mass'])
        user_dict['sex'] = (params[1] or user_dict['sex'])

    return user_dict


def update_user_guild_info(message, user):
    uid = message.author.id

    # If message is sent from a dm channel, author is instance of user, not member. User doesn't have nick attribute
    if (isinstance(message.author, discord.Member)):
        gid = message.author.guild.id
        sgid = str(gid)
        guild_users = get_guild_users(gid)

        user_modified = False
        if sgid not in user['guilds']:
            user['guilds'][sgid] = {}
            user['guilds'][sgid]['nick'] = message.author.nick
            user_modified = True

        if message.author.nick != user['guilds'][sgid]['nick']:
            user['guilds'][sgid]['nick'] = message.author.nick
            user_modified = True

        if user_modified:
            db.collection('users').document(
                str(uid)).update({'guilds': user['guilds']})

        if (guild_users == None) or (str(uid) not in guild_users):
            members = (guild_users or [])
            members.append(str(uid))
            db.collection('guilds').document(sgid).set(
                {'members': members})

    return user


def add_user(message, user):
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


def get_user_doses(uid):
    doses_ref = db.collection('users').document(str(uid)).collection('doses').where(
        'timestamp', '>', datetime.datetime.now().timestamp()-96*60*60).stream()
    doses = {}

    for dose in doses_ref:
        doses[dose.id] = dose.to_dict()

    return doses


def get_user_previous_dose(uid):
    doses_ref = db.collection('users').document(str(uid)).collection('doses').order_by(
        'timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()

    doses = {}
    for dose in doses_ref:
        doses[dose.id] = dose.to_dict()

    return doses


def add_dose(message, user):
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
                db.collection('basic_drinks').document(
                    '%' + attributes[3].replace('%', '')).set({'alcohol': float(attributes[2]), 'volume': float(attributes[1])})

        elif (attributes[0] == '%sama'):
            previous_dose = list(get_user_previous_dose(
                message.author.id).values())[-1]
            if previous_dose == None:
                return 0
            else:
                attributes[0] = previous_dose['drink']
                attributes[1] = previous_dose['volume']
                attributes[2] = previous_dose['alcohol']
                new_dose = previous_dose['pure_alcohol']
        else:
            return 0

    # Convert to int first to get rid of decimals
    db.collection('users').document(str(message.author.id)).collection(
        'doses').document(str(int(message.created_at.timestamp()))).set({'drink': attributes[0], 'volume': (attributes[1] or drink['volume']), 'alcohol': (attributes[2] or drink['alcohol']), 'pure_alcohol': new_dose, 'timestamp': int(message.created_at.timestamp())})
    return 1


def parse_params(msg):
    msg_list = msg.split(' ')
    attributes = [None]*5

    for i in range(len(msg_list)):
        attributes[i] = msg_list[i]

    return attributes


def alco_info():
    return """Promillea   Vaikutus
Tiedot kuvaavat alkoholin huippupitoisuuksien summittaisia vaikutuksia alkoholia aiemmin kohtuullisesti käyttäneellä tai raittiilla henkilöllä.
< 0,25      Estot vähenevät, itseluottamus kasvaa, lämmön ja hyvinvoinnin tunne, tarkkaavuus heikentyy.
0,25–0,5    Mielihyvän tunne, kömpelyyttä, arvostelukyky heikkenee.
0,5–1,0     Reaktioaika, ajokyky ja liikkeiden hallinta heikkenevät, tunteet ailahtelevat.
1,0–2,5     Heikkeneminen voimistuu, pahoinvointia, oksennuksia, sekavuutta.
2,5–4,0     Puhe sammaltaa, näköhäiriöitä, tajuttomuus.
\> 4,0       Hengitys vaikeutuu, verensokeri vähenee, lämmöntuotanto heikkenee.
5,0         Keskimäärin tappava pitoisuus"""


def per_mille(user):
    # https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
    # Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
    # Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
    # Naisilla vettä painosta = 0,66*massa
    # Miehillä vettä painosta = 0,75*massa
    # Nyrkkisääntö ilman tietoja, 0,1 g/h/kg

    user_doses = get_user_doses(user['id'])

    if user_doses == None:
        return 0, 0

    mass = (user['mass'] or default_mass)

    t_doses = list(user_doses.keys())
    t_doses = [int(t) for t in t_doses]
    now = datetime.datetime.now()
    g_alcohol = 0

    for i in range(len(t_doses)):
        g_alcohol += user_doses[str(t_doses[i])]['pure_alcohol']*7.9

        if i < (len(t_doses)-1):
            g_alcohol -= 0.1*mass*(t_doses[i+1]-t_doses[i])/60/60
        else:
            g_alcohol -= 0.1*mass * \
                max((int(now.timestamp())-t_doses[i]), 1)/60/60

        g_alcohol = max(g_alcohol, 0.0)

    return g_alcohol/water_multiplier[(user['sex'] or default_sex)]/mass, g_alcohol/0.1/mass


def per_mille_values_new(user, duration):
    # https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
    # Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
    # Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
    # Naisilla vettä painosta = 0,66*massa
    # Miehillä vettä painosta = 0,75*massa
    # Nyrkkisääntö ilman tietoja, 0,1 g/h/kg

    user_doses = get_user_doses(user['id'])

    if user_doses == None:
        return 0, 0

    mass = (user['mass'] or default_mass)

    now = datetime.datetime.now()
    num_points = int(duration*points_per_hour)
    default_points = int(pad_hours*points_per_hour)
    interpolation_points = num_points+default_points

    # Interpolate to 1 second before now
    t_interp = np.linspace(-interpolation_points /
                           points_per_hour*60*60, -1, interpolation_points)+now.timestamp()

    t_doses = list(user_doses.keys())
    t_doses.append(int(now.timestamp()))
    user_doses[str(int(now.timestamp()))] = {'pure_alcohol': 0}
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

        if g_alcohol <= 0.0:
            zeros_to_insert.append([i, t_doses[i]-absorption_time])
            zeros_to_insert.append([i, t_doses[i] + g_alcohol/0.1/mass*60*60])

            g_alcohol = 0.0

        if i < (len(t_doses)-1):
            g_alcohol += user_doses[str(t_doses[i])]['pure_alcohol']*7.9

        g_alcohol = max(g_alcohol, 0.0)
        values[i] = g_alcohol

    for i in range(len(zeros_to_insert)):
        t_doses.insert(zeros_to_insert[i][0]+i, zeros_to_insert[i][1])
        values = np.insert(values, zeros_to_insert[i][0]+i, 0.0)

    values = np.insert(values, 0, 0.0)
    t_doses.insert(0, t_interp[0]-1)

    print(values)
    print(t_doses)
    f = interpolate.interp1d(t_doses, values, kind='linear')
    interp_values = f(t_interp)

    return interp_values[default_points:]/water_multiplier[(user['sex'] or default_sex)]/mass


def per_mille_values(user, duration):

    # https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
    # Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
    # Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
    # Naisilla vettä painosta = 0,66*massa
    # Miehillä vettä painosta = 0,75*massa
    # Nyrkkisääntö ilman tietoja, 0,1 g/h/kg

    user_doses = get_user_doses(user['id'])
    if user_doses == None:
        return 0

    mass = (user['mass'] or default_mass)

    t_doses = list(user_doses.keys())
    t_doses = [int(t) for t in t_doses]
    now = datetime.datetime.now()
    g_alcohol = 0
    num_points = int(duration*points_per_hour)
    default_points = int(pad_hours*points_per_hour)
    interpolation_points = num_points+default_points
    values = np.zeros(interpolation_points, dtype=float)
    t_deltas = np.linspace(-interpolation_points /
                           points_per_hour*60*60, 0, interpolation_points)
    t_next_dose = t_doses[0]
    dose_index = 0
    previous_time = int(
        (now+datetime.timedelta(seconds=t_deltas[0]-1)).timestamp())

    while t_doses[dose_index] < previous_time:
        dose_index += 1
        t_next_dose = t_doses[dose_index]

    for i in range(interpolation_points):
        time = int((now+datetime.timedelta(seconds=t_deltas[i])).timestamp())

        if time > t_next_dose:
            # Doses need to be added up if multiple doses are consumed within one time bin
            g_next_dose = 0
            while (t_next_dose-time) <= (time-previous_time):
                g_alcohol += user_doses[str(t_doses[dose_index])
                                        ]['pure_alcohol']*7.9

                dose_index += 1

                if dose_index > (len(t_doses)-1):
                    t_next_dose = int(
                        (datetime.datetime.now()+datetime.timedelta(days=10)).timestamp())
                else:
                    t_next_dose = t_doses[dose_index]
                    points_to_next = (t_next_dose-time)/60/3

        g_alcohol -= 0.1*mass*(time-previous_time)/60/60

        g_alcohol = max(g_alcohol, 0.0)
        values[i] = g_alcohol
        previous_time = time

    return values[default_points:]/water_multiplier[(user['sex'] or default_sex)]/mass


async def remove_sober():
    for key in drunk:
        if per_mille(drunk[key]) == 0:
            print('wololoo')

client.run(os.getenv('DISCORDTOKEN'))


def term_signal_handler(signalNumber, frame):
    guilds = client.guilds
    for guild in guilds:
        for channel in guild.channels:
            if channel.name.lower() == 'lärvinen':
                channel.send("Larvinen on sammutettu huoltoa varten!")
    print('(SIGTERM) terminating the process')
    sys.exit()


signal.signal(signal.SIGTERM, term_signal_handler)
