from ctypes import windll, Structure, c_ushort, byref, c_ulong, c_long


class SYSTEMTIME(Structure):
    _fields_ = (
        ('wYear', c_ushort),
        ('wMonth', c_ushort),
        ('wDayOfWeek', c_ushort),
        ('wDay', c_ushort),
        ('wHour', c_ushort),
        ('wMinute', c_ushort),
        ('wSecond', c_ushort),
        ('wMilliseconds', c_ushort),
    )

    def __str__(self):
        return '%4d-%02d-%02d %02d:%02d:%02d.%03d' % (
            self.wYear, self.wMonth, self.wDay,
            self.wHour, self.wMinute, self.wSecond,
            self.wMilliseconds
        )


class LONG_INTEGER(Structure):
    _fields_ = (
        ('low', c_ulong),
        ('high', c_long),
    )


class WindowsTimeHelper:
    @staticmethod
    def get_system_time():
        """
        Retrieves the current system time as a SYSTEMTIME structure.
        """
        st = SYSTEMTIME(0, 0, 0, 0, 0, 0, 0, 0)
        windll.kernel32.GetSystemTime(byref(st))
        return st

    @staticmethod
    def set_system_time(st):
        """
        Sets the system time using the provided SYSTEMTIME structure.
        """
        return windll.kernel32.SetSystemTime(byref(st))

    @staticmethod
    def get_system_file_time():
        """
        Retrieves the current system time in FILETIME format as a 64-bit integer.
        """
        ft = LONG_INTEGER(0, 0)
        st = WindowsTimeHelper.get_system_time()
        if windll.kernel32.SystemTimeToFileTime(byref(st), byref(ft)):
            return (int(ft.high) << 32) | ft.low
        return None

    @staticmethod
    def set_system_file_time(ft):
        """
        Sets the system time using a FILETIME formatted 64-bit integer.
        """
        st = SYSTEMTIME(0, 0, 0, 0, 0, 0, 0, 0)
        ft_struct = LONG_INTEGER(ft & 0xFFFFFFFF, ft >> 32)
        if windll.kernel32.FileTimeToSystemTime(byref(ft_struct), byref(st)):
            return WindowsTimeHelper.set_system_time(st)
        return False

