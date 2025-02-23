import threading
import json
import time
from flask import Flask
import requests
from collections import defaultdict

host = '127.0.0.1'      # Сервер
port = '5000'           # Порт
tank_volume = 30        # Вместимость топливозаправщика (в тоннах)
max_trucks = 20         # Максимальное количество топливозаправщиков
total_trucks = 0        # Общее количество созданных топливозаправщиков
garagepoint = 10        # Точка гаража. Эту цифру надо взять у разработчика GUI
protokol = "http://"    # Протокол
gas = 'gas'             # Название в URL объекта "Заправка"
plane = 'plane'         # Название в URL объекта "Самолет"
garage = 'garage'       # Название в URL объекта "Гараж"
fueltruck = 'fueltruck' # Название в URL объекта "Гараж"
dr = "dr"               # Название в URL объекта "Диспетчер руления"
uno = "uno"             # Название в URL объекта "Управление наземными операциями"

class FuelTruck:
    def __init__(self, nomer, place_nomer, volume_plane, order_no): # Конструктор класса: plane_place - место самолета; volume_plane - объем бака самолета; order_no - номер заказа
       self.new_mission(nomer, place_nomer, volume_plane, order_no)


    def new_mission(self, nomer, place_nomer, volume_plane, order_no): # Новая миссия. Обнуление переменных и прием параметров заказа.
        self.nomer = nomer                         # Номер топливозаправщика как строка '1'. Это нужно для знания к какому бензовозу обращаются
        self.busy = 1                              # Занят ли топливозаправщик (при создании занят)
        self.full =  0                             # Статус топливозаправщика (30 - полный / 0 - пустой)
        self.current_place = garage                # Текущее местоположение (самолет, заправка, гараж). По умолчанию гараж
        self.next_target_place = gas               # Целевой объект (самолет, заправка, гараж). По умолчанию заправка
        self.current_checkpoint = garagepoint      # Текущая точка (число на сетке). По умолчанию заправщик создается в гараже
        self.next_checkpoint = 0                   # Следующий шаг чекпойнта в массиве
        self.place_nomer = place_nomer             # Номер площадки самолета
        self.volume_plane = volume_plane           # Объем бака самолета
        self.total_loaded = 0                      # Сколько уже заполнено
        self.order_no = order_no                   # Номер заказа

        self.thread = threading.Thread(target=self.do_mission) # Запускаем поток для выполнения задачи
        self.thread.start()   # Запускаем поток для выполнения задачи


    def do_mission(self):     # Метод выполняет работу заправщика
        while self.busy == 1: # Цикл до тех пор, пока бензовоз занят
            time.sleep(1)     # Задержка в 1 секунду

            if self.moving_to_target_is_done():                         # Если успешно перешли к цели (обновили поле current_place)
                if self.current_place == plane:                         # Если бензовоз у самолета
                    self.total_loaded = self.total_loaded + tank_volume # Прибавляем топливо к самолету
                    self.full =  0                                      # Обнуляем топливо у бензовоза

                    if self.total_loaded >= self.volume_plane:          # Если самолет заправлен полностью
                        self.send_success_to_plane()                    # Отправляем самолету сообщение об успешной заправке

                elif self.current_place == garage and self.total_loaded >= self.volume_plane: # Если бензовоз в гараже и самолет заправлен
                    self.busy = 0                                       # Освобождаем грузовик для выхода из цикла
                    self.send_mission_complete()                        # Отправляем сообщение в УНО - миссия завершена

                    if self.full == 0:                                  # Если бензовоз пустой
                        self.next_target_place = gas                    # Ставим следующую цель - заправка
                    else:
                        self.next_target_place = plane                  # Иначе - самолет

                elif self.current_place == gas:                         # Если бензовоз у заправки
                    self.full = tank_volume                             # Бензовоз заправлен

            self.set_next_target_place()                                # Назначаем новый целевой объект (обновляем поле next_target_place)

  
    def get_checkpoint_massiv(self): # Метод запрашивает маршрут до целевого объекта
        checkpoints = [] # Пустой массив чекпойнтов
        url = f"{protokol}{dr}/point/{self.current_checkpoint}/{self.target_place}/{self.place_nomer}"
        # Запрос маршрута. Расшифровка URL:
        # dr - Запрос к диспетчеру руления
        # point - Находимся на точке
        # current_checkpoint - Номер текущей точки (число на сетке)
        # target_place - Название целевого объекта (самолет, заправка, гараж)
        # place_nomer - Номер площадки самолета
        print(f"Отправка: {url}")
        response = requests.get(url) # Отправка запроса

        if response.status_code == 200: # Если ответ получен то
            checkpoints = response.json() # Преобразуем json в массив
        else:
            print(f"Ошибка запроса пути: {url} {response.status_code}")        
 
        return checkpoints


    def ask_next_point(self): # Запрос следующей точки
        url = f"{protokol}{dr}/point/{self.current_checkpoint}/{self.next_checkpoint}"
        # Запрос на разрешение движения к контрольной точке. Расшифровка URL:
        # dr - Запрос к диспетчеру руления
        # point - Находимся на точке
        # current_checkpoint - Номер текущей точки (число на сетке)
        # next_checkpoint - Номер следующей точки (число на сетке)
        print(f"Отправка: {url}")
        response = requests.get(url) # Отправка запроса

        if response.status_code == 200: # Если ответ получен то
            if response.text.upper() == 'OK': # Латинские символы 
                return True
            else:
                return False
        else:
            print(f"Ошибка запроса чекпойнта: {url} {response.status_code}")
    
        return False


    def moving_to_target_is_done(self): # Этот метод отвечает за движение от одного объекта до другого
        if self.current_pace == self.next_target_place: # Если текущее положение и цель одинаковы, то ничего не делаем
            return True

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

        self.current_place = self.next_target_place # Переопределяем текущий объект
  
        return True


    def set_next_target_place(self): 
        if self.full == 0 and self.total_loaded < self.volume_plane: # Если бензовоз пустой и самолет не заполнен едем на заправку
            self.target_place = gas
 
        elif self.full == 0 and self.total_loaded >= self.volume_plane: # Если бензовоз пустой и самолет заполнен едем в гараж
            self.target_place = garage

        elif self.full > 0 and self.total_loaded < self.volume_plane: # Если бензовоз полный и самолет не заполнен едем к самолету
            self.target_place = plane
 
        else: 
            self.target_place = garage  # На тот случай, если бензовоз полный и самолет заправлен, то едем в гараж


    def send_success_to_plane(self): # Метод отправки сообщения об успехе самолету
        url = f"{protokol}{fueltruck}/{plane}/{self.place_nomer}/success"
        print(f"Отправка: {url}")
        response = requests.get(url)
        if response.status_code == 200: # Если ответ получен то
           print(f"Успешно: {url}")
        else:
           print(f"Ошибка отправки success: {url} {response.status_code}")


    def send_mission_complete(self):  # Метод отправки сообщения о завершении миссии в УНО
        url = f"{protokol}{uno}/{fueltruck}/{self.order_no}/success"
        print(f"Отправка: {url}")
        response = requests.get(url)
        if response.status_code == 200: # Если ответ получен то
           print(f"Успешно: {url}")
        else:
           print(f"Ошибка отправки в УНО: {url} {response.status_code}")


