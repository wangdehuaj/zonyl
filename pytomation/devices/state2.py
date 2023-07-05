from datetime import datetime

from ..common import PytomationObject
from ..interfaces import Command
from ..utility import CronTimer
from ..utility.timer import Timer as CTimer

class State2(object):
    ALL = 'all'
    UNKNOWN = 'unknown'
    ON = 'on'
    OFF = 'off'
    LEVEL = 'level'
    MOTION = 'motion'
    STILL = 'still'
    OPEN = 'open'
    CLOSED = "close"
    LIGHT = "light"
    DARK = "dark"
    
class Attribute(object):
    MAPPED = 'mapped'
    COMMAND = 'command'
    TARGET = 'target'
    TIME = 'time'
    SECS = 'secs'
    SOURCE = 'source'
    
class State2Device(PytomationObject):
    STATES = [State2.UNKNOWN, State2.ON, State2.OFF, State2.LEVEL]
    COMMANDS = [Command.ON, Command.OFF, Command.LEVEL, Command.PREVIOUS, Command.TOGGLE, Command.INITIAL]
    
    def __init__(self, *args, **kwargs):
        super(State2Device, self).__init__(*args, **kwargs)
        if not kwargs.get('devices', None) and len(args)>0:
            kwargs.update({'devices': args[0]})
        self._initial_vars(*args, **kwargs)
        self._process_kwargs(kwargs)
        self._initial_from_devices(*args, **kwargs)
        if not self.state or self.state == State2.UNKNOWN:
            self.command(Command.INITIAL, source=self)

    def _initial_vars(self, *args, **kwargs):
        self._state = State2.UNKNOWN
        self._previous_state = self._state
        self._previous_command = None
        self._last_set = datetime.now()
        self._delegates = []
        self._times = []
        self._maps = {}
        self._delays = []
        self._triggers = []
        self._ignores = []
        self._idle_timer = None
        self._idle_command = None
        self._devices = []
        
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value, *args, **kwargs):
        source = kwargs.get('source', None)
        self._previous_state = self._state
        self._last_set = datetime.now()
        self._state = value
#        if self._idle_timer:
#            self._idle_timer.action(self.command, (self._state_to_command(value, None) ), source=self, original=source)
#            self._idle_timer.start()
        return self._state
    
    def __getattr__(self, name):
        # Give this object methods for each command supported
        if self._is_valid_command(name):
            return lambda *a, **k: self.command(name, *a, sub_state=a, **k)

    def command(self, command, *args, **kwargs):
        source = kwargs.get('source', None)
        if not self._is_ignored(command, source):
            m_command = self._process_maps(*args, command=command, **kwargs)
            if m_command != command:
                self._logger.debug("{name} Map from '{command}' to '{m_command}'".format(
                                                                        name=self.name,
                                                                        command=command,
                                                                        m_command=m_command,
                                                                                         ))
            (state, map_command) = self._command_state_map(m_command, *args, **kwargs)
    
            if state and map_command and self._is_valid_state(state):
                if source == self or not self._is_delayed(map_command, source):
                    self._logger.info('{name} changed state to state "{state}" by command {command} from {source}'.format(
                                                      name=self.name,
                                                      state=state,
                                                      command=map_command,
                                                      source=source.name if source else None,
                                                                                                                  ))
                    self.state = state
                    self._idle_start(*args, **kwargs)
                    self._previous_command = map_command
                    self._delegate_command(map_command, *args, **kwargs)
                    self._trigger_start(map_command, source)
                else:
                    self._delay_start(map_command, source)
            else:
                self._logger.debug("{name} ignored command {command} from {source}".format(
                                                                                           name=self.name,
                                                                                           command=command,
                                                                                           source=source.name if source else None
                                                                                           ))

    def _command_state_map(self, command, *args, **kwargs):
        source = kwargs.get('source', None)
        state = None
        state = self._command_to_state(command, state)
        m_command = self._state_to_command(state, command)
        if command == Command.LEVEL or (isinstance(command, tuple) and command[0] == Command.LEVEL):
            if isinstance(command, tuple):
                state = (State2.LEVEL, command[1])
#                m_command = command
            else:
                state = (State2.LEVEL, kwargs.get('sub_state', (0,))[0])
#                m_command = (Command.LEVEL,  kwargs.get('sub_state', (0,) ))
            m_command = self._state_to_command(state, m_command)
        elif command == Command.PREVIOUS:
            state = self._previous_state
            m_command = self._state_to_command(state, m_command)            
        elif command == Command.TOGGLE:
            state = self.toggle_state()
            m_command = self._state_to_command(state, m_command)
        elif command == Command.INITIAL:
            state = self.state

        return (state, m_command)

    def toggle_state(self):
        if self.state == State2.ON:
            state = State2.OFF
        else:
            state = State2.ON
        return state
    
    def _command_to_state(self, command, state):
        # Try to map the same state ID
        try:
