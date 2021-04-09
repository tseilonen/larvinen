#!/bin/bash

mv data/alkon-hinnasto-tekstitiedostona.xlsx data/alkon-hinnasto-tekstitiedostona.xlsx.backup
mv data/alko.db data/alko.db.backup
curl -sO "https://www.alko.fi/INTERSHOP/static/WFS/Alko-OnlineShop-Site/-/Alko-OnlineShop/fi_FI/Alkon%20Hinnasto%20Tekstitiedostona/alkon-hinnasto-tekstitiedostona.xlsx" > /dev/null
mv alkon-hinnasto-tekstitiedostona.xlsx data/
python larvinen/alko.py