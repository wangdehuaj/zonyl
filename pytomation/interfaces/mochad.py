from .common import *
from .ha_interface import HAInterface
#from pytomation.devices import State
'''
http://sourceforge.net/apps/mediawiki/mochad/index.php?title=Mochad_Reference

switched pl method for rf as both the cm19a only supports rf while the cm14a supports both pl and rf
'''

class Mochad(HAInterface):
    
    VERSION='0.3.0'
        
    def _init(self, *args, **kwargs):
        self._devicestatus = False
        self._securitystatus = False
        super(Mochad, self)._init(*args, **kwargs)

    def _readInterface(self, lastPacketHash):
        raw_response = self._interface.read()
        
        if len(raw_response) == 0: #if no data leave
            return
        
        #NOTE need to correct: Look for number of words first then 3rd term. Then decide what to do
        
        response_lines = raw_response.split('\n')
        
        self._logger.debug('Number of Lines '+str(len(response_lines)))
        
        for line in response_lines:
            if line.strip()=='':
                return #leave if empty
            self._logger.debug('line responses> ' + line)
            line_data=line.split(' ')
            if line_data[2]=='Rx' or line_data[2]=='Tx':
                """ Like below
                01/27 23:41:23 Rx RF HouseUnit: A3 Func: Off
                0     1        2  3  4          5  6     7 
                01/27 23:48:23 Rx RF HouseUnit: A1 Func: On
                12/07 20:49:37 Rx RFSEC Addr: C6:1B:00 Func: Motion_alert_MS10A
                0     1        2  3     4     5        6     7
                """
                #date=data[0]
                #time=data[1]
                #direction=data[2]
                #method=data[3]
                #ua=data[4]
                addr=line_data[5]
                func=data[7].strip().rsplit('_',1)[0]   #removing _devicemodel
                self._map(func,addr)
                
            """
            command sent > st
            02/01 16:44:23 Device selected
            02/01 16:44:23 House A: 2
            02/01 16:44:23 House B: 1
            02/01 16:44:23 Device status
            02/01 16:44:23 House A: 1=0,2=0,3=0,4=1,5=1,6=1,7=1,8=1,10=0,11=0
            0     1        2     3  4
            02/01 16:44:23 Security sensor status
            02/01 16:44:23 Sensor addr: 000003 Last: 1102:40 Arm_KR10A
            02/01 16:44:23 Sensor addr: 000093 Last: 1066:33 Disarm_SH624
            02/01 16:44:23 Sensor addr: 055780 Last: 1049:59 Contact_alert_max_DS10A
            02/01 16:44:23 Sensor addr: 27B380 Last: 01:42 Motion_normal_MS10A
            02/01 16:44:23 Sensor addr: AF1E00 Last: 238:19 Lights_Off_KR10A
            0     1        2      3     4      5     6      7 
            02/01 16:44:23 End status
            """    
                
            if line_data[2]=='Device':
                if line_data[3]=='status':
                    self._devicestatus = True
                    continue

            if line_data[2]=='Security':
                if line_data[3]=='sensor':
                    self._devicestatus = False
                    self._securitystatus = True
                    continue
                    
            if line_data[2]=='End':
                self._devicestatus = False #shouldn't need to set this false, but why not?
                self._securitystatus = False
                continue
                
            if self._devicestatus:      
                housecode = line_data[3].strip(":")
                    
                for device in line_data[4].split(','):
                    qdevicestatus=device.split('=')
                   
                    if qdevicestatus[1]=='0':
                          self._onCommand(command=Command.OFF,address=str(housecode+qdevicestatus[0]))
                    if qdevicestatus[1]=='1':
                          self._onCommand(command=Command.ON,address=str(housecode+qdevicestatus[0]))
                       
            if self._securitystatus:
                addr=line_data[4]
                func = line_data[7].rsplit('_',1)[0]
                self._logger.debug("Function: "+ func + " Address " + addr[0:2]+":"+addr[2:4]+":"+addr[4:6])
                # NOTE THIS NEEDS TO SET Security state!       

                  

    
    def status(self,address):
        self._logger.debug('Querying of last known status all devices including '+address)
        self._interface.write('st'+"\x0D")
        return None 
        
    def update_status(self):
        self._logger.debug('Mochad update status called')
        self.status('')

    def _onCommand(self, command=None, address=None):
        commands = command.split(' ')
        if commands[0] == 'rf':
            address = commands[1]
            command = commands[2][0:len(commands[2])-1]
        self._logger.debug('Command>'+command+' at '+address)
        super(Mochad, self)._onCommand(command=command, address=address)
    
    """ #Causes issues with web interface Disabling this feature.
    def __getattr__(self, command):
        return lambda address: self._interface.write('rf ' + address + ' ' + command + "\x0D" ) 
    """

    def on(self, address):
        self._logger.debug('Command on at '+address)
        self._interface.write('rf ' + address + ' on' + "\x0D")

    def off(self, address):
        self._logger.debug('Command off at '+address)
        self._interface.write('rf ' + address + ' off'+ "\x0D")
        
    def disarm(self, address):
        self._logger.debug('Command disarm at '+address)
        self._interface.write('rfsec ' + address + ' disarm'+ "\x0D")
        
    def arm(self, address):
        self._logger.debug('Command arm at '+address)
        self._interface.write('rfsec ' + address + ' arm'+ "\x0D")

    def version(self):
        self._logger.info("Mochad Pytomation Driver version " + self.VERSION)
        
    def _map(self,func,addr): #mapping output to a valid command
        #print func,addr
        if func=="On":
            self._onCommand(command=Command.ON,address=addr)
        elif func=="Off":
            self._onCommand(command=Command.OFF,address=addr)
        elif func=="Contact_normal_min":
            self._onCommand(command=Command.CLOSE,address=addr)
        elif func=="Contact_alert_min":
            self._onCommand(command=Command.OPEN,address=addr) 
        elif func=="Contact_normal_max":
            self._onCommand(command=Command.CLOSE,address=addr)
        elif func=="Contact_alert_max":
            self._onCommand(command=Command.OPEN,address=addr)
        elif func=="Motion_alert":
            self._onCommand(command=Command.MOTION,address=addr)
        elif func=="Motion_normal":
            self._onCommand(command=Command.STILL,address=addr)
        elif func=="Arm":
            self._onCommand(command=Command.ON,address=addr)
        elif func=="Panic":
            self._onCommand(command=Command.VACATE,address=addr)
        elif func=="Disarm":
            self._onCommand(command=Command.DISARM,address=addr)
        elif func=="Lights_On":
            self._onCommand(command=Command.ON,address=addr)
        elif func=="Lights_Off":
            self._onCommand(command=Command.OFF,address=addr)

