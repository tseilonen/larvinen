# Lärvinen

Lärvinen on discord botti, joka antaa tietoa alkoholin vaikutuksista, laskee käyttäjien humalatiloja ja suosittelee tuotteita Alkon katalogista.

# Setup

1. Luo python virtual environment, jossa `python=3.8` ja `pip install -r requirements.txt`
2. Alusta google firestore tietokanta <a href="https://cloud.google.com/firestore/docs/quickstart-servers">ohjeiden</a> mukaan
3. Luo sovellus <a href="https://discord.com/developers/applications"> discordin </a> kehittäjäportaalissa, ja aseta botin token ympäristömuuttujiin nimellä 'DISCORDTOKEN'
4. Alkon hinnaston saa ladattua <a href="https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/Alko-OnlineShop/fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/alkon-hinnasto-tekstitiedostona.xlsx"> täältä </a>.
Lataa se data kansioon.


Suorittamalla ./start.sh saat käynnistettyä botin.
