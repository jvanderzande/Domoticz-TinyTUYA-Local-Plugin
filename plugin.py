# Domoticz TinyTUYA Local Plugin
#
# Author: Xenomes (xenomes@outlook.com)
#
"""
<plugin key="tinytuyalocal" name="TinyTUYA (Local Control)" author="Xenomes" version="0.8" wikilink="" externallink="https://github.com/Xenomes/Domoticz-TinyTUYA-Local-Plugin.git">
    <description>
        <h2>TinyTUYA Plugin Local Controlversion Alpha 0.8</h2><br/>
        <br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>On/Off control</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>All devices that have on/off state should be supported</li>
        </ul>
    </description>
    <params>
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic + Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections + Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
try:
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
import tinytuya
# from tinytuya import Contrib
import subprocess
import platform
import os
import sys
import json
import ast
import time
import base64
import traceback
from datetime import datetime, timedelta


class BasePlugin:
    enabled = False
    def __init__(self):
        return

    def onStart(self):
        Domoticz.Log('TinyTUYA ' + Parameters['Version'] + ' plugin started')
        Domoticz.Log('TinyTuya Version:' + tinytuya.version )

        global testData

        if Parameters['Mode6'] != '0':
            Domoticz.Debugging(int(Parameters['Mode6']))
            # Domoticz.Log('Debugger started, use 'telnet 0.0.0.0 4444' to connect')
            # import rpdb
            # rpdb.set_trace()
            DumpConfigToLog()
        # Domoticz.Heartbeat(10)
        testData = False
        if os.path.isfile(Parameters['HomeFolder'] + '/testdata.on'):
            testData = True
            Domoticz.Error('!!! Warning Plugin overruled by local json file !!!')

        onCreateDevices()

    def onStop(self):
        Domoticz.Log('onStop called')

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log('onConnect called')

    def onMessage(self, Connection, Data):
        Domoticz.Log('onMessage called')

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Debug("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level) + "', Color: " + str(Color))

        # device for the Domoticz
        tuyaunit = Devices[DeviceID].Units[Unit]
        category = getConfigItem(DeviceID, 'category')
        # Domoticz.Debug('Device ID: ' + str(DeviceID))
        # Domoticz.Debug('Category: ' + str(category))
        # Domoticz.Debug('nValue: ' + str(tuyaunit.nValue))
        # Domoticz.Debug('sValue: ' + str(tuyaunit.sValue) + ' Type ' + str(type(tuyaunit.sValue)))
        # Domoticz.Debug('LastLevel: ' + str(tuyaunit.LastLevel))
        # Domoticz.Debug('Type: ' + str(tuyaunit.Type) + ' ' + str(tuyaunit.SubType) + ' ' + str(tuyaunit.SwitchType))
        # Domoticz.Debug(str(tuyadevsensors))
        # Control device and update status in Domoticz
        if Command == 'Set Level':
            if tuyaunit.Type == 244 and tuyaunit.SubType == 62 and tuyaunit.SwitchType == 18:
                mode = tuyaunit.Options['LevelNames'].split('|')
                SendCommand(DeviceID, Unit, mode[int(Level / 10)])
                UpdateDevice(DeviceID, Unit, Level, 1, 0)
            else:
                SendCommand(DeviceID, Unit, Level, category)
                UpdateDevice(DeviceID, Unit, Level, 1, 0)
        elif Command == 'Set Color':
            SendCommand(DeviceID, Unit, eval(Color), category)
            UpdateDevice(DeviceID, Unit, Color, 1, 0)
        else:
            if tuyaunit.Type == 81 and tuyaunit.SubType == 1:
                SendCommand(DeviceID, Unit, Command, category)
                UpdateDevice(DeviceID, Unit, 0, Command, 0)
            else:
                SendCommand(DeviceID, Unit, True if Command not in ['Off', 'Closed', False] else False, category)
                UpdateDevice(DeviceID, Unit, Command, 1 if Command not in ['Off', 'Closed'] else 0, 0)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log('Notification: ' + Name + ', ' + Subject + ', ' + Text + ', ' + Status + ', ' + str(Priority) + ', ' + Sound + ', ' + ImageFile)

    def onDeviceRemoved(self, DeviceID, Unit):
        Domoticz.Log('onDeviceDeleted called')

    def onDisconnect(self, Connection):
        Domoticz.Log('onDisconnect called')

    def onHeartbeat(self):
        Domoticz.Debug('onHeartbeat called')
        # if time.time() - getConfigItem(DeviceID, 'last_update') < 10:
        #     Domoticz.Debug("onHeartbeat called skipped")
        #     return
        # Domoticz.Debug("onHeartbeat called last run: " + str(time.time() - last_update))
        onHandleThread(False)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()


def onCreateDevices():
    try:
        global tuya, tuyadevsensors, last_update, result, tuya2domo
        last_update = time.time()
        tuyadevsensors = None
        if os.path.isfile(Parameters['HomeFolder'] + '/tuyadevices.json'):
            with open(Parameters['HomeFolder'] + '/tuyadevices.json') as dFile:
                tuyadevsensors = json.load(dFile)
    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())

    # Initialize/Update devices from TUYA API
    if tuyadevsensors is None:
        Domoticz.Error('tuyadevices.json is missing in the plugin folder!')
        exit

    try:
        tuya2domo = {}
        if os.path.isfile(Parameters['HomeFolder'] + '/tuya2domoticz.json'):
            with open(Parameters['HomeFolder'] + '/tuya2domoticz.json') as dFile:
                tuya2domo = json.load(dFile)
        # Domoticz.Debug('Devs: ' + str(tuyadevsensors))
        # Domoticz.Debug('Result: ' + str(result))

        Domoticz.Debug('Devices: ' + str(Devices))
        # Create devices
        for unitid, units in tuya2domo.items():
            for unit, devinfo in units.items():
                # Domoticz.Log('Check for: ' + str(unitid) + ' - ' + str(unit))
                if createDevice(unitid, unit):
                    subType = devinfo.get('subType', 1)
                    Domoticz.Log(f"Create Name={devinfo['Name']},DeviceID={unitid},Unit={unit},Type={devinfo['Type']}, Subtype={subType},Used=1")
                    Domoticz.Unit(
                        Name=devinfo['Name'],
                        DeviceID=str(unitid),
                        Unit=int(unit),
                        Type=int(devinfo['Type']),  # Temp+Hum combined
                        Subtype=int(subType),
                        Used=1
                    ).Create()
    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())

    if tuya2domo is None:
        Domoticz.Error('tuya2domoticz.json is missing in the plugin folder!')
        exit


def onHandleThread(startup):
    # Run for every device on startup and heartbeat
    try:
        # Update devices
        for unitid, unitinfo in tuya2domo.items():
            # Domoticz.Debug( 'Device name=' + str(tuyaunit['name']) + ' id=' + str(tuyaunit['id']) + ' ip=' + str(tuyaunit['ip']) + ' version=' + str(tuyaunit['version'])) # ' key=' + str(tuyaunit['key']) +

            tuyaunit = next((tuyaunit for tuyaunit in tuyadevsensors if tuyaunit['id'] == str(unitid)), None)
            # Domoticz.Debug('unitid:' + str(unitid) + '   tdev:' + str(tdev))
            # Domoticz.Debug(str(code_list))
            tuyaunitdevices = tuyaunit['mapping']
            # update devices in Domoticz
            Domoticz.Debug('Update devices in Domoticz')
            tuya = tinytuya.Device(dev_id=str(tuyaunit['id']), address=str(tuyaunit['ip']), local_key=str(tuyaunit['key']), version=str(tuyaunit['version']), connection_timeout=5, connection_retry_limit=1)
            tuya.detect_available_dps()
            tuya.detect_available_dps() # Two times for detection bulb devices
            tuyastatus = tuya.status()
            last_update = getConfigItem(str(unitid), 'last_update')
            if isinstance(last_update, dict):
                last_update = last_update.get('last_update', 0)

            if float(time.time()) > float(last_update) or testData:
                # Domoticz.Debug('tuyastatus: ' + str(tuyastatus))
                dps = tuyastatus.get('dps', {})
                for unit, devinfo in unitinfo.items():
                    # Domoticz.Debug(Devices[str(unitid)].Units[int(unit)])
                    try:
                        # ddev = Devices[str(unitid)].Units[int(unit)]
                        # dtype = ddev.Type
                        # dtype = Devices[str(unitid)].Units[unit]
                        # Domoticz.Debug('process unit '+str(unit) + "  dtype:" + str(dtype))
                        svalue=""
                        for dunit, tunit in devinfo["TuyaIDs"].items():  # loop through all entries/columns for this unit
                            # Domoticz.Debug('--> process '+str(dunit)+  " -> tunit:" + str(tunit))
                            # Domoticz.Debug('>dps '+ str(dps))
                            if tunit == "0":
                                currentstatus = 0
                            else:
                                item_value = dps.get(tunit, 0)   # tunit is e.g., '101'
                                # Domoticz.Debug('>process tunit '+ tunit + '  item_value: ' + str(item_value))
                                # Get Tuya sensor info
                                tuyasubdev = tuyaunitdevices.get(tunit)
                                # Domoticz.Debug('>process tuyasubdev: '+str(tuyasubdev))
                                factor = 1
                                if "factor" in devinfo:
                                    if dunit in devinfo["factor"]:
                                        factor = float(devinfo["factor"][dunit])
                                # Domoticz.Log('>process tunit '+ tunit + '  item_value: ' + str(item_value) + '  factor: ' + str(factor))
                                currentstatus = get_scale(item_value, tuyasubdev)
                                # factor 0 means => Don't try to translate or use factor and keep asis.
                                if factor != 0:
                                    # check if there is a range defined to which we need to translate the string to itemnumber
                                    if "range" in tuyasubdev["values"]:
                                        range_list = tuyasubdev["values"]["range"]
                                        try:
                                            # translate string to itemnumber
                                            currentstatus = range_list.index(currentstatus)
                                        except ValueError:
                                            currentstatus = 1  # or some default
                                    else:
                                        currentstatus = currentstatus
                                    # apply the found factor in case not 1
                                    if factor != 1:
                                        currentstatus = round(currentstatus * factor, 2)
                                    # Domoticz.Log('<process tunit '+ tunit + '  item_value: ' + str(item_value) + '  currentstatus: ' + str(currentstatus) + '  factor: ' + str(factor))

                            if svalue != "":
                                svalue+=";"
                            svalue += str(currentstatus)
                            Domoticz.Debug('+ process unit '+str(unit) + ' dunit:' + str(dunit) + '  tunit:' + str(tunit) + ' currentstatus:' + str(currentstatus) + ' new svalue:' + str(svalue))

                        Domoticz.Debug('< process unit '+str(unit)+ ' svalue:' + str(svalue))
                        UpdateDevice(str(unitid), unit, str(svalue), 0, 0)
                    except Exception:
                        Domoticz.Error('device value error:\n' + traceback.format_exc())

    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())
    # except Exception as err:
    #     Domoticz.Error('handleThread: ' + str(err)  + ' line ' + format(sys.exc_info()[-1].tb_lineno))

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

def UpdateDevice(ID, Unit, sValue, nValue, TimedOut, AlwaysUpdate = 0):
    Unit = int(Unit)
    #update sensors each minute when not changed
    update_due = False
    try:
        last_update = datetime.strptime(Devices[ID].Units[Unit].LastUpdate, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_update > timedelta(minutes=1):
            update_due = True
    except Exception:
        update_due = False

    # Domoticz.Debug('? Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    if update_due or str(Devices[ID].Units[Unit].sValue) != str(sValue) or str(Devices[ID].Units[Unit].nValue) != str(nValue) or str(Devices[ID].TimedOut) != str(TimedOut) or AlwaysUpdate == 1:
        if sValue == None:
            sValue = Devices[ID].Units[Unit].sValue
        if type(sValue) == int or type(sValue) == float:
            Devices[ID].Units[Unit].LastLevel = sValue
        elif type(sValue) == dict:
            Devices[ID].Units[Unit].Color = json.dumps(sValue)

        Devices[ID].Units[Unit].sValue = str(sValue)
        Devices[ID].Units[Unit].nValue = nValue
        Devices[ID].TimedOut = TimedOut
        Devices[ID].Units[Unit].Update(Log=True)

        Domoticz.Debug('Update device value: ' + str(ID) + ' Unit: ' + str(Unit) + ' sValue: ' +  str(sValue) + ' nValue: ' + str(nValue) + ' TimedOut=' + str(TimedOut))
    return

def SendCommand(ID, Unit, Status, Type = ''):
    Domoticz.Debug('SendCommand =  ID:' + str(ID) + ' IP:' + str(getConfigItem(ID, 'ip'))  + ' Type:' +  str(Type) + ' Status:' +  str(Status) + ' Status Type:' +  str(type(Status)) + ' Version:' + str(getConfigItem(ID, 'version')))
    if Type == 'light':
        selected_device = next((tuyaunit for tuyaunit in tuyadevsensors if tuyaunit['id'] == str(ID)), None)
        tuyasubdev = selected_device['mapping'][str(Unit)]
        Status = get_scale(Status, tuyasubdev)
        # Domoticz.Debug('Status: ' + str(Status))
        tuya = tinytuya.BulbDevice(dev_id=str(ID), address=str(getConfigItem(ID, 'ip')), local_key=str(getConfigItem(ID, 'key')), version=str(getConfigItem(ID, 'version')), connection_timeout=5, connection_retry_limit=1)
        tuya.detect_available_dps()
        # tuya = tinytuya.BulbDevice(str(ID), getConfigItem(ID, 'ip'), getConfigItem(ID, 'key'))
        # tuya.set_version(str(getConfigItem(ID, 'version')))
        if type(Status) == int or type(Status) == float:
            # Domoticz.Debug('SendCommand: brightness')
            tuya.turn_on(switch=Unit)
            tuya.set_brightness_percentage(Status)
        elif type(Status) == dict:
            if Status['m'] == 2:
                # Domoticz.Debug('SendCommand: colourtemp')
                tuya.turn_on()
                tuya.set_colourtemp(Status['cw'])
            if Status['m'] == 3:
                # Domoticz.Debug('SendCommand: colour')
                # Domoticz.Debug('Colour: r:' + str(Status['r']) + ' g:' + str(Status['g']) + ' b:' + str(Status['r']))
                tuya.turn_on()
                tuya.set_colour(Status['r'], Status['g'], Status['b'])
        elif Status == True:
            # Domoticz.Debug('SendCommand: On')
            tuya.turn_on()
        elif Status == False:
            # Domoticz.Debug('SendCommand: Off')
            tuya.turn_off()
        Domoticz.Debug('Command send to tuya BulbDevice: ' + str(ID) + ", " + str({'commands': [{'Type': Type, 'value': Status}]}))
    else:
        selected_device = next((tuyaunit for tuyaunit in tuyadevsensors if tuyaunit['id'] == str(ID)), None)
        tuyasubdev = selected_device['mapping'][str(Unit)]
        Status = get_scale(Status, tuyasubdev)
        tuya = tinytuya.Device(dev_id=str(ID), address=str(getConfigItem(ID, 'ip')), local_key=str(getConfigItem(ID, 'key')), version=str(getConfigItem(ID, 'version')), connection_timeout=5, connection_retry_limit=1)
        tuya.detect_available_dps()
        payload = tuya.generate_payload(tinytuya.CONTROL_NEW, {Unit: Status})
        tuya.send(payload)
        Domoticz.Debug('Command send to tuya Device: ' + str(ID) + ", " + str({'commands': [{'dsp': Unit, 'value': Status}]}))

def searchCode(Item, Functions):
    for OneItem in Functions:
        if Item == OneItem:
            return True
        else:
            return False
    # Domoticz.Debug("searchCodeActualFunction unable to find " + str(Item) + " in " + str(Function))
    return

def createDevice(ID, Unit):
    if ID in Devices:
        if Unit in Devices[ID].Units:
            value = False
        else:
            if int(Unit) in Devices[ID].Units:
                value = False
            else:
                value = True
    else:
        value = True

    return value

def battery_device(ID, ResultValue, StatusDeviceTuya):
    # Battery_device
    if searchCode('battery_state', ResultValue) or searchCode('battery', ResultValue) or searchCode('va_battery', ResultValue) or searchCode('battery_percentage', ResultValue):
        if searchCode('battery_state', ResultValue):
            if StatusDeviceTuya == 'high':
                currentbattery = 100
            if StatusDeviceTuya == 'middle':
                currentbattery = 50
            if StatusDeviceTuya == 'low':
                currentbattery = 5
        if searchCode('BatteryStatus', ResultValue):
            if int(StatusDeviceTuya) == 1:
                currentbattery = 100
            elif int(StatusDeviceTuya) == 2:
                currentbattery = 50
            elif int(StatusDeviceTuya) == 3:
                currentbattery = 5
            else:
                currentbattery = 100
        if searchCode('battery', ResultValue):
            currentbattery = StatusDeviceTuya * 10
        if searchCode('va_battery', ResultValue):
            currentbattery = StatusDeviceTuya
        if searchCode('battery_percentage', ResultValue):
            currentbattery = StatusDeviceTuya
        if searchCode('residual_electricity', ResultValue):
            currentbattery = StatusDeviceTuya
        for unit in Devices[ID].Units:
            if str(currentbattery) != str(Devices[ID].Units[unit].BatteryLevel):
                Devices[ID].Units[unit].BatteryLevel = currentbattery
                Devices[ID].Units[unit].Update()
    return

def online_offline(ID, StatusDeviceTuya):
    for unit in Devices[ID].Units:
        # Domoticz.Debug(str(ID) + '   ' + str(StatusDeviceTuya))
        if str(StatusDeviceTuya) != str(Devices[ID].TimedOut):
            Devices[ID].TimedOut = StatusDeviceTuya
            Devices[ID].Units[unit].Update()
    return

def nextUnit(ID):
    unit = 1
    while unit in Devices(ID) and unit < 255:
        unit = unit + 1
    return unit


def ping_ok(sHost) -> bool:
    try:
        subprocess.check_output(
            "ping -{} 1 {}".format("n" if platform.system().lower() == "windows" else "c", sHost), shell=True
        )
    except Exception:
        return False

    return True

def set_scale(raw, tuyasubdev):
    scale = 0
    try:
        # Domoticz.Debug('Scale :' + str(tuyasubdev['values'].get('scale', 0 )))
        if tuyasubdev['values'] in 'scale':
            scale = tuyasubdev['values'].get('scale')
        # step = the_values.get('step', 0)
        if tuyasubdev['values'] in 'unit':
            unit = tuyasubdev['values'].get('unit')
        if tuyasubdev['values'] in 'max':
            max = tuyasubdev['values'].get('max')

        if scale == 1:
            result = int(raw * 10)
        elif scale == 2:
            result = int(raw * 100)
        elif scale == 3:
            result = int(raw * 1000)
        else:
            result = int(raw)
        if result > max:
            result = int(max)
            Domoticz.Log('Value higher then maximum device')
        elif result < min:
            result = int(min)
            Domoticz.Log('Value lower then minium device')
    except:
        result = str(raw)
    return result

def get_scale(raw, tuyasubdev):
    scale = 0

    # Check if raw is a valid number (int, float, or numeric string)
    if not isinstance(raw, (list, tuple, dict, set, bool, complex, bytes, str)) or (isinstance(raw, str) and raw.isnumeric()):
        # Convert numeric strings to floats
        raw = float(raw) if isinstance(raw, str) else raw
        result = raw

        try:
            # Domoticz.Debug('Raw Value: ' + str(raw) + '  Type: ' + str(type(raw)))
            # Domoticz.Debug('Item Values: ' + str(tuyasubdev['values']))
            if 'scale' in tuyasubdev['values']:
                scale = tuyasubdev['values'].get('scale')

            if 'unit' in tuyasubdev['values']:
                unit = tuyasubdev['values'].get('unit')

            if 'max' in tuyasubdev['values']:
                max_value = tuyasubdev['values'].get('max')
            Domoticz.Debug(f'-> raw: {raw}  scale:{scale} unit:{unit}  max_value:{max_value}')

            if scale == 0:
                if unit == 'V' and len(str(max_value)) >= 4:
                    result = raw / 10
                elif unit == 'W' and len(str(max_value)) >= 5:
                    result = raw / 10
                else:
                    result = int(raw)
            elif scale == 1:
                result = raw / 10
                Domoticz.Debug(f'1 raw: {raw}  scale:{scale} result {result}')
            elif scale == 2:
                result = raw / 100
                Domoticz.Debug(f'2 raw: {raw}  scale:{scale} result {result}')
            elif scale == 3:
                result = raw / 1000
                Domoticz.Debug(f'3 raw: {raw}  scale:{scale} result {result}')
            else:
                result = int(raw)
                Domoticz.Debug(f'else raw: {raw}  scale:{scale} result {result}')
        except:
            result = raw
    else:
        # If raw is not numeric, return it unmodified
        result = raw
        Domoticz.Debug('Non-numeric input, returning raw value: ' + str(result))

    return result

    # Configuration Helpers
def getConfigItem(Key=None, Values=None):
    Value = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            # Domoticz.Debug(Config[Key][Values])
            Value = Config[Key][Values]  # only return requested key if there was one
        else:
            Value = Config      # return the whole configuration if no key
    except KeyError:
        Value = {}
    except Exception as inst:
        Domoticz.Error('Domoticz.Configuration read failed: ' + str(inst))
    return Value

def setConfigItem(Key=None, Value=None):
    Config = {}
    try:
        Config = Domoticz.Configuration()
        if (Key != None):
            Config[Key] = Value
        else:
            Config = Value  # set whole configuration if no key specified
        Config = Domoticz.Configuration(Config)
    # except Exception as inst:
    #     Domoticz.Error('Domoticz.Configuration operation failed: ' + str(inst))
    except Exception as err:
        Domoticz.Error('handleThread error:\n' + traceback.format_exc())
    return Config

def version(v):
    return tuple(map(int, (v.split("."))))