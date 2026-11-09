"""Cancelamento cooperativo por tarefa; nenhum estado clínico global."""
from contextlib import contextmanager
from threading import local
from ocr_runtime import LocalReadError

class ReadCancelled(LocalReadError):pass
_context=local()
def check_cancelled(event=None):
    event=event if event is not None else getattr(_context,'event',None)
    if event is not None and event.is_set():raise ReadCancelled('Análise cancelada. Nenhum atendimento parcial foi salvo.')
def current_event():return getattr(_context,'event',None)
def page_workers():
    import os
    from pathlib import Path
    cpus=os.cpu_count() or 1;memory=0
    try:
        if os.name=='nt':
            import ctypes
            class Memory(ctypes.Structure):_fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','available','pagefile','available_pagefile','virtual','available_virtual','reserved']]
            info=Memory();info.length=ctypes.sizeof(info)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):memory=info.total
        else:
            memory=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
            quota,period=Path('/sys/fs/cgroup/cpu.max').read_text().split()
            if quota!='max':cpus=min(cpus,max(1,int(quota)//int(period)))
            limit=Path('/sys/fs/cgroup/memory.max').read_text().strip()
            if limit!='max':memory=min(memory,int(limit))
    except (OSError,ValueError,AttributeError):pass
    default=2 if cpus>=2 and memory>=4*1024**3 else 1
    try:return max(1,min(2,default,int(os.getenv('SHIFT_OCR_WORKERS',str(default)))))
    except ValueError:return 1
@contextmanager
def reading_context(event):
    old=current_event();_context.event=event
    try:check_cancelled();yield
    finally:_context.event=old
