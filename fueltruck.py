import threading
import json
import time
from flask import Flask
import requests
from collections import defaultdict

ip_plane = '1.1.1.1'    # IP адрес сервера самолета (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
ip_uno = '1.1.1.1'      # IP адрес сервера УНО  (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
ip_dr = '0.0.0.0'       # IP адрес сервера диспетчера руления (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
is_testmode = True     # Флаг тестового режима
is_debugmode = True     # Флаг вывода отладочных сообщений
off_dispatcher = False  # Флаг отключения диспетчера движения
host = '0.0.0.0'        # Сервер локальный
port = '8080'           # Порт универсальный для всех серверов этого проекта
tank_volume = 25000     # Вместимость топливозаправщика (в литрах)
max_trucks = 3          # Максимальное количество топливозаправщиков
total_trucks = 0        # Общее количество созданных топливозаправщиков
garagepoint = 297       # Точка гаража. Эту цифру надо взять у разработчика Диспетчера движения
garage_free = True      # Индикатор свободного места у гаража
protokol = "http://"    # Протокол
gas = 'gas'             # Название в URL объекта "Заправка"
plane = 'plane'         # Название в URL объекта "Самолет"
garage = 'garage'       # Название в URL объекта "Гараж"
fueltruck = 'fueltruck' # Название в URL объекта "Гараж"
dr = "dr"               # Название в URL объекта "Диспетчер руления"
uno = "uno"             # Название в URL объекта "Управление наземными операциями"

