// "DINO Autofocus.exe": starts the web app server with the repo's uv env (no console) and
// opens the browser. Built by tools\launcher\build.ps1; see docs\runbooks\launcher.md.
//   click             server already answering -> open the browser; else start it, wait for
//                     GET /api/health, then open the browser
//   Ctrl + click      stop the server, or --stop: POST /api/shutdown first (the engine switches
//                     the lights off and finishes its records), wait up to ShutdownWaitSec for
//                     /api/health to go quiet, and only then kill the process tree it started.
//                     Every stop and how it ended goes to launcher.log next to server.log.
// Remote view is never switched on here: the server binds 127.0.0.1 only.
// Tests set DINO_AF_LAUNCHER_HEADLESS=<file>: messages, confirmations (answered OK) and browser
// opens are appended to that file instead of shown, no window opens, and server.log /
// server.pid go next to it instead of %LOCALAPPDATA%\dino-autofocus.
// Compiled by the .NET Framework csc (C# 5): no string interpolation, no ?. operator.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("DINO Autofocus")]
[assembly: System.Reflection.AssemblyProduct("dino-autofocus")]

static class Program
{
    // build.ps1 rewrites these two lines (the clone it is run from, and -Port)
    const string Repo = @"D:\AutoFocus\dino-autofocus";
    const int Port = 8765;

    const string Title = "DINO Autofocus";
    const int StartTimeoutSec = 60;  // the first `uv run` after a pull may sync the env
    const int ShutdownPostTimeoutMs = 20000;  // the engine aborts, switches off, finishes records
    const int ShutdownWaitSec = 10;  // then /api/health must stop answering within this

    static string Url { get { return "http://127.0.0.1:" + Port + "/"; } }

    static readonly string Headless = Environment.GetEnvironmentVariable("DINO_AF_LAUNCHER_HEADLESS");

    static string DataDir
    {
        get
        {
            if (!string.IsNullOrEmpty(Headless))
                return Path.GetDirectoryName(Path.GetFullPath(Headless));
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(local, "dino-autofocus");
        }
    }

    static string LogPath { get { return Path.Combine(DataDir, "server.log"); } }
    static string PidPath { get { return Path.Combine(DataDir, "server.pid"); } }
    static string LauncherLogPath { get { return Path.Combine(DataDir, "launcher.log"); } }

