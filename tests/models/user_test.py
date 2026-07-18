#!/usr/bin/env python3

from flasquelistan import models


def test_group_model(app):
    group = models.Group(
        name="Knights who say 'Ni!'",
        weight=1000
    )

    models.db.session.add(group)
    models.db.session.commit()

    assert group.id > 0


def test_profilepicture_model(app):
    brian = models.User(
        email='brian@pfoj.tld',
        first_name='Brian',
        last_name='Smith',
        balance=0
    )

    models.db.session.add(brian)
    models.db.session.commit()

    pic = models.ProfilePicture(
        filename='brian.gif',
        user_id=brian.id
    )

    models.db.session.add(pic)
    models.db.session.commit()

    assert pic.id > 0
    assert pic.user == brian


def test_registrationrequest_model(app):
    reg_req = models.RegistrationRequest(
        email='brian@pfoj.tld',
        first_name='Brian',
        last_name='Smith',
        phone='0711234567',
        message="Ni!"
    )

    models.db.session.add(reg_req)
    models.db.session.commit()

    assert reg_req.id > 0


def test_user_model(app):
    user = models.User(
        email='monty@python.tld',
        first_name='Monty',
        last_name='Python',
        phone='074-345 32 10',
    )

    models.db.session.add(user)
    models.db.session.commit()

    assert user.id > 0

    # Valid phone numbers are automatically normalized.
    assert user.phone == '+46743453210'

    # Invalid phone numbers are allowed as well (but not normalized).
    invalid_example_number = '+4674-876 543 226 189 416 854 65'
    user.phone = invalid_example_number
    models.db.session.commit()
    assert user.phone == invalid_example_number

    # Phone number is not required.
    user.phone = ''
    models.db.session.commit()
    assert user.phone == ''
