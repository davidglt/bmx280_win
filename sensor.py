import bmx280

sensor = bmx280.BMX280(0, 0x76)

print(f"Temperature: {sensor.temperature} °C")
print(f"Pressure: {sensor.pressure}")
print(f"Humidity: {sensor.humidity} %")
