import threading
import json
import time
from flask import Flask, render_template, request
import requests
from collections import defaultdict

ip_tablo = '192.168.35.244'   # IP адрес табло
ip_plane = '192.168.35.209'   # IP адрес сервера самолета (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
ip_uno = '192.168.35.125'     # IP адрес сервера УНО  (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
ip_dr = '192.168.35.219'       # IP адрес сервера диспетчера руления (ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ НА РЕАЛЬНЫЙ)
is_plane = False           # Имитатор самолёта
is_dispatcher = False       # Имитатор диспетчера движения
is_uno = False             # Имитатор УНО
is_tablo = False           # табло заглушка
is_debugmode = True        # Флаг вывода отладочных сообщений
host = '0.0.0.0'           # Сервер локальныйr
port = '5555'              # Порт универсальный для всех серверов этого проекта
tank_volume = 10000        # Вместимость топливозаправщика (в литрах)
max_trucks = 3             # Максимальное количество топливозаправщиков
total_trucks = 0           # Общее количество созданных топливозаправщиков
garagepoint = 300          # Точка гаража. Эту цифру надо взять у разработчика Диспетчера движения
protokol = "http://"       # Протокол
gas = 'gas'                # Название в URL объекта "Заправка"
plane = 'plane'            # Название в URL объекта "Самолет"
garage = 'garage'          # Название в URL объекта "Гараж"
fueltruck = 'fueltruck'    # Название в URL объекта "Гараж"
dr = "dr"                  # Название в URL объекта "Диспетчер руления"
uno = "uno"                # Название в URL объекта "Управление наземными операциями"
frequency = 0.5            # Частота хождения по маршруту в секундах
loginfo = 'Лог:'           # Глобальная переменная, хранящая последнее сообщение
total_orders = 0           # Общее количество выполненных заказов
orders = []                # Массив заказов
tries_request = 100        # Количество попыток перезапроса
fueltrucks = []            # Массив бензовозов