class FuelTruck:
    def __init__(self, nomer, plane_id, volume_plane, order_no): # Конструктор класса: plane_id - id самолета; volume_plane - объем бака самолета; order_no - номер заказа
       self.new_mission(nomer, plane_id, volume_plane, order_no)


    def new_mission(self, nomer, plane_id, volume_plane, order_no): # Новая миссия. Обнуление переменных и прием параметров заказа.
        self.nomer = nomer                         # Номер топливозаправщика как строка '1'. Это нужно для знания к какому бензовозу обращаются
        dbg(f"Новая миссия бензовоза №{self.nomer}")
        self.busy = 1                              # Занят ли топливозаправщик (при создании занят)
        self.full =  0                             # Статус топливозаправщика (30 - полный / 0 - пустой)
        self.current_place = garage                # Текущее местоположение (самолет, заправка, гараж). По умолчанию гараж
        self.next_target_place = gas               # Целевой объект (самолет, заправка, гараж). По умолчанию заправка
        self.current_checkpoint = garagepoint      # Текущая точка (число на сетке). По умолчанию заправщик создается в гараже
        self.next_checkpoint = 0                   # Следующий шаг чекпойнта в массиве
        self.plane_id = plane_id                   # ID самолета
        self.volume_plane = volume_plane           # Объем бака самолета
        self.total_loaded = 0                      # Сколько уже заполнено
        self.order_no = order_no                   # Номер заказа

        self.thread = threading.Thread(target=self.do_mission) # Запускаем поток для выполнения задачи
        self.thread.start()   # Запускаем поток для выполнения задачи


    def do_mission(self):     # Метод выполняет работу заправщика
        global garage_free

        if self.current_checkpoint == garagepoint:                      # Если текущая точка - гараж, то ставим отметку - Занято
            garage_free = False                                         # Гараж занят 
        else:
            garage_free = True                                          # Гараж свободен 

        while self.busy == 1:                                           # Цикл до тех пор, пока бензовоз занят
            time.sleep(1)                                               # Задержка в 1 секунду

            if self.moving_to_target_is_done():                         # Если успешно перешли к цели (обновили поле current_place)
                if self.current_place == plane:                         # Если бензовоз у самолета
                    self.total_loaded = self.total_loaded + tank_volume # Прибавляем топливо к самолету
                    self.full =  0                                      # Обнуляем топливо у бензовоза

                    if self.total_loaded > self.volume_plane:
                        self.total_loaded = self.volume_plane           # На всякий случай округляем до объема бака самолета

                    dbg(f"Заправка самолета: Всего заправлено {self.total_loaded} требуется {self.volume_plane}")

                    if self.total_loaded >= self.volume_plane:          # Если самолет заправлен полностью
                        self.send_success_to_plane()                    # Отправляем самолету сообщение об успешной заправке

                elif self.current_place == garage and self.total_loaded >= self.volume_plane: # Если бензовоз в гараже и самолет заправлен
                    self.busy = 0                                       # Освобождаем грузовик для выхода из цикла
                    dbg(f"Освобождаем бензовоз: {self.nomer}")
                    self.send_mission_complete()                        # Отправляем сообщение в УНО - миссия завершена

                elif self.current_place == gas:                         # Если бензовоз у заправки
                    self.full = tank_volume                             # Бензовоз заправлен

            self.set_next_target_place()                                # Назначаем новый целевой объект (обновляем поле next_target_place)

  
    def get_checkpoint_massiv(self): # Метод запрашивает маршрут до целевого объекта
        checkpoints = [] # Пустой массив чекпойнтов

        if is_testmode or off_dispatcher: # Заглушка для режима тестирования
            checkpoints = [1, 2, 3, 4, 5]
            return checkpoints
       
        if self.next_target_place == plane:
            url = f"{protokol}{ip_dr}:{port}/{self.next_target_place}/{self.current_checkpoint}/{self.plane_id}"
        else:
            url = f"{protokol}{ip_dr}:{port}/{self.current_checkpoint}/{self.next_target_place}"
 
        # Запрос маршрута. Расшифровка URL:
        # current_checkpoint - Номер текущей точки (число на сетке)
        # next_target_place - Название целевого объекта (самолет, заправка, гараж)
        # plane_id - Номер площадки самолета
        dbg(f"Отправка: {url}")
        response = requests.get(url) # Отправка запроса

        if response.status_code == 200: # Если ответ получен то
            checkpoints = response.json() # Преобразуем json в массив
        else:
            dbg(f"Ошибка запроса пути: {url} {response.status_code}")        
 
        return checkpoints


    def ask_next_point(self): # Запрос следующей точки
        global garage_free

        if is_testmode or off_dispatcher: # Заглушка для режима тестирования
            garage_free = True
            return True

        url = f"{protokol}{ip_dr}:{port}/point/{self.current_checkpoint}/{self.next_checkpoint}"
        # Запрос на разрешение движения к контрольной точке. Расшифровка URL:
        # dr - Запрос к диспетчеру руления
        # point - Находимся на точке
        # current_checkpoint - Номер текущей точки (число на сетке)
        # next_checkpoint - Номер следующей точки (число на сетке)
        dbg(f"Отправка: {url}")
        response = requests.get(url)                       # Отправка запроса

        if response.status_code == 200:                    # Если ответ получен то
            if response.text == 'true':                    # Латинские символы
                if self.current_checkpoint == garagepoint: # Если текущей была точка гаража
                    garage_free = True                     # Освобождаем точку гаража

                return True
            else:
                return False
        else:
            dbg(f"Ошибка запроса чекпойнта: {url} {response.status_code}")
    
        return False


    def moving_to_target_is_done(self):                   # Этот метод отвечает за движение от одного объекта до другого
        if self.current_place == self.next_target_place:  # Если текущее положение и цель одинаковы, то ничего не делаем
            return True

        dbg(f"Движемся к {self.next_target_place}")

        checkpoints = []                                  # Пустой массив чекпойнтов

        while True:                                       # Цикл по количеству попыток. После 5 попыток запрашивается новый путь
            checkpoints = self.get_checkpoint_massiv()    # Запрашиваем массив чекпойнтов до цели
            index = 1                                     # Предполагаем, что в массиве нулевой чекпойнт - это текущий, по этому начинаем с первого а не с нулевого
            kol_tries = 0                                 # Счетчик количества попыток пройти по маршруту

            while index < len(checkpoints):               # Перебор чекпойнтов
                self.next_checkpoint = checkpoints[index] # Берем из массива следующий чекпойнт
    
                while True:                                            # Цикл ожидающий разрешение на движение
                    kol_tries = kol_tries + 1                          # Наращиваем счетчик количества попыток

                    if kol_tries >= 5:                                 # Если количество попыток больше или равно 5
                        break                                          # Выходим из цикла

                    if self.ask_next_point():                          # Если разрешили переход на следующий чекпойнт, то
                        self.current_checkpoint = self.next_checkpoint # Переходим на новый чекпойнт
                        index = index + 1                              # Наращиваем счетчик
                        dbg(f"Чекпойнт: {self.current_checkpoint}. Разрешен переход на следующий чекпойнт: {self.next_checkpoint}. Количество попыток {kol_tries}") # Если не разрешили, то счетчик не наращиваем и ждем
                        kol_tries = 0                                  # Сбрасываем счетчик попыток
                        break
                    else:
                        dbg(f"Чекпойнт: {self.current_checkpoint}. Ожидание следующего чекпойнта: {self.next_checkpoint}. Количество попыток {kol_tries}") # Если не разрешили, то счетчик не наращиваем и ждем

                if kol_tries >= 5:                                     # Если количество попыток больше или равно 5
                    break                                              # Выходим из цикла

            if index >= len(checkpoints):                              # Если дошли до конца массива
                break                                                  # Выходим из цикла

        self.current_place = self.next_target_place                    # Переопределяем текущий объект
        dbg(f"Достигли {self.next_target_place}")

        return True


    def set_next_target_place(self): 
        if self.current_place != gas and self.full == 0 and self.total_loaded < self.volume_plane: # Если бензовоз пустой и самолет не заполнен едем на заправку
            self.next_target_place = gas
 
        elif self.current_place != garage and self.full == 0 and self.total_loaded >= self.volume_plane: # Если бензовоз пустой и самолет заполнен едем в гараж
            self.next_target_place = garage

        elif self.current_place != plane and self.full > 0 and self.total_loaded < self.volume_plane: # Если бензовоз полный и самолет не заполнен едем к самолету
            self.next_target_place = plane
 
        elif self.current_place == garage:                            # Если бензовоз в гараже
            if self.full == 0:                                        # Если бензовоз пустой
                self.next_target_place = gas                          # Ставим следующую цель - заправка
            else:
                self.next_target_place = plane                        # Иначе - самолет

        else: 
            self.next_target_place = garage  # На тот случай, если бензовоз полный и самолет заправлен, то едем в гараж

        dbg(f"Смена целевого объекта: текущее {self.current_place} целевое {self.next_target_place}. Статус: full {self.full}, total_loaded {self.total_loaded}, volume_plane {self.volume_plane}")


    def send_success_to_plane(self): # Метод отправки сообщения об успехе самолету
        dbg("Уведомление самолета")

        if is_testmode: # Заглушка для режима тестирования
            return 

        url = f"{protokol}{ip_plane}:{port}/{fueltruck}/{plane}/{self.plane_id}/success"

        dbg(f"Отправка: {url}")
        response = requests.get(url)
        if response.status_code == 200: # Если ответ получен то
           dbg(f"Успешно: {url}")
        else:
           dbg(f"Ошибка отправки success: {url} {response.status_code}")


    def send_mission_complete(self):  # Метод отправки сообщения о завершении миссии в УНО
        dbg("Уведомление УНО")

        if is_testmode: # Заглушка для режима тестирования
            return 

        url = f"{protokol}{ip_uno}:{port}/{uno}/api/v1/order/successReport/{self.order_no}/tanker-truck"

        dbg(f"Отправка: {url}")
        response = requests.get(url)
        if response.status_code == 200: # Если ответ получен то
           dbg(f"Успешно: {url}")
        else:
           dbg(f"Ошибка отправки в УНО: {url} {response.status_code}")