    // One line per stop: when, what was asked, how it ended. server.log stays the server's own.
    static void LauncherLog(string text)
    {
        try
        {
            Directory.CreateDirectory(DataDir);
            File.AppendAllText(LauncherLogPath, string.Format("{0:yyyy-MM-dd HH:mm:ss} {1}\r\n",
                                                            DateTime.Now, text), new UTF8Encoding(false));
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        Note("log", text);
    }

    // ---- uv ----------------------------------------------------------------------------

    static string FindUv()
    {
        foreach (string dir in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            try
            {
                if (dir.Trim().Length == 0) continue;
                string p = Path.Combine(dir.Trim(), "uv.exe");
                if (File.Exists(p)) return p;
            }
            catch (ArgumentException) { }
        }
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string[] standard = {
            Path.Combine(home, @".local\bin\uv.exe"),               // official installer
            Path.Combine(home, @".cargo\bin\uv.exe"),               // older installer
            Path.Combine(local, @"Microsoft\WinGet\Links\uv.exe"),  // winget
            Path.Combine(home, @"scoop\shims\uv.exe"),              // scoop
        };
        foreach (string p in standard)
            if (File.Exists(p)) return p;
        return null;
    }

    // ---- server probes -----------------------------------------------------------------

    static bool HealthOk(int timeoutMs)
    {
        try
        {
            var req = (HttpWebRequest)WebRequest.Create(Url + "api/health");
            req.Timeout = timeoutMs;
            req.ReadWriteTimeout = timeoutMs;
            req.Proxy = null;
            using (var resp = (HttpWebResponse)req.GetResponse())
                return resp.StatusCode == HttpStatusCode.OK;
        }
        catch (WebException) { return false; }
    }

    static bool PortOpen()
    {
        try
        {
            using (var c = new TcpClient())
            {
                IAsyncResult r = c.BeginConnect(IPAddress.Loopback, Port, null, null);
                if (!r.AsyncWaitHandle.WaitOne(300)) return false;
                c.EndConnect(r);
                return true;
            }
        }
        catch (SocketException) { return false; }
    }

    // ---- messages ----------------------------------------------------------------------

    static bool Note(string kind, string text)
    {
        if (string.IsNullOrEmpty(Headless)) return false;
        File.AppendAllText(Headless, kind + ": " + text.Replace("\n", "\n    ") + "\r\n",
                           new UTF8Encoding(false));
        return true;
    }

    static void Error(string text)
    {
        if (Note("error", text)) return;
        MessageBox.Show(text, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    static void Info(string text)
    {
        if (Note("info", text)) return;
        MessageBox.Show(text, Title, MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    static bool Confirm(string text)
    {
        if (Note("confirm", text)) return true;
        return MessageBox.Show(text, Title, MessageBoxButtons.OKCancel, MessageBoxIcon.Question)
               == DialogResult.OK;
    }

    static string LogTail(int lines)
    {
        try
        {
            using (var fs = new FileStream(LogPath, FileMode.Open, FileAccess.Read,
                                           FileShare.ReadWrite | FileShare.Delete))
            using (var sr = new StreamReader(fs))
            {
                string[] all = sr.ReadToEnd().Replace("\r", "").TrimEnd().Split('\n');
                int from = Math.Max(0, all.Length - lines);
                return string.Join("\n", all, from, all.Length - from);
            }
        }
        catch (IOException) { return ""; }
    }

    static void OpenBrowser()
    {
        if (Note("browser", Url)) return;
        Process.Start(new ProcessStartInfo(Url) { UseShellExecute = true });
    }

    // ---- start / stop ------------------------------------------------------------------

    // The server runs under a hidden cmd.exe that appends its output to the log file, so
    // nothing has to stay alive here to drain pipes. server.pid records that cmd.exe.
    static Process StartServer(string uv)
    {
        Directory.CreateDirectory(DataDir);
        string prev = Path.Combine(DataDir, "server.prev.log");
        try
        {
            if (File.Exists(LogPath)) { File.Delete(prev); File.Move(LogPath, prev); }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }

        string args = "run python -m dino_autofocus.server --port " + Port;
        File.WriteAllText(LogPath, string.Format("# {0:yyyy-MM-dd HH:mm:ss} {1} {2}\r\n# cwd {3}\r\n",
                                                 DateTime.Now, uv, args, Repo), new UTF8Encoding(false));
        string line = "\"" + uv + "\" " + args + " >> \"" + LogPath + "\" 2>&1";
        var psi = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "cmd.exe"),
                                       "/d /s /c \"" + line + "\"");
        psi.WorkingDirectory = Repo;
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        Process p = Process.Start(psi);
        File.WriteAllText(PidPath, p.Id + " " + p.StartTime.ToFileTimeUtc());
        return p;
    }

    // The process recorded in server.pid, if it is still the one this launcher started.
    static Process RecordedServer()
    {
        try
        {
            string[] parts = File.ReadAllText(PidPath).Trim().Split(' ');
            Process p = Process.GetProcessById(int.Parse(parts[0]));
            if (!p.HasExited && p.StartTime.ToFileTimeUtc() == long.Parse(parts[1])) return p;
        }
        catch (Exception e)
        {
            if (!(e is IOException || e is ArgumentException || e is FormatException
                  || e is IndexOutOfRangeException || e is InvalidOperationException
                  || e is UnauthorizedAccessException || e is System.ComponentModel.Win32Exception))
                throw;
        }
        return null;
    }

    // POST /api/shutdown: the engine aborts, switches the lights off with readback and finishes
    // its records, then the server exits. Returns the HTTP status, or 0 when nothing answered.
    static int PostShutdown(out string body)
    {
        body = "";
        try
        {
            var req = (HttpWebRequest)WebRequest.Create(Url + "api/shutdown");
            req.Method = "POST";
            req.ContentType = "application/json";
            req.Timeout = ShutdownPostTimeoutMs;
            req.ReadWriteTimeout = ShutdownPostTimeoutMs;
            req.Proxy = null;
            byte[] data = Encoding.UTF8.GetBytes("{\"reason\": \"launcher stop\"}");
            req.ContentLength = data.Length;
            using (Stream s = req.GetRequestStream()) s.Write(data, 0, data.Length);
            using (var resp = (HttpWebResponse)req.GetResponse())
            using (var sr = new StreamReader(resp.GetResponseStream()))
            {
                body = sr.ReadToEnd();
                return (int)resp.StatusCode;
            }
        }
        catch (WebException e)
        {
            var resp = e.Response as HttpWebResponse;
            if (resp == null) { body = e.Message; return 0; }
            using (resp)
            using (var sr = new StreamReader(resp.GetResponseStream()))
            {
                body = sr.ReadToEnd();
                return (int)resp.StatusCode;
            }
        }
    }

    // True once /api/health stops answering and (if known) the process tree has exited.
    static bool WaitStopped(Process p, int seconds)
    {
        DateTime end = DateTime.Now.AddSeconds(seconds);
        while (true)
        {
            bool alive = (p != null && !p.HasExited) || HealthOk(500);
            if (!alive) return true;
            if (DateTime.Now >= end) return false;
            Thread.Sleep(250);
        }
    }

    static void KillTree(Process p)
    {
        // cmd.exe -> uv.exe -> python.exe: end the whole tree
        var kill = new ProcessStartInfo("taskkill", "/PID " + p.Id + " /T /F");
        kill.UseShellExecute = false;
        kill.CreateNoWindow = true;
        using (Process k = Process.Start(kill)) k.WaitForExit(10000);
    }

    static void StopServer()
    {
        Process p = RecordedServer();
        bool answering = HealthOk(1500);
        if (p == null && !answering)
        {
            LauncherLog("stop: no server running (already gone)");
            try { File.Delete(PidPath); } catch (IOException) { }
            Info("No DINO Autofocus server is running."
                 + (PortOpen() ? "\n\nSomething else is listening on port " + Port + "." : ""));
            return;
        }
        string whose = p != null ? "" : "\n\nThis launcher did not start it: it is stopped through "
                                        + "the server only, never killed.";
        if (!Confirm("Stop the DINO Autofocus server (" + Url + ")?\n\n"
                     + "The engine switches the lights off and finishes its records first. "
                     + "Open pages lose their connection." + whose)) return;

        string body;
        int code = PostShutdown(out body);
        bool accepted = code >= 200 && code < 300;
        LauncherLog("stop: POST /api/shutdown -> " + (code == 0 ? "no answer" : code.ToString())
                    + (body.Length > 0 ? " " + body.Replace("\r", " ").Replace("\n", " ") : ""));
        if (WaitStopped(p, ShutdownWaitSec))
        {
            LauncherLog(accepted ? "stop: graceful, server exited"
                                 : "stop: server gone without a graceful answer");
            try { File.Delete(PidPath); } catch (IOException) { }
            Info(accepted
                 ? "The server stopped: lights off and records finished by the engine."
                 : "The server is gone, but it did not confirm a graceful stop (HTTP " + code
                   + "). Check the lights on the microscope.\n\nLog: " + LauncherLogPath);
            return;
        }
        if (p == null)
        {
            LauncherLog("stop: still answering after " + ShutdownWaitSec + " s; not started by "
                        + "this launcher, not killed");
            Error("The server did not stop within " + ShutdownWaitSec + " s. This launcher did not "
                  + "start it, so it is not killed from here: stop it where it runs (Ctrl+C in "
                  + "its terminal).\n\nLog: " + LauncherLogPath);
            return;
        }
        KillTree(p);
        bool gone = WaitStopped(p, 5);
        LauncherLog("stop: no exit within " + ShutdownWaitSec + " s of the shutdown request; "
                    + "FORCED KILL (taskkill /T /F) " + (gone ? "done" : "did not end it"));
        try { File.Delete(PidPath); } catch (IOException) { }
        Error("The server did not exit within " + ShutdownWaitSec + " s, so it was killed "
              + "(forced). " + (accepted
                                ? "The engine had accepted the shutdown, so the lights should be off,"
                                : "The engine did not confirm the shutdown (HTTP " + code + "),")
              + " but check the lights on the microscope.\n\nLog: " + LauncherLogPath);
    }

    // ---- waiting window ----------------------------------------------------------------

    static bool PollHealth(Process server, Func<bool> cancelled)
    {
        DateTime end = DateTime.Now.AddSeconds(StartTimeoutSec);
        while (!cancelled() && DateTime.Now < end && !server.HasExited)
        {
            if (HealthOk(1000)) return true;
            Thread.Sleep(400);
        }
        return false;
    }

    // A small "starting" window while the server comes up. True once /api/health answers;
    // false on timeout, when the server exits, or when the user closes the window.
    static bool WaitForServer(Process server)
    {
        if (Note("wait", Url + "api/health"))
            return PollHealth(server, delegate { return false; });

        var form = new Form();
        form.Text = Title;
        form.FormBorderStyle = FormBorderStyle.FixedDialog;
        form.MaximizeBox = false;
        form.MinimizeBox = false;
        form.StartPosition = FormStartPosition.CenterScreen;
        form.ClientSize = new Size(380, 70);
        form.Font = new Font("Segoe UI", 10f);
        try { form.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
        catch (ArgumentException) { }
        var label = new Label();
        label.Dock = DockStyle.Fill;
        label.TextAlign = ContentAlignment.MiddleCenter;
        label.Text = "Starting the server on " + Url + " ...";
        form.Controls.Add(label);

        bool ok = false;
        bool done = false;
        form.FormClosing += delegate { done = true; };
        var poll = new Thread(delegate ()
        {
            ok = PollHealth(server, delegate { return done; });
            try { form.BeginInvoke((MethodInvoker)delegate { form.Close(); }); }
            catch (InvalidOperationException) { }  // already closed by the user
        });
        poll.IsBackground = true;
        form.Shown += delegate { poll.Start(); };
        Application.Run(form);
        return ok;
    }

    static void ReportStartFailure(Process server)
    {
        string why = server.HasExited
            ? "The server stopped while starting."
            : "The server did not answer " + Url + "api/health within " + StartTimeoutSec
              + " s. It may still be starting: click the launcher again to keep waiting, or "
              + "Ctrl + click to stop it.";
        string tail = LogTail(12);
        Error(why + "\n\nLog: " + LogPath + (tail.Length > 0 ? "\n\n" + tail : ""));
    }

    // ---- main --------------------------------------------------------------------------

    [STAThread]
    static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Keys mods = Control.ModifierKeys;
        bool stop = Array.IndexOf(args, "--stop") >= 0 || (mods & Keys.Control) != 0;

        if (stop) { StopServer(); return; }

        if (!Directory.Exists(Repo))
        {
            Error("Repository not found:\n" + Repo + "\n\nRebuild the launcher from the clone "
                  + "you use (tools\\launcher\\build.ps1).");
            return;
        }
        string uv = FindUv();
        if (uv == null)
        {
            Error("uv not found (PATH, %USERPROFILE%\\.local\\bin, winget, scoop).\n\n"
                  + "Install uv, run `uv sync` in\n" + Repo + "\nand try again.");
            return;
        }
        if (HealthOk(1500)) { OpenBrowser(); return; }

        // A server from an earlier click may still be starting: wait for it, never start a second.
        Process mine = RecordedServer();
        if (mine != null)
        {
            if (WaitForServer(mine)) OpenBrowser(); else ReportStartFailure(mine);
            return;
        }
        if (PortOpen())
        {
            Error("Port " + Port + " is in use, but no DINO Autofocus server answers there\n("
                  + Url + "api/health).\n\nClose the program using the port, or rebuild the "
                  + "launcher with another port (build.ps1 -Port N).");
            return;
        }

        string module = Path.Combine(Repo, @"src\dino_autofocus\server\__main__.py");
        if (!File.Exists(module))
        {
            Error("Server not found in this clone:\n" + module + "\n\n"
                  + "Pull the latest main (the web server comes with task T-009), run `uv sync`, "
                  + "and try again.");
            return;
        }

        Process server;
        try { server = StartServer(uv); }
        catch (Exception e)
        {
            Error("Could not start the server:\n" + e.Message + "\n\nLog: " + LogPath);
            return;
        }
        if (WaitForServer(server)) OpenBrowser(); else ReportStartFailure(server);
    }
}
