from plc_comms import PlcComms
import time
plc = PlcComms()
plc.connect()
plc.set_k(0)
plc.set_k(1000)
plc.set_k(1234)
plc.set_k(0)
plc.disconnect()
