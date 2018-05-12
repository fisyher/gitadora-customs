from lxml import objectify

def get_bonus_notes_by_timestamp(xml, game_type="drum"):
    if len(xml) == 0:
        return {}

    tree = objectify.fromstring(xml)

    #game_type_id = {"drum":0, "guitar":1, "bass":2}[game_type]

    bonus_notes = {}
    for game in tree.xpath("//music/game"):
        gametype = int(game.gametype)

        for event in game.xpath("//events/event"):
            event_type = int(event.eventtype.text)
            timestamp = int(event.time.text)
            note = int(event.note.text)
            gamelevel = int(event.gamelevel.text)

            if timestamp not in bonus_notes:
                bonus_notes[timestamp] = []

            bonus_notes[timestamp].append({
                'game_type': gametype,
                'event_type': event_type,
                'timestamp': timestamp,
                'note': note,
                'gamelevel': gamelevel
            })


    return bonus_notes