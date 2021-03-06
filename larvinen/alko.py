import sqlite3
import os
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import json
import googlemaps

DRINK_QUERY_PARAMS = {'hinta_min': ' hinta > ?', 'hinta_max': ' hinta < ?', 'tyyppi': ' tyyppi like ?',
                      'vol_min': ' alkoholi > ?', 'vol_max': ' alkoholi < ?', 'alatyyppi': ' alatyyppi like ?',
                      'luonnehdinta': ' luonnehdinta like ?', 'myymälä': ''}

DB_NAME = 'data/alko.db'
CATALOGUE_NAME = 'data/alkon-hinnasto-tekstitiedostona.xlsx'
STORE_JSON_PATH = 'data/stores.json'


class Alko():
    connection = None
    stores = None

    def __init__(self):
        """Initialize the Alko db connection
        """

        self.connection = sqlite3.connect(DB_NAME)
        query = 'SELECT name FROM sqlite_master WHERE type="table" AND name="juomat";'
        cursor = self.connection.cursor()
        cursor.execute(query)
        row = cursor.fetchone()

        if row == None and os.path.isfile(CATALOGUE_NAME):
            db_init()

        self.stores = json.load(open(STORE_JSON_PATH, 'r'))

    def random_item(self):
        """Get a random item from Alko product catalogue

        Returns:
            dict: A dictionary describing the random product
        """

        cursor = self.connection.cursor()
        fields = ['numero', 'nimi', 'alkoholi', 'hinta', 'pullokoko']
        str_fields = str(fields)[1:-1].replace("\'", "")
        cursor.execute(
            f'SELECT {str_fields} FROM juomat ORDER BY RANDOM() LIMIT 1')
        row = cursor.fetchone()
        return({fields[i]: row[i] for i in range(len(fields))})

    def random_drink(self, params):
        """Get a random item from Alko product catalogue

        Args:
            params (dict): A dictionary containing the query params

        Returns:
            dict: A dictionary describing the random product
        """

        cursor = self.connection.cursor()
        fields = ['numero', 'nimi', 'alkoholi',
                  'hinta', 'pullokoko', 'luonnehdinta']
        str_fields = str(fields)[1:-1].replace("\'", "")
        # {'hinta_min': ' hinta > ?', 'hinta_max': ' hinta < ?', 'tyyppi': ' tyyppi like ?', 'vol_min': ' alkoholi > ?', 'vol_max': ' alkoholi < ?', 'alatyyppi': ' alatyyppi like ?'}
        params_dict = DRINK_QUERY_PARAMS
        str_where = 'WHERE valikoima == "vakiovalikoima"'
        params_list = []

        for param in list(params_dict.keys()):
            if param in params and param != 'myymälä':
                if len(str_where) == 0:
                    str_where = 'WHERE'
                else:
                    str_where += ' AND'

                if param == 'tyyppi' or param == 'alatyyppi' or param == 'luonnehdinta':
                    params_list.append('%'+params[param]+'%')
                else:
                    params_list.append(params[param])

                str_where += params_dict[param]

        qry = f'SELECT {str_fields} FROM juomat {str_where} ORDER BY RANDOM() LIMIT 1'

        i = 0
        max_products = 10
        while i < max_products:
            cursor.execute(qry, params_list)
            row = cursor.fetchone()

            if row == None:
                break

            row = list(row)
            stores = get_alko_stock(row[0])

            if 'myymälä' in params.keys():
                if params['myymälä'].lower() in ''.join(self.stores["stores"]).lower():
                    for store in stores.keys():
                        if params['myymälä'].lower() in store.lower():
                            fields.append('saatavuus')
                            row.append(stores)
                            i = max_products
                            break
                else:
                    return None
            else:
                fields.append('saatavuus')
                row.append(stores)
                i = max_products

            i += 1

        if row != None:
            return {fields[i]: row[i] for i in range(len(fields))}
        else:
            return None

    def product_types(self):
        """Get list of product types

        Returns:
            list: List of product types
        """

        query = 'SELECT DISTINCT tyyppi FROM juomat;'
        cursor = self.connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        return [row[0] for row in rows if row[0] != None]

    def product_subtypes(self):
        """Get list of product subtypes

        Returns:
            list: List of product types
        """

        query = 'SELECT DISTINCT alatyyppi FROM juomat;'
        cursor = self.connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        return [row[0] for row in rows if row[0] != None]


def get_alko_stock(id):
    """Get products stock in stores

    Args:
        id (int): An integer describing the product

    Returns:
        dictionary: A dictionary representing stores and their stock saldos
    """

    url = 'https://www.alko.fi/INTERSHOP/web/WFS/Alko-OnlineShop-Site/fi_FI/-/EUR/ViewProduct-Include?SKU='

    page = requests.get(url+str(id))
    soup = BeautifulSoup(page.content, 'html.parser')

    list_of_stores = soup.text.split('Määrä')[1].replace(
        '\n\n\n\n', '\n').strip().split('\n')

    stores = {list_of_stores[i]: list_of_stores[i+1]
              for i in np.arange(int(len(list_of_stores)/2))*2}
    return stores


