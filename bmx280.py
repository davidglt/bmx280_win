'''
Fork from lemariva/uPySensors/bmx280.py, https://github.com/lemariva/uPySensors
Modified by Chris Wallace, Jan 2021
Windows ported by David Gonzalez, Nov 2024
'''

from i2cpy import I2C
from struct import unpack as unp
import time

NORMAL = 0

BMX280_TEMP_OS_SKIP = 0
BMX280_TEMP_OS_1 = 1
BMX280_TEMP_OS_2 = 2
BMX280_TEMP_OS_4 = 3
BMX280_TEMP_OS_8 = 4
BMX280_TEMP_OS_16 = 5

BMX280_PRES_OS_SKIP = 0
BMX280_PRES_OS_1 = 1
BMX280_PRES_OS_2 = 2
BMX280_PRES_OS_4 = 3
BMX280_PRES_OS_8 = 4
BMX280_PRES_OS_16 = 5

# BMP280 Temperature Registers
BMX280_REGISTER_DIG_T1 = 0x88
BMX280_REGISTER_DIG_T2 = 0x8A
BMX280_REGISTER_DIG_T3 = 0x8C
# BMP280 Pressure Registers
BMX280_REGISTER_DIG_P1 = 0x8E
BMX280_REGISTER_DIG_P2 = 0x90
BMX280_REGISTER_DIG_P3 = 0x92
BMX280_REGISTER_DIG_P4 = 0x94
BMX280_REGISTER_DIG_P5 = 0x96
BMX280_REGISTER_DIG_P6 = 0x98
BMX280_REGISTER_DIG_P7 = 0x9A
BMX280_REGISTER_DIG_P8 = 0x9C
BMX280_REGISTER_DIG_P9 = 0x9E

BME280_REGISTER_DIG_H1 = 0xA1
BME280_REGISTER_DIG_H2 = 0xE1
BME280_REGISTER_DIG_H3 = 0xE3
BME280_REGISTER_DIG_H4 = 0xE4
BME280_REGISTER_DIG_H5 = 0xE5
BME280_REGISTER_DIG_H6 = 0xE6
BME280_REGISTER_DIG_H7 = 0xE7

BMX280_REGISTER_ID = 0xD0
BMX280_REGISTER_RESET = 0xE0
BMX280_REGISTER_STATUS = 0xF3
BMX280_REGISTER_CONTROL = 0xF4
BMX280_REGISTER_CONFIG = 0xF5  # IIR filter config

BMX280_REGISTER_DATA = 0xF7

BMX280_BMP_CHIP_ID = 0x58  # temperature and pressure
BMX280_BME_CHIP_ID = 0x60  # temperature pressure and humidity

class MPUException(OSError):
    '''
    Exception for MPU devices
    '''
    pass

