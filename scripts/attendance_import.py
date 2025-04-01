from common.models import *

d = open("assigned_locations.tsv", "r")
t = d.read()
d.close()

rows = [r for r in t.split("\n") if r != ""]

print(rows)

for r in rows:
    cols = [c for c in r.split("\t")]
    badge, first_name, surname = cols
    print(r)
    e, e_isnew = Employee.objects.get_or_create(given_name=first_name, surname=surname)

    card, card_isnew = Card.objects.get_or_create(designation=badge)

    e.card_number = card

    e.save()
