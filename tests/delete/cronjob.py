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
from functions import DELETE, GET
from auto_config import results_xml
RunTest = True
TestName = "delete cronjob"


class cronjob_test(unittest.TestCase):

    # Delete cronjob from API
    def test_01_Deleting_cron_job_which_will_run_every_minuted(self):
        assert DELETE("/tasks/cronjob/1/") == 204

    # Check that cronjob was deleted from API
    def test_02_Check_that_the_API_reports_the_cronjob_as_deleted(self):
        assert GET("/tasks/cronjob/1/") == 404


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(cronjob_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
