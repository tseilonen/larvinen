from user import User


def get_guild_users(db, gid, duration_seconds, timestamp_high, user_list=None):
    """Gets guild's users that have had a dose of alcohol before timestamp_high until duration_seconds

    Args:
        db (firestore.Client): The database client
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
        dose_in_range = User.get_previous_dose_by_uid(
            db, int(uid), timestamp_high-duration_seconds, timestamp_high)

        if dose_in_range != None and len(dose_in_range) == 1:
            users_with_doses.append(uid)

    return users_with_doses
