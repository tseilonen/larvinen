import discord
import os
import matplotlib.pyplot as plt
import datetime
import numpy as np
import pickle
from dateutil import tz

client = discord.Client()

default_plot_hours = 24.0
points_per_hour = 20
default_mass = 80
default_sex = 'm'

doses = {}
users = {}

basic_drinks = {'%olut': [4.7, 33],
                '%aolut': [5.5, 33],
                '%viini': [15.0, 16],
                '%viina': [40.0, 4],
                '%siideri': [4.8, 33]}

special_drinks = {'%juoma': [None, None],
                  '%sama': [None, None]}

users_path = os.getcwd()+'/users.pickle'
doses_path = os.getcwd()+'/doses.pickle'
drinks_path = os.getcwd()+'/drinks.pickle'
plot_path = os.getcwd()+'/plot.png'

if os.path.isfile(users_path):
    users = pickle.load(open(users_path, 'rb'))

if os.path.isfile(doses_path):
    doses = pickle.load(open(doses_path, 'rb'))

if os.path.isfile(drinks_path):
    basic_drinks = pickle.load(open(drinks_path, 'rb'))

# Males have 75% of their weight worth water, females 66%
water_multiplier = {'m': 0.75, 'f': 0.66}


@client.event
async def on_ready():
    print(f'Logattu sisään {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    msg = message.content

    if msg.startswith('%alkoholin vaikutukset'):
        await message.channel.send(alco_info())

    if msg.startswith('%kuvaaja'):
        params = parse_params(msg)

        create_plot(message, float(
            params[1] or default_plot_hours), params[2] != 'false')
        await message.channel.send(file=discord.File(open(plot_path, 'rb'), 'larvit.png'))

    if msg.startswith('%humala'):
        await send_per_milles(message)

    if msg.startswith('%help'):
        await send_help(message)

    if msg.startswith('%tiedot'):
        params = parse_params(msg)

        if params[1] == 'aseta':
            set_personal_info(message, params)

        if message.author.id in users:
            await message.author.send(f'Nimi: {users[message.author.id]["name"]}\nMassa: {users[message.author.id]["mass"]}\nSukupuoli: {users[message.author.id]["sex"]}')
        else:
            await message.author.send('Et ole aiemmin käyttänyt palvelujani. Jos haluat asettaa tietosi, lähetä "%tiedot aseta <massa[kg]> <sukupuoli[m/f]>"')

    if msg.startswith('%menu'):
        drink_list = generate_drink_list()
        await message.channel.send(f'{drink_list}')

    if sum([msg.startswith(drink) for drink in (list(basic_drinks.keys()) + list(special_drinks.keys()))]) == 1:
        success = add_dose(message)

        if not success:
            await message.author.send('Juoman lisääminen epäonnistui')
        else:
            if not isinstance(message.channel, discord.channel.DMChannel):
                await message.delete()
            await send_per_milles(message)


def generate_drink_list():
    return "".join([drink + "\t\t" + str(basic_drinks[drink][1]) +
                    " cl \t\t" + str(basic_drinks[drink][0]) + " %\n" for drink in basic_drinks])


def set_personal_info(message, params):
    if message.author.id not in users:
        add_user(message)

    update_user_base_info(message, [float(params[2]), params[3]])
    update_user_guild_info(message)
    save_users()


def user_name_or_nick(message, uid=None):
    if uid == None:
        uid = message.author.id

    if isinstance(message.author, discord.Member):
        try:
            return (users[uid]['guilds'][message.guild.id]['nick'] or users[uid]['name'])
        except:
            pass

    return users[uid]['name']


async def send_per_milles(message):
    per_milles, sober_in = per_mille(message.author.id)
    name = user_name_or_nick(message)

    await message.author.send(f'{name}: {per_milles:.2f} promillea\n'
                              + f'Alkoholi on poistunut elimistöstäsi aikaisintaan {sober_in:.0f} tunnin {int(sober_in%1*60):.0f} minuutin kuluttua')


async def send_help(message):
    drink_list = generate_drink_list()
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


def create_plot(message, duration, plot_all):

    vals = {}
    points = int(duration*points_per_hour)
    t_deltas = np.linspace(-duration*60*60, 0, points+1)
    now = datetime.datetime.now(tz.gettz('Europe/Helsinki'))
    times = [(now+datetime.timedelta(seconds=t)).strftime('%d.%m.%Y %H:%M:%S')
             for t in t_deltas]

    plt.clf()
    plt.title('Käyttäjien humalatilat')
    plt.ylabel('Humalan voimakkuus [‰]')
    plt.xlabel('Aika')

    if plot_all and isinstance(message.author, discord.Member):
        for user in doses:
            if message.guild.id in users[user]['guilds']:
                vals[user] = per_mille_values(user, duration)
                plt.plot(vals[user], label=user_name_or_nick(message, user))
    else:
        user = message.author.id
        vals[user] = per_mille_values(user, duration)
        plt.plot(vals[user], label=user_name_or_nick(message, user))

    plt.legend()
    plt.grid()

    locs = [0]*6
    labels = ['']*6
    for i in range(6):
        labels[i] = times[int(i*points/5)]
        locs[i] = int(i*points/5)

    plt.xticks(locs, labels, rotation=20)
    plt.tight_layout()
    plt.savefig(plot_path)


def update_user_base_info(message, params=[None, None]):
    uid = message.author.id

    users[uid]['name'] = message.author.name
    users[uid]['mass'] = (params[0] or users[uid]['mass'])
    users[uid]['sex'] = (params[1] or users[uid]['sex'])


def update_user_guild_info(message):
    uid = message.author.id
    modified = False

    # If message is sent from a dm channel, author is instance of user, not member. User doesn't have nick attribute
    if (isinstance(message.author, discord.Member)):
        gid = message.author.guild.id

    if gid not in users[uid]['guilds']:
        users[uid]['guilds'][gid] = {}
        users[uid]['guilds'][gid]['nick'] = message.author.nick
        modified = True

    if message.author.nick != users[uid]['guilds'][gid]['nick']:
        users[uid]['guilds'][gid]['nick'] = message.author.nick
        modified = True

    return modified


def add_user(message):
    modified = False
    uid = message.author.id

    if uid not in users:
        users[uid] = {}
        users[uid]['guilds'] = {}
        users[uid]['name'] = None
        users[uid]['sex'] = None
        users[uid]['mass'] = None

    update_user_base_info(message)
    modified = True

    modified = max(update_user_guild_info(message), modified)

    return modified


def add_dose(message):
    write_users = add_user(message)
    write_basic_drinks = False

    if (message.author.id not in doses):
        doses[message.author.id] = {}

    attributes = parse_params(message.content)

    if (attributes[0] in basic_drinks):
        doses[message.author.id][int(message.created_at.timestamp())] = float(
            attributes[1] or basic_drinks[attributes[0]][1])*float((attributes[2] or basic_drinks[attributes[0]][0]))/100
    elif ((attributes[0] == '%juoma') and (attributes[1] != None) and (attributes[2] != None)):
        doses[message.author.id][int(message.created_at.timestamp())] = float(
            attributes[1])*float(attributes[2])/100
        if attributes[3] != None:
            basic_drinks['%' + attributes[3].replace('%', '')] = [
                float(attributes[2]), float(attributes[1])]
            write_basic_drinks = True
    elif (attributes[0] == '%sama') and (len(doses[message.author.id]) > 0):
        doses[message.author.id][int(message.created_at.timestamp(
        ))] = doses[message.author.id][list(doses[message.author.id].keys())[-1]]
    else:
        return 0

    if write_users:
        save_users()

    if write_basic_drinks:
        with open(drinks_path, 'wb') as file:
            pickle.dump(basic_drinks, file)

    with open(doses_path, 'wb') as file:
        pickle.dump(doses, file)

    return 1


def parse_params(msg):
    msg_list = msg.split(' ')
    attributes = [None]*5

    for i in range(len(msg_list)):
        attributes[i] = msg_list[i]

    return attributes


def save_users():
    with open(users_path, 'wb') as file:
        pickle.dump(users, file)


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

    if user not in doses:
        return 0, 0

    mass = (users[user]['mass'] or default_mass)

    t_doses = list(doses[user].keys())
    now = datetime.datetime.now()
    g_alcohol = 0

    for i in range(len(t_doses)):
        g_alcohol += doses[user][t_doses[i]]*7.9

        if i < (len(t_doses)-1):
            g_alcohol -= 0.1*mass*(t_doses[i+1]-t_doses[i])/60/60
        else:
            g_alcohol -= 0.1*mass * \
                max((int(now.timestamp())-t_doses[i]), 1)/60/60

        g_alcohol = max(g_alcohol, 0.0)

    return g_alcohol/water_multiplier[(users[user]['sex'] or default_sex)]/mass, g_alcohol/0.1/mass


def per_mille_values(user, duration):

    # https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
    # Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
    # Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
    # Naisilla vettä painosta = 0,66*massa
    # Miehillä vettä painosta = 0,75*massa
    # Nyrkkisääntö ilman tietoja, 0,1 g/h/kg
    if user not in doses:
        return 0

    mass = (users[user]['mass'] or default_mass)

    t_doses = list(doses[user].keys())
    now = datetime.datetime.now()
    g_alcohol = 0
    num_points = int(duration*points_per_hour)
    default_points = int(default_plot_hours*points_per_hour)
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
            while (t_next_dose-time) <= (time-previous_time):
                g_alcohol += doses[user][t_doses[dose_index]]*7.9
                dose_index += 1

                if dose_index > (len(t_doses)-1):
                    t_next_dose = int(
                        (datetime.datetime.now()+datetime.timedelta(days=1)).timestamp())
                else:
                    t_next_dose = t_doses[dose_index]

        g_alcohol -= 0.1*mass*(time-previous_time)/60/60

        g_alcohol = max(g_alcohol, 0.0)
        values[i] = g_alcohol
        previous_time = time

    return values[default_points:]/water_multiplier[(users[user]['sex'] or default_sex)]/mass


async def remove_sober():
    for key in drunk:
        if per_mille(drunk[key]) == 0:
            print('wololoo')


client.run(os.getenv('DISCORDTOKEN'))