def create_app():
    app = Flask(__name__)

    # Расшифровка URL:
    # fueltruck - Запрос к бензовозу
    # order - Признак того, что это заказ
    # order_no - Номер заказа
    # volume_plane - Объем бака ксамолета
    # place_nomer - Номер площадки самолета

    @app.route('/fueltruck/order/<int:order_no>/<int:volume_plane>/<int:place_nomer>/')
    def serve_order(order_no, volume_plane, place_nomer):                         # Процедура приема заказа
        print(f"Прием заказа: {order_no}, {volume_plane}, {place_nomer}")

        if total_trucks < max_trucks: 
            total_trucks = total_trucks + 1                                       # Наращиваем количество грузовиков
            truck = FuelTruck(total_trucks, place_nomer, volume_plane, order_no)  # Создаем бензовоз. Там же в конструкторе создается поток
            fueltrucks[total_trucks] = truck                                      # Добавляем в массив
            print(f"Создали новый бензовоз: {total_trucks} {order_no}, {volume_plane}, {place_nomer}")
        else:                                                                     # Все грузовики созданы
            print(f"Ищем свободный бензовоз: {order_no}, {volume_plane}, {place_nomer}")
            index = 1                                                             # Начинаем индекс с единицы
            while index <= len(fueltrucks):                                       # Цикл по бензовозам
                truck = fueltrucks[index]                                         # Достаем очередной грузовик
                if truck.busy == 0:                                               # Если грузовик свободен
                    print(f"Бензовоз найден: {index} {order_no}, {volume_plane}, {place_nomer}")
                    truck.new_mission(index, place_nomer, volume_plane, order_no) # Запуск новой миссии
                    print(f"Бензовоз запущен: {index} {order_no}, {volume_plane}, {place_nomer}")
                    return "success"
 
                index = index + 1                                                 # Наращиваем счетчик
            print(f"Бензовоз не найден: {index} {order_no}, {volume_plane}, {place_nomer}")
            return "default" 
    return app

fueltrucks = defaultdict(FuelTruck)  # Массив бензовозов

def main():
    app = create_app()
    app.run(debug=True)

if __name__ == '__main__':
    main()
