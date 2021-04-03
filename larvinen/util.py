import datetime
from .alko import DRINK_QUERY_PARAMS


def round_date_to_minutes(date, round_up=False):
    """This function rounds datetime object to whole minutes

    Args:
        date (datetime): Date to be rounded
        round_up (boolean): Boolean defining whether to round up (True) or down (False)
            (default False)

    Returns:
        datetime: A datetime object rounded to whole minutes

    """

    timestamp = date.timestamp()
    timestamp = int(timestamp/60)*60+round_up*60
    return datetime.datetime.fromtimestamp(timestamp)


def generate_drink_list(db):
    """A function that sends a list of doses one has enjoyed to user requesting them

    Args:
        db (firestore.Client): The database client

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
