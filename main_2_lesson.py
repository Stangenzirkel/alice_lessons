from flask import Flask, request
import logging
import json
import random
import os
import requests

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

cities = {
    'москва': ['1030494/c4d9c748c06f8b4a7202',
               '1030494/c4f9a099c59de8705844'],
    'нью-йорк': ['965417/3bd3f4717387c3341fa1',
                 '1540737/7b969272d1a4e1b0059b'],
    'париж': ["937455/df7b63c7581484c04fdd",
              '1521359/014e8f273c64aaa1e8bd']
}

sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True
            }
        ]
        sessionStorage[user_id] = {
            'first_name': None,  # здесь будет храниться имя
            'game_started': False
        # здесь информация о том, что пользователь начал игру. По умолчанию False
        }
        return

    elif "помощь" in req['request']['nlu']['tokens']:
        res['response']['text'] = 'Текст справки по игре'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True
            }
        ]
        return

    elif sessionStorage[user_id]['first_name'] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
            res['response']['buttons'] = [
                {
                    'title': 'Помощь',
                    'hide': True
                }
            ]
        else:
            sessionStorage[user_id]['first_name'] = first_name
            # создаём пустой массив, в который будем записывать города, которые пользователь уже отгадал
            sessionStorage[user_id]['guessed_cities'] = []
            # как видно из предыдущего навыка, сюда мы попали, потому что пользователь написал своем имя.
            # Предлагаем ему сыграть и два варианта ответа "Да" и "Нет".
            res['response'][
                'text'] = f'Приятно познакомиться, {first_name.title()}. Я Алиса. Отгадаешь город по фото?'
            res['response']['buttons'] = [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                },
                {
                    'title': 'Помощь',
                    'hide': True
                }
            ]
    else:
        # У нас уже есть имя, и теперь мы ожидаем ответ на предложение сыграть.
        # В sessionStorage[user_id]['game_started'] хранится True или False в зависимости от того,
        # начал пользователь игру или нет.
        if not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if 'да' in req['request']['nlu']['tokens']:
                # если пользователь согласен, то проверяем не отгадал ли он уже все города.
                # По схеме можно увидеть, что здесь окажутся и пользователи, которые уже отгадывали города
                if len(sessionStorage[user_id]['guessed_cities']) == 3:
                    # если все три города отгаданы, то заканчиваем игру
                    res['response']['text'] = f'{sessionStorage[user_id]["first_name"]}, ты отгадал все города!'
                    res['end_session'] = True
                else:
                    # если есть неотгаданные города, то продолжаем игру
                    sessionStorage[user_id]['game_started'] = True
                    # номер попытки, чтобы показывать фото по порядку
                    sessionStorage[user_id]['attempt'] = 1
                    sessionStorage[user_id]['ask_country'] = False
                    # функция, которая выбирает город для игры и показывает фото
                    play_game(res, req)
            elif 'нет' in req['request']['nlu']['tokens']:
                res['response']['text'] = 'Ну и ладно!'
                res['end_session'] = True
            else:
                res['response']['text'] = f'{sessionStorage[user_id]["first_name"]}, не поняла ответа! Так да или нет?'
                res['response']['buttons'] = [
                    {
                        'title': 'Да',
                        'hide': True
                    },
                    {
                        'title': 'Нет',
                        'hide': True
                    },
                    {
                        'title': 'Помощь',
                        'hide': True
                    }
                ]
        else:
            play_game(res, req)


