from .alko import DRINK_QUERY_PARAMS


def alco_info_message():
    info = "Tiedot kuvaavat alkoholin huippupitoisuuksien summittaisia vaikutuksia alkoholia aiemmin kohtuullisesti käyttäneellä tai raittiilla henkilöllä.\n"
    info += "Promillea   Vaikutus\n"
    info += "< 0,25      Estot vähenevät, itseluottamus kasvaa, lämmön ja hyvinvoinnin tunne, tarkkaavuus heikentyy.\n"
    info += "0,25–0,5    Mielihyvän tunne, kömpelyyttä, arvostelukyky heikkenee.\n"
    info += "0,5–1,0     Reaktioaika, ajokyky ja liikkeiden hallinta heikkenevät, tunteet ailahtelevat.\n"
    info += "1,0–2,5     Heikkeneminen voimistuu, pahoinvointia, oksennuksia, sekavuutta.\n"
    info += "2,5–4,0     Puhe sammaltaa, näköhäiriöitä, tajuttomuus.\n"
    info += "> 4,0       Hengitys vaikeutuu, verensokeri vähenee, lämmöntuotanto heikkenee.\n"
    info += "5,0         Keskimäärin tappava pitoisuus.\n"

    return info


def help_messages():
    messages = []

    message = ""
    message += "Tässä tuntemani komennot. Kaikki komennot toimivat myös yksityisviestillä minulle. Käyttämällä palveluitani hyväksyt "
    message += "tietojesi tallentamisen Googlen palvelimille Yhdysvaltoihin.\n\n"
    message += "%alkoholin_vaikutukset: \t Antaa tietoa humalatilan vaikutuksista.\n\n"
    message += "%kuvaaja <h> <user_list> <date>: \t Plottaa kuvaajan viimeisen <h> tunnin aikana alkoholia nauttineiden humalatilan. "
    message += "Jotta henkilö voi näkyä palvelimella kuvaajassa, on hänen tullut ilmoittaa vähintään yksi annos tältä palvelimelta. "
    message += "<h> oletusarvo on 24h. <user_list> on lista henkilöitä, esim [Tino,Aleksi,Henri]. Henkilöt tulee olla erotettu "
    message += "pilkuilla ilman välilyöntejä. Ilman listaa plotataan kaikki palvelimen käyttäjät. <date> on päivämäärä iso formattissa, "
    message += "josta vähennettään <h>, jotta saadaan kuvaajan x-akseli. Esim '%kuvaaja 24 [Tino] 2021-03-30T20:30:00'.\n\n"
    message += "%humala: \t Lärvinen tulostaa humalatilasi voimakkuuden, ja arvion selviämisajankohdasta.\n\n"
    message += "%olut/%aolut/%viini/%viina/%siideri <cl> <vol> <public>: \t Lisää  <cl> senttilitraa <%-vol> vahvuista juomaa nautittujen "
    message += "annosten listaasi. <cl>, <vol> ja <public> ovat vapaaehtoisia. Käytä desimaalierottimena pistettä. Mikäli haluat lähettää "
    message += "juomia yksityisesti, tai toiselta palvelimelta, mutta haluat näkyä käyttämiesi palvelinten kuvaajissa, aseta kaikki "
    message += "parametrit, ja kirjoita loppuun public. Esim: '%olut 40 7.2 public' tai '%viini'.\n\n"
    message += "%juoma <cl> <vol> <nimi>: \t Lisää cl senttilitraa %-vol vahvuista juomaa nautittujen annosten listaasi. Kaksi ensimmäistä "
    message += "parametria ovat pakollisia. Mikäli asetat myös nimen, tallenetaan juoma menuun.\n\n"
    message += "%sama: \t Lisää nautittujen annosten listaasi saman juoman kuin edellinen.\n\n"

    messages.append(message)

    message = ""
    message += "%menu: \t Tulostaa mahdollisten juomien listan, juomien oletus vahvuuden ja juoman oletus tilavuuden.\n\n"
    message += "%peruuta: \t Poistaa edellisen annoksen nautittujen annosten listasta. Edellisen annoksen tulee olla nautittu tunnin sisään.\n\n"
    message += "%annokset <isodate>: \t Lähettää sinulle <isodate> jälkeen nauttimasi annokset. <isodate> muuttujan formaatti tulee olla ISO "
    message += "8601 mukainen. Parametri on vapaaehtoinen ja oletusarvo on viimeisen viikon annokset. Esim 30.3.2021 klo 20:30:05 UTC jälkeen "
    message += "nautitut annokset saa komennolla'%annokset 2021-03-30T20:30:00'.\n\n"
    message += "%tiedot <aseta massa sukupuoli>/<poista>: \t Lärvinen lähettää sinulle omat tietosi. Komennolla '%tiedot aseta <massa> <m/f>' "
    message += "saat asetettua omat tietosi botille. Oletuksena kaikki ovat 80 kg miehiä. Esim: %tiedot aseta 80 m. Tiedot voi asettaa "
    message += "yksityisviestillä Lärviselle. Komennolla '%tiedot poista' saat poistettua kaikki tietosi Lärvisen tietokannasta.\n\n"
    message += "%suosittele < ehto: arvo > : \t Lärvinen suosittelee sinulle alkon vakiovalikoimasta satunnaista juomaa antamillasi ehdoilla. "
    message += f"Mahdolliset ehdot: {list(DRINK_QUERY_PARAMS.keys())}.\n\n"
    message += "%tuotetyypit: \t Lärvinen lähettää kaikki tuotetyypit, joita voit käyttää %suosittele komennon tyyppi parametrin arvona.\n\n"
    message += "%alatyypit: \t Lärvinen lähettää kaikki alatyypit, joita voit käyttää %suosittele komennon alatyyppi parametrin arvona.\n\n"
    message += "%highscore: \t Lärvinen lähettää kovimmat humalatilasi.\n\n"
    message += "%help: \t Tulostaa tämän tekstin"

    messages.append(message)
    return messages
