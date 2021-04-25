import select

from unittest import TestCase, main

from pytomation.interfaces import UPB, Serial, HACommand, MockInterface


class UPBInterfaceTests(TestCase):
    useMock = True

    def setUp(self):
        self.ms = MockInterface()
        if self.useMock:  # Use Mock Serial Port
            self.upb = UPB(self.ms)
        else:
            self.serial = Serial('/dev/ttyUSB0', 4800)
            self.upb = UPB(self.serial)

        self.upb.start()

    def test_instantiation(self):
        self.assertIsNotNone(self.upb,
                             'UPB interface could not be instantiated')

    def test_get_firmware_version(self):
        # What will be written / what should we get back
        self.ms._responses.update({'\x120202FC\x0D': 'PR021234\x0D'})

        response = self.upb.get_register(2, 2)
        self.assertEqual(response, '1234')
#        if self.useMock:
#            self.assertEqual(self.ms._written, '\x120202FC\x0D')
        #sit and spin, let the magic happen
        #select.select([], [], [])


if __name__ == '__main__':
    main()
