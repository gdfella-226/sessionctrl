import subprocess
import os
import sqlite3
from pathlib import Path
from time import sleep, localtime, asctime
from datetime import datetime, timezone


class Controller:
    def __init__(self):
        '''
        Инициализация парметров значениями по умолчанию и дальнейшая попытка перезаписать их
        значениями из конфигурационного файла.
        '''
        # Путь до файла конфиграции (неизменяемый)
        self.CONFIG_PATH = "/etc/SessionControl/session.conf"
        # Путь до бинарного файла-разделителя (неизменяемый, не обязательный - используется для страховки)
        self.BIN_PATH = "/etc/SessionControl/bin"
        # Путь до лог-файла (неизменяемый)
        self.LOG_PATH = "/etc/SessionControl/session.log"
        # Задержка меду итерациями проверки (в секундах)
        self.ITERATION_TIMEOUT = 20
        # Время ожидания ракции пользователя (в секундах)
        self.DELAY = 10
        # Тип браузера (для получения журнала истории)
        self.BROWSER = "firefox"
        # Имя пользователя от которого будет запущен браузер (для получения журнала истории)
        self.USER = "user"
        
        self.copy_db_path = self.prepare_firefox_db()
        
        # Попытка чтения конфигурационного файла
        try:
            with open(self.CONFIG_PATH, 'r') as conf_file:
                for line in conf_file:
                    if 'ITER' in line:
                        self.ITERATION_TIMEOUT = int(line[line.find('=')+1:])
                    elif 'DELAY' in line:
                        self.DELAY = int(line[line.find('=')+1:])
                    elif 'BROWSER' in line:
                        self.BROWSER = line[line.find('=')+1:]
                    elif 'USER' in line:
                        self.USER = line[line.find('=')+1:]
        except Exception as err:
            # Вывод предупреждения при ошибке
            cmd = f"zenity --info --title 'Р’РЅРёРјР°РЅРёРµ!' --text 'РћС€РёР±РєР° РІ РєРѕРЅС„РёРіСѓСЂР°С†РёРѕРЅРЅРѕРј С„Р°Р№Р»Рµ!\n{err}'"
            out = subprocess.run(cmd, shell=True, executable="/bin/bash")

        self.bin_file = open(self.BIN_PATH, 'w')
        self.log_file = open(self.LOG_PATH, 'a')
    
    def get_pids(self):
        '''
        Получение идентификатора корневого процесса браузера
        return: str - "iiii" номер процесса / "" (пустая строка), если процеса нет
        '''
        try:
            cmd = f"ps aux | pgrep {self.BROWSER}"
            out = subprocess.check_output(cmd, shell=True, executable="/bin/bash")
            return out.decode("utf-8")
        except Exception:
            return ""

    def prepare_firefox_db(self):
        '''
        Подготовка базы данных с историей браузера для обеспечения возможности чтения
        История браузера хранится в sqlite БД:
            /home/$USER/snap/firefox/common/.mozilla/firefox/<id>.default/places.sqlite
        где <id> генерируется случайно. Так как при использовании браузера файл открывается для записи,
        во избежание проблем с разделенными ресурсами, с БД снимается временная копия:
            /etc/SessionControl/tmp_history.sqlite
        с которой и производится дальнейшая работа
        return: str - путь к копии БД
        '''
        # Определение полного пути до БД
        firefox_dir = Path(f'/home/{self.USER}/snap/firefox/common/.mozilla/firefox/')
        for root, dirs, files in os.walk(firefox_dir):
            for dir in dirs:
                if '.default' in dir:
                    subdir = dir            
                    break
        # Создание копии БД
        db_path = firefox_dir / subdir / 'places.sqlite'
        copy_db_path = "/etc/SessionControl/tmp_history.sqlite"
        cmd = f"cp \"{db_path}\" \"{copy_db_path}\""
        out = subprocess.run(cmd, shell=True, executable="/bin/bash")
        return copy_db_path

    def get_history(self):
        '''
        Получение последней (актуальной) записи из объединенных таблиц копии БД
        return: (str, str) - пара значений (<время посещения>, <URL>)
        '''
        db = sqlite3.connect(os.fspath(self.copy_db_path))
        cur = db.cursor()
        query = "select h.visit_date, p.url \
            from moz_historyvisits as h, moz_places as p \
            where p.id == h.place_id order by h.visit_date"
        cur.execute(query)
        output = cur.fetchall() 
        return output[-1]

    def check_history(self, prevline):
        '''
        Сравнение текущей и актуальной записи в БД
        return: bool - True если записи равны
        '''
        newline = self.get_history()
        return prevline == newline
    
    def show_alert(self):
        '''
        Вызов графической утилиты zenity для вывода уведомления
        return: int:
            - 0 - пользователь ответил на уведомление (нажал ОК)
            - 5 - пользователь не ответил на уведомление в течение указанного срока
            - 1 - окно уведомления было закрыто некорректно (из-за действий пользователя или системной ошибки)
        '''
        try:
            cmd = f"zenity --info --title 'Р’РЅРёРјР°РЅРёРµ!' --text 'РџРѕС…РѕР¶Рµ Р’Р°С€Р° СЃРµСЃСЃРёСЏ РІ Р±СЂР°СѓР·Рµ РЅРµ Р°РєС‚РёРІРЅР°! РќР°Р¶РјРёС‚Рµ РћРљ, РёРЅР°С‡Рµ РѕРЅР° Р·Р°РєСЂРѕРµС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё С‡РµСЂРµР· {str(self.DELAY)} СЃРµРєСѓРЅРґ' --ok-label OK --timeout {str(self.DELAY)}"
            out = subprocess.run(cmd, shell=True, executable="/bin/bash")
            return out.returncode
        except Exception:
            return 1

    def run(self):
        '''
        Запуск алгоритма в цикле
        '''
        self.log_file.write('\n===Service restart===\n')
        while True:
            self.log_file.write(f'[{asctime(localtime())}] Checking for browser process...\n')
            # Получение записи из истории
            prevline = self.get_history()
            # Получение id процесса браузера
            pid = self.get_pids()
            # Если есть процесс браузера и в истории нет изменений...
            if pid and self.check_history(prevline):
                self.log_file.write(f'[{asctime(localtime())}] \tFound!\n\t-Sending alert\n\t-Waiting for {self.DELAY} sec\n')
                # Вывод уведомления + ожидание действия
                confirm = self.show_alert()
                # Если пользователь не нажал ОК, завершение процесса браузера
                if confirm != 0:
                    self.log_file.write(f'[{asctime(localtime())}] Killing session ({pid})\n')
                    cmd = f"kill -9 {pid}"
                    out = subprocess.run(cmd, shell=True, executable="/bin/bash")
                else:
                    self.log_file.write(f'[{asctime(localtime())}] Session restored by user\n')
            self.log_file.write(f'[{asctime(localtime())}] Waiting for next iteration {self.ITERATION_TIMEOUT} sec\n')
            # Ожидание таймаута до следующей итерации
            sleep(self.ITERATION_TIMEOUT)
        



if __name__ == '__main__':
    ctrl = Controller()
    ctrl.run()
