using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Diagnostics;
using System.Text.RegularExpressions;
using System.Threading;
using System.IO;
using System.Runtime.InteropServices;
using System.Globalization;
using System.Data;
using System.Data.SQLite;
using System.Collections;
using System.Management;

namespace SessionControl
{
    class Controller
    {
        string BIN_PATH;
        string LOG_PATH;
        int ITERATION_TIMEOUT;
        int DELAY;
        bool enabled = true;
        bool isAccessedToHistory = false;
        //MsgBox _msgBox;

        public Controller()
        {
            string[] confData = init();
            if (confData.Length == 0)
                return;
            BIN_PATH = confData[0];
            LOG_PATH = confData[1];
            ITERATION_TIMEOUT = Int32.Parse(confData[2]);
            DELAY = Int32.Parse(confData[3]);
            //_msgBox = MsgBox.Create("Похоже ваша сессия в браузере неактивна. Она будет автоматически завершена через " + (DELAY / 1000).ToString() + " секунд\nНажмите \"Отмена\" чтобы продолжить сесиию", "Внимание", MessageBoxButtons.OKCancel);
        }

        private string exec(string task, bool getResault = false)
        {
            using (Process process = new Process())
            {
                process.StartInfo = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = "/c \"" + task + "\"",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                process.Start();

                string result;
                if (getResault)
                    result = process.StandardOutput.ReadToEnd();
                else
                    result = "";

                return result;
            }
        }

        private List<string> getPID(string processName)
        {
            string task = "tasklist | find \"" + processName + "\"";
            string result = exec(task, true);
            string[] processes = result.Split('\n');

            List<string> pids = new List<string>();
            foreach (string proc in processes)
            {
                var matches = new Regex(@"^browser\w*").Matches(proc);
                if (matches.Count > 0)
                {
                    Regex r = new Regex(@"\s+");
                    string trimmedProc = r.Replace(proc, @" ");
                    string pid = trimmedProc.Split(' ')[1];
                    pids.Add(pid);
                }
            }
            return pids;
        }


        private bool compareHistory(string prevLine) {
            if (isAccessedToHistory) {
                string newLine = checkHistory();
                File.AppendAllText(LOG_PATH, $"Сравнение: {prevLine} -- {newLine}\n");
                return newLine == prevLine;
            }
            return true;
        }


        public string checkHistory() {
            string idString = System.Security.Principal.WindowsIdentity.GetCurrent().Name;
            string userName = idString.Substring(idString.IndexOf('\\') + 1);
            string path = $@"C:\Users\{userName}\AppData\Local\Yandex\YandexBrowser\User Data\Default\History";
            string copyPath = @"C:\SessionControl\tmp\history_db_tmp_copy";

            try {
                if (File.Exists(copyPath)) {
                    GC.Collect();
                    GC.WaitForPendingFinalizers();
                    FileInfo f = new FileInfo(copyPath);
                    f.Delete();
                }
                File.Copy(path, copyPath);

                using (var connection = new SQLiteConnection($"Data Source={copyPath}")) {
                    connection.Open();
                    var command = connection.CreateCommand();
                    command.CommandText = @"SELECT * FROM visits";
                    DataTable data = new DataTable();
                    SQLiteDataAdapter adapter = new SQLiteDataAdapter(command);
                    adapter.Fill(data);
                    string line = "";
                    foreach (var cell in data.Rows[0].ItemArray)
                        line += cell.ToString();
                    isAccessedToHistory = true;
                    return line;
                }
            } catch {
                isAccessedToHistory = false;
                MessageBox.Show("Ошибка доступа к истории браузера!");
                return "";
            }
        }

        private void showalert()
        {
            /*_msgBox.TopMost = true;
            _msgBox.Activate();
            _msgBox.BringToFront();
            var result = _msgBox.ShowDialog();*/

            var result = MessageBox.Show("Похоже ваша сессия в браузере неактивна. Она будет автоматически завершена через " + (DELAY / 1000).ToString() + " секунд\nНажмите \"OK\" чтобы продолжить сесиию");
            if (result == DialogResult.OK)
                File.WriteAllText(BIN_PATH, "0");
        }

