"""Microfone: os dois jeitos de "mutar".

- "muta o microfone": só o Jarvis para de agir. O microfone segue ligado no Windows, então ele
  continua ouvindo UMA coisa: "desmuta" / "escuta" (isso é feito na tela, em jarvis.js).
- "muta o microfone do PC": muta no Windows (reunião, ligação). Aí nada escuta, nem o Jarvis:
  volta clicando no 7 da tela, que chama /api/microfone.
"""
import re
import subprocess

DESMUTAR = re.compile(r"^(?:jarvis[ ,]*)?(?:desmut\w*|desmute|ativa\w*|liga\w*|abre|volta)\s*(?:o\s+)?(?:microfone|mic)\b|"
                      r"^(?:jarvis[ ,]*)?(?:desmuta|desmute|escuta|me escuta|pode escutar|pode ouvir|volta a (?:ouvir|escutar))\b", re.I)
MUTAR = re.compile(r"\b(?:mut\w*|silenci\w*|deslig\w*|fecha|corta|bloquei\w*|tira)\s+(?:o\s+)?(?:som\s+do\s+)?(?:microfone|mic)\b|"
                   r"\b(?:microfone|mic)\s+(?:mutado|no mudo|desligado)\b|\bpara de (?:me )?(?:ouvir|escutar)\b", re.I)
DO_WINDOWS = re.compile(r"\b(?:do (?:pc|computador|windows)|de tudo|geral|pra reuni[aã]o|pra (?:a )?liga[cç][aã]o|"
                        r"pra (?:a )?call|no windows)\b", re.I)


def entender(texto):
    """"mutar" | "mutar_windows" | "desmutar" | None."""
    t = texto.strip()
    if DESMUTAR.search(t):
        return "desmutar"
    if MUTAR.search(t):
        return "mutar_windows" if DO_WINDOWS.search(t) else "mutar"
    return None


# Core Audio do Windows (IAudioEndpointVolume) no microfone padrão, sem instalar nada
_CSHARP = r"""
using System; using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {
  int a(); int b(); int c(); int d(); int e(); int f(); int g(); int h(); int i(); int j(); int k();
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool mudo, ref Guid contexto);
  int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mudo);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref Guid id, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int a(); int GetDefaultAudioEndpoint(int fluxo, int papel, out IMMDevice d); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class Enumerador {}
public static class Mic {
  static IAudioEndpointVolume Volume(int papel) {
    var en = (IMMDeviceEnumerator)new Enumerador(); IMMDevice d;
    Marshal.ThrowExceptionForHR(en.GetDefaultAudioEndpoint(1, papel, out d));  // 1 = captura (microfone)
    var id = typeof(IAudioEndpointVolume).GUID; object o;
    Marshal.ThrowExceptionForHR(d.Activate(ref id, 23, IntPtr.Zero, out o));
    return (IAudioEndpointVolume)o;
  }
  public static void Mutar(bool mudo) { var g = Guid.Empty; Volume(0).SetMute(mudo, ref g); Volume(2).SetMute(mudo, ref g); }
  public static bool Mudo() { bool m; Volume(0).GetMute(out m); return m; }
}
"""


def _rodar(chamada):
    script = f"Add-Type -TypeDefinition @'\n{_CSHARP}\n'@\n{chamada}"
    r = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return r.stdout.strip()


def mutar_windows(mudo=True):
    _rodar(f"[Mic]::Mutar(${'true' if mudo else 'false'})")


def mudo_no_windows():
    return _rodar("[Mic]::Mudo()").lower() == "true"
