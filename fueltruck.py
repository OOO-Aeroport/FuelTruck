import socket
import threading
import json
import time

class FuelTruck:
    host = '127.0.0.1' # Сервер
    port = '12345'     # Порт
    tank_volume = 30   # Вместимость топливозаправщика (в тоннах)
    max_trucks = 20    # Максимальное количество топливозаправщиков
    total_trucks = 0   # Общее количество созданных топливозаправщиков
    garagepoint = 10   # Точка гаража
    fuelstation1 = 100 # Точка станции заправки 1
    fuelstation2 = 200 # Точка станции заправки 2
    fuelstation3 = 300 # Точка станции заправки 2
    planepoint1 = 1000 # Точка площадки самолета 1
    planepoint2 = 2000 # Точка площадки самолета 2
    planepoint3 = 3000 # Точка площадки самолета 3
    planepoint4 = 4000 # Точка площадки самолета 4
    planepoint5 = 5000 # Точка площадки самолета 5
      
    def __init__(self, host, port): # Конструктор класса
        FuelTruck.total_trucks = FuelTruck.total_trucks + 1
        self.nomer = str(FuelTruck.total_trucks).zfill(2) # Номер топливозаправщика как строка '01'. Это нужно для знания к какому бензовозу обращаются
        self.busy = 0                                     # Занят ли топливозаправщик (по умолчанию свободен)
        self.full =  0                                    # Статус топливозаправщика
        self.current_checkpoint = FuelTruck.garagepoint   # Гараж. По умолчанию заправщик создается в гараже
        self.checkpoints = []                             # Пустой массив чекпойнтов
        self.next_checkpoint = 0                          # Следующий шаг чекпойнта в массиве
        self.target_checkpoint = 0                        # Целевой чекпойнт (самолет, заправка, гараж). По умолчанию не заполнен
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Создаем TCP/IP сокет
        self.client_socket.connect(FuelTruck.host, FuelTruck.port)             # Подключаемся к серверу
        self.receive_thread = threading.Thread(target=self.do_work)            # Создаем поток для получения сообщений
        self.receive_thread.start()	                      # Запускаем поток для получения сообщений

    def do_work(self): # Работа заправщика. Прослушка порта и реакция
        try:
             while True: # Бесконечный цикл по порту
                 time.sleep(0.1) 
                 data = self.client_socket.recv(2048) # Считываем пакет
                 if not data:
                     print("Сервер отключился.")
                     break

                 if (self.nomer == data[:2]): # Если обратились к нашему грузовику. Первые два символа - это номер грузовика
                     type_message = data[2:4] # Тип сообщения 01 - Массив чекпойнтов, 02 - Разрешение или запрет на движение
                     self.checkpoints = json.loads(data[4:])     # Забираем массив чекпойнтов
                     self.target_checkpoint  = self.checkpoints  # Узнаем значение целевого чекпойнта
                     index = 1 # Предполагаем, что в массиве нулевой чекпойнт - это текущий, по этому начинаем с первого а не с нулевого
                     while index < len(self.checkpoints):  # Перебор элементов с использованием while
                        self.next_checkpoint = self.checkpoints[index]
                        if(self.ask()):
                            index = index + 1

        except Exception as e:
            print(f"Ошибка при получении сообщений: {e}")

    def ask_(self): # Отправка 
        truck_dict = self.__dict__  # Получаем словарь атрибутов
        json_string = json.dumps(truck_dict, indent=4)  # Преобразуем словарь в JSON
        self.client_socket.sendall(json_string)         # Отправка данных через сокет

	