def create_app():
    app = Flask(__name__)

    # Расшифровка URL:
    # fueltruck - Запрос к бензовозу
    # order - Признак того, что это заказ
    # order_no - Номер заказа
    # volume_plane - Объем бака ксамолета
    # plane_id - Номер площадки самолета

    @app.route('/fueltruck/order/<int:order_no>/<int:volume_plane>/<int:plane_id>')
    def serve_order(order_no, volume_plane, plane_id):                            # Процедура приема заказа
        dbg(f"Прием заказа: {order_no}, {volume_plane}, {plane_id}")
        global total_trucks 

        if total_trucks < max_trucks:                                             # Если не все бензовозы созданы
            wait = 0
            while not garage_free and wait <= 10000:                              # Включаем режим ожидания освобождения точки гаража
                time.sleep(0.1)
                wait = wait + 1

            total_trucks = total_trucks + 1                                       # Наращиваем количество бензовозов
            truck = FuelTruck(total_trucks, plane_id, volume_plane, order_no)     # Создаем бензовоз. Там же в конструкторе создается поток
            fueltrucks[total_trucks] = truck                                      # Добавляем в массив
            dbg(f"Создали новый бензовоз: {total_trucks} {order_no}, {volume_plane}, {plane_id}")
        else:                                                                     # Все бензовозы созданы
            dbg(f"Ищем свободный бензовоз: {order_no}, {volume_plane}, {plane_id}")

            cnt = 0

            while cnt <= 10000:                                                       # Цикл поиска свободного бензовоза. Один миллион попыток
                time.sleep(0.1)                                                       # Задержка 0.1
                index = 1                                                             # Начинаем индекс с единицы

                while index <= len(fueltrucks):                                       # Цикл по бензовозам
                    truck = fueltrucks[index]                                         # Достаем очередной бензовоз
                    if truck.busy == 0:                                               # Если бензовоз свободен
                        dbg(f"Бензовоз №{index} найден: {order_no}, {volume_plane}, {plane_id}")
                        wait = 0
                        while not garage_free and wait <= 10000:                      # Включаем режим ожидания освобождения точки гаража
                            time.sleep(0.1)
                            wait = wait + 1

                        truck.new_mission(index, plane_id, volume_plane, order_no)    # Запуск новой миссии
                        dbg(f"Бензовоз №{index} запущен: {order_no}, {volume_plane}, {plane_id}")
                        return "success"
 
                    index = index + 1                                                 # Наращиваем счетчик
                # Конец цикла по index
                cnt = cnt + 1
            # Конец цикла по cnt
            dbg(f"Бензовоз не найден: {order_no}, {volume_plane}, {plane_id}, попыток {cnt}")
            return "Заказ не выполнен: Бензовоз не найден" 
        return f"Заказ выполнен: {order_no}, {volume_plane}, {plane_id}"
    return app

def dbg(word): # Процедура выводит в консоль отладочные сообщения
    if is_debugmode:
        print(word)

fueltrucks = defaultdict(FuelTruck)  # Массив бензовозов

def main():
    app = create_app()
    dbg("Запуск сервера")
    app.run(debug=True, host=host, port=port) # Доступен на всех интерфейсах сети

if __name__ == '__main__':
    main()