        string[] init()
        {
            string CONFIG_PATH = @"C:\SessionControl\session.conf";
            string BIN_PATH = @"C:\SessionControl\bin";
            string LOG_PATH = @"C:\SessionControl\session.log";
            int ITERATION_TIMEOUT = 60000;
            int DELAY = 10000;
            /*using (OpenFileDialog openFileDialog = new OpenFileDialog()) {
                openFileDialog.InitialDirectory = "c:\\";
                openFileDialog.Filter = "txt files (*.txt)|*.txt|All files (*.*)|*.*";
                openFileDialog.FilterIndex = 2;
                openFileDialog.RestoreDirectory = true;

                if (openFileDialog.ShowDialog() == DialogResult.OK)
                    CONFIG_PATH = openFileDialog.FileName;
            }*/
            try
            {
                foreach (string line in File.ReadLines(CONFIG_PATH))
                    if (line.Contains("BIN"))
                        BIN_PATH = line.Substring(line.IndexOf('=') + 1);
                    else if (line.Contains("LOG"))
                        LOG_PATH = line.Substring(line.IndexOf('=') + 1);
                    else if (line.Contains("ITER"))
                        ITERATION_TIMEOUT = Int32.Parse(line.Substring(line.IndexOf('=') + 1));
                    else if (line.Contains("DELAY"))
                        DELAY = Int32.Parse(line.Substring(line.IndexOf('=') + 1));
            }
            catch
            {
                MessageBox.Show("Ошибка конфигурационного файла");
                return new string[0];
            }
            return new string[] { BIN_PATH, LOG_PATH, ITERATION_TIMEOUT.ToString(), DELAY.ToString() };
        }

        public void run()
        {
            enabled = true;
            File.AppendAllText(LOG_PATH, "===== СЛУЖБА ПЕРЕЗАПУЩЕНА =====\n[" + DateTime.Now.ToString() + "]Запуск с параметрами:\n\tbin=" + BIN_PATH + "\n\tlog=" + LOG_PATH + "\n");

            while (enabled)
            {
                File.WriteAllText(BIN_PATH, "1");
                File.AppendAllText(LOG_PATH, "[" + DateTime.Now.ToString() + "] Обнаружение процессов браузера... ");
                List<string> pids = getPID("browser");
                string historyLine = checkHistory();
                if (pids.Count() > 0 && compareHistory(historyLine))
                {
                    File.AppendAllText(LOG_PATH, pids.Count().ToString() + " aктивных процессов\n\t- Вывод предупреждения\n\t- Ожидание " + (DELAY / 1000).ToString() + " сек\n");
                    Thread th = new Thread(showalert);
                    th.Start();
                    Thread.Sleep(DELAY);
                    string flag = File.ReadAllText(BIN_PATH);
                    if (flag == "1")
                    {
                        File.AppendAllText(LOG_PATH, "[" + DateTime.Now.ToString() + "] Сигнал прерывания от пользователя не обнаружен. Завершение сессии\n");
                        foreach (string pid in pids)
                        {
                            File.AppendAllText(LOG_PATH, "Killing: " + pid + "\n");
                            exec("taskkill /f /pid " + pid, false);
                        }
                        th.Abort();
                    }
                    else
                    {
                        File.AppendAllText(LOG_PATH, "[" + DateTime.Now.ToString() + "] Сессия востановлена пользователем\n");
                    }
                }
                else
                {
                    File.AppendAllText(LOG_PATH, "\n");
                }
                File.AppendAllText(LOG_PATH, "[" + DateTime.Now.ToString() + "] Ожидание следующей итерации (" + (ITERATION_TIMEOUT / 60000).ToString() + " мин)\n");
                Thread.Sleep(ITERATION_TIMEOUT);
            }
        }

        public void stop()
        {
            enabled = false;
        }
    }

}

