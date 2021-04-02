from alko import DRINK_QUERY_PARAMS


def alco_info_message():
    return """Tiedot kuvaavat alkoholin huippupitoisuuksien summittaisia vaikutuksia alkoholia aiemmin kohtuullisesti käyttäneellä tai raittiilla henkilöllä.
Promillea   Vaikutus
< 0,25      Estot vähenevät, itseluottamus kasvaa, lämmön ja hyvinvoinnin tunne, tarkkaavuus heikentyy.
0,25–0,5    Mielihyvän tunne, kömpelyyttä, arvostelukyky heikkenee.
0,5–1,0     Reaktioaika, ajokyky ja liikkeiden hallinta heikkenevät, tunteet ailahtelevat.
1,0–2,5     Heikkeneminen voimistuu, pahoinvointia, oksennuksia, sekavuutta.
2,5–4,0     Puhe sammaltaa, näköhäiriöitä, tajuttomuus.
\> 4,0       Hengitys vaikeutuu, verensokeri vähenee, lämmöntuotanto heikkenee.
5,0         Keskimäärin tappava pitoisuus"""


def help_messages():
    messages = []
    messages.append('''Tässä tuntemani komennot. Kaikki komennot toimivat myös yksityisviestillä minulle. Käyttämällä palveluitani hyväksyt tietojesi tallentamisen Googlen palvelimille Yhdysvaltoihin.\n
%alkoholin_vaikutukset: \t Antaa tietoa humalatilan vaikutuksista.\n
%kuvaaja <h> <user_list> <date>: \t Plottaa kuvaajan viimeisen <h> tunnin aikana alkoholia nauttineiden humalatilan. Jotta henkilö voi näkyä palvelimella kuvaajassa, on hänen tullut ilmoittaa vähintään yksi annos tältä palvelimelta. <h> oletusarvo on 24h. <user_list> on lista henkilöitä, esim [Tino,Aleksi,Henri]. Henkilöt tulee olla erotettu pilkuilla ilman välilyöntejä. Ilman listaa plotataan kaikki palvelimen käyttäjät. <date> on päivämäärä iso formattissa, josta vähennettään <h>, jotta saadaan kuvaajan x-akseli. Esim "%kuvaaja 24 [Tino] 2021-03-30T20:30:00"\n
%humala: \t Lärvinen tulostaa humalatilasi voimakkuuden, ja arvion selviämisajankohdasta.\n
%olut/%aolut/%viini/%viina/%siideri <cl> <vol>: \t Lisää  <cl> senttilitraa <%-vol> vahvuista juomaa nautittujen annosten listaasi. <cl> ja <vol> ovat vapaaehtoisia. Käytä desimaalierottimena pistettä. Esim: "%olut 40 7.2" tai "%viini"\n
%juoma <cl> <vol> <nimi>: \t Lisää cl senttilitraa %-vol vahvuista juomaa nautittujen annosten listaasi. Kaksi ensimmäistä parametria ovat pakollisia. Mikäli asetat myös nimen, tallenetaan juoma menuun.\n
%sama: \t Lisää nautittujen annosten listaasi saman juoman, kuin edellinen\n''')

    messages.append(f'''%menu: \t Tulostaa mahdollisten juomien listan, juomien oletus vahvuuden ja juoman oletus tilavuuden\n
%peruuta: \t Poistaa edellisen annoksen nautittujen annosten listasta. Edellisen annoksen tulee olla nautittu tunnin sisään\n
%annokset <isodate>: \t Lähettää sinulle <isodate> jälkeen nauttimasi annokset. <isodate> muuttujan formaatti tulee olla ISO 8601 mukainen. Parametri on vapaaehtoinen ja oletusarvo on viimeisen viikon annokset. Esim 30.3.2021 klo 20:30:05 UTC jälkeen nautit annokset saa komennolla"%annokset 2021-03-30T20:30:00"\n
%tiedot <aseta massa sukupuoli>/<poista>: \t Lärvinen lähettää sinulle omat tietosi. Komennolla "%tiedot aseta <massa> <m/f>" saat asetettua omat tietosi botille. Oletuksena kaikki ovat 80 kg miehiä. Esim: %tiedot aseta 80 m. Tiedot voi asettaa yksityisviestillä Lärviselle. Komennolla "%tiedot poista" saat poistettua kaikki tietosi Lärvisen tietokannasta.\n
%suosittele <ehto:arvo>: \t Lärvinen suosittelee sinulle alkon valikoimasta satunnaista juomaa antamillasi ehdoilla. Mahdolliset ehdot: {list(DRINK_QUERY_PARAMS.keys())}\n
%help: \t Tulostaa tämän tekstin''')

    return messages
