import numpy as np
import discord
import datetime
import os
import matplotlib.pyplot as plt
from dateutil import tz

from user import User
from util import round_date_to_minutes
from guilds import get_guild_users

POINTS_PER_HOUR = 60
PLOT_PATH = os.getcwd()+'/plot.png'


def create_plot(db, message, duration, plot_users, date_high=None):
    """Creates plot of the drunkness state

    Args:
        message (discord.message): The message that triggered the event
        duration (int): An int describing the timespan to plot in hours
        plot_users (str): A string describing the list of users to be plotted
        date_high (datetime): A datetime object defining the last timestamp to plot

    """

    date_high = round_date_to_minutes(
        datetime.datetime.now()) if date_high == None else date_high
    vals = {}
    duration_seconds = duration*60*60

    num_points = int(duration*POINTS_PER_HOUR)

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
                db, message.guild.id, duration_seconds, date_high.timestamp())
    else:
        guild_users = [str(message.author.id)]

    for uid in guild_users:
        uid = int(uid)
        user = User(db, uid)
        vals[uid], _, t_doses = user.per_mille_values(
            db, duration_seconds, date_high, t_vals)
        if sum(vals[uid]) > 0:
            ind_doses = np.searchsorted(t_vals, t_doses, side='right')-1
            ind_doses = np.unique(ind_doses[ind_doses >= 0])
            plt.plot(t_vals, vals[uid], '-o', markevery=ind_doses,
                     label=user.name_or_nick(message))

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

    locs = []
    labels = []

    for i in range(len(t_vals)):
        date = datetime.datetime.fromtimestamp(
            t_vals[i], tz=tz.gettz('Europe/Helsinki'))
        if (date.second+date.minute*60+date.hour*60*60) % spacing == 0:
            labels.append(date.strftime('%H:%M'))
            locs.append(t_vals[i])

    plt.xticks(locs, labels, rotation=0)
    plt.tight_layout()
    plt.savefig(PLOT_PATH)