def distance_to_alko(origin, destination, mode='driving'):
    """Get distance to specified alko

    Args:
        origin (str): A string descrribing the origin address
        destination (str): A string describing the destination address

    Returns:
        dictionary: A dictionary having the driving times and distances
    """

    gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_KEY'))
    distance_matrix = gmaps.distance_matrix(origin, destination, mode=mode)

    if distance_matrix['rows'][0]['elements'][0]['status'] == 'OK':
        if int(distance_matrix['rows'][0]['elements'][0]['duration']['value']/60) > 60:
            hours = int(distance_matrix['rows'][0]
                        ['elements'][0]['duration']['value']/60/60)
            mins = int(distance_matrix['rows'][0]['elements'][0]['duration']['value']/60) - int(
                distance_matrix['rows'][0]['elements'][0]['duration']['value']/60/60)*60
            duration = f'{hours} h {mins} min'
        else:
            duration = f"{int(distance_matrix['rows'][0]['elements'][0]['duration']['value']/60)} min"

        return {'distance': distance_matrix['rows'][0]['elements'][0]['distance']['text'],
                'duration': duration}
    else:
        return None


def db_init():
    """Initialize the Alko product catalogue database
    """

    conn = sqlite3.connect(DB_NAME)
    data = pd.read_excel(CATALOGUE_NAME, skiprows=3)

    create = """CREATE TABLE IF NOT EXISTS juomat (
                                    id integer PRIMARY KEY,
                                    numero text,
                                    nimi text,
                                    valmistaja text,
                                    pullokoko real,
                                    hinta real,
                                    litrahinta real,
                                    uutuus integer,
                                    tyyppi text,
                                    alatyyppi text,
                                    erityisryhma text,
                                    oluttyyppi text,
                                    valmistusmaa text,
                                    alue text,
                                    vuosikerta integer,
                                    etikettimerkinnat text,
                                    huomautus text,
                                    rypaleet text,
                                    luonnehdinta text,
                                    pakkaustyyppi text,
                                    suljentatyyppi text,
                                    alkoholi real,
                                    hapot real,
                                    sokeri real,
                                    kantavierre real,
                                    vari_ebc real,
                                    katkerot_ebu real,
                                    energia real,
                                    valikoima text,
                                    ean text
                                );"""

    c = conn.cursor()
    c.execute(create)

    new_columns = ['numero', 'nimi', 'valmistaja', 'pullokoko', 'hinta', 'litrahinta', 'hinnastokoodi', 'uutuus', 'tyyppi', 'alatyyppi', 'erityisryhma', 'oluttyyppi', 'valmistusmaa', 'alue', 'vuosikerta', 'etikettimerkinnat',
                   'huomautus', 'rypaleet', 'luonnehdinta', 'pakkaustyyppi', 'suljentatyyppi', 'alkoholi', 'hapot', 'sokeri', 'kantavierre', 'vari_ebc', 'katkerot_ebu', 'energia', 'valikoima', 'ean']

    data.columns = new_columns

    del data['hinnastokoodi']

    # Some row is missing 'l' from the end and is thus interperetted as float
    data['pullokoko'] = [str(s) for s in data['pullokoko']]
    data['pullokoko'] = [float(s.replace(',', '.').split(' ')[0])
                         for s in data['pullokoko']]
    data['hinta'] = [float(h) for h in data['hinta']]
    data['litrahinta'] = [float(h) for h in data['litrahinta']]
    data['uutuus'] = [u == 'uutuus' for u in data['uutuus']]
    data['vuosikerta'] = data['vuosikerta'].astype('Int32')
    data['alkoholi'] = [float(a) for a in data['alkoholi']]
    data['hapot'] = [float(v) for v in data['hapot']]
    data['sokeri'] = [float(s) for s in data['sokeri']]
    data['kantavierre'] = [float(k) for k in data['kantavierre']]
    data['vari_ebc'] = [float(v) for v in data['vari_ebc']]
    data['katkerot_ebu'] = [float(k) for k in data['katkerot_ebu']]
    data['energia'] = [float(e) for e in data['energia']]

    data.to_sql('juomat', con=conn, if_exists='append', index=False)


def load_list_of_alkos():
    """Loads a list of alkos to a json file
    """

    url = 'https://www.alko.fi/myymalat-palvelut'
    page = requests.get(url)
    soup = BeautifulSoup(page.content, 'html.parser')

    stores = []
    shop_soup = soup.find_all('div', class_='outletType_myymalat')

    for store in shop_soup:
        stores.append(store.find(class_='name').text)

    json.dump({'stores': stores}, open(STORE_JSON_PATH, 'w'))


if __name__ == "__main__":
    db_init()
    load_list_of_alkos()