#            state = getattr(State2, command)
            primary = command
            if isinstance(command, tuple):
                primary = command[0]
            for attribute in dir(State2):
                if getattr(State2, attribute) == primary:
                    return command
        except Exception, ex:
            self._logger.debug("{name} Could not find command to state for {command}".format(
                                                                            name=self.name,
                                                                            command=command,                                                                                                                 
                                                                            ))
        return state
    
    def _state_to_command(self, state, command):
        try:
#            return Command['state']
            primary = state
            if isinstance(state, tuple):
                primary = state[0]
            for attribute in dir(Command):
                if getattr(Command, attribute) == primary:
                    return state
            return command
        except Exception, ex:
            self._logger.debug("{name} could not map state {state} to command".format(
                                                                        name=self.name,
                                                                        state=state,
                                                                                                    ))
            return command
    
    def _process_kwargs(self, kwargs):
        # Process each initializing attribute as a method call on this object
        # devices have priority
        if kwargs.get('devices', None):
            try:
                getattr(self, 'devices')( **kwargs['devices'])
            except:
                getattr(self, 'devices')( kwargs['devices'])
        # run through the rest
        for k, v in kwargs.iteritems():
            if k.lower() != 'devices':
                attribute = getattr(self, k)
                try:
                    attribute(**v)
                except Exception, ex:
                    if callable(attribute):
                        if isinstance(v, tuple):
                            for v1 in v:
                                try:
                                    attribute(**v1)
                                except Exception, ex:
                                    attribute(v1)
                        else:
                                attribute(v)
                    else:
                        attribute = v
                
            
    def _process_maps(self, *args, **kwargs):
        source = kwargs.get(Attribute.SOURCE, None)
        command = kwargs.get(Attribute.COMMAND, None)
        mapped = None

        self._logger.debug("{name} MAPS dump: {maps}".format(
                                                name=self.name,
                                                maps=str(self._maps),
                                                            ))

        for (c, s), (target, timer) in self._maps.iteritems():
            commands = []
            sources = []
            if isinstance(s, tuple):
                sources = s
            else:
                sources = (s, )
            if isinstance(c, tuple):
                commands = c
            else:
                commands = (c, )
            
            # Find specific first
            if command in commands and source in sources:
                if not timer:
                    return target
                else:
                    timer.action(self.command, (target, ), source=self, original=source)
                    timer.restart()
                    return None

            # Go for a more general match next
            if command in commands and None in sources:
                if not timer:
                    return target
                else:
                    timer.action(self.command, (target, ), source=self, original=source)
                    timer.restart()
                    return None

        
        return command
 
    def _is_valid_state(self, state):
        isFound = state in self.STATES
        if not isFound:
            try:
                isFound = state[0] in self.STATES
            except:
                pass
        return isFound

    def _is_valid_command(self, command):
        return command in self.COMMANDS

    def initial(self, state):
        try: # Check to see if this is a device reference
            last_command = state.last_command
            self.command(last_command, source=state)
#            (m_state, m_command) = self._command_state_map(last_command)
#            self.state = m_state
        except: # Just a value
#            self.state = state
            self.command(self._state_to_command(state, None), source=None)
        
    def time(self, *args, **kwargs):
        # time, command
        times = kwargs.get('time', None)
        command = kwargs.get('command', State2.UNKNOWN)
        
        if times:
            if not isinstance( times, tuple):
                times = (times, )
            for time in times:
                timer = CronTimer()
                if isinstance(time, tuple):
                    timer.interval(*time)
                else:
                    timer.interval(*CronTimer.to_cron(time))
                timer.action(self.command, (command))
                timer.start()
                self._times.append((command, timer))

    def on_command(self, device=None):
        self._delegates.append(device)
    
    def _delegate_command(self, command, *args, **kwargs):
        source = kwargs.get('source', None)
        for delegate in self._delegates:
            self._logger.debug("{name} delegating command {command} from {source} to object {delegate}".format(
                                                                               name=self.name,
                                                                               command=command,
                                                                               source=source.name if source else None,
                                                                               delegate=delegate.name,
                                                                                                               
                                                                                                               ))
            delegate.command(command=command, source=self)
        
    def devices(self, *args, **kwargs):
        devices = args[0]

        if not isinstance(devices, tuple):
            devices = (devices, )
                   
        for device in devices:
            if device:
                self._add_device(device)

    def _add_device(self, device):
        self._devices.append(device)
        return device.on_command(device=self)

    def mapped(self, *args, **kwargs):
        command = kwargs.get('command', None)
        mapped = kwargs.get('mapped', None)
        source = kwargs.get('source', None)
        secs = kwargs.get('secs', None)
        timer = None
        commands = command
        if not isinstance(command, tuple):
            commands = (command, )
        for c in commands:
            if secs:
                timer = CTimer()
                timer.interval = secs
                timer.action(self.command, (mapped, ), source=self, original=source)
    #        self._maps.append({'command': command, 'mapped': mapped, 'source': source})
            sources = source
            if not isinstance(source, tuple):
                sources = (source ,)
            for s in sources:
                self._maps.update({(c, s): (mapped, timer)}) 
            
    def delay(self, *args, **kwargs):
        command = kwargs.get('command', None)
        mapped = kwargs.get('mapped', None)
        if not mapped:
            mapped = command
        source = kwargs.get('source', None)
        secs = kwargs.get('secs', None)
        timer = CTimer()
        timer.interval=secs
        timer.action(self.command, (mapped, ), source=self, original=source)
