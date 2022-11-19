import os, time

from unittest import TestCase

from pytomation.interfaces import NamedPipe

class NamedPipeTests(TestCase):
    def setUp(self):
        self._path_name = "/tmp/named_pipe_test"
        self.interface = NamedPipe(self._path_name)
            
    def test_instance(self):
        self.assertIsNotNone(self.interface)
    
    def test_pipe_read(self):
        test_message = 'Test'
        pipe = os.open(self._path_name, os.O_WRONLY)
        os.write(pipe, test_message)
        response = self.interface.read()
        self.assertEqual(test_message, response)
        
    def tearDown(self):
        self.interface.close()
        