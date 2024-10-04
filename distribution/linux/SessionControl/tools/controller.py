import subprocess
import os
import sqlite3
from pathlib import Path
from time import sleep, localtime, asctime
from datetime import datetime, timezone


class Controller:
    def __init__(self):
        self.CONFIG_PATH = "/etc/SessionControl/session.conf"
        self.BIN_PATH = "/etc/SessionControl/bin"
        self.LOG_PATH = "/etc/SessionControl/session.log"
        self.ITERATION_TIMEOUT = 20
        self.DELAY = 10
        self.BROWSER = "firefox"
        self.USER = "user"
        self.copy_db_path = self.prepare_firefox_db()

        try:
            with open(self.CONFIG_PATH, 'r') as conf_file:
                for line in conf_file:
                    #if 'BIN' in line:
                    #    self.BIN_PATH = line[line.find('=')+1:]
                    #elif 'LOG' in line:
                    #    self.LOG_PATH = line[line.find('=')+1:]
                    if 'ITER' in line:
                        self.ITERATION_TIMEOUT = int(line[line.find('=')+1:])
                    elif 'DELAY' in line:
                        self.DELAY = int(line[line.find('=')+1:])
                    elif 'BROWSER' in line:
                        self.BROWSER = line[line.find('=')+1:]
                    elif 'USER' in line:
                        self.USER = line[line.find('=')+1:]
        except Exception as err:
            cmd = f"zenity --info --title 'Внимание!' --text 'Ошибка в конфигурационном файле!\n{err}'"
            out = subprocess.run(cmd, shell=True, executable="/bin/bash")

        self.bin_file = open(self.BIN_PATH, 'w')
        self.log_file = open(self.LOG_PATH, 'a')
    
    def get_pids(self):
        try:
            cmd = f"ps aux | pgrep {self.BROWSER}"
            out = subprocess.check_output(cmd, shell=True, executable="/bin/bash")
            return out.decode("utf-8")
        except Exception:
            return ""

    def prepare_firefox_db(self):
        firefox_dir = Path(f'/home/{self.USER}/snap/firefox/common/.mozilla/firefox/')
        for root, dirs, files in os.walk(firefox_dir):
            for dir in dirs:
                if '.default' in dir:
                    subdir = dir            
                    break
        
        db_path = firefox_dir / subdir / 'places.sqlite'
        copy_db_path = "/etc/SessionControl/tmp_history.sqlite"
        cmd = f"cp \"{db_path}\" \"{copy_db_path}\""
        out = subprocess.run(cmd, shell=True, executable="/bin/bash")
        return copy_db_path

    def get_history(self):
        #if 'firefox' in self.BROWSER.lower():
        db = sqlite3.connect(os.fspath(self.copy_db_path))
        cur = db.cursor()
        query = "select h.visit_date, p.url \
            from moz_historyvisits as h, moz_places as p \
            where p.id == h.place_id order by h.visit_date"
        cur.execute(query)
        output = cur.fetchall() 
        return output[-1]

    def check_history(self, prevline):
        newline = self.get_history()
        return prevline == newline
    
    def show_alert(self):
        try:
            cmd = f"zenity --info --title 'Внимание!' --text 'Похоже Ваша сессия в браузе не активна! Нажмите ОК, иначе она закроется автоматически через {str(self.DELAY)} секунд' --ok-label OK --timeout {str(self.DELAY)}"
            out = subprocess.run(cmd, shell=True, executable="/bin/bash")
            return out.returncode
        except Exception:
            return 1
           

    def run(self):
        self.log_file.write('\n===Service restart===\n')
        while True:
            self.log_file.write(f'[{asctime(localtime())}] Checking for browser process...\n')
            prevline = self.get_history()
            pid = self.get_pids()
            if pid and self.check_history(prevline):
                self.log_file.write(f'[{asctime(localtime())}] \tFound!\n\t-Sending alert\n\t-Waiting for {self.DELAY} sec\n')
                confirm = self.show_alert()
                if confirm != 0:
                    self.log_file.write(f'[{asctime(localtime())}] Killing session ({pid})\n')
                    cmd = f"kill -9 {pid}"
                    out = subprocess.run(cmd, shell=True, executable="/bin/bash")
                else:
                    self.log_file.write(f'[{asctime(localtime())}] Session restored by user\n')
            self.log_file.write(f'[{asctime(localtime())}] Waiting for next iteration {self.ITERATION_TIMEOUT} sec\n')
            sleep(self.ITERATION_TIMEOUT)
        



if __name__ == '__main__':
    ctrl = Controller()
    ctrl.run()
