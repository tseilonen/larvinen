import discord
import datetime
import numpy as np

from google.cloud import firestore
from scipy import interpolate

from .util import delete_collection

PAD_HOURS = 96.0
DEFAULT_MASS = 80
DEFAULT_SEX = 'm'
FIRST_DOSE_DRINKING_TIME_MINUTES = 20

# Males have 75% of their weight worth water, females 66%
WATER_MULTIPLIER = {'m': 0.75, 'f': 0.66}


class User():
    guilds = {}
    high_score = {}
    changed_data = {}
    changed_guild = {}

    def __init__(self, db, id):
        """Initialize user

        Args:
            db (firestore.client): The database client
            id (int): The id of the user
        """
        self.id = str(id)
        user_dict = db.collection('users').document(self.id).get().to_dict()

        if user_dict != None:
            self.sex = user_dict['sex']
            self.mass = user_dict['mass']
            self.name = user_dict['name']
            if 'guilds' in user_dict:
                self.guilds = user_dict['guilds']
            if 'high_scroe' in user_dict:
                self.high_score = user_dict['high_score']
            self.in_db = True
        else:
            self.sex = None
            self.mass = None
            self.name = None
            self.guilds = None
            self.in_db = False

    @property
    def sex(self):
        return (self.__sex or None)

    @sex.setter
    def sex(self, sex):
        if sex != None and sex in ['m', 'f']:
            self.__sex = sex
        else:
            self.__sex = None

    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, id):
        self.__id = id

    @property
    def mass(self):
        return (self.__mass or None)

    @mass.setter
    def mass(self, mass):
        if mass != None and mass > 0 and mass < 300:
            self.__mass = mass
        else:
            self.__mass = None

    @property
    def in_db(self):
        return self.__in_db

    @in_db.setter
    def in_db(self, in_db):
        self.__in_db = in_db

    @property
    def name(self):
        return (self.__name or None)

    @name.setter
    def name(self, name):
        self.__name = name

    def asdict(self):
        return {'id': self.id, 'name': self.name, 'mass': self.mass, 'sex': self.sex, 'in_db': self.in_db}

    def update_info(self, db, message, params={}):
        """Updates user's info to match params and message

        Args:
            db (firestore.Client): The database client
            message (discord.Message): The message that triggered the event
            params (dict): Dictionary that contains the params to update

        """

        if 'mass' in params and self.mass != params['mass']:
            self.mass = params['mass']
            self.changed_data['mass'] = params['mass']

        if 'sex' in params and self.sex != params['sex']:
            self.sex = params['sex']
            self.changed_data['sex'] = params['sex']

        if self.name != message.author.name:
            self.name = message.author.name
            self.changed_data['name'] = message.author.name

        if (isinstance(message.author, discord.Member)):
            gid = message.author.guild.id
            sgid = str(gid)

            if sgid not in self.guilds:
                self.changed_guild[sgid] = {}
                self.changed_guild[sgid]['nick'] = message.author.nick
                self.changed_guild[sgid]['member'] = True
                self.changed_guild[sgid]['guildname'] = message.guild.name

            if (message.author.nick != self.guilds[sgid]['nick']) or (message.guild.name != self.guilds[sgid]['guildname']):
                self.changed_guild[sgid] = {}
                self.changed_guild[sgid]['nick'] = message.author.nick
                self.changed_guild[sgid]['guildname'] = message.guild.name

        if len(self.changed_guild) > 0:
            self.changed_data['guilds'][sgid] = self.changed_data['guilds'][sgid]

        if self.in_db:
            self.update_database(db)
        else:
            self.insert_to_database(db)

    def delete_user(self, db):
        """Deletes user from database, along with one's doses

        Args:
            db (firestore.Client): The database client

        """

        doses_ref = db.collection('users').document(
            self.id).collection('doses')
        delete_collection(doses_ref, 16)

        db.collection('users').document(self.id).delete()

    def update_database(self, db):
        """Updates user's info to database

        Args:
            db (firestore.Client): The database client

        """
        if len(self.changed_data) > 0:
            db.collection('users').document(self.id).update(self.changed_data)
            self.changed_data = {}

    def insert_to_database(self, db):
        """Updates user's info to database

        Args:
            db (firestore.Client): The database client

        """

        db.collection('users').document(self.id).set(self.changed_data)
        self.changed_data = {}
        self.in_db = True

    def name_or_nick(self, message):
        """Returns users nick if one is set for guild. Otherwise returns name.

        Args:
            message (discord.message): The message that triggered the event

        Returns:
            str: User's name or nick

        """

        if isinstance(message.author, discord.Member):
            try:
                return (self.guilds[str(message.guild.id)]['nick'] or self.name)
            except:
                pass

        return self.name

    def get_doses(self, db, duration_seconds, date_high=None):
        """Gets user's all doses before date_high until duration_seconds has passed

        Args:
            db (firestore.Client): The database client
            duration_seconds (int): An int describing the length of the query in seconds
            date_high (datetime): A datetime object defining the upper limit for the dose timestamps
                (default None)

        Returns:
            dict: A dictionary representing the user's doses in the time interval

        """

        date_high = datetime.datetime.now() if date_high == None else date_high
        doses_ref = db.collection('users').document(self.id).collection('doses').where(
            'timestamp', '>', date_high.timestamp()-duration_seconds).where('timestamp', '<', date_high.timestamp()).stream()
        doses = {}

        for dose in doses_ref:
            doses[dose.id] = dose.to_dict()

        return doses

    def get_previous_dose(self, db, time_low=0, time_high=90000000000):
        """Gets users previous dose of alcohol

        Args:
            db (firestore.Client): The database client
            time_low (int): An int describing the earliest valid timestamp for the previous dose
            time_high (int): An int describing the latest valid timestamp for the previous dose

        Returns:
            dict: A dictionary representing the user's previous dose

        """

        doses_ref = db.collection('users').document(self.id).collection('doses').where('timestamp', '>=', time_low).where(
            'timestamp', '<=', time_high).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()

        doses = {}
        for dose in doses_ref:
            doses[dose.id] = dose.to_dict()

        return doses

    def add_dose(self, db, message, params):
        """Adds as dose for user to the database

        Args:
            db (firestore.Client): The database client
            message (discord.message): The message that triggered the event
            params (list): A list of parameters parsed from the message

        Returns:
            bool: A boolean describing the success of adding a drink

        """

        drink = db.collection('basic_drinks').document(
            params[0]).get().to_dict()

        if drink != None:
            new_dose = float(params[1] or drink['volume']) * \
                float((params[2] or drink['alcohol']))/100
        else:
            drink = {'volume': None, 'alcohol': None}

            if ((params[0] == '%juoma') and (params[1] != None) and (params[2] != None)):
                new_dose = float(params[1])*float(params[2])/100

                if params[3] != None and params[3] != 'public':
                    drink_name = '%' + params[3].replace('%', '')
                    params[0] = drink_name
                    db.collection('basic_drinks').document(drink_name).set(
                        {'alcohol': float(params[2]), 'volume': float(params[1])})

            elif (params[0] == '%sama'):
                previous_dose = list(self.get_previous_dose(db).values())[-1]
                if previous_dose == None:
                    return 0
                else:
                    params[0] = previous_dose['drink']
                    params[1] = previous_dose['volume']
                    params[2] = previous_dose['alcohol']
                    new_dose = previous_dose['pure_alcohol']
            else:
                return 0

        # Convert time to be utc always
        t = int(message.created_at.replace(
            tzinfo=datetime.timezone.utc).timestamp())

        document = {'drink': params[0], 'volume': (params[1] or drink['volume']), 'alcohol': (
            params[2] or drink['alcohol']), 'pure_alcohol': new_dose,
            'timestamp': t,
            'user': str(message.author.id)}

        guild = ['private']
        if params[3] == 'public':
            guild.extend(self.guilds_to_list())
        elif isinstance(message.author, discord.Member):
            guild.append(str(message.author.guild.id))

        document['guild'] = guild

        # Convert to int first to get rid of decimals
        db.collection('users').document(self.id).collection(
            'doses').document(str(int(message.created_at.timestamp()))).set(document)
        return 1

    def per_mille(self, db):
        """Gets users blood alcohol content at the current timestamp

        Args:
            db (firestore.Client): The database client

        Returns:
            float: A float describing the current state of the user
            float: A float describing the time in hours it takes the user to get sober 

        """
        mass = (self.mass or DEFAULT_MASS)

        g_alcohol, _, _ = self.get_alcohol_grams(db, datetime.datetime.now())
        if np.any(g_alcohol == None):
            g_alcohol = [0]

        return g_alcohol[-1]/WATER_MULTIPLIER[(self.sex or DEFAULT_SEX)]/mass, g_alcohol[-1]/0.1/mass

    # https://www.terveyskirjasto.fi/dlk01084/alkoholihumala-ja-muita-alkoholin-valittomia-vaikutuksia?q=alkoholi%20palaminen
    # Alkoholimäärä grammoina = 7.9 × (pullon tilavuus senttilitroina) × (alkoholipitoisuus tilavuusprosentteina)
    # Veren alkoholipitoisuus promilleina = (alkoholimäärä grammoina) / 1 000 grammaa verta
    # Naisilla vettä painosta = 0,66*massa
    # Miehillä vettä painosta = 0,75*massa
    # Nyrkkisääntö alkoholin palamiselle ilman tietoja, 0,1 g/h/kg

    def get_alcohol_grams(self, db, now, duration_seconds=86400):
        """Gets a single user's body alcohol content in grams, timestamps and zeros to insert for plotting

        Args:
            db (firestore.Client): The database client
            now (datetime): A datetime object representing the last moment in time, to get the body alcohol content
            duration_seconds (int): Int determining the period of querying the data before now
                (default is 86400 seconds = 24 hours)

        Returns:
            np.array: an array of values representing the body alcohol content at specific times
            list: a list that has the timestamps of the values
            list: a list of timestamps and indices to insert zeros for when the alcohol content has reached zero
        """

        user_doses = self.get_doses(db, duration_seconds+PAD_HOURS*60*60, now)

        if user_doses == None or len(user_doses) == 0:
            return [None]*3

        mass = (self.mass or DEFAULT_MASS)

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
                absorption_time = FIRST_DOSE_DRINKING_TIME_MINUTES*60
            else:
                absorption_time = min(
                    FIRST_DOSE_DRINKING_TIME_MINUTES*60, t_doses[i]-t_doses[i-1])

                g_alcohol -= 0.1*mass*(max(t_doses[i]-t_doses[i-1], 1))/60/60

            if g_alcohol <= 0:
                if int(t_doses[i]-absorption_time) < int(t_doses[i] + g_alcohol/0.1/mass*60*60):
                    zeros_to_insert.append(
                        [i, int(t_doses[i]-absorption_time)])
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

    def per_mille_values(self, db, duration_seconds, now, t_interp):
        """Gets user's per mille values interpolated to t_interp timestamps

        Args:
            db (firestore.Client): The database client
            duration_seconds (int): An int used to define the duration of the interpolation
            now (datetime): A datetime object defining the last moment of interpolation
            t_interp (np.array): A numpy array defining the interpolation points

        Returns:
            np.array: An array having the interpolated points
            np.array: An array having the points used for interpolation
            list: A list having the timestamps of interpolation points

        """
        mass = (self.mass or DEFAULT_MASS)

        values, t_doses, zeros_to_insert = self.get_alcohol_grams(
            db, now, duration_seconds)

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

        return interp_values/WATER_MULTIPLIER[(self.sex or DEFAULT_SEX)]/mass, values[1:-1], t_doses[1:-1]

    def guilds_to_list(self):
        """Converts user's guild memberships to as list of strings

        Returns:
            list: A list of strings representing user's guild memberships
        """

        list_of_gids = []

        for gid in self.guilds:
            list_of_gids.append(str(gid))

        return list_of_gids

    @staticmethod
    def get_previous_dose_by_uid(db, uid, time_low=0, time_high=90000000000, guild='private'):
        """Gets users previous dose of alcohol

        Args:
            db (firestore.Client): The database client
            uid (int): An int describing the user's id
            time_low (int): An int describing the earliest valid timestamp for the previous dose
                (default is 0)
            time_high (int): An int describing the latest valid timestamp for the previous dose
                (default is 90000000000)
            guild (str): An string describing the guilds id
                (default is private)


        Returns:
            dict: A dictionary representing the user's previous dose

        """

        doses_ref = db.collection('users').document(str(uid)).collection('doses').where('timestamp', '>=', time_low).where(
            'timestamp', '<=', time_high).where('guild', 'array_contains', guild).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).stream()

        doses = {}
        for dose in doses_ref:
            doses[dose.id] = dose.to_dict()

        return doses
