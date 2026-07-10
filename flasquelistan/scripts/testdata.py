from flasquelistan import models


def populate():
    monty = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='+468-46500400',
        balance=10000,
        active=True,
    )

    rick = models.User(
        email='rick_astley@example.com',
        first_name='Rick',
        nickname='The Roll',
        last_name='Astley',
        phone='0710001122', # Invalid phone number
        balance=20050,
        active=True,
    )

    barack = models.User(
        email='no.44@hotmail.tld',
        first_name='Barack',
        last_name='Obama',
        nickname='Barry',
        phone='+1 (808) 555-2643',
        balance=100000,
        active=True,
    )

    kor = models.User(
        email='kor.ist@example.se',
        first_name='Kor',
        last_name='Ist',
        nickname="Party-'pranen",
        phone='074 876 54 32',
        balance=-1000,
        active=True,
    )

    malvina = models.User(
        email='maltek@kth.tld',
        first_name='Malvina',
        last_name='Teknolog',
        nickname='Osqulda',
        phone='',
        balance=-10000,
        active=True,
    )

    soprano = models.Group(name='Sopran', weight='40')
    alto = models.Group(name='Alt', weight='30')
    tenor = models.Group(name='Tenor', weight='20')
    bass = models.Group(name='Bas', weight='10')

    beer = models.Article(name='Öl', value=1600, weight=50, standardglas=1)
    cider = models.Article(name='Cider', value=1500, weight=40, standardglas=1)
    wine = models.Article(name='Vin', value=1400, weight=30, standardglas=1)
    shot = models.Article(name='4 cl', value=1300, weight=20, standardglas=1)
    soft = models.Article(name='Alkfritt', value=1200, weight=10,
                          standardglas=0)

    quote1 = models.Quote(
        text="Kom igen, testa citaten, det blir kul!",
        who="Någon, om Strequelistan",
    )

    quote2 = models.Quote(text="Ett citat utan upphovsman, spännade!")

    quote3 = models.Quote(
        text=("Explicabo possimus dolorem voluptate. "
              "Aut perferendis mollitia dolor nulla. "
              "Perferendis at consequuntur ea aliquam "
              "aut inventore quis neque."),
        who="Godtycklig medietekniker",
    )

    quote4 = models.Quote(text="much quote, such fun", who="shibe")

    models.db.session.add_all([monty, rick, barack, kor, malvina,
                               soprano, alto, tenor, bass,
                               beer, cider, wine, shot, soft,
                               quote1, quote2, quote3, quote4])
    models.db.session.commit()

    kor.group = soprano
    malvina.group = alto
    monty.group = tenor
    rick.group = bass
    barack.group = bass

    models.db.session.commit()