class FuelTruck:
    def __init__(self, nomer, plane_id, volume_plane, order_no): # Конструктор класса: plane_id - id самолета; volume_plane - объем бака самолета; order_no - номер заказа
       self.new_mission(nomer, plane_id, volume_plane, order_no)


    def new_mission(self, nomer, plane_id, volume_plane, order_no): # Новая миссия. Обнуление переменных и прием параметров заказа.
        self.nomer = nomer                         # Номер топливозаправщика как строка '1'. Это нужно для знания к какому бензовозу обращаются
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

        wlg(f"Новая миссия бензовоза {self.nomer}. Заказ {self.order_no}")
        self.thread = threading.Thread(target=self.do_mission) # Запускаем поток для выполнения задачи
        self.thread.start()   # Запускаем поток для выполнения задачи


    def do_mission(self):     # Метод выполняет работу заправщика
        while self.busy == 1:                                           # Цикл до тех пор, пока бензовоз занят
            #time.sleep(frequency)                                       # Задержка в 1 секунду

            if self.moving_to_target_is_done():                         # Если успешно перешли к цели (обновили поле current_place)
                if self.current_place == plane:                         # Если бензовоз у самолета
                    self.total_loaded = self.total_loaded + tank_volume # Прибавляем топливо к самолету
                    self.full =  0                                      # Обнуляем топливо у бензовоза

                    if self.total_loaded > self.volume_plane:
                        self.total_loaded = self.volume_plane           # На всякий случай округляем до объема бака самолета

                    wlg(f"Заправка самолета: Всего заправлено {self.total_loaded} требуется {self.volume_plane}")

                    if self.total_loaded >= self.volume_plane:          # Если самолет заправлен полностью
                        self.send_success_to_plane()                    # Отправляем самолету сообщение об успешной заправке
                        self.send_mission_complete()                    # Отправляем сообщение в УНО - миссия завершена

                elif self.current_place == garage and self.total_loaded >= self.volume_plane: # Если бензовоз в гараже и самолет заправлен
                    self.free_fueltruck()                               # Шлем диспетчеру движения сообщение о самоликвидации
                    self.busy = 0                                       # Освобождаем грузовик для выхода из цикла
                    wlg(f"Освобождили бензовоз: {self.nomer}")

                elif self.current_place == gas:                         # Если бензовоз у заправки
                    if self.volume_plane >= tank_volume:                # Если емкость самолета бльше бензовоза
                        self.full = tank_volume                         # Бензовоз заправлен полностью
                    else:
                        self.full = self.volume_plane                   # Иначе заправляем на величину емкости самолета

            self.set_next_target_place()                                # Назначаем новый целевой объект (обновляем поле next_target_place)

    def free_fueltruck(self):        # Метод отправляет уведомление диспетчеру движения о самоликвидации
        url = f"{protokol}{ip_dr}:{port}/dispatcher/garage/free/{self.current_checkpoint}"
        wlg(f"Отправка диспетчеру сообщения об особождении бензовоза {self.nomer}: {url}")

        if is_dispatcher:            # Заглушка для режима тестирования.
            wlg(f"Заглушка. Бензовоз {self.nomer} свободен")
            return

        response = requests.delete(url) # Отправка запроса

        if response.status_code == 200: # Если ответ получен то
            wlg(f"Бензовоз {self.nomer} свободен")
            return
        else:
            wlg(f"Ошибка отправки диспетчеру сообщения об особождении бензовоза {self.nomer}: {response.status_code}, адрес: {url}")        
        return


    def get_checkpoint_massiv(self): # Метод запрашивает маршрут до целевого объекта
        checkpoints = []             # Пустой массив чекпойнтов
        cnt = 0 # Попытка

        while cnt <= tries_request: # Цикл запроса пути до цели
            #time.sleep(frequency)
            cnt = cnt + 1

            if self.next_target_place == plane:
                url = f"{protokol}{ip_dr}:{port}/dispatcher/plane/fueltruck/{self.current_checkpoint}/{self.plane_id}"
            elif self.current_place == plane and self.next_target_place == gas:
                url = f"{protokol}{ip_dr}:{port}/dispatcher/plane/{self.current_checkpoint}/gas"
            else:
                url = f"{protokol}{ip_dr}:{port}/dispatcher/{self.current_checkpoint}/{self.next_target_place}"

            wlg(f"Отправка запроса пути от {self.current_place} к {self.next_target_place}: {url}")

            if is_dispatcher:            # Заглушка для режима тестирования
                checkpoints = [1, 2, 3]
                wlg(f"Заглушка. Путь от {self.current_place} к {self.next_target_place} получен: точек {len(checkpoints)}")
                return checkpoints
            

            response = requests.get(url) # Отправка запроса

            if response.status_code == 200: # Если ответ получен то
                checkpoints = response.json() # Преобразуем json в массив
                wlg(f"Путь с массивом чекпойнтов получен: точек {len(checkpoints)}")
                wlg(f"Точки маршрута: {checkpoints}")
                return checkpoints
            else:
                wlg(f"Ошибка запроса пути от {self.current_place} к {self.next_target_place}: {response.status_code}, адрес: {url}")
                
        return checkpoints      
 
    def delay(self): # Процедура задержки вместо sleep
        _ = requests.get(f"{protokol}{ip_tablo}:{port}/dep-board/api/v1/time/timeout?timeout=40")
        return

    def ask_next_point(self): # Запрос следующей точки
        if self.current_checkpoint == self.next_checkpoint: # Если чекпойнты совпадают, то и спрашивать не надо
            wlg(f"Чекпойнты совпадают: {self.current_checkpoint} = {self.next_checkpoint}")
            return True

        cnt = 0 # Попытка

        while cnt <= tries_request:  # Цикл запроса чекпойнта
            if not is_tablo:
                self.delay()           

            cnt = cnt + 1

            url = f"{protokol}{ip_dr}:{port}/dispatcher/point/{self.current_checkpoint}/{self.next_checkpoint}"

            wlg(f"Отправка запроса с чекпойнта {self.current_checkpoint} на чекпойнт {self.next_checkpoint}")

            if is_dispatcher:                                  # Заглушка для режима тестирования
                wlg(f"Заглушка: Переход с чекпойнта {self.current_checkpoint} на чекпойнт {self.next_checkpoint} разрешен")
                return True

            response = requests.get(url)                       # Отправка запроса

            if response.status_code == 200:                    # Если ответ получен то
                if response.text == 'true':                    # Латинские символы
                    wlg(f"Переход с чекпойнта {self.current_checkpoint} на чекпойнт {self.next_checkpoint} разрешен:")
                    return True
                else:
                    wlg(f"Переход с чекпойнта {self.current_checkpoint} на чекпойнт {self.next_checkpoint} запрещен:")
                    return False
            else:
                wlg(f"Ошибка запроса перехода с чекпойнта {self.current_checkpoint} на чекпойнт {self.next_checkpoint}: {response.status_code}, адрес: {url}")

        return False


    def moving_to_target_is_done(self):                   # Этот метод отвечает за движение от одного объекта до другого
        if self.current_place == self.next_target_place:  # Если текущее положение и цель одинаковы, то ничего не делаем
            return True

        wlg(f"Движемся к {self.next_target_place}")

        checkpoints = []                                               # Пустой массив чекпойнтов

        while True:                                                    # Цикл по количеству попыток. После 5 попыток запрашивается новый путь
            checkpoints = self.get_checkpoint_massiv()                 # Запрашиваем массив чекпойнтов до цели
            index = 0                                                  # Предполагаем, что в массиве нулевой чекпойнт - это текущий, по этому начинаем с первого а не с нулевого
            cnt_tries = 0                                              # Счетчик количества попыток пройти по маршруту

            while index < len(checkpoints):                            # Перебор чекпойнтов с прерыванием по количеству попыток
                self.next_checkpoint = checkpoints[index]              # Берем из массива следующий чекпойнт
    
                while cnt_tries < 5:                                   # Цикл ожидающий разрешение на движение
                    cnt_tries = cnt_tries + 1                          # Наращиваем счетчик количества попыток

                    if self.ask_next_point():                          # Если разрешили переход на следующий чекпойнт, то
                        oldpoint = self.current_checkpoint
                        self.current_checkpoint = self.next_checkpoint # Переходим на новый чекпойнт
                        index = index + 1                              # Наращиваем счетчик
                        wlg(f"Чекпойнт {oldpoint}. Разрешен переход на следующий чекпойнт: {self.next_checkpoint}")
                        cnt_tries = 0                                  # Сбрасываем счетчик попыток
                        break
                    else:
                        wlg(f"Чекпойнт {self.current_checkpoint}. Ожидание следующего чекпойнта: {self.next_checkpoint}. Количество попыток {cnt_tries}") # Если не разрешили, то индекс массива не наращиваем и ждем
                # Конец цикла по количеству попыток
                if cnt_tries >= 5:                                     # После 5 попыток выходим из цикла для поиска нового пути
                    break        
            # Конец цикла по массиву чекпойтнов
            if index >= len(checkpoints):                              # Если дошли до конца массива
                break                                                  # Выходим из цикла
        # Конец цикла по запросу путей

        self.current_place = self.next_target_place                    # Переопределяем текущий объект
        wlg(f"Достигли {self.next_target_place}")

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

        wlg(f"Смена целевого объекта: Текущее {self.current_place}, Целевое {self.next_target_place}. Статус: full {self.full}, total_loaded {self.total_loaded}, volume_plane {self.volume_plane}")


    def send_success_to_plane(self): # Метод отправки сообщения об успехе самолету
        url = f"{protokol}{ip_plane}:{port}/refuel/{self.plane_id}"

        wlg(f"Отправка уведомления самолету {self.plane_id}: {url}")

        if is_plane: # Заглушка для режима тестирования
            wlg(f"Заглушка: Уведомление самолету {self.plane_id} отправлено успешно")
            return 

        response = requests.get(url)

        if response.status_code == 200: # Если ответ получен то
           wlg(f"Уведомление самолету {self.plane_id} отправлено успешно")
           return
        else:
           wlg(f"Ошибка отправки уведомления самолету {self.plane_id}: {response.status_code}, адрес: {url}")

        return


    def send_mission_complete(self):  # Метод отправки сообщения о завершении миссии в УНО
        global total_orders

        url = f"{protokol}{ip_uno}:{port}/{uno}/api/v1/order/successReport/{self.order_no}/tanker-truck"

        wlg(f"Отправка уведомления в УНО о выполнении заказа {self.order_no}: {url}")

        if is_uno: # Заглушка для режима тестирования
            total_orders = total_orders + 1
            wlg(f"Заглушка: Уведомление в УНО о выполнении заказа {self.order_no} отправлено успешно") 
            return

        response = requests.post(url)
 
        if response.status_code == 200: # Если ответ получен то
           wlg(f"Уведомление в УНО о выполнении заказа {self.order_no} отправлено успешно")
           total_orders = total_orders + 1
           return
        else:
           wlg(f"Ошибка отправки уведомления в УНО: {response.status_code}, адрес: {url}")


