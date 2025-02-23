import threading
import json
import time
from flask import Flask
import requests

host = '127.0.0.1'     # Сервер
port = '5000'          # Порт
tank_volume = 30       # Вместимость топливозаправщика (в тоннах)
max_trucks = 20        # Максимальное количество топливозаправщиков
total_trucks = 0       # Общее количество созданных топливозаправщиков
garagepoint = 10       # Точка гаража
gasstation1 = 100      # Точка станции заправки 1
gasstation2 = 200      # Точка станции заправки 2
gasstation3 = 300      # Точка станции заправки 2
planepoint1 = 1000     # Точка площадки самолета 1
planepoint2 = 2000     # Точка площадки самолета 2
planepoint3 = 3000     # Точка площадки самолета 3
planepoint4 = 4000     # Точка площадки самолета 4
planepoint5 = 5000     # Точка площадки самолета 5
gas = 'gas'            # Название в URL точки "Заправка"
plane = 'plane'        # Название в URL точки "Самолет"
garage = 'garage'      # Название в URL точки "Гараж"

class FuelTruck:
    def __init__(self, place_nomer, volume_plane, total_loaded): # Конструктор класса: plane_place - место самолета; volume_plane - объем бака самолета; total_loaded - сколько уже заполнено
        total_trucks = total_trucks + 1            # Наращиваем количество грузовиков
        self.nomer = total_trucks                  # Номер топливозаправщика как строка '1'. Это нужно для знания к какому бензовозу обращаются
        self.busy = 1                              # Занят ли топливозаправщик (при создании занят)
        self.full =  0                             # Статус топливозаправщика (30 - полный / 0 - пустой)
        self.current_place = garage                # Текущее местоположение (самолет, заправка, гараж). По умолчанию гараж
        self.target_place = gas                    # Целевой объект (самолет, заправка, гараж). По умолчанию заправка
        self.current_checkpoint = garagepoint      # Текущая точка (число на сетке). По умолчанию заправщик создается в гараже
        self.next_checkpoint = 0                   # Следующий шаг чекпойнта в массиве
        self.place_nomer = place_nomer             # Номер площадки самолета
        self.volume_plane = volume_plane           # Объем бака самолета
        self.total_loaded = total_loaded           # Сколько уже заполнено

        self.thread = threading.Thread(target=self.do_mission) # Запускаем поток для выполнения задачи
        self.thread.start() # Запускаем поток для выполнения задачи
        self.thread.join()  # Ждем завершения

    def do_mission(self): # Метод выполняет работу заправщика
        while self.busy == 1: # Цикл до тех пор, пока бензовоз занят
            time.sleep(1) # Задержка в 1 секунду

            if self.full == 0 and self.total_loaded < self.volume_plane: # Если бензовоз пустой и самолет не заполнен едем на заправку
                self.target_place = gas
 
            elif self.full == 0 and self.total_loaded >= self.volume_plane: # Если бензовоз пустой и самолет заполнен едем в гараж
                self.target_place = garage

            elif self.full > 0 and self.total_loaded < self.volume_plane: # Если бензовоз полный и самолет не заполнен едем к самолету
                self.target_place = plane
 
            else: 
                self.target_place = garage  # На тот случай, если бензовоз полный и самолет заправлен, то едем в гараж



    def get_checkpoint_massiv(self): # Метод запрашивает маршрут до целевого объекта
        checkpoints = [] # Пустой массив чекпойнтов
        # Запрос маршрута. Расшифровка URL:
        # dr - Запрос к диспетчеру руления
        # point - Находимся на точке
        # current_checkpoint - Номер текущей точки (число на сетке)
        # target_place - Название целевого объекта (самолет, заправка, гараж)
        # place_nomer - Номер площадки самолета
        response = requests.get(f"dr/point/{self.current_checkpoint}/{self.target_place}/{self.place_nomer}")
 
        if response.status_code == 200: # Если ответ получен то
            checkpoints = response.json() # Преобразуем json в массив
        else:
            print(f"Ошибка запроса пути: {response.status_code}")        
 
        return checkpoints

    def ask_next_point(self): # 
        # Запрос на разрешение движения к контрольной точке. Расшифровка URL:
        # dr - Запрос к диспетчеру руления
        # point - Находимся на точке
        # current_checkpoint - Номер текущей точки (число на сетке)
        # next_checkpoint - Номер следующей точки (число на сетке)
        response = requests.get(f"dr/point/{self.current_checkpoint}/{self.next_checkpoint}")

        if response.status_code == 200: # Если ответ получен то
            if response.text.upper() == 'OK': # Латинские символы 
                return True
            else:
                return False
        else:
            print(f"Ошибка запроса чекпойнта: {response.status_code}")        
    
        return False
    
    def moving_to_target_is_done(self): # Этот метод отвечает за движение от одного объекта до другого
        checkpoints = [] # Пустой массив чекпойнтов
        checkpoints = self.get_checkpoint_massiv() # Запрашиваем массив чекпойнтов до цели
        index = 1 # Предполагаем, что в массиве нулевой чекпойнт - это текущий, по этому начинаем с первого а не с нулевого
 
        while index < len(checkpoints):  # Перебор чекпойнтов
            self.next_checkpoint = checkpoints[index] # Берем из массива следующий чекпойнт
 
            if self.ask_next_point(): # Если разрешили переход на следующий чекпойнт, то
               self.current_checkpoint = self.next_checkpoint # Переходим на новый чекпойнт
               index = index + 1 # Наращиваем счетчик
            else:
                print("Чекпойнт: " + self.current_checkpoint +  ". Ожидание следующего чекпойнта: " + self.next_checkpoint) # Если не разрешили, то счетчик не наращиваем и ждем

        return True
