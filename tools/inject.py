import ctypes
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualAllocEx.restype = wintypes.LPVOID
k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
                               wintypes.DWORD, wintypes.DWORD]
k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.GetModuleHandleA.restype = wintypes.HMODULE
k32.GetModuleHandleA.argtypes = [wintypes.LPCSTR]
k32.GetProcAddress.restype = wintypes.LPVOID
k32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
k32.CreateRemoteThread.restype = wintypes.HANDLE
k32.CreateRemoteThread.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
                                   wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD,
                                   wintypes.LPVOID]

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT_RESERVE = 0x3000
PAGE_READWRITE = 0x04


def inject(pid: int, dll_path: str) -> None:
    raw = dll_path.encode("ascii") + b"\x00"
    h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    addr = k32.VirtualAllocEx(h, None, len(raw), MEM_COMMIT_RESERVE, PAGE_READWRITE)
    if not addr:
        raise ctypes.WinError(ctypes.get_last_error())
    written = ctypes.c_size_t(0)
    if not k32.WriteProcessMemory(h, addr, raw, len(raw), ctypes.byref(written)):
        raise ctypes.WinError(ctypes.get_last_error())
    load = k32.GetProcAddress(k32.GetModuleHandleA(b"kernel32.dll"), b"LoadLibraryA")
    th = k32.CreateRemoteThread(h, None, 0, load, addr, 0, None)
    if not th:
        raise ctypes.WinError(ctypes.get_last_error())
    k32.WaitForSingleObject(th, 10000)
    print("injected %s into pid %d" % (dll_path, pid))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python tools/inject.py <pid> <absolute_dll_path>")
        sys.exit(2)
    inject(int(sys.argv[1]), sys.argv[2])
