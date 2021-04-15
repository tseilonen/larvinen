#!/bin/bash

mv data/alkon-hinnasto-tekstitiedostona.xlsx data/alkon-hinnasto-tekstitiedostona.xlsx.backup 2> /dev/null
mv data/alko.db data/alko.db.backup 2> /dev/null
curl -sO "https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/Alko-OnlineShop/fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/alkon-hinnasto-tekstitiedostona.xlsx" > /dev/null
mv alkon-hinnasto-tekstitiedostona.xlsx data/ 2> /dev/null
python larvinen/alko.py 2> /dev/null