class BMX280():
    _I2Cerror = "I2C failure when communicating with the BMP/E"
 
    def __init__(self, i2c, addr):
        
        self._i2c_addr = addr
        self._i2c = I2C(i2c)
        self._chip_id = self.chip_id  
        
        self._buf1 = bytearray(1)
        self._buf2 = bytearray(2)
        self._load_calibration()
        
        self._t_os = BMX280_TEMP_OS_2  # temperature oversampling
        self._p_os = BMX280_PRES_OS_16  # pressure oversampling

        self._t_raw = 0
        self._t_fine = 0
        self._t = 0

        self._p_raw = 0
        self._p = 0

        self._read_wait_ms = 100 
        self._new_read_ms = 200 
        self._last_read_ts = 0
        

    def _read(self, memaddr, size=1):
        data = self._i2c.readfrom_mem(self._i2c_addr, memaddr, size)
        return data
        
    def _write(self, addr, b_arr):
        if not type(b_arr) is bytearray:
            b_arr = bytearray([b_arr])
        return self._i2c.writeto_mem(self._i2c_addr, addr, b_arr)

    def _load_calibration(self):
        # read calibration data
        # < little-endian
        # H unsigned short
        # h signed short
        self._T1 = unp('<H', self._read(BMX280_REGISTER_DIG_T1, 2))[0]
        self._T2 = unp('<h', self._read(BMX280_REGISTER_DIG_T2, 2))[0]
        self._T3 = unp('<h', self._read(BMX280_REGISTER_DIG_T3, 2))[0]
        self._P1 = unp('<H', self._read(BMX280_REGISTER_DIG_P1, 2))[0]
        self._P2 = unp('<h', self._read(BMX280_REGISTER_DIG_P2, 2))[0]
        self._P3 = unp('<h', self._read(BMX280_REGISTER_DIG_P3, 2))[0]
        self._P4 = unp('<h', self._read(BMX280_REGISTER_DIG_P4, 2))[0]
        self._P5 = unp('<h', self._read(BMX280_REGISTER_DIG_P5, 2))[0]
        self._P6 = unp('<h', self._read(BMX280_REGISTER_DIG_P6, 2))[0]
        self._P7 = unp('<h', self._read(BMX280_REGISTER_DIG_P7, 2))[0]
        self._P8 = unp('<h', self._read(BMX280_REGISTER_DIG_P8, 2))[0]
        self._P9 = unp('<h', self._read(BMX280_REGISTER_DIG_P9, 2))[0]

        if self._chip_id == BMX280_BME_CHIP_ID:
            self._H1 = unp('<b', self._read(BME280_REGISTER_DIG_H1, 1))[0]
            self._H2 = unp('<h', self._read(BME280_REGISTER_DIG_H2, 2))[0]
            self._H3 = unp('<b', self._read(BME280_REGISTER_DIG_H3, 1))[0]
            self._H6 = unp('<b', self._read(BME280_REGISTER_DIG_H7, 1))[0]

            h4 = unp('<b', self._read(BME280_REGISTER_DIG_H4, 1))[0]
            h4 = (h4 << 24) >> 20
            self._H4 = h4 | (
                unp('<b', self._read(BME280_REGISTER_DIG_H5, 1))[0] & 0x0F)

            h5 = unp('<b', self._read(BME280_REGISTER_DIG_H6, 1))[0]
            h5 = (h5 << 24) >> 20
            self._H5 = h5 | (
                unp('<b', self._read(BME280_REGISTER_DIG_H5, 1))[0] >> 4 & 0x0F)


    def print_calibration(self):
        print("T1: {} {}".format(self._T1, type(self._T1)))
        print("T2: {} {}".format(self._T2, type(self._T2)))
        print("T3: {} {}".format(self._T3, type(self._T3)))
        print("P1: {} {}".format(self._P1, type(self._P1)))
        print("P2: {} {}".format(self._P2, type(self._P2)))
        print("P3: {} {}".format(self._P3, type(self._P3)))
        print("P4: {} {}".format(self._P4, type(self._P4)))
        print("P5: {} {}".format(self._P5, type(self._P5)))
        print("P6: {} {}".format(self._P6, type(self._P6)))
        print("P7: {} {}".format(self._P7, type(self._P7)))
        print("P8: {} {}".format(self._P8, type(self._P8)))
        print("P9: {} {}".format(self._P9, type(self._P9)))
        if self._chip_id == BMX280_BME_CHIP_ID:
            print("H1: {} {}".format(self._H1, type(self._H1)))
            print("H2: {} {}".format(self._H2, type(self._H2)))
            print("H3: {} {}".format(self._H3, type(self._H3)))
            print("H4: {} {}".format(self._H4, type(self._H4)))
            print("H5: {} {}".format(self._H5, type(self._H5)))
            print("H6: {} {}".format(self._H6, type(self._H6)))

    def power_off(self):
        self._write(BMX280_REGISTER_CONTROL, 0)

    # normal mode
    def power_on(self):
        self._write(BMX280_REGISTER_CONTROL, 0x2F)

    def _gauge(self):
        now = int(time.time() * 1000)
        if (now - self._last_read_ts) > self._new_read_ms:
            self._last_read_ts = now
            r = self._t_os + (self._p_os << 3) + (1 << 6)
            self._write(BMX280_REGISTER_CONTROL, r)
            time.sleep(0.1) # TODO calc sleep
            if self._chip_id == BMX280_BMP_CHIP_ID:
                d = self._read(BMX280_REGISTER_DATA, 6)  # read all data at once (as by spec)
  
                self._p_raw = (d[0] << 12) + (d[1] << 4) + (d[2] >> 4)
                self._t_raw = (d[3] << 12) + (d[4] << 4) + (d[5] >> 4)
            else:
                d = self._read(BMX280_REGISTER_DATA, 8)  # read all data at once (as by spec)
                self._p_raw = (d[0] << 12) + (d[1] << 4) + (d[2] >> 4)
                self._t_raw = (d[3] << 12) + (d[4] << 4) + (d[5] >> 4)
                self._h_raw = (d[6] << 8) + d[7]

            self._t_fine = 0
            self._t = 0
            self._h = 0
            self._p = 0

    def _calc_t_fine(self):
        # From datasheet page 22
        self._gauge()
        if self._t_fine == 0:
            var1 = (((self._t_raw >> 3) - (self._T1 << 1)) * self._T2) >> 11
            var2 = (((((self._t_raw >> 4) - self._T1) * ((self._t_raw >> 4) - self._T1)) >> 12) * self._T3) >> 14
            self._t_fine = var1 + var2

    @property
    def humidity(self):
        if self._chip_id == BMX280_BME_CHIP_ID:
            var1 = self._calc_t_fine - 76800
            var1 = (((((self._h_raw << 14) - (self._H5 << 20) - (self._H5 * var1)) +
                16384) >> 15) * (((((((var1 * self._H6) >> 10) * (((var1 *
                                self._H3) >> 11) + 32768)) >> 10) + 2097152) *
                                self._H2 + 8192) >> 14))
            var1 = var1 - (((((var1 >> 15) * (var1 >> 15)) >> 7) * self._H1) >> 4)
            var1 = 0 if var1 < 0 else var1
            var1 = 419430400 if var1 > 419430400 else var1
            return var1 >> 12
        else:
            print("This is a BMP not a BME, therefore it cannot measure humidity! :(")
            return 0

    @property
    def temperature(self):
        self._calc_t_fine()
        if self._t == 0:
            self._t = ((self._t_fine * 5 + 128) >> 8) / 100.
        return self._t

    @property
    def pressure(self):
        # From datasheet page 22 (BMP) /25 (BME)
        self._calc_t_fine()
        if self._p == 0:
            var1 = self._t_fine - 128000
            var2 = var1 * var1 * self._P6
            var2 = var2 + ((var1 * self._P5) << 17)
            var2 = var2 + (self._P4 << 35)
            var1 = ((var1 * var1 * self._P3) >> 8) + ((var1 * self._P2) << 12)
            var1 = (((1 << 47) + var1) * self._P1) >> 33

            if var1 == 0:
                return 0

            p = 1048576 - self._p_raw
            p = int((((p << 31) - var2) * 3125) / var1)
            var1 = (self._P9 * (p >> 13) * (p >> 13)) >> 25
            var2 = (self._P8 * p) >> 19

            p = ((p + var1 + var2) >> 8) + (self._P7 << 4)
            self._p = p / 256.0
        return self._p


    @property
    def chip_id(self):
        try:
            chip_id = unp('<b',self._read(BMX280_REGISTER_ID, 1))[0]
        except OSError:
            raise MPUException(self._I2Cerror)
        return chip_id