import sqlite3
import os
import pandas as pd
import numpy as np

DRINK_QUERY_PARAMS = {'hinta_min': ' hinta > ?', 'hinta_max': ' hinta < ?', 'tyyppi': ' tyyppi like ?',
                      'vol_min': ' alkoholi > ?', 'vol_max': ' alkoholi < ?', 'alatyyppi': ' alatyyppi like ?',
                      'luonnehdinta': ' luonnehdinta like ?'}

DB_NAME = 'data/alko.db'
CATALOGUE_NAME = 'data/alkon-hinnasto-tekstitiedostona.xlsx'


class Alko():
    connection = None

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
            if param in params:
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

        cursor.execute(qry, params_list)
        row = cursor.fetchone()

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


if __name__ == "__main__":
    db_init()
