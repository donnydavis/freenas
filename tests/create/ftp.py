#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, RC_TEST
from auto_config import ip, results_xml
RunTest = True
TestName = "create ftp"


class ftp_test(unittest.TestCase):

    def test_01_Configuring_ftp_service(self):
        payload = {"ftp_clients": 10, "ftp_rootlogin": "true"}
        assert PUT("/services/ftp/", payload) == 200

    def test_02_Starting_ftp_service(self):
        payload = {"srv_enable": "true"}
        assert PUT("/services/services/ftp/", payload) == 200

    def test_03_Checking_to_see_if_FTP_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/ftp/", "srv_state") == "RUNNING"

    def test_04_Fetching_file_via_FTP(self):
        cmd = "ftp -o /tmp/ftpfile ftp://testuser:test@" + ip + "/.cshrc"
        RC_TEST(cmd) is True


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(ftp_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
