using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Threading;

namespace SessionControl
{
    static class Program
    {
        [STAThreadAttribute]
        static void Main()
        {
            Controller ctrl = new Controller();
            Thread ctrlThread = new Thread(new ThreadStart(ctrl.run));
            ctrlThread.Start();
        }
    }
}
