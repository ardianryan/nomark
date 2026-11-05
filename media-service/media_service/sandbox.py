"""Deny network socket creation in Linux image workers, including native codecs."""
import ctypes
import ctypes.util
import errno
import sys


def deny_network():
    if sys.platform != 'linux':
        return
    path = ctypes.util.find_library('seccomp')
    if not path:
        raise RuntimeError('worker_sandbox_unavailable')
    library = ctypes.CDLL(path, use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_rule_add.restype = ctypes.c_int
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_load.restype = ctypes.c_int
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7fff0000)
    if not context:
        raise RuntimeError('worker_sandbox_unavailable')
    try:
        for name in (b'socket', b'socketpair', b'connect', b'sendto', b'sendmsg', b'sendmmsg'):
            syscall = library.seccomp_syscall_resolve_name(name)
            if syscall < 0 or library.seccomp_rule_add(context, 0x00050000 | errno.EPERM, syscall, 0) != 0:
                raise RuntimeError('worker_sandbox_unavailable')
        if library.seccomp_load(context) != 0:
            raise RuntimeError('worker_sandbox_unavailable')
    finally:
        library.seccomp_release(context)