def create_app():
    app = Flask(__name__)

    @app.route('/fueltruck/order/<int:order_no>/<int:volume_plane>/<int:plane_id>')
    def serve_order(order_no, volume_plane, plane_id):                            # Процедура приема заказа
        wlg(f"Прием заказа: Заказ {order_no}, Объем {volume_plane}. ID самолета {plane_id}")
        global total_trucks, orders, fueltrucks

        if total_trucks < max_trucks:                                             # Если не все бензовозы созданы
            if order_no not in orders:
                orders.append(order_no)                                               # Если заказ не в работе то добавляем список в работе 
                wait = 0
                while not garage_free() and wait <= 100000:                            # Включаем режим ожидания освобождения точки гаража
                    time.sleep(0.1)
                    wait = wait + 1

                total_trucks = total_trucks + 1                                       # Наращиваем количество бензовозов
                truck = FuelTruck(total_trucks, plane_id, volume_plane, order_no)     # Создаем бензовоз. Там же в конструкторе создается поток
                fueltrucks.append(truck)                                              # Добавляем в массив
                wlg(f"Создали новый бензовоз: {len(fueltrucks)}. Заказ {order_no}. Объем {volume_plane}. ID самолета {plane_id}")
            # Конец условия если заказ не в списке orders
        else:                                                             # Все грузовики заняты
            if order_no not in orders:                                    # Проверяем, в работе ли заказ 
                orders.append(order_no)                                   # Если заказ не в работе то добавляем список в работе                                                                
                wlg(f"Ищем свободный бензовоз: заказ {order_no}. Объем {volume_plane}, ID самолета {plane_id}")

                cnt = 0

                while cnt <= 100000:                                                      # Цикл поиска свободного бензовоза. Один миллион попыток
                    time.sleep(0.1)                                                       # Задержка 0.1
                    index = 0                                                             # Начинаем индекс с 0

                    while index < len(fueltrucks):                                        # Цикл по бензовозам
                        truck = fueltrucks[index]                                         # Достаем очередной бензовоз
                        if truck.busy == 0:                                               # Если бензовоз свободен
                            wlg(f"Бензовоз {index + 1} найден: Заказ {order_no}. Заказано {volume_plane} литров топлива. ID самолета {plane_id}")
                            wait = 0
                            while not garage_free() and wait <= 100000:                    # Включаем режим ожидания освобождения точки гаража
                                time.sleep(0.1)
                                wait = wait + 1

                            truck.new_mission(index + 1, plane_id, volume_plane, order_no)    # Запуск новой миссии
                            wlg(f"Бензовоз {index + 1} запущен: Заказ {order_no}. Заказано {volume_plane} литров топлива. ID самолета {plane_id}")
                            return "success"
    
                        index = index + 1                                                 # Наращиваем счетчик
                    # Конец цикла по index
                    cnt = cnt + 1
                # Конец цикла по cnt
                wlg(f"Свободный бензовоз не найден: {order_no}, {volume_plane}, {plane_id}, попыток {cnt}")
                return "Заказ не выполнен: Свободный бензовоз не найден"
            # Конец условия если заказ не в списке orders
        return f"Заказ {order_no} принят в работу. Заказано {volume_plane} литров топлива. ID самолета {plane_id}"

    @app.route('/gas', methods=['GET', 'POST'])
    def gas():
        global max_trucks, total_trucks, frequency, loginfo, tank_volume, total_orders

        if request.method == 'POST':
            # Обновление переменных на основе данных формы
            max_trucks = int(request.form['max_trucks'])
            tank_volume = int(request.form['tank_volume'])

        # Отображение HTML-страницы с текущими значениями переменных
        return render_template("fueltruck2.html", max_trucks=max_trucks, total_trucks=total_trucks, loginfo=loginfo, tank_volume=tank_volume, total_orders=total_orders)
    return app


def wlg(word): # Процедура выводит в консоль отладочные сообщения
    if is_debugmode:
        global loginfo
        
        if len(loginfo) >= 32767:
            loginfo = word
        else:    
            loginfo = loginfo + "\n" + word

        print(word)


def garage_free():        # Запрос доступности точки гаража
    url = f"{protokol}{ip_dr}:{port}/dispatcher/garage/fuel_truck"

    if is_dispatcher:        # Заглушка для режима тестирования
        wlg(f"Заглушка спавна: Спавн разрешен")
        return True

    wlg(f"Отправка запроса на спавн: {url}")
    response = requests.get(url)                       # Отправка запроса

    if response.status_code == 200:                    # Если ответ получен то
        if response.text == 'true':                    # Латинские символы
            wlg(f"Спавн разрешен")
            return True
        else:
            wlg(f"Спавн запрещен")
            return False
    else:
        wlg(f"Ошибка запроса на спавн: {response.status_code}, адрес: {url}")

    return False


def main():
    app = create_app()
    wlg("Запуск сервера")
    app.run(debug=True, host=host, port=port) # Доступен на всех интерфейсах сети

if __name__ == '__main__':
    main()