def play_game(res, req):
    user_id = req['session']['user_id']
    attempt = sessionStorage[user_id]['attempt']
    ask_country = sessionStorage[user_id]['ask_country']
    if ask_country:
        country = sessionStorage[user_id]['country']
        city = sessionStorage[user_id]['city']
        if country in req['request']['nlu']['tokens']:
            res['response']['text'] = 'Правильно! Сыграем ещё?'

        else:
            res['response']['text'] = f'{sessionStorage[user_id]["first_name"]},' \
                                      f' неправильно, но ты все равно молодец, что отгадал город!' \
                                      f' Это {country}. Сыграем ещё?'
        res['response']['buttons'] = [
            {
                'title': 'Да',
                'hide': True
            },
            {
                'title': 'Нет',
                'hide': True
            },
            {
                'title': 'Покажи город на карте',
                'url': f'https://yandex.ru/maps/?mode=search&text={city}',
                'hide': True
            },
            {
                'title': 'Помощь',
                'hide': True
            }
        ]
        sessionStorage[user_id]['game_started'] = False
        return
    elif attempt == 1:
        # если попытка первая, то случайным образом выбираем город для гадания
        city = random.choice(list(cities))
        country = get_country(city).lower()
        # выбираем его до тех пор пока не выбираем город, которого нет в sessionStorage[user_id]['guessed_cities']
        while city in sessionStorage[user_id]['guessed_cities']:
            city = random.choice(list(cities))
        # записываем город в информацию о пользователе
        sessionStorage[user_id]['city'] = city
        sessionStorage[user_id]['country'] = country
        # добавляем в ответ картинку
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = 'Что это за город?'
        res['response']['card']['image_id'] = cities[city][attempt - 1]
        res['response']['text'] = 'Тогда сыграем!'
        res['response']['buttons'] = [
            {
                'title': 'Помощь',
                'hide': True
            }
        ]
    else:
        # сюда попадаем, если попытка отгадать не первая
        city = sessionStorage[user_id]['city']
        # проверяем есть ли правильный ответ в сообщение
        if get_city(req) == city:
            # если да, то добавляем город к sessionStorage[user_id]['guessed_cities'] и
            res['response']['text'] = f'{sessionStorage[user_id]["first_name"]}, правильно! Пробуешь отгадать страну?'
            sessionStorage[user_id]['ask_country'] = True
            sessionStorage[user_id]['guessed_cities'].append(city)
            return
        else:
            # если нет
            if attempt == 3:
                # если попытка третья, то значит, что все картинки мы показали.
                # В этом случае говорим ответ пользователю,
                # добавляем город к sessionStorage[user_id]['guessed_cities'] и отправляем его на второй круг.
                # Обратите внимание на этот шаг на схеме.
                res['response']['text'] = f'{sessionStorage[user_id]["first_name"]},' \
                                          f' вы пытались. Это {city.title()}. Сыграем ещё?'
                res['response']['buttons'] = [
                    {
                        'title': 'Да',
                        'hide': True
                    },
                    {
                        'title': 'Нет',
                        'hide': True
                    },
                    {
                        'title': 'Покажи город на карте',
                        'url': f'https://yandex.ru/maps/?mode=search&text={city}',
                        'hide': True
                    },
                    {
                        'title': 'Помощь',
                        'hide': True
                    }
                ]
                sessionStorage[user_id]['game_started'] = False
                sessionStorage[user_id]['guessed_cities'].append(city)
                return
            else:
                # иначе показываем следующую картинку
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card']['title'] = f'{sessionStorage[user_id]["first_name"]},' \
                                                   f' неправильно. Вот тебе дополнительное фото'
                res['response']['card']['image_id'] = cities[city][attempt - 1]
                res['response']['text'] = 'А вот и не угадал!'
                res['response']['buttons'] = [
                    {
                        'title': 'Помощь',
                        'hide': True
                    }
                ]
    # увеличиваем номер попытки доля следующего шага
    sessionStorage[user_id]['attempt'] += 1


def get_city(req):
    # перебираем именованные сущности
    for entity in req['request']['nlu']['entities']:
        # если тип YANDEX.GEO, то пытаемся получить город(city), если нет, то возвращаем None
        if entity['type'] == 'YANDEX.GEO':
            # возвращаем None, если не нашли сущности с типом YANDEX.GEO
            return entity['value'].get('city', None)


def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name', то возвращаем её значение.
            # Во всех остальных случаях возвращаем None.
            return entity['value'].get('first_name', None)


def get_country(city_name):
    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": "40d1649f-0493-4b70-98ba-98533de7710b",
            'geocode': city_name,
            'format': 'json'
        }
        data = requests.get(url, params).json()
        # все отличие тут, мы получаем имя страны
        return data['response']['GeoObjectCollection'][
            'featureMember'][0]['GeoObject']['metaDataProperty'][
            'GeocoderMetaData']['AddressDetails']['Country']['CountryName']
    except Exception as e:
        return e


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)