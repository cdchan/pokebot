# -*- coding: utf-8 -*-

import argparse
import codecs
import json
import math
import requests
import time

from pgoapi import PGoApi
from pgoapi import utilities as util

from geopy import Point
from geopy.distance import vincenty

from s2sphere import Cell, CellId, LatLng


CONFIG = json.load(open("config.json", 'r'))


def main():
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    # load locale
    pokemon_mapping = json.load(open("pokemon.en.json", 'r'))

    # load cached pokemon
    cached_pokemons = json.load(open("known_pokemons.json", 'r'))

    # only keep pokemon that haven't expired yet
    pokemons = {encounter_id: pokemon for encounter_id, pokemon in cached_pokemons.items() if pokemon['hides_at'] > time.time()}
    json.dump(pokemons, open("known_pokemons.json", 'w'))
    print u"removed {} expired pokemon out of {}".format(len(cached_pokemons) - len(pokemons), len(cached_pokemons))

    # instantiate pgoapi
    api = PGoApi()
    api.login(CONFIG['authentication']['auth_service'], CONFIG['authentication']['username'].encode('utf-8'), CONFIG['authentication']['password'].encode('utf-8'))

    coords = create_hexagon(CONFIG['office']['latitude'], CONFIG['office']['longitude'])

    for coord in coords:
        lat = coord[0]
        lng = coord[1]
        print lat, lng

        cell_ids = get_cell_ids(lat, lng)
        timestamps = [0,] * len(cell_ids)
        api.set_position(lat, lng, 0)  # provide player position on the earth
        api.get_map_objects(latitude = util.f2i(lat), longitude = util.f2i(lng), since_timestamp_ms = timestamps, cell_id = cell_ids)
        time.sleep(1)
        response_dict = api.call()

        if 'status' in response_dict['responses']['GET_MAP_OBJECTS']:
            if response_dict['responses']['GET_MAP_OBJECTS']['status'] == 1:
                for map_cell in response_dict['responses']['GET_MAP_OBJECTS']['map_cells']:
                    if 'wild_pokemons' in map_cell:
                        for pokemon in map_cell['wild_pokemons']:
                            if str(pokemon['encounter_id']) not in pokemons:
                                pokemon['hides_at'] = time.time() + pokemon['time_till_hidden_ms'] / 1000
                                pokemon['name'] = pokemon_mapping[str(pokemon['pokemon_data']['pokemon_id'])]

                                pokemons[str(pokemon['encounter_id'])] = pokemon
                                json.dump(pokemons, open("known_pokemons.json", 'w'))

                                alert_slack(pokemon)
                                save_pokemon(pokemon)

    return pokemons


def alert_slack(pokemon):
    feet_from_origin = vincenty((CONFIG['office']['latitude'], CONFIG['office']['longitude']), (pokemon['latitude'], pokemon['longitude'])).feet
    blocks_from_origin = int(math.ceil(feet_from_origin / 264.0))  # 20 blocks to a mile, so 264 feet is a block

    time_left = int((pokemon['hides_at'] - time.time()) / 60)

    payload = {'text': u'A {name} is within <http://maps.google.com/?q={lat},{lng}|{distance} block(s)> (:dash: in {time_left} minutes).'.format(name=pokemon['name'], distance=blocks_from_origin, time_left=time_left, lat=pokemon['latitude'], lng=pokemon['longitude'])}
    print payload['text']

    payload['username'] = "Pokébot"
    payload['icon_emoji'] = ":slowpoke:"

    if blocks_from_origin <= 1:
        payload['channel'] = CONFIG['prod_channel']
    else:
        payload['channel'] = CONFIG['test_channel']

    payload_json = dict(payload=json.dumps(payload))
    response = requests.post(CONFIG['webhook_url'], data=payload_json)


def save_pokemon(pokemon):
    with codecs.open('pokemon.csv', 'a', 'utf-8') as log_file:
        log_file.write(u"{encounter_id}, {spawnpoint_id}, {name}, {hides_at}, {lat}, {lng}\n".format(
            encounter_id=pokemon['encounter_id'],
            spawnpoint_id=pokemon['spawnpoint_id'],
            name=pokemon['name'],
            hides_at=pokemon['hides_at'],
            lat=pokemon['latitude'],
            lng=pokemon['longitude'],
        ))


def get_cell_ids(lat, long, radius = 10):
    origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
    # bounds(origin)
    walk = [origin.id()]
    right = origin.next()
    left = origin.prev()

    # Search around provided radius
    for i in range(radius):
        # bounds(right)
        # bounds(left)
        walk.append(right.id())
        walk.append(left.id())
        right = right.next()
        left = left.prev()

    # Return everything
    return sorted(walk)


def bounds(cell_id):
    cell = Cell(cell_id)

    url_string = 'http://maps.googleapis.com/maps/api/staticmap?size=400x400&path='

    coords = []
    for i in range(4) + [0]:
        point = cell.get_vertex(i)
        coords.append("{},{}".format(LatLng.latitude(point).degrees, LatLng.longitude(point).degrees))

    url_string += "|".join(coords)
    print url_string


def create_hexagon(lat, lng):
    bearings = [0, 60, 120, 180, 240, 300]

    coords = [(lat, lng)]
    for bearing in bearings:
        point = vincenty(meters=100).destination((lat, lng), bearing)
        coords.append((point.latitude, point.longitude))

    return coords


if __name__ == '__main__':
    main()
