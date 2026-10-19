"""Close only owned desktop processes through their normal document-save path."""
import os
import time


def request_close(pid):
    if os.name!='nt':
        raise RuntimeError('Native editor shutdown needs its platform close-window transport; the editor remains owned.')
    import ctypes
    from ctypes import wintypes
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    user.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT]
    user.GetWindow.restype=wintypes.HWND
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    windows=[]
    @callback_type
    def collect(window,_value):
        owner=wintypes.DWORD()
        user.GetWindowThreadProcessId(window,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(window) and not user.GetWindow(window,4):
            windows.append(window)
        return True
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    if not user.EnumWindows(collect,0): raise ctypes.WinError(ctypes.get_last_error())
    if not windows: raise RuntimeError('Owned editor has no closeable window; it has not been reported OFF.')
    for window in windows:
        if not user.PostMessageW(window,0x0010,0,0): raise ctypes.WinError(ctypes.get_last_error())


def close_owned(process):
    """WM_CLOSE respects unsaved-document dialogs; never force-kill or time out."""
    if process.poll() is not None: return
    request_close(process.pid)
    if hasattr(process,'wait'):
        process.wait()
    else:
        while process.poll() is None: time.sleep(.05)
