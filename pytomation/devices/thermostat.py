from pytomation.devices import InterfaceDevice, State
from pytomation.interfaces import Command

class Thermostat(InterfaceDevice):
    STATES = [State.UNKNOWN, State.OFF, State.HEAT, State.COOL, State.LEVEL, State.CIRCULATE, State.STILL, State.AUTOMATIC, State.HOLD, State.VACANT, State.OCCUPIED, State.SETPOINT]
    COMMANDS = [Command.AUTOMATIC, Command.MANUAL, Command.COOL, Command.HEAT, Command.HOLD, Command.SCHEDULE, Command.OFF, Command.LEVEL, Command.STATUS, Command.CIRCULATE, Command.STILL, Command.VACATE, Command.OCCUPY, Command.SETPOINT]
    DEFAULT_COMMAND = Command.STATUS
    DEFAULT_NUMERIC_COMMAND = Command.SETPOINT
    
    def __init__(self, *args, **kwargs):
        for level in range(60,90):
            self.COMMANDS.append((Command.SETPOINT, level))
            
        self._level = None
        self._setpoint = None
        self._automatic_mode = False
        self._automatic_delta = 0
        self._away_delta = 0
        self._away_mode = False
        self._current_mode = None
        self._last_temp = None
        self._sync_interface = False
        self._thermostat_states = {'temp': 'unknown', 'mode': 'unknown', 'setpoint': 'unknown'}

        super(Thermostat, self).__init__(*args, **kwargs)
    
    def _send_command_to_interface(self, interface, address, command):
        try:
            super(Thermostat, self)._send_command_to_interface(interface, address, command)
        except (AttributeError, TypeError) as ex:
            if command == Command.AUTOMATIC:
                #Thermostat doesnt have Automatic mode
                self._automatic_mode = True
                self.automatic_check()
    
    def automatic_check(self):
        self._logger.debug('Automatic Check a:{0} ad:{1} set:{2} state:{3} ltemp:{4} mode:{5}'.format(
                                                                                 self._automatic_mode,
                                                                                 self._automatic_delta,
                                                                                 self._setpoint,
                                                                                 str(self._state),
                                                                                 self._last_temp,
                                                                                 self._current_mode,
                                                                                 ))

        if self._automatic_mode:
            if self._state and self._setpoint and isinstance(self._state, tuple) and self._state[0] == State.LEVEL and self._state[1] != self._setpoint:
                previous_temp = self._state[1]
                if (self._state[1] < self._setpoint - self._automatic_delta and not self._away_mode) or \
                        (self._away_mode and self._state[1] < self._setpoint - self._away_delta):
                    # If the current mode isnt already heat or for some wild reason we are heading in the wrong dir
                    if self._current_mode != Command.HEAT or \
                        (self._last_temp and self._last_temp > self._state[1]) or \
                        self._sync_interface:
                        self._clear_sync_with_interface()
                        self.heat(address=self._address, source=self)
                elif (self._state[1] > self._setpoint + self._automatic_delta and not self._away_mode) or \
                        (self._away_mode and self._state[1] > self._setpoint + self._away_delta):
                    # If the current mode isnt already cool or for some wild reason we are heading in the wrong dir
                    if self._current_mode != Command.COOL or \
                        (self._last_temp and self._last_temp < self._state[1]) or \
                        self._sync_interface:
                        self._clear_sync_with_interface()
                        self.cool(address=self._address, source=self)
                self._last_temp = previous_temp

    def command(self, command, *args, **kwargs):
        source = kwargs.get('source', None)
        primary_command = command
        secondary_command = None
        if len(args) > 0:
            secondary_command=args[0]

        if isinstance(primary_command, tuple):
            primary_command=command[0]
            secondary_command=command[1]
        
        if primary_command == Command.SETPOINT:
            self._setpoint = secondary_command

        if primary_command == Command.HEAT:
            self._current_mode = Command.HEAT
        elif primary_command == Command.COOL:
            self._current_mode = Command.COOL
        elif primary_command == Command.OFF:
            self._current_mode = Command.OFF
        elif primary_command == Command.AUTOMATIC:
            self._current_mode = Command.AUTOMATIC
        elif primary_command == Command.MANUAL:
            self._automatic_mode = False
        elif primary_command == Command.VACATE:
            self._sync_with_interface()
            self._away_mode = True
        elif primary_command == Command.OCCUPY:
            self._sync_with_interface()
            self._away_mode = False
            

        result = super(Thermostat, self).command(command, *args, **kwargs)
        
        self.automatic_check()
        return result

    def _set_state(self, value, *args, **kwargs):
        if isinstance(value, tuple) and value[0] == State.LEVEL:
            self._thermostat_states['temp'] = value[1]
        elif isinstance(value, tuple) and value[0] == State.SETPOINT:
            self._thermostat_states['setpoint'] = value[1]
        elif value in [State.OFF, State.COOL, State.HEAT, State.AUTOMATIC]:
            self._thermostat_states['mode'] = value
        else:
            status = self._thermostat_states.items()
            status.append(value)
            return super(Thermostat, self)._set_state(status, *args, **kwargs)
        return super(Thermostat, self)._set_state(self._thermostat_states.items(), *args, **kwargs)

    def automatic_delta(self, value):
        self._automatic_delta = value
        
    def away_delta(self, value):
        self._away_delta = value
        
    def _sync_with_interface(self):
        self._sync_interface = True
    
    def _clear_sync_with_interface(self):
        self._sync_interface = False
        