#            timer.action(self.command, (mapped), source=self)
        self._delays.append({'command': command, 'mapped': mapped, 'source': source, 'secs': secs, 'timer': timer})

    def _is_delayed(self, command, source):
        for delay in self._delays:
            try:
                if delay['command'] == command and \
                    (not delay['source'] or delay['source'] == source or source in delay['source']):
                    return True
            except TypeError, ex:
                # Not found and source is not iterable
                pass
#        return command in [ delay['command'] for delay in self._delays]
        return False
       
    def _delay_start(self, command, source):
        for delay in self._delays:
            try:
                if delay['command'] == command and (delay['source'] == None or delay['source'] == source or source in delay['source']):
                    delay['timer'].action(self.command, (delay['mapped'], ), source=self, original=source)
                    delay['timer'].restart()
            except TypeError, ex:
                # Not found and source is not iterable
                pass

    @property
    def idle_time(self):
        difference = datetime.now() - self._last_set
        return difference.total_seconds()

    def idle(self, *args, **kwargs):
        command = kwargs.get('command', None)
        source = kwargs.get('source', None)
        secs = kwargs.get('secs', None)
        self._idle_command = command
        if secs:
            timer = CTimer()
            timer.interval = secs
            timer.action(self.command, (self._idle_command, ), source=self, original=source)
            self._idle_timer = timer
            
    def _idle_start(self, *args, **kwargs):
        if self._idle_command:
            source = kwargs.get('source', None)
            self._idle_timer.action(self.command, (self._idle_command, ), source=self, original=source)
            self._idle_timer.start()
        
        
    def ignore(self, *args, **kwargs):
        command = kwargs.get('command', None)
        source = kwargs.get('source', None)
        self._ignores.append({'command': command,'source': source})
        self._logger.debug("{name} add ignore for {command} from {source}".format(
										name=self.name,
										command=command,
										source=source.name if source else None,
										));
        
    def _is_ignored(self, command, source):
        is_ignored = False
        for ignore in self._ignores:
            if ignore['command'] == command and \
            (ignore['source'] == None or ignore['source'] == source):
                is_ignored = True
        self._logger.debug("{name} check ignore for {command} from {source}".format(
        								name=self.name,
        								command=command,
        								source=source.name if source else None,
        								));
        return is_ignored
    
    def trigger(self, *args, **kwargs):
        command = kwargs.get('command', None)
        source = kwargs.get('source', None)
        mapped = kwargs.get('mapped', command)
        secs = kwargs.get('secs', None)
        timer = CTimer()
        timer.interval=secs
        timer.action(self.command, (mapped, ), source=self, original=source)
        self._triggers.append({'command': command, 'mapped': mapped, 'source': source, 'secs': secs, 'timer': timer})

    def _trigger_start(self, command, source):
        for trigger in self._triggers:
            if trigger['command'] == command and \
            (not trigger['source'] or trigger['source'] == source):
                trigger['timer'].action(self.command, (trigger['mapped'], ), source=self, original=source)
                trigger['timer'].start()
                
    def _initial_from_devices(self, *args, **kwargs):
        state = None
        if self.state == State2.UNKNOWN:
            for device in self._devices:
#                state = device.state
                (state, command) =  self._command_state_map(device.last_command)
                if state:
                    self.initial(device)
                    self._logger.debug("{name} initial for {command} from {state}".format(
        										name=self.name,
        										command=command,
        										state=state,
        										));
        return
    
    @property
    def last_command(self):
        return self._previous_command
